#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
import gi
import os
import sys
import json
import math
import time
import cairo
import base64
import select
import urllib
import requests
import websocket

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gio, GdkPixbuf, Gdk, Pango
from gi.repository.GdkPixbuf import Pixbuf
from configparser import ConfigParser

try:
    from xdg.BaseDirectory import xdg_config_home
except ModuleNotFoundError:
    from xdg import XDG_CONFIG_HOME as xdg_config_home


access_token = "none"
# TODO Magic number
oauth_token = "207646673902501888"
access_delay = 0

guilds = {}
channels = {}
user = {}
userlist = {}
in_room= []
current_voice = "0"
list_altered = False
last_connection=""

def get_access_token_stage1(ws):
    global oauth_token
    ws.send("{\"cmd\":\"AUTHORIZE\",\"args\":{\"client_id\":\"%s\",\"scopes\":[\"rpc\",\"messages.read\"],\"prompt\":\"none\"},\"nonce\":\"deadbeef\"}" % (oauth_token))

def get_access_token_stage2(ws, code1):
    global access_token, access_delay
    time.sleep(access_delay)
    access_delay+=1
    if access_delay > 5:
        access_delay = 5
    url = "https://streamkit.discord.com/overlay/token"
    myobj = {"code" : code1}
    x = requests.post(url, json=myobj)
    try:
        j = json.loads(x.text)
    except JSONDecodeError:
        j = {}
    if "access_token" in j:
        access_token = j["access_token"]
        req_auth(ws)
    else:
        sys.exit(1)

def set_channel(ws,channel,need_req=True):
    global current_voice, channels
    if not channel:
        current_voice="0"
        return
    if channel != current_voice:
        cn = channels[channel]['name']
        print("Joined room: %s" % (cn))
        current_voice = channel
        if need_req:
             req_channel_details(ws, channel)

def set_in_room(userid, present):
    global in_room
    if present:
        if userid not in in_room:
            in_room.append(userid)
    else:
        if userid in in_room:
            in_room.remove(userid)

def update_user(user):
    global userlist
    if user["id"] in userlist:
        if not "mute" in user and "mute" in userlist[user["id"]]:
            user["mute"] = userlist[user["id"]]["mute"]
        if not "deaf" in user and "deaf" in userlist[user["id"]]:
            user["deaf"] = userlist[user["id"]]["deaf"]
        if not "speaking" in user and "speaking" in userlist[user["id"]]:
            user["speaking"] = userlist[user["id"]]["speaking"]
    userlist[user["id"]]=user

def on_message(ws, message):
    global guilds, user, access_delay, channels, userlist, current_voice,list_altered,in_room, last_connection
    j = json.loads(message)
    if j["cmd"] == "AUTHORIZE":
        get_access_token_stage2(ws,j["data"]["code"])
        return
    elif j["cmd"] == "DISPATCH":
        if j["evt"] == "READY":
            req_auth(ws)
        elif j["evt"] == "VOICE_STATE_UPDATE":
            list_altered=True
            thisuser = j["data"]["user"]
            un=j["data"]["user"]["username"]
            mute = j["data"]["voice_state"]["mute"] or j["data"]["voice_state"]["self_mute"]
            deaf = j["data"]["voice_state"]["deaf"] or j["data"]["voice_state"]["self_deaf"]
            thisuser["mute"]=mute
            thisuser["deaf"]=deaf
            update_user(thisuser)
        elif j["evt"] == "VOICE_STATE_CREATE":
            list_altered=True
            update_user(j["data"]["user"])
            # If someone joins any voice room grab it fresh from server
            req_channel_details(ws,current_voice)
            un=j["data"]["user"]["username"]
            if j["data"]["user"]["id"] == user["id"]:
                find_user(ws)
        elif j["evt"] == "VOICE_STATE_DELETE":
            list_altered=True
            set_in_room(j["data"]["user"]["id"], False)
            if j["data"]["user"]["id"] == user["id"]:
                in_room=[]
                sub_all_voice(ws)
            else:
                un = j["data"]["user"]["username"]
        elif j["evt"] == "SPEAKING_START":
            list_altered=True
            # It's only possible to get alerts for the room you're in
            set_channel(ws,j["data"]["channel_id"])
            userlist[j["data"]["user_id"]]["speaking"] = True
            set_in_room(j["data"]["user_id"],True)
        elif j["evt"] == "SPEAKING_STOP":
            list_altered=True
            # It's only possible to get alerts for the room you're in
            set_channel(ws,j["data"]["channel_id"])
            if j["data"]["user_id"] in userlist:
                userlist[j["data"]["user_id"]]["speaking"] = False
            set_in_room(j["data"]["user_id"],True)
        elif j["evt"] == "VOICE_CHANNEL_SELECT":
            set_channel(ws, j["data"]["channel_id"])
        elif j["evt"] == "VOICE_CONNECTION_STATUS":
            # VOICE_CONNECTED > CONNECTING > AWAITING_ENDPOINT > DISCONNECTED
            last_connection = j["data"]["state"]
        else:
            print(j)
        return
    elif j["cmd"] == "AUTHENTICATE":
        if j["evt"] == "ERROR":
            get_access_token_stage1(ws)
            return
        else:
            req_guilds(ws)
            user=j["data"]["user"]
            print("ID is %s" %(user["id"]))
            print("Logged in as %s" % (user["username"]))
            return
    elif j["cmd"] == "GET_GUILDS":
        for guild in j["data"]["guilds"]:
            req_channels(ws, guild["id"])
            guilds[guild["id"]]=guild
        return
    elif j["cmd"] == "GET_CHANNELS":
        guilds[j['nonce']]["channels"] = j["data"]["channels"]
        for channel in j["data"]["channels"]:
            channels[channel["id"]] = channel
            if channel["type"] == 2:
                req_channel_details(ws, channel["id"])
        check_guilds()
        sub_all_voice_guild(ws,j["nonce"])
        return
    elif j["cmd"] == "SUBSCRIBE":
        if j["data"]["evt"] == "SPEAKING_STOP" or j["data"]["evt"] == "SPEAKING_START" or j["data"]["evt"] == "VOICE_STATE_CREATE" or j["data"]["evt"] == "VOICE_STATE_UPDATE" or j["data"]["evt"] == "VOICE_STATE_DELETE" or j["data"]["evt"]=="VOICE_CHANNEL_SELECT" or j["data"]["evt"]=="VOICE_CONNECTION_STATUS" or j["data"]["evt"] == "VOICE_SETTINGS_UPDATE":
            return
        print(j)
        return
    elif j["cmd"] == "GET_CHANNEL":
        if j["evt"] == "ERROR":
            print("Could not get room")
            return
        for voice in j["data"]["voice_states"]:
            if voice["user"]["id"] == user["id"]:
                set_channel(ws, j["data"]["id"], False)
        if j["data"]["id"] == current_voice:
          list_altered=True
          in_room=[]
          for voice in j["data"]["voice_states"]:
              update_user(voice["user"])
              set_in_room(voice["user"]["id"], True)
        return
    print(j)

def check_guilds():
    global guilds
    # Check if all of the guilds contain a channel
    for guild in guilds.values():
        if "channels" not in guild:
            return
    # All guilds are filled!
    on_connected()

def on_connected():
    global guilds, ws
    for guild in guilds.values():
        channels = ""
        for channel in guild["channels"]:
            if channel["type"] == 2:
                channels = channels+" "+channel["name"]
        print("%s: %s" % (guild["name"], channels))
    sub_server(ws)
    find_user(ws)

def on_error(ws, error):
    print("ERROR : %s" % (error))

def on_close():
    global ws
    print("Connection closed")
    ws = None

def req_auth(ws):
    ws.send("{\"cmd\":\"AUTHENTICATE\",\"args\":{\"access_token\":\"%s\"},\"nonce\":\"deadbeef\"}" % (access_token))

def req_guilds(ws):
    ws.send("{\"cmd\":\"GET_GUILDS\",\"args\":{},\"nonce\":\"3333\"}")

def req_channels(ws, guild):
    ws.send("{\"cmd\":\"GET_CHANNELS\",\"args\":{\"guild_id\":\"%s\"},\"nonce\":\"%s\"}" % (guild, guild))

def req_channel_details(ws, channel):
    ws.send("{\"cmd\":\"GET_CHANNEL\",\"args\":{\"channel_id\":\"%s\"},\"nonce\":\"%s\"}" % (channel, channel))

def find_user(ws):
    global channels
    for channel in channels:
        req_channel_details(ws, channel)

def sub_raw(ws, cmd, channel, nonce):
    ws.send("{\"cmd\":\"SUBSCRIBE\",\"args\":{%s},\"evt\":\"%s\",\"nonce\":\"%s\"}" % (channel, cmd, nonce))

def sub_server(ws):
    # Experimental
    sub_raw(ws,"VOICE_CHANNEL_SELECT", "", "VOICE_CHANNEL_SELECT")
    sub_raw(ws,"VOICE_CONNECTION_STATUS", "", "VOICE_CONNECTION_STATUS")
    #sub_raw(ws,"ACTIVITY_JOIN", "","ACTIVITY_JOIN")
    #sub_raw(ws,"ACTIVITY_JOIN_REQUEST", "","ACTIVITY_JOIN_REQUEST")
    #sub_raw(ws,"ACTIVITY_SPECTATE", "", "ACTIVITY_SPECTATE")
    #sub_raw(ws,"ACTIVITY_INVITE","","ACTIVITY_INVITE")
    #sub_raw(ws,"GAME_JOIN", "", "GAME_JOIN")
    #sub_raw(ws,"GAME_SPECTATE", "", "GAME_SPECTATE")
    #sub_raw(ws,"VOICE_SETTINGS_UPDATE", "", "VOICE_SETTINGS_UPDATE")
    #sub_raw(ws,"GUILD_STATUS", "\"guild_id\":\"147073008450666496\"", "GUILD_STATUS")

def sub_channel(ws, cmd, channel):
    sub_raw(ws,cmd,"\"channel_id\":\"%s\""%(channel),channel)

def sub_voice_channel(ws, channel):
    sub_channel(ws,"VOICE_STATE_CREATE", channel)
    sub_channel(ws,"VOICE_STATE_UPDATE", channel)
    sub_channel(ws,"VOICE_STATE_DELETE", channel)
    sub_channel(ws,"SPEAKING_START", channel)
    sub_channel(ws,"SPEAKING_STOP", channel)

def sub_all_voice_guild(ws, gid):
    global guilds
    for channel in guilds[gid]["channels"]:
        sub_voice_channel(ws, channel["id"])

def sub_all_voice(ws):
    for guild in guilds:
        sub_all_voice_guild(ws, guild)

def do_read():
    global ws, win, userlist, list_altered, warn_connection
    if not ws:
        # Reconnect if needed
        connect()
        if warn_connection:
            print("Unable to connect to Discord client")
            warn_connection=False
        return True
    # Recreate a list of users in current room
    newlist = []
    for userid in in_room:
        newlist.append(userlist[userid])
    win.set_user_list(newlist, list_altered)
    win.set_connection(last_connection)
    list_altered=False

    # Poll socket for new information
    r,w,e=select.select((ws.sock,),(),(),0)
    while r:
        try:
            # Recieve & send to on_message
            a = ws.recv()
            on_message(ws, a)
            r,w,e=select.select((ws.sock,),(),(),0)
        except websocket._exceptions.WebSocketConnectionClosedException:
            on_close()
            return True
    return True 

class SettingsWindow(Gtk.Window):
    def __init__(self, overlay):
        Gtk.Window.__init__(self)
        self.overlay = overlay
        self.set_size_request(400,200)
        self.connect("destroy", self.close_window)
        self.connect("delete-event", self.close_window)

        # Find config file
        self.configDir = os.path.join(xdg_config_home, "discover")
        os.makedirs(self.configDir, exist_ok=True)
        self.configFile = os.path.join(self.configDir, "discover.ini")
        self.config = ConfigParser(interpolation=None)
        self.config.read(self.configFile)

        self.read_config()

        self.create_gui()

    def close_window(self, a=None,b=None):
        self.hide()
        return True

    def get_monitor_index(self, name):
        display = Gdk.Display.get_default()
        for i in range(0, display.get_n_monitors()):
            if display.get_monitor(i).get_model() == name:
                return i
        print("Could not find monitor : %s" % (name))
        return 0



    def read_config(self):
        self.align_x = self.config.getboolean("main", "rightalign", fallback=True)
        self.align_y = self.config.getint("main", "topalign", fallback=1)
        self.bg_col = json.loads(self.config.get("main","bg_col",fallback="[0.0,0.0,0.0,0.5]"))
        self.fg_col = json.loads(self.config.get("main","fg_col",fallback="[1.0,1.0,1.0,1.0]"))
        self.tk_col = json.loads(self.config.get("main","tk_col",fallback="[0.0,0.7,0.0,1.0]"))
        self.mt_col = json.loads(self.config.get("main","mt_col",fallback="[0.6,0.0,0.0,1.0]"))
        self.avatar_size = self.config.getint("main","avatar_size", fallback=48)
        self.icon_spacing = self.config.getint("main","icon_spacing", fallback=8)
        self.text_padding = self.config.getint("main","text_padding", fallback=6)
        self.font = self.config.get("main","font",fallback=None)
        self.square_avatar = self.config.getboolean("main","square_avatar", fallback=False)
        self.monitor = self.config.get("main", "monitor", fallback="None")
        self.edge_padding = self.config.getint("main","edge_padding", fallback=0)

        # Pass all of our config over to the overlay
        self.overlay.set_align_x(self.align_x)
        self.overlay.set_align_y(self.align_y)
        self.overlay.set_bg(self.bg_col)
        self.overlay.set_fg(self.fg_col)
        self.overlay.set_tk(self.tk_col)
        self.overlay.set_mt(self.mt_col)
        self.overlay.set_avatar_size(self.avatar_size)
        self.overlay.set_icon_spacing(self.icon_spacing)
        self.overlay.set_text_padding(self.text_padding)
        self.overlay.set_square_avatar(self.square_avatar)
        self.overlay.set_monitor(self.get_monitor_index(self.monitor))
        self.overlay.set_edge_padding(self.edge_padding)

        if self.font:
            desc = Pango.FontDescription.from_string(self.font)
            s = desc.get_size()
            if not desc.get_size_is_absolute():
                s = s / Pango.SCALE
            self.overlay.set_font(desc.get_family(), s)


    def save_config(self):
        if not self.config.has_section("main"):
            self.config.add_section("main")

        self.config.set("main","rightalign", "%d" % (int(self.align_x)))
        self.config.set("main","topalign", "%d" % (self.align_y))
        self.config.set("main","bg_col",json.dumps(self.bg_col))
        self.config.set("main","fg_col",json.dumps(self.fg_col))
        self.config.set("main","tk_col",json.dumps(self.tk_col))
        self.config.set("main","mt_col",json.dumps(self.mt_col))
        self.config.set("main","avatar_size", "%d" % (self.avatar_size))
        self.config.set("main","icon_spacing", "%d" % (self.icon_spacing))
        self.config.set("main","text_padding", "%d" % (self.text_padding))
        if self.font:
            self.config.set("main","font",self.font)
        self.config.set("main","square_avatar","%d"%(int(self.square_avatar)))
        self.config.set("main","monitor",self.monitor)
        self.config.set("main","edge_padding","%d"%(self.edge_padding))
        
        with open(self.configFile, 'w') as file:
            self.config.write(file)

    def create_gui(self):
        box = Gtk.Grid()

        # Font chooser
        font_label = Gtk.Label.new("Font")
        font = Gtk.FontButton()
        if self.font:
            font.set_font(self.font)
        font.connect("font-set", self.change_font)

        # Colours
        bg_col_label = Gtk.Label.new("Background colour")
        bg_col = Gtk.ColorButton.new_with_rgba(Gdk.RGBA(self.bg_col[0],self.bg_col[1],self.bg_col[2],self.bg_col[3]))
        fg_col_label = Gtk.Label.new("Text colour")
        fg_col = Gtk.ColorButton.new_with_rgba(Gdk.RGBA(self.fg_col[0],self.fg_col[1],self.fg_col[2],self.fg_col[3]))
        tk_col_label = Gtk.Label.new("Talk colour")
        tk_col = Gtk.ColorButton.new_with_rgba(Gdk.RGBA(self.tk_col[0],self.tk_col[1],self.tk_col[2],self.tk_col[3]))
        mt_col_label = Gtk.Label.new("Mute colour")
        mt_col = Gtk.ColorButton.new_with_rgba(Gdk.RGBA(self.mt_col[0],self.mt_col[1],self.mt_col[2],self.mt_col[3]))
        bg_col.set_use_alpha(True)
        fg_col.set_use_alpha(True)
        tk_col.set_use_alpha(True)
        mt_col.set_use_alpha(True)
        bg_col.connect("color-set", self.change_bg)
        fg_col.connect("color-set", self.change_fg)
        tk_col.connect("color-set", self.change_tk)
        mt_col.connect("color-set", self.change_mt)

        # Avatar size
        avatar_size_label = Gtk.Label.new("Avatar size")
        avatar_adjustment = Gtk.Adjustment.new(self.avatar_size,8,128,1,1,8)
        avatar_size = Gtk.SpinButton.new(avatar_adjustment,0,0)
        avatar_size.connect("value-changed", self.change_avatar_size)

        # Monitor & Alignment
        align_label = Gtk.Label.new("Overlay Location")

        monitor_store = Gtk.ListStore(str)
        display = Gdk.Display.get_default()
        for i in range(0, display.get_n_monitors()):
            monitor_store.append([display.get_monitor(i).get_model()])
        monitor = Gtk.ComboBox.new_with_model(monitor_store)
        monitor.set_active(self.get_monitor_index(self.monitor))
        monitor.connect("changed", self.change_monitor)
        rt = Gtk.CellRendererText()
        monitor.pack_start(rt,True)
        monitor.add_attribute(rt, "text", 0)

        align_x_store = Gtk.ListStore(str)
        align_x_store.append(["Left"])
        align_x_store.append(["Right"])
        align_x = Gtk.ComboBox.new_with_model(align_x_store)
        align_x.set_active(True if self.align_x else False)
        align_x.connect("changed", self.change_align_x)
        rt = Gtk.CellRendererText()
        align_x.pack_start(rt, True)
        align_x.add_attribute(rt,"text",0)

        align_y_store = Gtk.ListStore(str)
        align_y_store.append(["Top"])
        align_y_store.append(["Middle"])
        align_y_store.append(["Bottom"])
        align_y = Gtk.ComboBox.new_with_model(align_y_store)
        align_y.set_active(self.align_y)
        align_y.connect("changed", self.change_align_y)
        rt = Gtk.CellRendererText()
        align_y.pack_start(rt, True)
        align_y.add_attribute(rt,"text",0)

        # Icon spacing
        icon_spacing_label = Gtk.Label.new("Icon Spacing")
        icon_spacing_adjustment = Gtk.Adjustment.new(self.icon_spacing,0,64,1,1,0)
        icon_spacing = Gtk.SpinButton.new(icon_spacing_adjustment,0,0)
        icon_spacing.connect("value-changed", self.change_icon_spacing)

        # Text padding
        text_padding_label = Gtk.Label.new("Text Padding")
        text_padding_adjustment = Gtk.Adjustment.new(self.text_padding,0,64,1,1,0)
        text_padding = Gtk.SpinButton.new(text_padding_adjustment,0,0)
        text_padding.connect("value-changed", self.change_text_padding)

        # Edge padding
        edge_padding_label = Gtk.Label.new("Edge Padding")
        edge_padding_adjustment = Gtk.Adjustment.new(self.edge_padding,0,1000,1,1,0)
        edge_padding = Gtk.SpinButton.new(edge_padding_adjustment,0,0)
        edge_padding.connect("value-changed", self.change_edge_padding)

        # Avatar shape
        square_avatar_label = Gtk.Label.new("Square Avatar")
        square_avatar = Gtk.CheckButton.new()
        square_avatar.set_active(self.square_avatar)
        square_avatar.connect("toggled", self.change_square_avatar)

        box.attach(font_label,0,0,1,1)
        box.attach(font,1,0,1,1)
        box.attach(bg_col_label,0,1,1,1)
        box.attach(bg_col,1,1,1,1)
        box.attach(fg_col_label,0,2,1,1)
        box.attach(fg_col,1,2,1,1)
        box.attach(tk_col_label,0,3,1,1)
        box.attach(tk_col,1,3,1,1)
        box.attach(mt_col_label,0,4,1,1)
        box.attach(mt_col,1,4,1,1)
        box.attach(avatar_size_label,0,5,1,1)
        box.attach(avatar_size,1,5,1,1)
        box.attach(align_label,0,6,1,3)
        box.attach(monitor,1,6,1,1)
        box.attach(align_x,1,7,1,1)
        box.attach(align_y,1,8,1,1)
        box.attach(icon_spacing_label,0,9,1,1)
        box.attach(icon_spacing,1,9,1,1)
        box.attach(text_padding_label,0,10,1,1)
        box.attach(text_padding,1,10,1,1)
        box.attach(edge_padding_label,0,11,1,1)
        box.attach(edge_padding,1,11,1,1)
        box.attach(square_avatar_label,0,12,1,1)
        box.attach(square_avatar,1,12,1,1)

        self.add(box)

        pass

    def change_font(self, button):
        font = button.get_font()
        desc = Pango.FontDescription.from_string(font)
        s = desc.get_size()
        if not desc.get_size_is_absolute():
            s = s / Pango.SCALE
        self.overlay.set_font(desc.get_family(), s)

        self.font = desc.to_string()
        self.save_config()

    def change_bg(self, button):
        c= button.get_rgba()
        c = [c.red, c.green, c.blue, c.alpha]
        self.overlay.set_bg(c)

        self.bg_col = c
        self.save_config()

    def change_fg(self, button):
        c = button.get_rgba()
        c = [c.red, c.green, c.blue, c.alpha]
        self.overlay.set_fg(c)

        self.fg_col = c
        self.save_config()

    def change_tk(self, button):
        c = button.get_rgba()
        c = [c.red, c.green, c.blue, c.alpha]
        self.overlay.set_tk(c)

        self.tk_col = c
        self.save_config()

    def change_mt(self, button):
        c = button.get_rgba()
        c = [c.red, c.green, c.blue, c.alpha]
        self.overlay.set_mt(c)

        self.mt_col = c
        self.save_config()

    def change_avatar_size(self, button):
        self.overlay.set_avatar_size(button.get_value())

        self.avatar_size = button.get_value()
        self.save_config()

    def change_monitor(self, button):
        display = Gdk.Display.get_default()
        mon = display.get_monitor(button.get_active())
        m_s = mon.get_model()
        self.overlay.set_monitor(button.get_active())

        self.monitor = m_s
        self.save_config()

    def change_align_x(self, button):
        self.overlay.set_align_x(button.get_active()==1)

        self.align_x = (button.get_active()==1)
        self.save_config()

    def change_align_y(self, button):
        self.overlay.set_align_y(button.get_active())

        self.align_y = button.get_active()
        self.save_config()

    def change_icon_spacing(self, button):
        self.overlay.set_icon_spacing(button.get_value())

        self.icon_spacing = int(button.get_value())
        self.save_config()

    def change_text_padding(self, button):
        self.overlay.set_text_padding(button.get_value())

        self.text_padding = button.get_value()
        self.save_config()

    def change_edge_padding(self,button):
        self.overlay.set_edge_padding(button.get_value())
        
        self.edge_padding = button.get_value()
        self.save_config()

    def change_square_avatar(self, button):
        self.overlay.set_square_avatar(button.get_active())

        self.square_avatar = button.get_active()
        self.save_config()


class OverlayWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, type=Gtk.WindowType.POPUP)

        self.set_size_request(400, 220)

        self.connect('draw', self.draw)

        self.compositing = False
        # Set RGBA
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)
            self.compositing=True
        else:
            print("Using XShape instead of composite")

        self.set_app_paintable(True)

        self.show_all()

        self.avatars = {}

        self.avatar_size=48
        self.monitor = 0
        self.align_right=True
        self.align_vert=1
        self.text_pad=6
        self.text_font=None
        self.text_size=13
        self.icon_spacing=8
        self.edge_padding=0

        self.round_avatar=True
        self.talk_col = [0.0,0.6,0.0,0.1]
        self.text_col = [1.0,1.0,1.0,1.0]
        self.norm_col = [0.0,0.0,0.0,0.5]
        self.wind_col = [0.0,0.0,0.0,0.0]
        self.mute_col = [0.7,0.0,0.0,1.0]
        self.userlist=[]
        self.connected=False
        self.set_untouchable()
        self.force_location()
        self.set_skip_pager_hint(True)
        self.set_skip_taskbar_hint(True)
        self.def_avatar = self.get_img("https://cdn.discordapp.com/embed/avatars/3.png")

        self.first_draw=True

    def set_font(self, name, size):
        self.text_font=name
        self.text_size=size
        self.redraw()

    def set_bg(self, bg):
        self.norm_col = bg
        self.redraw()

    def set_fg(self, fg):
        self.text_col = fg
        self.redraw()

    def set_tk(self, tk):
        self.talk_col = tk
        self.redraw()

    def set_mt(self, mt):
        self.mute_col = mt
        self.redraw()

    def set_avatar_size(self, size):
        self.avatar_size=size
        self.reset_avatar()
        self.redraw()

    def set_monitor(self, idx):
        self.monitor = idx
        self.force_location()

    def set_align_x(self, b):
        self.align_right = b
        self.force_location()

    def set_align_y(self, i):
        self.align_vert = i
        self.force_location()

    def set_icon_spacing(self, i):
        self.icon_spacing = i
        self.redraw()

    def set_text_padding(self, i):
        self.text_pad = i
        self.redraw()

    def set_edge_padding(self, i):
        self.edge_padding=i
        self.redraw()

    def set_square_avatar(self, i):
        self.round_avatar = not i
        self.redraw()

    def set_untouchable(self):
        (w, h) = self.get_size()
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        surface_ctx = cairo.Context(surface)
        surface_ctx.set_source_rgba(0.0,0.0,0.0,0.0)
        surface_ctx.set_operator(cairo.OPERATOR_SOURCE)
        surface_ctx.paint()
        reg = Gdk.cairo_region_create_from_surface(surface)
        self.input_shape_combine_region(reg)
        #self.shape_combine_region(reg)

    def unset_shape(self):
        if "window" in self and self.window:
            self.window.shape_combine_region(None,0,0)

    def force_location(self):
        self.set_decorated(False)
        self.set_keep_above(True)
        display = Gdk.Display.get_default()
        monitor = display.get_monitor(self.monitor)
        geometry = monitor.get_geometry()
        scale_factor = monitor.get_scale_factor()
        w = scale_factor * geometry.width
        h = scale_factor * geometry.height
        x = geometry.x
        y = geometry.y
        self.resize(400, h)
        if self.align_right:
            self.move(x+w-400,y+0)
        else:
            self.move(x,y)
        self.redraw()

    def col(self,c,a=1.0):
        self.context.set_source_rgba(c[0],c[1],c[2],c[3]*a)

    def set_wind_col(self):
        self.col(self.wind_col)

    def set_text_col(self):
        self.col(self.text_col)

    def set_norm_col(self):
        self.col(self.norm_col)

    def set_talk_col(self,a=1.0):
        self.col(self.talk_col,a)

    def set_mute_col(self,a=1.0):
        self.col(self.mute_col,a)

    def reset_avatar(self):
        self.avatars = {}
        self.def_avatar = self.get_img("https://cdn.discordapp.com/embed/avatars/3.png")

    def set_user_list(self, userlist,alt):
        self.userlist = userlist
        self.userlist.sort(key=lambda x: x["username"])
        if alt:
            self.redraw()

    def set_connection(self, connection):
        is_connected = connection == "VOICE_CONNECTED"
        if self.connected != is_connected:
            self.connected = is_connected
            self.redraw()

    def redraw(self):
        gdkwin = self.get_window()
        if not self.compositing and gdkwin:
            (w, h) = self.get_size()
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
            surface_ctx = cairo.Context(surface)
            self.do_draw(surface_ctx)
            reg = Gdk.cairo_region_create_from_surface(surface)
            gdkwin.shape_combine_region(reg,0,0)
        self.queue_draw()

    def draw(self, widget, context):
        # Draw
        self.do_draw(context)

    def do_draw(self,context):
        self.context = context
        context.set_antialias(self.compositing)
        
        # Make background transparent
        self.set_wind_col()
        # Don't layer drawing over each other, always replace
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        context.set_operator(cairo.OPERATOR_OVER)
        if not self.connected:
            return

        # Get size of window
        (w,h) = self.get_size()
        # Calculate height needed to show overlay
        height = (len(self.userlist) * self.avatar_size) + (len(self.userlist)+1)*self.icon_spacing

        # Choose where to start drawing
        rh = 0 + self.edge_padding
        if self.align_vert==1:
            # Ignore padding?
            rh = (h/2) - (height/2)
        elif self.align_vert==2:
            rh = h-height - self.edge_padding
        # Iterate users in room.
        for user in self.userlist:
            self.draw_avatar(context, user, rh)
            # Shift the relative position down to next location
            rh+=self.avatar_size+self.icon_spacing

        # Don't hold a ref
        self.context=None

    def get_img(self, url):
        req = urllib.request.Request(url)
        req.add_header('Referer','https://streamkit.discord.com/overlay/voice')
        req.add_header('User-Agent', 'Mozilla/5.0')
        try:
            response = urllib.request.urlopen(req)
            input_stream = Gio.MemoryInputStream.new_from_data(response.read(), None)
            pixbuf = Pixbuf.new_from_stream(input_stream, None)
            pixbuf = pixbuf.scale_simple(self.avatar_size, self.avatar_size,
                      GdkPixbuf.InterpType.BILINEAR)
            return pixbuf
        except:
            print("Could not access : %s"%(url))
        return none


    def draw_avatar(self, context, user,y):
        # Ensure pixbuf for avatar
        if user["id"] not in self.avatars and user["avatar"]:
            url= "https://cdn.discordapp.com/avatars/%s/%s.jpg" % (user["id"], user["avatar"])
            print(url)
            p = self.get_img(url)
            if p:
                self.avatars[user["id"]] = p

        (w,h)=self.get_size()
        c = None
        mute=False
        alpha = 1.0
        if "speaking" in user and user["speaking"]:
            c = self.talk_col
        if "mute" in user and user["mute"]:
            mute=True
        if "deaf" in user and user["deaf"]:
            alpha=0.5
        pix = None
        if user["id"] in self.avatars:
            pix = self.avatars[user["id"]]
        if self.align_right:
            self.draw_text(context, user["username"],w-self.avatar_size,y)
            self.draw_avatar_pix(context, pix,w-self.avatar_size,y,c,alpha)
            if mute:
                self.draw_mute(context, w-self.avatar_size, y,alpha)
        else:
            self.draw_text(context, user["username"],self.avatar_size,y)
            self.draw_avatar_pix(context, pix,0,y,c,alpha)
            if mute:
                self.draw_mute(context, 0,y,alpha)

    def draw_text(self,context, string,x,y):
        if self.text_font:
            context.set_font_face(cairo.ToyFontFace(self.text_font,cairo.FontSlant.NORMAL,cairo.FontWeight.NORMAL))
        context.set_font_size(self.text_size)
        xb, yb, w, h, dx, dy = context.text_extents(string)
        ho = (self.avatar_size/2) - (h/2)
        if self.align_right:
            context.move_to(0,0)
            self.set_norm_col()
            context.rectangle(x-w-(self.text_pad*2),y+ho-self.text_pad,w+(self.text_pad*4),h+(self.text_pad*2))
            context.fill()

            self.set_text_col()
            context.move_to(x-w-self.text_pad,y+ho+h)
            context.show_text(string) 
        else:
            context.move_to(0,0)
            self.set_norm_col()
            context.rectangle(x-(self.text_pad*2),y+ho-self.text_pad,w+(self.text_pad*4),h+(self.text_pad*2))
            context.fill()

            self.set_text_col()
            context.move_to(x+self.text_pad,y+ho+h)
            context.show_text(string)

    def draw_avatar_pix(self, context, pixbuf,x,y,c,alpha):
        context.move_to(x,y)
        context.save()
        #context.set_source_pixbuf(pixbuf, 0.0, 0.0)
        if self.round_avatar:
            context.arc(x+(self.avatar_size/2), y+(self.avatar_size/2), self.avatar_size/2,0,2*math.pi)
            context.clip()
        if not pixbuf:
            pixbuf = self.def_avatar
        self.set_wind_col()
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.rectangle(x,y,self.avatar_size,self.avatar_size)
        context.fill()
        context.set_operator(cairo.OPERATOR_OVER)
        Gdk.cairo_set_source_pixbuf(context,pixbuf,x,y)
        context.paint_with_alpha(alpha)
        context.restore()
        if c:
            if self.round_avatar:
                context.arc(x+(self.avatar_size/2), y+(self.avatar_size/2), self.avatar_size/2, 0, 2*math.pi)
                self.col(c)
                context.stroke()
            else:
                context.rectangle(x,y,self.avatar_size,self.avatar_size)
                self.col(c)
                context.stroke()

    def draw_mute(self, context, x, y, a):
        context.save()
        context.translate(x,y)
        context.scale(self.avatar_size, self.avatar_size)
        self.set_mute_col(a)
        context.save()

        # Clip Strike-through
        context.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        context.set_line_width(0.1)
        context.move_to(0.0,0.0)
        context.line_to(1.0,0.0)
        context.line_to(1.0,1.0)
        context.line_to(0.0,1.0)
        context.line_to(0.0,0.0)
        context.close_path()
        context.new_sub_path()
        context.arc(0.9,0.1,0.05,1.25*math.pi, 2.25*math.pi)
        context.arc(0.1,0.9,0.05,.25*math.pi,1.25*math.pi)
        context.close_path()
        context.clip()

        # Center
        context.set_line_width(0.07)
        context.arc(0.5,0.3,0.1,math.pi, 2*math.pi)
        context.arc(0.5,0.5,0.1,0, math.pi)
        context.close_path()
        context.fill()

        context.set_line_width(0.05)

        # Stand rounded
        context.arc(0.5,0.5,0.15,0, 1.0*math.pi)
        context.stroke()

        # Stand vertical
        context.move_to(0.5,0.65)
        context.line_to(0.5,0.75)
        context.stroke()

        # Stand horizontal
        context.move_to(0.35,0.75)
        context.line_to(0.65,0.75)
        context.stroke()

        context.restore()
        # Strike through
        context.arc(0.7,0.3,0.035,1.25*math.pi, 2.25*math.pi)
        context.arc(0.3,0.7,0.035,.25*math.pi,1.25*math.pi)
        context.close_path()
        context.fill()

        context.restore()

def create_gui():
    global win, box, tray, settings, menu, ind
    win = OverlayWindow()

    # Create System Menu
    menu = Gtk.Menu()
    settings_opt = Gtk.MenuItem.new_with_label("Settings")
    close_opt = Gtk.MenuItem.new_with_label("Close")

    menu.append(settings_opt)
    menu.append(close_opt)

    settings_opt.connect("activate", show_settings)
    close_opt.connect("activate", close)
    menu.show_all()

    # Create AppIndicator
    try:
        from gi.repository import AppIndicator3
        ind = AppIndicator3.Indicator.new(
                "discover",
                "discover",
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
        ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        ind.set_menu(menu)
    except:

        # Create System Tray
        tray = Gtk.StatusIcon.new_from_icon_name("discover")
        tray.connect('popup-menu', show_menu)

    settings = SettingsWindow(win)

def show_menu(obj, button, time):
    menu.show_all()
    menu.popup(None,None,Gtk.StatusIcon.position_menu,obj,button,time)

def show_settings(obj=None, data=None):
    global settings
    settings.show_all()

def close(a=None, b=None, c=None):
    Gtk.main_quit()

def connect():
    global ws, oauth_token, error_connection
    if ws:
        return
    try:
        ws = websocket.create_connection("ws://127.0.0.1:6463/?v=1&client_id=%s" % (oauth_token),
                origin="https://streamkit.discord.com")
    except Exception as e:
        if error_connection:
            print(e)
            error_connection=False
        pass

def main():
    connect()

    create_gui()
    win.show_all()

    GLib.timeout_add((1000/60), do_read)

    try:
        Gtk.main()
    except:
        pass


def entrypoint():
    global ws,win,box,tray,settings,ind,menu,warn_connection,error_connection
    ws=None
    win=None
    box=None
    tray=None
    settings=None
    ind=None
    menu=None
    warn_connection=True
    error_connection=True
    main()

if __name__ == "__main__":
    entrypoint()
