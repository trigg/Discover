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
from gi.repository import Gtk, GLib, Gio, GdkPixbuf, Gdk, Pango, PangoCairo
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
current_text = "0"
list_altered = False
text_altered = False
last_connection=""
text=[]
authed=False


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
    except:
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

def set_text_channel(ws,channel,need_req=True):
    global current_text, channels
    if not channel:
        current_text="0"
        return
    if channel != current_text:
        current_text = channel
        print("Changing text room: %s" % (channel))
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

def add_text(message):
    global text, text_altered
    un = message["author"]["username"]
    if "nick" in message and message['nick'] and len(message["nick"])>1:
        un = message["nick"]
    ac = "#ffffff"
    if "author_color" in message:
        ac = message["author_color"]
    
    text.append({'id':message["id"],
                 'content' : get_message_from_message(message),
                 'nick' : un,
                 'nick_col' : ac,
                 })
    text_altered = True

def update_text(message_in):
    global text, text_altered
    for idx in range(0, len(text)):
        message = text[idx]
        if message['id'] == message_in['id']:
            new_message = {'id': message['id'],
                           'content': get_message_from_message(message_in),
                           'nick': message['nick'],
                           'nick_col': message['nick_col']}
            text[idx] = new_message
            text_altered = True
            return

def delete_text(message_in):
    global text, text_altered
    for idx in range(0, len(text)):
        message = text[idx]
        if message['id'] == message_in['id']:
            del text[idx]
            #text[idx] = {"id":message["id"], "content":"-- redacted --", "nick":"-- redacted --","nick_col":"#ffffff"}
            text_altered = True
            return

def get_message_from_message(message):
    if len(message["content"])>0:
        return message["content"]
    elif len(message["embeds"]) == 1:
        if "rawDescription" in message["embeds"][0]:
            return message["embeds"][0]["rawDescription"]
        if "author" in message["embeds"][0]:
            return message["embeds"][0]["author"]["name"]
    elif len(message["attachments"]) ==1:
        # Need to care
        return "-- attachment --"
    return ""


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
    global guilds, user, access_delay, channels, userlist, current_voice, current_text,list_altered,in_room, last_connection, text,authed
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
        elif j["evt"] == "MESSAGE_CREATE":
            if current_text == j["data"]["channel_id"]: 
                add_text(j["data"]["message"])
        elif j["evt"] == "MESSAGE_UPDATE":
            if current_text == j["data"]["channel_id"]: 
                update_text(j["data"]["message"])
        elif j["evt"] == "MESSAGE_DELETE":
            if current_text == j["data"]["channel_id"]: 
                delete_text(j["data"]["message"])
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
            authed=True
            return
    elif j["cmd"] == "GET_GUILDS":
        for guild in j["data"]["guilds"]:
            req_channels(ws, guild["id"])
            guilds[guild["id"]]=guild
        return
    elif j["cmd"] == "GET_CHANNELS":
        guilds[j['nonce']]["channels"] = j["data"]["channels"]
        for channel in j["data"]["channels"]:
            channel['guild_id'] = j['nonce']
            channel['guild_name'] = guilds[j['nonce']]["name"]
            channels[channel["id"]] = channel
            if channel["type"] == 2:
                req_channel_details(ws, channel["id"])
        check_guilds()
        sub_all_voice_guild(ws,j["nonce"])
        sub_all_text_guild(ws,j["nonce"])
        return
    elif j["cmd"] == "SUBSCRIBE":
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
        if current_text == j["data"]["id"]:
            text=[]
            for message in j["data"]["messages"]:
                add_text(message)
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
        if channels[channel]["type"]==2:
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

def sub_text_channel(ws, channel):
    sub_channel(ws,"MESSAGE_CREATE", channel)
    sub_channel(ws,"MESSAGE_UPDATE", channel)
    sub_channel(ws,"MESSAGE_DELETE", channel)

def sub_voice_channel(ws, channel):
    sub_channel(ws,"VOICE_STATE_CREATE", channel)
    sub_channel(ws,"VOICE_STATE_UPDATE", channel)
    sub_channel(ws,"VOICE_STATE_DELETE", channel)
    sub_channel(ws,"SPEAKING_START", channel)
    sub_channel(ws,"SPEAKING_STOP", channel)

def sub_all_voice_guild(ws, gid):
    global guilds
    for channel in guilds[gid]["channels"]:
        if channel["type"]==2:
            sub_voice_channel(ws, channel["id"])

def sub_all_text_guild(ws, gid):
    global guilds
    for channel in guilds[gid]["channels"]:
        if channel["type"]==0:
            sub_text_channel(ws, channel["id"])

def sub_all_voice(ws):
    for guild in guilds:
        sub_all_voice_guild(ws, guild)

def sub_all_text(ws):
    for guild in guilds:
        sub_all_text_guild(ws, guild)

def do_read():
    global ws, twin, win, userlist, list_altered, warn_connection, text_altered, tsettings, channels,authed
    # Ensure connection
    if not ws:
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
    list_altered=False
    win.set_connection(last_connection)
    # Update text list
    if text_altered:
        twin.set_text_list(text, text_altered)
        text_altered = False
    # Update text channels
    tsettings.set_channels(channels)
    # Check for changed channel
    if authed:
        set_text_channel(ws,tsettings.get_channel())
    

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

class DraggableWindow(Gtk.Window):
    def __init__(self, x=0, y=0, w=300, h=300, message="Message"):
        Gtk.Window.__init__(self, type=Gtk.WindowType.POPUP)
        if w < 100:
            w = 100
        if h < 100:
            h = 100
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.message = message
        self.set_size_request(50,50)

        self.connect('draw', self.draw)
        self.connect('motion-notify-event', self.drag)
        self.connect('button-press-event', self.button_press)
        self.connect('button-release-event', self.button_release)

        self.compositing = False
        # Set RGBA
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            # Set the visual even if we can't use it right now
            self.set_visual(visual)
        if screen.is_composited():
            self.compositing=True

        self.set_app_paintable(True)
        self.monitor = 0

        self.drag_type = None
        self.drag_x = 0
        self.drag_y = 0
        self.force_location()
        self.show_all()

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
        #self.resize(400, h)
        self.move(self.x,self.y)
        self.resize(self.w,self.h)

    def drag(self,w,event):
        if event.state & Gdk.ModifierType.BUTTON1_MASK:
            if self.drag_type == 1:
                # Center is move
                self.x = event.x_root - self.drag_x
                self.y = event.y_root - self.drag_y
                self.force_location()
            elif self.drag_type == 2:
                # Right edge
                self.w += event.x - self.drag_x
                self.drag_x = event.x
                self.force_location()
            elif self.drag_type == 3:
                # Bottom edge
                self.h += event.y - self.drag_y
                self.drag_y = event.y
                self.force_location()
            else:
                # Bottom Right
                self.w += event.x - self.drag_x
                self.h += event.y - self.drag_y
                self.drag_x = event.x
                self.drag_y = event.y
                self.force_location()

    def button_press(self, w, event):
        (w, h) = self.get_size()
        if not self.drag_type:
            self.drag_type = 1
            # Where in the window did we press?
            if event.y> h-32:
                self.drag_type+=2
            if event.x> w-32:
                self.drag_type+=1
            self.drag_x = event.x
            self.drag_y = event.y

    def button_release(self, w, event):
        self.drag_type = None

    def draw(self,widget,context):
        context.set_source_rgba(1.0,1.0,0.0,0.7)
        # Don't layer drawing over each other, always replace
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        context.set_operator(cairo.OPERATOR_OVER)
        # Get size of window
        (sw,sh) = self.get_size()

        # Draw text
        context.set_source_rgba(0.0,0.0,0.0,1.0)
        xb, yb, w, h, dx, dy = context.text_extents(self.message)
        context.move_to(sw/2-w/2,sh/2-h/2)
        context.show_text(self.message)
        
        # Draw resizing edges
        context.set_source_rgba(0.0,0.0,1.0,0.5)
        context.rectangle(sw-32,0,32,sh)
        context.fill()

        context.rectangle(0,sh-32,sw,32)
        context.fill()

class SettingsWindow(Gtk.Window):
    def init_config(self):
        self.configDir = os.path.join(xdg_config_home, "discover")
        os.makedirs(self.configDir, exist_ok=True)
        self.configFile = os.path.join(self.configDir, "discover.ini")
        self.read_config()

    def close_window(self,a=None,b=None):
        self.hide()
        return True

    def get_monitor_index(self,name):
        display = Gdk.Display.get_default()
        for i in range(0, display.get_n_monitors()):
            if display.get_monitor(i).get_model() == name:
                return i
        print("Could not find monitor : %s" % (name))
        return 0

    def present(self):
        self.show_all()

class TextSettingsWindow(SettingsWindow):
    def __init__(self, overlay):
        Gtk.Window.__init__(self)
        self.overlay = overlay
        self.set_size_request(400,200)
        self.connect("destroy", self.close_window)
        self.connect("delete-event", self.close_window)
        self.placement_window = None
        self.init_config()
        self.list_channels_keys = []
        self.ignore_channel_change = False
        self.create_gui()

    def present(self):
        self.show_all()
        if not self.floating:
            self.align_x_widget.show()
            self.align_y_widget.show()
            self.align_monitor_widget.show()
            self.align_placement_widget.hide()
        else:
            self.align_x_widget.hide()
            self.align_y_widget.hide()
            self.align_monitor_widget.hide()
            self.align_placement_widget.show()
        model = monitor_store = Gtk.ListStore(str, bool)
        #for c in self.list_channels_keys:
        #    print(self.list_channels[c])
        #    model.append([self.list_channels[c]["name"]])
        self.channel_lookup=[]
        for guild in self.guild_list():
            guild_id, guild_name = guild
            self.channel_lookup.append('0')
            model.append([guild_name, False])
            for c in self.list_channels_keys:
                chan = self.list_channels[c]
                if chan['guild_id'] == guild_id:
                    model.append([chan["name"], True])
                    self.channel_lookup.append(c)
                    
        self.channel_widget.set_model(model)
        self.channel_model = model

        idx = 0
        for c in self.channel_lookup:
            if c == self.channel:
                self.ignore_channel_change = True
                self.channel_widget.set_active(idx)
                self.ignore_channel_change = False
                break
            idx+=1

    def guild_list(self):
        guilds = []
        done = []
        for channel in self.list_channels.values():
            if not channel["guild_id"] in done:
                done.append(channel["guild_id"])
                guilds.append([channel["guild_id"],channel["guild_name"]])
        return guilds

    def set_channels(self, in_list):
        self.list_channels = in_list
        self.list_channels_keys = []
        for key in in_list.keys():
            if in_list[key]["type"]==0:
                self.list_channels_keys.append(key)
        self.list_channels_keys.sort()

    def read_config(self):
        config = ConfigParser(interpolation=None)
        config.read(self.configFile)
        self.enabled = config.getboolean("text", "enabled", fallback = False)
        self.align_x = config.getboolean("text", "rightalign", fallback=True)
        self.align_y = config.getint("text", "topalign", fallback=2)
        self.monitor = config.get("text", "monitor", fallback="None")
        self.floating = config.getboolean("text", "floating", fallback=True)
        self.floating_x = config.getint("text","floating_x", fallback=0)
        self.floating_y = config.getint("text","floating_y", fallback=0)
        self.floating_w = config.getint("text","floating_w", fallback=400)
        self.floating_h = config.getint("text","floating_h", fallback=400)
        self.channel = config.get("text","channel", fallback="0")
        self.font = config.get("text","font",fallback=None)
        self.bg_col = json.loads(config.get("text","bg_col",fallback="[0.0,0.0,0.0,0.5]"))
        self.fg_col = json.loads(config.get("text","fg_col",fallback="[1.0,1.0,1.0,1.0]"))

        print("Loading saved channel %s" % (self.channel))


        # Pass all of our config over to the overlay
        self.overlay.set_enabled(self.enabled)
        self.overlay.set_align_x(self.align_x)
        self.overlay.set_align_y(self.align_y)
        self.overlay.set_monitor(self.get_monitor_index(self.monitor))
        self.overlay.set_floating(self.floating, self.floating_x, self.floating_y, self.floating_w, self.floating_h)
        self.overlay.set_bg(self.bg_col)
        self.overlay.set_fg(self.fg_col)
    
    def save_config(self):
        config = ConfigParser(interpolation=None)
        config.read(self.configFile)
        if not config.has_section("text"):
            config.add_section("text")

        config.set("text","rightalign", "%d" % (int(self.align_x)))
        config.set("text","topalign", "%d" % (self.align_y))
        config.set("text","monitor",self.monitor)
        config.set("text","enabled","%d"%(int(self.enabled)))
        config.set("text","floating","%s"%(int(self.floating)))
        config.set("text","floating_x","%s"%(self.floating_x))
        config.set("text","floating_y","%s"%(self.floating_y))
        config.set("text","floating_w","%s"%(self.floating_w))
        config.set("text","floating_h","%s"%(self.floating_h))
        config.set("text","channel",self.channel)
        config.set("text","bg_col",json.dumps(self.bg_col))
        config.set("text","fg_col",json.dumps(self.fg_col))

        if self.font:
            config.set("text","font",self.font)
        
        with open(self.configFile, 'w') as file:
            config.write(file)

    def create_gui(self):
        box = Gtk.Grid()

        # Enabled
        enabled_label = Gtk.Label.new("Enable")
        enabled = Gtk.CheckButton.new()
        enabled.set_active(self.enabled)
        enabled.connect("toggled", self.change_enabled)

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
        bg_col.set_use_alpha(True)
        fg_col.set_use_alpha(True)
        bg_col.connect("color-set", self.change_bg)
        fg_col.connect("color-set", self.change_fg)

         # Monitor & Alignment
        align_label = Gtk.Label.new("Overlay Location")

        align_type_box = Gtk.HBox()
        align_type_edge = Gtk.RadioButton.new_with_label(None, "Anchor to edge")
        align_type_floating = Gtk.RadioButton.new_with_label_from_widget(align_type_edge,"Floating")
        if self.floating:
            align_type_floating.set_active(True)
        align_type_box.add(align_type_edge)
        align_type_box.add(align_type_floating)

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

        align_placement_button = Gtk.Button.new_with_label("Place Window")

        align_type_edge.connect("toggled", self.change_align_type_edge)
        align_type_floating.connect("toggled", self.change_align_type_floating)
        align_placement_button.connect("pressed", self.change_placement)

        channel_label = Gtk.Label.new("Channel")
        channel = Gtk.ComboBox.new()

        channel.connect("changed", self.change_channel)
        rt = Gtk.CellRendererText()
        #channel.set_row_separator_func(lambda model, path: model[path][1])
        channel.pack_start(rt, True)
        channel.add_attribute(rt,"text",0)   
        channel.add_attribute(rt,'sensitive',1)

        self.align_x_widget= align_x
        self.align_y_widget= align_y
        self.align_monitor_widget= monitor
        self.align_placement_widget = align_placement_button
        self.channel_widget = channel

        box.attach(enabled_label,0,0,1,1)
        box.attach(enabled,1,0,1,1)
        box.attach(channel_label,0,1,1,1)
        box.attach(channel,1,1,1,1)

        box.attach(font_label,0,2,1,1)
        box.attach(font,1,2,1,1)
        box.attach(fg_col_label,0,3,1,1)
        box.attach(fg_col,1,3,1,1)
        box.attach(bg_col_label,0,4,1,1)
        box.attach(bg_col,1,4,1,1)
        box.attach(align_label,0,5,1,5)
        box.attach(align_type_box,1,5,1,1)
        box.attach(monitor,1,6,1,1)
        box.attach(align_x,1,7,1,1)
        box.attach(align_y,1,8,1,1)
        box.attach(align_placement_button,1,9,1,1)

        self.add(box)

    def change_font(self, button):
        font = button.get_font()
        desc = Pango.FontDescription.from_string(font)
        s = desc.get_size()
        if not desc.get_size_is_absolute():
            s = s / Pango.SCALE
        self.overlay.set_font(desc.get_family(), s)

        self.font = desc.to_string()
        self.save_config()

    def change_channel(self, button):
        if self.ignore_channel_change:
            return
        c = self.channel_lookup[button.get_active()]
        self.channel = c
        self.save_config()

    def change_placement(self, button):
        if self.placement_window:
            (x,y) = self.placement_window.get_position()
            (w,h) = self.placement_window.get_size()
            self.floating_x = x
            self.floating_y = y
            self.floating_w = w
            self.floating_h = h
            self.overlay.set_floating(True, x, y, w, h)
            self.save_config()
            button.set_label("Place Window")

            self.placement_window.close()
            self.placement_window=None
        else:
            self.placement_window = DraggableWindow(x = self.floating_x,y=self.floating_y,w=self.floating_w, h=self.floating_h, message="Place & resize this window then press Save!")
            button.set_label("Save this position")

    def change_align_type_edge(self, button):
        if button.get_active():
            self.overlay.set_floating(False,self.floating_x,self.floating_y,self.floating_w,self.floating_h)
            self.floating = False
            self.save_config()

            # Re-sort the screen
            self.align_x_widget.show()
            self.align_y_widget.show()
            self.align_monitor_widget.show()
            self.align_placement_widget.hide()

    def change_align_type_floating(self, button):
        if button.get_active():
            self.overlay.set_floating(True,self.floating_x,self.floating_y,self.floating_w,self.floating_h)
            self.floating = True
            self.save_config()
            self.align_x_widget.hide()
            self.align_y_widget.hide()
            self.align_monitor_widget.hide()
            self.align_placement_widget.show()

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

    def change_enabled(self, button):
        self.overlay.set_enabled(button.get_active())

        self.enabled = button.get_active()
        self.save_config()

    def get_channel(self):
        return self.channel


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

class VoiceSettingsWindow(SettingsWindow):
    def __init__(self, overlay):
        Gtk.Window.__init__(self)
        self.overlay = overlay
        self.set_size_request(400,200)
        self.connect("destroy", self.close_window)
        self.connect("delete-event", self.close_window)
        self.placement_window = None
        self.init_config()

        self.create_gui()

    def present(self):
        self.show_all()
        if not self.floating:
            self.align_x_widget.show()
            self.align_y_widget.show()
            self.align_monitor_widget.show()
            self.align_placement_widget.hide()
        else:
            self.align_x_widget.hide()
            self.align_y_widget.hide()
            self.align_monitor_widget.hide()
            self.align_placement_widget.show()

    def read_config(self):
        config = ConfigParser(interpolation=None)
        config.read(self.configFile)
        self.align_x = config.getboolean("main", "rightalign", fallback=True)
        self.align_y = config.getint("main", "topalign", fallback=1)
        self.bg_col = json.loads(config.get("main","bg_col",fallback="[0.0,0.0,0.0,0.5]"))
        self.fg_col = json.loads(config.get("main","fg_col",fallback="[1.0,1.0,1.0,1.0]"))
        self.tk_col = json.loads(config.get("main","tk_col",fallback="[0.0,0.7,0.0,1.0]"))
        self.mt_col = json.loads(config.get("main","mt_col",fallback="[0.6,0.0,0.0,1.0]"))
        self.avatar_size = config.getint("main","avatar_size", fallback=48)
        self.icon_spacing = config.getint("main","icon_spacing", fallback=8)
        self.text_padding = config.getint("main","text_padding", fallback=6)
        self.font = config.get("main","font",fallback=None)
        self.square_avatar = config.getboolean("main","square_avatar", fallback=False)
        self.monitor = config.get("main", "monitor", fallback="None")
        self.edge_padding = config.getint("main","edge_padding", fallback=0)
        self.floating = config.getboolean("main", "floating", fallback=False)
        self.floating_x = config.getint("main","floating_x", fallback=0)
        self.floating_y = config.getint("main","floating_y", fallback=0)
        self.floating_w = config.getint("main","floating_w", fallback=400)
        self.floating_h = config.getint("main","floating_h", fallback=400)

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

        self.overlay.set_floating(self.floating, self.floating_x, self.floating_y, self.floating_w, self.floating_h)


        if self.font:
            desc = Pango.FontDescription.from_string(self.font)
            s = desc.get_size()
            if not desc.get_size_is_absolute():
                s = s / Pango.SCALE
            self.overlay.set_font(desc.get_family(), s)


    def save_config(self):
        config = ConfigParser(interpolation=None)
        config.read(self.configFile)
        if not config.has_section("main"):
            config.add_section("main")

        config.set("main","rightalign", "%d" % (int(self.align_x)))
        config.set("main","topalign", "%d" % (self.align_y))
        config.set("main","bg_col",json.dumps(self.bg_col))
        config.set("main","fg_col",json.dumps(self.fg_col))
        config.set("main","tk_col",json.dumps(self.tk_col))
        config.set("main","mt_col",json.dumps(self.mt_col))
        config.set("main","avatar_size", "%d" % (self.avatar_size))
        config.set("main","icon_spacing", "%d" % (self.icon_spacing))
        config.set("main","text_padding", "%d" % (self.text_padding))
        if self.font:
            config.set("main","font",self.font)
        config.set("main","square_avatar","%d"%(int(self.square_avatar)))
        config.set("main","monitor",self.monitor)
        config.set("main","edge_padding","%d"%(self.edge_padding))
        config.set("main","floating","%s"%(int(self.floating)))
        config.set("main","floating_x","%s"%(self.floating_x))
        config.set("main","floating_y","%s"%(self.floating_y))
        config.set("main","floating_w","%s"%(self.floating_w))
        config.set("main","floating_h","%s"%(self.floating_h))
        
        with open(self.configFile, 'w') as file:
            config.write(file)

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

        align_type_box = Gtk.HBox()
        align_type_edge = Gtk.RadioButton.new_with_label(None, "Anchor to edge")
        align_type_floating = Gtk.RadioButton.new_with_label_from_widget(align_type_edge, "Floating")
        if self.floating:
            align_type_floating.set_active(True)
        align_type_box.add(align_type_edge)
        align_type_box.add(align_type_floating)

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

        align_placement_button = Gtk.Button.new_with_label("Place Window")

        align_type_edge.connect("toggled", self.change_align_type_edge)
        align_type_floating.connect("toggled", self.change_align_type_floating)
        align_placement_button.connect("pressed", self.change_placement)

        self.align_x_widget = align_x
        self.align_y_widget = align_y
        self.align_monitor_widget= monitor
        self.align_placement_widget = align_placement_button

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
        box.attach(align_label,0,6,1,5)
        box.attach(align_type_box,1,6,1,1)
        box.attach(monitor,1,7,1,1)
        box.attach(align_x,1,8,1,1)
        box.attach(align_y,1,9,1,1)
        box.attach(align_placement_button,1,10,1,1)
        box.attach(icon_spacing_label,0,11,1,1)
        box.attach(icon_spacing,1,11,1,1)
        box.attach(text_padding_label,0,12,1,1)
        box.attach(text_padding,1,12,1,1)
        box.attach(edge_padding_label,0,13,1,1)
        box.attach(edge_padding,1,13,1,1)
        box.attach(square_avatar_label,0,14,1,1)
        box.attach(square_avatar,1,14,1,1)

        self.add(box)

        pass

    def change_placement(self, button):
        if self.placement_window:
            (x,y) = self.placement_window.get_position()
            (w,h) = self.placement_window.get_size()
            self.floating_x = x
            self.floating_y = y
            self.floating_w = w
            self.floating_h = h
            self.overlay.set_floating(True, x, y, w, h)
            self.save_config
            button.set_label("Place Window")

            self.placement_window.close()
            self.placement_window=None
        else:
            self.placement_window = DraggableWindow(x = self.floating_x,y=self.floating_y,w=self.floating_w, h=self.floating_h, message="Place & resize this window then press Save!")
            button.set_label("Save this position")

    def change_align_type_edge(self, button):
        if button.get_active():
            self.overlay.set_floating(False,self.floating_x,self.floating_y,self.floating_w,self.floating_h)
            self.floating = False
            self.save_config()

            # Re-sort the screen
            self.align_x_widget.show()
            self.align_y_widget.show()
            self.align_monitor_widget.show()
            self.align_placement_widget.hide()

    def change_align_type_floating(self, button):
        if button.get_active():
            self.overlay.set_floating(True,self.floating_x,self.floating_y,self.floating_w,self.floating_h)
            self.floating = True
            self.save_config()
            self.align_x_widget.hide()
            self.align_y_widget.hide()
            self.align_monitor_widget.hide()
            self.align_placement_widget.show()

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
        self.set_size_request(50, 50)

        self.connect('draw', self.draw)

        self.compositing = False
        # Set RGBA
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            # Set the visual even if we can't use it right now
            self.set_visual(visual)
        if screen.is_composited():
            self.compositing=True

        self.set_app_paintable(True)
        self.set_untouchable()
        self.set_skip_pager_hint(True)
        self.set_skip_taskbar_hint(True)

        self.show_all()
        self.monitor = 0
        self.align_right=True
        self.align_vert=1
        self.floating=False

    def draw(self,widget,context):
        pass

    def do_draw(self, context):
        pass

    def set_font(self, name, size):
        self.text_font=name
        self.text_size=size
        self.redraw()

    def set_floating(self, floating, x, y, w, h):
        self.floating = floating
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.force_location()

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
        self.get_window().shape_combine_region(None,0,0)

    def force_location(self):
        self.set_decorated(False)
        self.set_keep_above(True)
        display = Gdk.Display.get_default()
        monitor = display.get_monitor(self.monitor)
        geometry = monitor.get_geometry()
        scale_factor = monitor.get_scale_factor()
        if not self.floating:
            w = scale_factor * geometry.width
            h = scale_factor * geometry.height
            x = geometry.x
            y = geometry.y
            self.resize(400, h)
            if self.align_right:
                self.move(x+w-400,y+0)
            else:
                self.move(x,y)
        else:
            self.move(self.x,self.y)
            self.resize(self.w,self.h)
        self.redraw()

    def redraw(self):
        gdkwin = self.get_window()

        if gdkwin:
            if not self.compositing:
                (w, h) = self.get_size()
                surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
                surface_ctx = cairo.Context(surface)
                self.do_draw(surface_ctx)
                reg = Gdk.cairo_region_create_from_surface(surface)
                gdkwin.shape_combine_region(reg,0,0)
            else:
                gdkwin.shape_combine_region(None,0,0)
        self.queue_draw()

    def set_monitor(self, idx):
        self.monitor = idx
        self.force_location()
        self.redraw()
    
    def set_align_x(self, b):
        self.align_right = b
        self.force_location()
        self.redraw()

    def set_align_y(self, i):
        self.align_vert = i
        self.force_location()
        self.redraw()

    def col(self,c,a=1.0):
        self.context.set_source_rgba(c[0],c[1],c[2],c[3]*a)


class TextOverlayWindow(OverlayWindow):
    def __init__(self):
        OverlayWindow.__init__(self)
        self.text_spacing = 4
        self.content = []
        self.text_font=None
        self.text_size=13

        self.connected = True

    def set_text_list(self,tlist, alt):
        self.content = tlist
        if alt:
            self.redraw()

    def set_enabled(self, en):
        if en:
            self.show_all()
        else:
            self.hide()

    def set_fg(self, fg_col):
        self.fg_col = fg_col
        self.redraw()
    
    def set_bg(self, bg_col):
        self.bg_col = bg_col
        self.redraw()

    def do_draw(self,context):
        self.context = context
        context.set_antialias(self.compositing)
        (w, h) = self.get_size()

        # Make background transparent
        context.set_source_rgba(0.0,0.0,0.0,0.4)
        # Don't layer drawing over each other, always replace
        self.col(self.bg_col)
        context.paint()
        context.set_operator(cairo.OPERATOR_OVER)
        self.col(self.fg_col)
        
        if not self.connected:
            return

        long_string=""
        for line in self.content:
            col = "#fff"
            if 'nick_col' in line and line['nick_col']:
                col = line['nick_col']
            long_string = "%s\n<span foreground='%s'>%s</span>: %s" %(
                 long_string, 
                 self.santize_string(col),
                 self.santize_string(line["nick"]), 
                 self.santize_string(line["content"]))
        layout = self.create_pango_layout(long_string)
        layout.set_markup(long_string, -1)
        attr = Pango.AttrList()

        layout.set_width(Pango.SCALE *w)
        layout.set_spacing(Pango.SCALE * 3)
        if(self.text_font):
            font = Pango.FontDescription("%s %s" % (self.text_font, self.text_size))
            layout.set_font_description(font)
        tw,th =layout.get_pixel_size()
        context.move_to(0,-th+h)
        PangoCairo.show_layout(context, layout)
    
    def santize_string(self, string):
        # I hate that Pango has nothing for this.
        return string.replace("&", "&amp;").replace("<","&lt;").replace(">","&gt;").replace("'", "&#39;").replace("\"", "&#34;")

class VoiceOverlayWindow(OverlayWindow):
    def __init__(self):
        OverlayWindow.__init__(self)

        self.avatars = {}

        self.avatar_size=48
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
        self.force_location()
        self.def_avatar = self.get_img("https://cdn.discordapp.com/embed/avatars/3.png")

        self.first_draw=True

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
        screen = self.get_screen()
        c = screen.is_composited()
        if not self.compositing == c:
            alt = True
            self.compositing = c
        if alt:
            self.redraw()

    def set_connection(self, connection):
        is_connected = connection == "VOICE_CONNECTED"
        if self.connected != is_connected:
            self.connected = is_connected
            self.redraw()

    def draw(self, widget, context):
        # Draw
        self.do_draw(context)

    def do_draw(self,context):
        self.context = context
        context.set_antialias(cairo.ANTIALIAS_GOOD)
        
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
    global win, box, tray, vsettings, tsettings, menu, ind,twin
    win = VoiceOverlayWindow()
    twin= TextOverlayWindow()

    # Create System Menu
    menu = Gtk.Menu()
    vsettings_opt = Gtk.MenuItem.new_with_label("Voice Settings")
    tsettings_opt = Gtk.MenuItem.new_with_label("Text Settings")
    close_opt = Gtk.MenuItem.new_with_label("Close")

    menu.append(vsettings_opt)
    menu.append(tsettings_opt)
    menu.append(close_opt)

    vsettings_opt.connect("activate", show_vsettings)
    tsettings_opt.connect("activate", show_tsettings)
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

    vsettings = VoiceSettingsWindow(win)
    tsettings = TextSettingsWindow(twin)

def show_menu(obj, button, time):
    menu.show_all()
    menu.popup(None,None,Gtk.StatusIcon.position_menu,obj,button,time)

def show_vsettings(obj=None, data=None):
    global vsettings
    vsettings.present()

def show_tsettings(obj=None, data=None):
    global tsettings
    tsettings.present()

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
    global ws,win,box,tray,vsettings,tsettings,ind,menu,warn_connection,error_connection
    ws=None
    win=None
    box=None
    tray=None
    vsettings=None
    tsettings=None
    ind=None
    menu=None
    warn_connection=True
    error_connection=True
    main()

if __name__ == "__main__":
    entrypoint()
