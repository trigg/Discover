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
"""
The connector for discord.
Connects in as if it was Streamkit for OBS or Xsplit and
communicates to get voice & text info to display

Terminology:
GUILDS - Often called 'Servers' in discord. It is the group of users and channels that make up
         one server.
CHANNEL - Often called 'Rooms'. Both voice and text channels are types of channel
"""
import select
import time
import json
import sys
import logging
import calendar
import websocket
import requests

import gi
from gi.repository import GLib

log = logging.getLogger(__name__)


class DiscordConnector:
    """
    The connector for discord.
    Connects in as if it was Streamkit for OBS or Xsplit and
    communicates to get voice & text info to display
    """

    def __init__(self, discover):
        self.discover = discover
        self.websocket = None
        self.access_token = discover.config().get(
            "cache", "access_token", fallback=None)
        self.oauth_token = "207646673902501888"

        self.guilds = {}
        self.channels = {}
        self.user = {}
        self.userlist = {}
        self.in_room = []
        self.current_guild = "0"
        self.current_voice = "0"
        self.current_text = "0"
        self.current_text_guild = "0"
        self.list_altered = False
        self.text_altered = False
        self.text = []
        self.authed = False
        self.last_rate_limit_send = 0

        self.socket_watch = None

        self.rate_limited_channels = []
        self.reconnect_cb = None

    def get_access_token_stage1(self):
        """
        First stage of getting an access token. Request authorization from Discord client
        """
        if self.access_token:
            self.req_auth()
            return
        cmd = {
            "cmd": "AUTHORIZE",
            "args":
            {
                "client_id": self.oauth_token,
                "scopes": ["rpc", "messages.read", "rpc.notifications.read"],
                "prompt": "none",
            },
            "nonce": "deadbeef"
        }
        self.websocket.send(json.dumps(cmd))

    def get_access_token_stage2(self, code1):
        """
        Second stage of getting an access token. Give auth code to streamkit
        """
        url = "https://streamkit.discord.com/overlay/token"
        myobj = {"code": code1}
        response = requests.post(url, json=myobj)
        try:
            jsonresponse = json.loads(response.text)
        except json.JSONDecodeError:
            jsonresponse = {}
        if "access_token" in jsonresponse:
            self.access_token = jsonresponse["access_token"]
            self.req_auth()
        else:
            log.error("No access token in json response")
            log.error(response.text)
            log.error("The user most likely denied permission for this app")
            sys.exit(1)

    def set_channel(self, channel, guild, need_req=True):
        """
        Set currently active voice channel
        """
        if not channel:
            if self.current_voice:
                self.unsub_voice_channel(self.current_voice)
            self.current_voice = "0"
            self.current_guild = "0"
            self.discover.voice_overlay.set_blank()
            self.in_room = []
            return
        if channel != self.current_voice:
            if self.current_voice != "0":
                self.unsub_voice_channel(self.current_voice)
            self.sub_voice_channel(channel)
            self.current_voice = channel
            self.current_guild = guild
            if need_req:
                self.req_channel_details(channel)

    def set_text_channel(self, channel, guild, need_req=True):
        """
        Set currently active text channel
        """
        if not channel:
            self.current_text = "0"
            self.current_text_guild = "0"
            return
        if guild != self.current_text_guild:
            self.current_text_guild = guild
            self.request_text_rooms_for_guild(guild)
        if channel != self.current_text:
            self.current_text = channel
            self.current_text_guild = guild
            self.start_listening_text(channel)
            if need_req:
                self.req_channel_details(channel)

    def set_in_room(self, userid, present):
        """
        Set user currently in given room
        """
        if present:
            if userid not in self.in_room:
                self.in_room.append(userid)
        else:
            if userid in self.in_room:
                self.in_room.remove(userid)

    def add_text(self, message):
        """
        Add line of text to text list. Assumes the message is from the correct room
        """
        utc_time = None
        try:
            utc_time = time.strptime(
                message["timestamp"], "%Y-%m-%dT%H:%M:%S.%f%z")
        except ValueError:
            utc_time = time.strptime(
                message["timestamp"], "%Y-%m-%dT%H:%M:%S%z")

        epoch_time = calendar.timegm(utc_time)
        username = message["author"]["username"]
        if ("nick" in message and message['nick'] and len(message["nick"]) > 1
                and 'object Object' not in json.dumps(message["nick"])):
            username = message["nick"]
        colour = "#ffffff"
        if "author_color" in message:
            colour = message["author_color"]

        self.text.append({'id': message["id"],
                          'content': self.get_message_from_message(message),
                          'nick': username,
                          'nick_col': colour,
                          'time': epoch_time,
                          'attach': self.get_attachment_from_message(message),
                          })
        self.text_altered = True

    def update_text(self, message_in):
        """
        Update a line of text
        """
        for idx in range(0, len(self.text)):
            message = self.text[idx]
            if message['id'] == message_in['id']:
                new_message = {'id': message['id'],
                               'content': self.get_message_from_message(message_in),
                               'nick': message['nick'],
                               'nick_col': message['nick_col'],
                               'time': message['time'],
                               'attach': message['attach']}
                self.text[idx] = new_message
                self.text_altered = True
                return

    def delete_text(self, message_in):
        """
        Delete a line of text
        """
        for idx in range(0, len(self.text)):
            message = self.text[idx]
            if message['id'] == message_in['id']:
                del self.text[idx]
                self.text_altered = True
                return

    def get_message_from_message(self, message):
        """
        Messages are sent as JSON objects, with varying information.
        Decides which bits are shown and which are discarded
        """
        if "content_parsed" in message:
            return message["content_parsed"]
        elif "content" in message and len(message["content"]) > 0:
            return message["content"]
        elif "embeds" in message and len(message["embeds"]) == 1:
            if "rawDescription" in message["embeds"][0]:
                return message["embeds"][0]["rawDescription"]
            if "author" in message["embeds"][0]:
                return message["embeds"][0]["author"]["name"]
        elif "attachments" in message and len(message["attachments"]) == 1:
            return ""
        return ""

    def get_attachment_from_message(self, message):
        """
        Messages with attachments come in different forms, decide what is and is
        not an attachment
        """
        if "attachments" in message and len(message["attachments"]) == 1:
            return message["attachments"]
        return None

    def update_user(self, user):
        """
        Update user information
        Pass along our custom user information from version to version
        """
        if user["id"] in self.userlist:
            olduser = self.userlist[user["id"]]
            if "mute" not in user and "mute" in olduser:
                user["mute"] = olduser["mute"]
            if "deaf" not in user and "deaf" in olduser:
                user["deaf"] = olduser["deaf"]
            if "speaking" not in user and "speaking" in olduser:
                user["speaking"] = olduser["speaking"]
            if "nick" not in user and "nick" in olduser:
                user["nick"] = olduser["nick"]
            if "lastspoken" not in user and "lastspoken" in olduser:
                user["lastspoken"] = olduser["lastspoken"]
            if olduser["avatar"] != user["avatar"]:
                self.discover.voice_overlay.delete_avatar(user["id"])
        if "lastspoken" not in user:  # Still nothing?
            user["lastspoken"] = 0  # EEEEPOOCH EEEEEPOCH! BELIEVE MEEEE
        if "speaking" not in user:
            user["speaking"] = False
        self.userlist[user["id"]] = user

    def on_message(self, message):
        """
        Recieve websocket message super-function
        """
        j = json.loads(message)
        if j["cmd"] == "AUTHORIZE":
            if 'data' in j and 'code' in j['data']:
                self.get_access_token_stage2(j["data"]["code"])
            else:
                log.error("Authorization rejected")
                sys.exit(0)
            return
        elif j["cmd"] == "DISPATCH":
            if j["evt"] == "READY":
                self.req_auth()
            elif j["evt"] == "VOICE_STATE_UPDATE":
                self.list_altered = True
                thisuser = j["data"]["user"]
                nick = j["data"]["nick"]
                thisuser["nick"] = nick
                mute = (j["data"]["voice_state"]["mute"] or
                        j["data"]["voice_state"]["self_mute"] or
                        j["data"]["voice_state"]["suppress"])
                deaf = j["data"]["voice_state"]["deaf"] or j["data"]["voice_state"]["self_deaf"]
                thisuser["mute"] = mute
                thisuser["deaf"] = deaf
                if self.current_voice != "0":
                    self.update_user(thisuser)
                self.set_in_room(thisuser["id"], True)
            elif j["evt"] == "VOICE_STATE_CREATE":
                self.list_altered = True
                thisuser = j["data"]["user"]
                nick = j["data"]["nick"]
                thisuser["nick"] = nick
                self.update_user(thisuser)
                # We've joined a room... but where?
                if j["data"]["user"]["id"] == self.user["id"]:
                    self.find_user()
            elif j["evt"] == "VOICE_STATE_DELETE":
                self.list_altered = True
                self.set_in_room(j["data"]["user"]["id"], False)
                if j["data"]["user"]["id"] == self.user["id"]:
                    self.in_room = []
                    self.find_user()
                    self.discover.voice_overlay.set_channel_title(None)
                    self.discover.voice_overlay.set_channel_icon(None)
                    # User might have been forcibly moved room
            elif j["evt"] == "SPEAKING_START":
                self.list_altered = True
                self.userlist[j["data"]["user_id"]]["speaking"] = True
                self.userlist[j["data"]["user_id"]]["lastspoken"] = time.time()
                self.set_in_room(j["data"]["user_id"], True)
            elif j["evt"] == "SPEAKING_STOP":
                self.list_altered = True
                if j["data"]["user_id"] in self.userlist:
                    self.userlist[j["data"]["user_id"]]["speaking"] = False
                self.set_in_room(j["data"]["user_id"], True)
            elif j["evt"] == "VOICE_CHANNEL_SELECT":
                if j["data"]["channel_id"]:
                    self.set_channel(j["data"]["channel_id"],
                                     j["data"]["guild_id"])
                else:
                    self.set_channel(None, None)
            elif j["evt"] == "VOICE_CONNECTION_STATUS":
                self.discover.voice_overlay.set_connection_status(j["data"])
            elif j["evt"] == "MESSAGE_CREATE":
                if self.current_text == j["data"]["channel_id"]:
                    self.add_text(j["data"]["message"])
            elif j["evt"] == "MESSAGE_UPDATE":
                if self.current_text == j["data"]["channel_id"]:
                    self.update_text(j["data"]["message"])
            elif j["evt"] == "MESSAGE_DELETE":
                if self.current_text == j["data"]["channel_id"]:
                    self.delete_text(j["data"]["message"])
            elif j["evt"] == "CHANNEL_CREATE":
                # We haven't been told what guild this is in
                self.req_channel_details(j["data"]["id"], 'new')
            elif j["evt"] == "NOTIFICATION_CREATE":
                self.discover.notification_overlay.add_notification_message(j)
            elif j["evt"] == "VOICE_SETTINGS_UPDATE":
                source = j['data']['input']['device_id']
                sink = j['data']['output']['device_id']
                if sink == 'default':
                    for available_sink in j['data']['output']['available_devices']:
                        if available_sink['id'] == 'default':
                            sink = available_sink['name'][9:]
                if source == 'default':
                    for available_source in j['data']['input']['available_devices']:
                        if available_source['id'] == 'default':
                            source = available_source['name'][9:]
                self.discover.audio_assist.set_devices(sink, source)

            else:
                log.warning(j)
            return
        elif j["cmd"] == "AUTHENTICATE":
            if j["evt"] == "ERROR":
                self.access_token = None
                self.get_access_token_stage1()
                return
            else:
                self.discover.config_set(
                    "cache", "access_token", self.access_token)
                self.req_guilds()
                self.user = j["data"]["user"]
                log.info(
                    "ID is %s", self.user["id"])
                log.info(
                    "Logged in as %s", self.user["username"])
                self.authed = True
                self.on_connected()
                return
        elif j["cmd"] == "GET_GUILDS":
            for guild in j["data"]["guilds"]:
                self.guilds[guild["id"]] = guild
                self.dump_channel_data()
            return
        elif j["cmd"] == "GET_GUILD":
            # We currently only get here because of a "CHANNEL_CREATE" event. Stupidly long winded way around
            if j["data"]:
                guild = j["data"]
            self.dump_channel_data()

            return
        elif j["cmd"] == "GET_CHANNELS":
            if j['evt'] == 'ERROR':
                log.error('%s', j['data']['message'])
                return
            self.guilds[j['nonce']]["channels"] = j["data"]["channels"]
            for channel in j["data"]["channels"]:
                channel['guild_id'] = j['nonce']
                channel['guild_name'] = self.guilds[j['nonce']]["name"]
                self.channels[channel["id"]] = channel
                if channel["type"] == 2:
                    self.req_channel_details(channel["id"])
            self.dump_channel_data()
            return
        elif j["cmd"] == "SUBSCRIBE":
            # Only log errors
            if j['evt']:
                log.warning(j)
            return
        elif j["cmd"] == "UNSUBSCRIBE":
            return
        elif j["cmd"] == "GET_SELECTED_VOICE_CHANNEL":
            if 'data' in j and j['data'] and 'id' in j['data']:
                self.set_channel(j['data']['id'], j['data']['guild_id'])
                self.discover.voice_overlay.set_channel_title(
                    j["data"]["name"])
                if self.current_guild in self.guilds and 'icon_url' in self.guilds[self.current_guild]:
                    self.discover.voice_overlay.set_channel_icon(
                        self.guilds[self.current_guild]['icon_url'])
                else:
                    self.discover.voice_overlay.set_channel_icon(None)
                self.list_altered = True
                self.in_room = []
                for u in j['data']['voice_states']:
                    thisuser = u["user"]
                    nick = u["nick"]
                    thisuser["nick"] = nick
                    mute = (u["voice_state"]["mute"] or
                            u["voice_state"]["self_mute"] or
                            u["voice_state"]["suppress"])
                    deaf = u["voice_state"]["deaf"] or u["voice_state"]["self_deaf"]
                    thisuser["mute"] = mute
                    thisuser["deaf"] = deaf
                    self.update_user(thisuser)
                    self.set_in_room(thisuser["id"], True)
            return
        elif j["cmd"] == "GET_CHANNEL":
            if j["evt"] == "ERROR":
                log.info(
                    "Could not get room")
                return
            if j["nonce"] == "new":
                self.req_channels(j["data"]["guild_id"])
            if j["data"]["type"] == 0:  # Text channel
                if self.current_text == j["data"]["id"]:
                    self.text = []
                    for message in j["data"]["messages"]:
                        self.add_text(message)

            return
        elif j["cmd"] == "SELECT_VOICE_CHANNEL":
            return
        elif j["cmd"] == "SET_VOICE_SETTINGS":
            return
        elif j["cmd"] == "GET_VOICE_SETTINGS":
            return
        log.warning(j)

    def dump_channel_data(self):
        with open(self.discover.channel_file, 'w') as f:
            f.write(json.dumps(
                {'channels': self.channels, 'guild': self.guilds}))

    def on_connected(self):
        """
        Called when connection is finalised
        """
        self.sub_server()
        self.find_user()
        if self.current_text:
            self.start_listening_text(self.current_text)

    def on_error(self, error):
        """
        Called when an error has occured
        """
        log.error("ERROR : %s", error)

    def on_close(self):
        """
        Called when connection is closed
        """
        log.warning("Connection closed")
        if self.socket_watch:
            GLib.source_remove(self.socket_watch)
            self.socket_watch = None
        self.websocket = None
        self.update_overlays_from_data()
        self.current_voice = "0"
        self.schedule_reconnect()

    def req_auth(self):
        """
        Request authentication token
        """
        cmd = {
            "cmd": "AUTHENTICATE",
            "args": {
                "access_token": self.access_token
            },
            "nonce": "deadbeef"
        }
        self.websocket.send(json.dumps(cmd))

    def req_guild(self, guild_id, nonce):
        """
        Request info on one guild
        """
        cmd = {
            "cmd": "GET_GUILD",
            "args": {"guild_id": guild_id},
            "nonce": nonce
        }
        self.websocket.send(json.dumps(cmd))

    def req_guilds(self):
        """
        Request all guilds information for logged in user
        """
        cmd = {
            "cmd": "GET_GUILDS",
            "args": {},
            "nonce": "deadbeef"
        }
        self.websocket.send(json.dumps(cmd))

    def req_channels(self, guild):
        """
        Request all channels information for given guild.
        Don't perform now but pass off to rate-limiter
        """

        if guild in self.guilds:
            self.rate_limited_channels.append(guild)
        else:
            log.warning(f"Didn't find guild with id {guild}")

    def req_channel_details(self, channel, nonce=None):
        """message
        Request information about a specific channel
        """
        if not self.websocket:
            return
        if not nonce:
            nonce = channel
        cmd = {
            "cmd": "GET_CHANNEL",
            "args": {
                "channel_id": channel
            },
            "nonce": nonce
        }
        self.websocket.send(json.dumps(cmd))

    def find_user(self):
        """
        Find the user
        """

        cmd = {
            "cmd": "GET_SELECTED_VOICE_CHANNEL",
            "args": {

            },
            "nonce": "test"
        }
        self.websocket.send(json.dumps(cmd))

    def sub_raw(self, event, args, nonce):
        """
        Subscribe to event helper function
        """
        cmd = {
            "cmd": "SUBSCRIBE",
            "args": args,
            "evt": event,
            "nonce": nonce
        }
        self.websocket.send(json.dumps(cmd))

    def unsub_raw(self, event, args, nonce):
        """
        Subscribe to event helper function
        """
        cmd = {
            "cmd": "UNSUBSCRIBE",
            "args": args,
            "evt": event,
            "nonce": nonce
        }
        self.websocket.send(json.dumps(cmd))

    def sub_server(self):
        """
        Subscribe to helpful events that report connectivity issues &
        when the user has intentionally changed channel

        Unfortunatly no event has been found to alert to being forcibly moved
        or that reports the users current location
        """
        self.sub_raw("VOICE_CHANNEL_SELECT", {}, "VOICE_CHANNEL_SELECT")
        self.sub_raw("VOICE_SETTINGS_UPDATE", {}, "VOICE_SETTINGS_UPDATE")
        self.sub_raw("VOICE_CONNECTION_STATUS", {}, "VOICE_CONNECTION_STATUS")
        self.sub_raw("GUILD_CREATE", {}, "GUILD_CREATE")
        self.sub_raw("CHANNEL_CREATE", {}, "CHANNEL_CREATE")
        self.sub_raw("NOTIFICATION_CREATE", {}, "NOTIFICATION_CREATE")

    def sub_channel(self, event, channel):
        """
        Subscribe to event on channel
        """
        self.sub_raw(event, {"channel_id": channel}, channel)

    def unsub_channel(self, event, channel):
        """
        Subscribe to event on channel
        """
        self.unsub_raw(event, {"channel_id": channel}, channel)

    def sub_text_channel(self, channel):
        """
        Subscribe to text-based events.
        """
        self.sub_channel("MESSAGE_CREATE", channel)
        self.sub_channel("MESSAGE_UPDATE", channel)
        self.sub_channel("MESSAGE_DELETE", channel)

    def unsub_text_channel(self, channel):
        """
        Unsubscribe to text-based events.
        """
        self.unsub_channel("MESSAGE_CREATE", channel)
        self.unsub_channel("MESSAGE_UPDATE", channel)
        self.unsub_channel("MESSAGE_DELETE", channel)

    def sub_voice_channel(self, channel):
        """
        Subscribe to voice-based events
        """
        self.sub_channel("VOICE_STATE_CREATE", channel)
        self.sub_channel("VOICE_STATE_UPDATE", channel)
        self.sub_channel("VOICE_STATE_DELETE", channel)
        self.sub_channel("SPEAKING_START", channel)
        self.sub_channel("SPEAKING_STOP", channel)

    def unsub_voice_channel(self, channel):
        """
        Remove subscription to voice-based events
        """
        self.unsub_channel("VOICE_STATE_CREATE", channel)
        self.unsub_channel("VOICE_STATE_UPDATE", channel)
        self.unsub_channel("VOICE_STATE_DELETE", channel)
        self.unsub_channel("SPEAKING_START", channel)
        self.unsub_channel("SPEAKING_STOP", channel)

    def get_voice_settings(self):
        """
        Request a recent version of voice settings
        """
        cmd = {
            "cmd": "GET_VOICE_SETTINGS",
            "args": {},
            "nonce": "deadbeef"
        }
        if self.websocket:
            self.websocket.send(json.dumps(cmd))

    def set_mute(self, muted):
        cmd = {
            "cmd": "SET_VOICE_SETTINGS",
            "args": {"mute": muted},
            "nonce": "deadbeef"
        }
        if self.websocket:
            self.websocket.send(json.dumps(cmd))
        return False

    def set_deaf(self, deaf):
        cmd = {
            "cmd": "SET_VOICE_SETTINGS",
            "args": {"deaf": deaf},
            "nonce": "deadbeef"
        }
        if self.websocket:
            self.websocket.send(json.dumps(cmd))
        return False

    def change_voice_room(self, id):
        """
        Switch to another voice room
        """
        cmd = {
            "cmd": "SELECT_VOICE_CHANNEL",
            "args": {
                "channel_id": id,
                "force": True
            },
            "nonce": "deadbeef"
        }
        if self.websocket:
            self.websocket.send(json.dumps(cmd))

    def change_text_room(self, id):
        """
        Switch to another text room
        """
        cmd = {
            "cmd": "SELECT_TEXT_CHANNEL",
            "args": {
                "channel_id": id
            },
            "nonce": "deadbeef"
        }
        if self.websocket:
            self.websocket.send(json.dumps(cmd))

    def update_overlays_from_data(self):
        if self.websocket == None:
            self.discover.voice_overlay.set_blank()
            if self.discover.text_overlay:
                self.discover.text_overlay.set_blank()
            if self.discover.notification_overlay:
                self.discover.notification_overlay.set_blank()
            return
        newlist = []
        for userid in self.in_room:
            newlist.append(self.userlist[userid])
        self.discover.voice_overlay.set_user_list(newlist, self.list_altered)
        self.list_altered = False
        # Update text list
        if self.discover.text_overlay.popup_style:
            self.text_altered = True
        if self.text_altered:
            self.discover.text_overlay.set_text_list(
                self.text, self.text_altered)
            self.text_altered = False

        if self.authed and len(self.rate_limited_channels) > 0:
            now = time.time()
            if self.last_rate_limit_send < now - 60:
                guild = self.rate_limited_channels.pop()

                cmd = {
                    "cmd": "GET_CHANNELS",
                    "args": {
                        "guild_id": guild
                    },
                    "nonce": guild
                }
                self.websocket.send(json.dumps(cmd))
                self.last_rate_limit_send = now

    def start_listening_text(self, channel):
        """
        Subscribe to text events on channel, or remember the channel for when we've connected

        Helper function to avoid race conditions of reading config vs connecting to websocket
        """
        if self.websocket:
            if self.current_text != "0":
                self.unsub_text_channel(self.current_text)
            if channel != "0":
                self.sub_text_channel(channel)
                self.req_channel_details(channel)
        self.current_text = channel

    def request_text_rooms_for_guild(self, guild_id):
        """
        Request a correctly ordered list of text channels.

        This will be mixed in with 'None' in the list where a voice channel is
        """
        if (guild_id == 0):
            return
        self.rate_limited_channels.append(guild_id)

    def schedule_reconnect(self):
        if self.reconnect_cb == None:
            log.info("Scheduled a reconnect")
            self.reconnect_cb = GLib.timeout_add_seconds(60, self.connect)
        else:
            log.error("Reconnect already scheduled")

    def connect(self):
        """
        Attempt to connect to websocket

        Should not throw simply for being unable to connect, only for more serious issues
        """
        log.info("Connecting...")
        if self.websocket:
            log.warn("Already connected?")
            return
        if self.reconnect_cb:
            GLib.source_remove(self.reconnect_cb)
            self.reconnect_cb = None
        try:
            self.websocket = websocket.create_connection(
                "ws://127.0.0.1:6463/?v=1&client_id=%s" % (self.oauth_token),
                origin="http://localhost:3000",
                timeout=0.1
            )
            if self.socket_watch:
                GLib.source_remove(self.socket_watch)
            self.socket_watch = GLib.io_add_watch(
                self.websocket.sock, GLib.PRIORITY_DEFAULT_IDLE, GLib.IOCondition.HUP | GLib.IOCondition.IN | GLib.IOCondition.ERR, self.socket_glib)
        except ConnectionError as error:
            self.schedule_reconnect()

    def socket_glib(self, fd, condition):
        if condition == GLib.IO_IN and self.websocket:
            recv, _w, _e = select.select((self.websocket.sock,), (), (), 0)
            while recv:
                try:
                    # Receive & send to on_message
                    msg = self.websocket.recv()
                    self.on_message(msg)
                    if not self.websocket:
                        # Connection was closed in the meantime
                        break
                    recv, _w, _e = select.select(
                        (self.websocket.sock,), (), (), 0)
                except (websocket.WebSocketConnectionClosedException, json.decoder.JSONDecodeError):
                    self.on_close()
                    break
            self.update_overlays_from_data()
        else:
            self.update_overlays_from_data()
            return False
        return True
