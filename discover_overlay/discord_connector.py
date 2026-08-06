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
import logging
import calendar
import websocket
import requests
from .connection_state import ConnectionState
import os
import signal
from .rpc import validate, ValidationError, RPCCmd, RPCEvent, ChannelType


from gi.repository import GObject, GLib

log = logging.getLogger(__name__)


class DiscordConnector(GObject.Object):
    """
    The connector for discord.
    Connects in as if it was Streamkit for OBS or Xsplit and
    communicates to get voice & text info to display
    """

    __gsignals__ = {
        "status-changed": (GObject.SignalFlags.RUN_LAST, None, (str,)),
        "voice-channel-selected": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str, str, str),
        ),  # channel_id, name, guild_id
        "voice-blanked": (GObject.SignalFlags.RUN_LAST, None, ()),
        "text-message-received": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (GObject.TYPE_PYOBJECT,),
        ),
        "text-message-updated": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str, GObject.TYPE_PYOBJECT),
        ),  # msg_id, payload
        "text-message-deleted": (GObject.SignalFlags.RUN_LAST, None, (str,)),  # msg_id
        "user-updated": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (GObject.TYPE_PYOBJECT,),
        ),  # user
        "user-deleted": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (GObject.TYPE_PYOBJECT,),
        ),  # user
        "user-speaking-changed": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str, bool),
        ),  # user_id, is_speaking
        "notification-received": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (GObject.TYPE_PYOBJECT,),
        ),
        "audio-devices-changed": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str, str),
        ),  # sink_name, source_name
        "access-token-verified": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),
        ),  # token
        "voice-channel-title-changed": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),
        ),  # name
        "voice-channel-icon-changed": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),
        ),  # icon_url
        "text-cleared": (GObject.SignalFlags.RUN_LAST, None, ()),  # None
        "channel-data-updated": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT),
        ),  # channels dict, guilds dict
        "overlays-blanked": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (),
        ),
        "connection-state-changed": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (GObject.TYPE_PYOBJECT,),
        ),  # ConnectionState
    }

    def __init__(self, token=None, port=6463):
        GObject.Object.__init__(self)
        self.websocket = None
        self.access_token = token
        self.oauth_token = "207646673902501888"

        self.guilds = {}
        self.channels = {}
        self.user = None
        self.current_guild = "0"
        self.current_voice = "0"
        self.current_text = "0"
        self.current_text_guild = "0"
        self.authed = False
        self.last_rate_limit_send = 0
        self.muted = False
        self.deafened = False
        self.port = port

        self.socket_watch = None

        self.rate_limited_channels = []
        self.reconnect_cb = None
        self.reconnect_time = 5

        self.rate_limit = None

        self.state = ConnectionState.NO_DISCORD

    def get_access_token_stage1(self):
        """
        First stage of getting an access token. Request authorization from Discord client
        """
        if self.access_token:
            self.req_auth()
            return
        cmd = {
            "cmd": "AUTHORIZE",
            "args": {
                "client_id": self.oauth_token,
                "scopes": ["rpc", "messages.read", "rpc.notifications.read"],
                "prompt": "none",
            },
            "nonce": "deadbeef",
        }
        self.websocket.send(json.dumps(cmd))

    def get_access_token_stage2(self, code1):
        """
        Second stage of getting an access token. Give auth code to streamkit
        """
        url = "https://streamkit.discord.com/overlay/token"
        myobj = {"code": code1}
        response = requests.post(url, json=myobj, timeout=10)
        try:
            jsonresponse = json.loads(response.text)
        except requests.exceptions.Timeout:
            self.websocket.close()
            return
        except requests.exceptions.TooManyRedirects:
            jsonresponse = {}
        except json.JSONDecodeError:
            jsonresponse = {}
        if "access_token" in jsonresponse:
            self.access_token = jsonresponse["access_token"]
            self.req_auth()
        else:
            log.error("No access token in json response")
            log.error(response.text)
            log.error("The user most likely denied permission for this app")
            exit()

    def set_channel(self, channel, guild, need_req=True):
        """
        Set currently active voice channel
        """
        if not channel:
            self.set_state(ConnectionState.NO_VOICE_CHAT)
            if self.current_voice:
                self.unsub_voice_channel(self.current_voice)
            self.current_voice = "0"
            self.current_guild = "0"
            self.emit("voice-blanked")
            return
        if channel != self.current_voice:
            self.set_state(ConnectionState.VOICE_CHAT_NOT_CONNECTED)
            if self.current_voice != "0":
                self.unsub_voice_channel(self.current_voice)
            self.emit("voice-blanked")
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

    def add_text(self, message):
        """
        Add line of text to text list. Assumes the message is from the correct room
        """
        utc_time = None
        try:
            utc_time = time.strptime(message["timestamp"], "%Y-%m-%dT%H:%M:%S.%f%z")
        except ValueError:
            utc_time = time.strptime(message["timestamp"], "%Y-%m-%dT%H:%M:%S%z")

        epoch_time = calendar.timegm(utc_time)
        username = message["author"]["username"]
        if (
            "nick" in message
            and message["nick"]
            and len(message["nick"]) > 1
            and "object Object" not in json.dumps(message["nick"])
        ):
            username = message["nick"]
        colour = "#ffffff"
        if "author_color" in message:
            colour = message["author_color"]

        payload = {
            "id": message["id"],
            "content": self.get_message_from_message(message),
            "nick": username,
            "nick_col": colour,
            "time": epoch_time,
            "attach": self.get_attachment_from_message(message),
        }

        self.emit("text-message-received", payload)

    def update_text(self, message_in):
        """
        Update a line of text
        """
        self.emit("text-message-updated", message_in["id"], message_in)

    def delete_text(self, message_in):
        """
        Delete a line of text
        """
        self.emit("text-message-deleted", message_in["id"])

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

    def on_message(self, message):
        """
        Recieve websocket message super-function
        """

        try:
            validated = validate(message)
        except ValidationError as error:
            log.error(f"Dropped unknown packet: {error}")
            log.error(f"{message}")
            return
        cmd = validated.cmd
        evt = validated.evt
        nonce = validated.nonce
        data = validated.data

        if cmd == RPCCmd.AUTHORIZE:
            if data.code:
                self.get_access_token_stage2(data.code)
            else:
                log.error("Authorization rejected")
                self.exit()
            return
        elif cmd == RPCCmd.DISPATCH:
            if evt == RPCEvent.READY:
                self.req_auth()
            elif evt == RPCEvent.VOICE_STATE_UPDATE:
                thisuser = data.user
                nick = data.nick
                thisuser.nick = nick
                thisuser.mute = data.voice_state.is_muted()
                thisuser.deaf = data.voice_state.is_deaf()
                self.emit("user-updated", thisuser)
            elif evt == RPCEvent.VOICE_STATE_CREATE:
                thisuser = data.user
                nick = data.nick
                thisuser.nick = nick
                thisuser.mute = data.voice_state.is_muted()
                thisuser.deaf = data.voice_state.is_deaf()
                # We've joined a room... but where?
                log.error(self.user)
                if data.user.id == self.user.id:
                    self.find_user()

                self.emit("user-updated", thisuser)
            elif evt == RPCEvent.VOICE_STATE_DELETE:
                if data.user.id == self.user.id:
                    # We've left the room, empty overlay and ask where we are now
                    self.find_user()
                    self.emit("voice-blanked")
                else:
                    # Remove this user from overlay
                    self.emit("user-deleted", data.user)
            elif evt == RPCEvent.SPEAKING_START:
                self.emit("user-speaking-changed", data.user_id, True)
            elif evt == RPCEvent.SPEAKING_STOP:
                self.emit("user-speaking-changed", data.user_id, False)
            elif evt == RPCEvent.VOICE_CHANNEL_SELECT:
                if data.channel_id:
                    self.set_channel(data.channel_id, data.guild_id)
                else:
                    self.set_channel(None, None)
            elif evt == RPCEvent.VOICE_CONNECTION_STATUS:
                state = data.state
                if (
                    state == "NO_ROUTE"
                    or state == "VOICE_DISCONNECTED"
                    or state == "ICE_CHECKING"
                    or state == "AWAITING_ENDPOINT"
                    or state == "AUTHENTICATING"
                    or state == "VOICE_CONNECTING"
                    or state == "CONNECTING"
                ):
                    self.set_state(ConnectionState.VOICE_CHAT_NOT_CONNECTED)
                elif state == "CONNECTED" or state == "VOICE_CONNECTED":
                    self.set_state(ConnectionState.CONNECTED)
            elif evt == RPCEvent.MESSAGE_CREATE:
                if self.current_text == data.channel_id:
                    self.add_text(data.message)
            elif evt == RPCEvent.MESSAGE_UPDATE:
                if self.current_text == data.channel_id:
                    self.update_text(data.message)
            elif evt == RPCEvent.MESSAGE_DELETE:
                if self.current_text == data.channel_id:
                    self.delete_text(data.message)
            elif evt == RPCEvent.CHANNEL_CREATE:
                # We haven't been told what guild this is in
                self.req_channel_details(data.id, "new")
            elif evt == RPCEvent.NOTIFICATION_CREATE:
                self.emit("notification-received", data)
            elif evt == RPCEvent.VOICE_SETTINGS_UPDATE:
                source = data.input.device_id
                sink = data.output.device_id
                if sink == "default":
                    for available_sink in data.output.available_devices:
                        if available_sink.id == "default":
                            sink = available_sink.name[9:]
                if source == "default":
                    for available_source in data.input.available_devices:
                        if available_source.id == "default":
                            source = available_source.name[9:]
                self.emit("audio-devices-changed", sink, source)
            else:
                log.warning(data)
            return
        elif cmd == RPCCmd.AUTHENTICATE:
            self.set_state(ConnectionState.NO_VOICE_CHAT)

            if evt == RPCEvent.ERROR:
                self.access_token = None
                self.get_access_token_stage1()
                return
            else:
                self.emit("access-token-verified", self.access_token)
                self.req_guilds()
                log.error(data.user)
                self.user = data.user
                log.info("Successfully connected to a Discord client")
                self.authed = True
                self.on_connected()
                return
        elif cmd == RPCCmd.GET_GUILDS:
            for guild in data.guilds:
                self.guilds[guild.id] = guild
                self.dump_channel_data()
            return
        elif cmd == RPCCmd.GET_GUILD:
            # We currently only get here because of a "CHANNEL_CREATE" event.
            # Stupidly long winded way around
            if data:
                guild = data
            self.dump_channel_data()

            return
        elif cmd == RPCCmd.GET_CHANNELS:
            if evt == RPCEvent.ERROR:
                log.error("%s", data.messages)
                return
            self.guilds[nonce].channels = data.channels
            for channel in data.channels:
                channel.guild_id = nonce
                channel.guild_name = self.guilds[nonce].name
                self.channels[channel.id] = channel
                if channel.type == 2:
                    self.req_channel_details(channel.id)
            self.dump_channel_data()
            return
        elif cmd == RPCCmd.SUBSCRIBE:
            return
        elif cmd == RPCCmd.UNSUBSCRIBE:
            return
        elif cmd == RPCCmd.GET_SELECTED_VOICE_CHANNEL:
            if data is not None and data.id is not None:
                self.set_channel(data.id, data.guild_id)

                self.emit("voice-channel-title-changed", data.name)

                if (
                    self.current_guild in self.guilds
                    and self.guilds[self.current_guild].icon_url is not None
                ):
                    self.emit(
                        "voice-channel-icon-changed",
                        self.guilds[self.current_guild].icon_url,
                    )
                else:
                    self.emit("voice-channel-icon-changed", None)

                for u in data.voice_states:
                    thisuser = u.user
                    nick = u.nick
                    thisuser.nick = nick

                    thisuser.mute = u.voice_state.is_muted()
                    thisuser.deaf = u.voice_state.is_deaf()

                    self.emit("user-updated", thisuser)
            return
        elif cmd == RPCCmd.GET_CHANNEL:
            if evt == RPCEvent.ERROR:
                log.info("Could not get room")
                return
            if nonce == "new":
                self.req_channels(data.guild_id)
            if data.type == ChannelType.GUILD_TEXT:
                if self.current_text == data.id:
                    self.emit("text-cleared")
                    for message in data.messages:
                        self.add_text(message)

            return
        elif cmd == RPCCmd.SELECT_VOICE_CHANNEL:
            return
        elif cmd == RPCCmd.SET_VOICE_SETTINGS:
            # Keep this for toggling mute from RPC
            self.muted = data.mute
            self.deafened = data.deaf
            return
        elif cmd == RPCCmd.GET_VOICE_SETTINGS:
            return
        log.warning(message)

    def dump_channel_data(self):
        """Write all channel data out to file"""
        self.emit("channel-data-updated", self.channels, self.guilds)

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
        self.set_state(ConnectionState.NO_DISCORD)
        self.websocket = None
        self.blank_overlays()
        self.current_voice = "0"
        self.schedule_reconnect()

    def req_auth(self):
        """
        Request authentication token
        """
        cmd = {
            "cmd": "AUTHENTICATE",
            "args": {"access_token": self.access_token},
            "nonce": "deadbeef",
        }
        self.websocket.send(json.dumps(cmd))

    def req_guild(self, guild_id, nonce):
        """
        Request info on one guild
        """
        cmd = {"cmd": "GET_GUILD", "args": {"guild_id": guild_id}, "nonce": nonce}
        self.websocket.send(json.dumps(cmd))

    def req_guilds(self):
        """
        Request all guilds information for logged in user
        """
        if not self.websocket:
            return
        cmd = {"cmd": "GET_GUILDS", "args": {}, "nonce": "deadbeef"}
        self.websocket.send(json.dumps(cmd))

    def req_channels(self, guild):
        """
        Request all channels information for given guild.
        Don't perform now but pass off to rate-limiter
        """

        if guild in self.guilds:
            self.rate_limited_channels.append(guild)
        else:
            log.warning("Didn't find guild with id %s", guild)

    def req_channel_details(self, channel, nonce=None):
        """message
        Request information about a specific channel
        """
        if not self.websocket:
            return
        if not nonce:
            nonce = channel
        cmd = {"cmd": "GET_CHANNEL", "args": {"channel_id": channel}, "nonce": nonce}
        self.websocket.send(json.dumps(cmd))

    def find_user(self):
        """
        Find the user
        """

        cmd = {"cmd": "GET_SELECTED_VOICE_CHANNEL", "args": {}, "nonce": "test"}
        self.websocket.send(json.dumps(cmd))

    def sub_raw(self, event, args, nonce):
        """
        Subscribe to event helper function
        """
        cmd = {"cmd": "SUBSCRIBE", "args": args, "evt": event, "nonce": nonce}
        self.websocket.send(json.dumps(cmd))

    def unsub_raw(self, event, args, nonce):
        """
        Subscribe to event helper function
        """
        cmd = {"cmd": "UNSUBSCRIBE", "args": args, "evt": event, "nonce": nonce}
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
        cmd = {"cmd": "GET_VOICE_SETTINGS", "args": {}, "nonce": "deadbeef"}
        if self.websocket:
            self.websocket.send(json.dumps(cmd))

    def set_mute(self, muted):
        """Set client muted status"""
        cmd = {
            "cmd": "SET_VOICE_SETTINGS",
            "args": {"mute": muted},
            "nonce": "deadbeef",
        }
        if self.websocket:
            self.websocket.send(json.dumps(cmd))
        return False

    def set_deaf(self, deaf):
        """Set client deafened status"""
        cmd = {"cmd": "SET_VOICE_SETTINGS", "args": {"deaf": deaf}, "nonce": "deadbeef"}
        if self.websocket:
            self.websocket.send(json.dumps(cmd))
        return False

    def change_voice_room(self, room_id):
        """
        Switch to another voice room
        """
        cmd = {
            "cmd": "SELECT_VOICE_CHANNEL",
            "args": {"channel_id": room_id, "force": True},
            "nonce": "deadbeef",
        }
        if self.websocket:
            self.websocket.send(json.dumps(cmd))

    def change_text_room(self, room_id):
        """
        Switch to another text room
        """
        cmd = {
            "cmd": "SELECT_TEXT_CHANNEL",
            "args": {"channel_id": room_id},
            "nonce": "deadbeef",
        }
        if self.websocket:
            self.websocket.send(json.dumps(cmd))

    def channel_rate_limit(self):
        """Called regularly to pull in any required channels"""
        if self.websocket and self.authed and len(self.rate_limited_channels) > 0:
            guild = self.rate_limited_channels.pop()
            log.info("Getting guild : %s", guild)
            cmd = {
                "cmd": "GET_CHANNELS",
                "args": {"guild_id": guild},
                "nonce": guild,
            }
            self.websocket.send(json.dumps(cmd))

        continue_rate_limit = len(self.rate_limited_channels) > 0
        if not continue_rate_limit:
            self.rate_limit = None
        return continue_rate_limit

    def blank_overlays(self):
        """Send all overlays a blank"""
        self.emit("overlays-blanked")

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
        if guild_id == 0:
            return
        if guild_id not in self.rate_limited_channels:
            self.rate_limited_channels.append(guild_id)
        if not self.rate_limit:
            # Run once now and schedule for 15 seconds.
            # Any others added suddently will have to wait, or timeout will clear eventually
            self.channel_rate_limit()
            self.rate_limit = GLib.timeout_add_seconds(15, self.channel_rate_limit)

    def schedule_reconnect(self):
        """Set a timer to attempt reconnection"""
        if self.reconnect_cb is None:
            log.info("Scheduled a reconnect in %s seconds", self.reconnect_time)
            self.reconnect_cb = GLib.timeout_add_seconds(
                self.reconnect_time, self.connect_socket
            )
            self.reconnect_time += 5
            if self.reconnect_time > 60:
                self.reconnect_time = 60
        else:
            log.error("Reconnect already scheduled")

    def connect_socket(self):
        """
        Attempt to connect to websocket

        Should not throw simply for being unable to connect, only for more serious issues
        """
        self.authed = False
        log.info("Connecting...")
        if self.websocket:
            log.warning("Already connected?")
            return
        if self.reconnect_cb:
            GLib.source_remove(self.reconnect_cb)
            self.reconnect_cb = None
        try:
            self.websocket = websocket.create_connection(
                f"ws://127.0.0.1:{self.port}/?v=1&client_id={self.oauth_token}",
                origin="http://localhost:3000",
                timeout=0.2,
            )
            if self.socket_watch:
                GLib.source_remove(self.socket_watch)
            self.socket_watch = GLib.io_add_watch(
                self.websocket.sock,
                GLib.PRIORITY_DEFAULT_IDLE,
                GLib.IOCondition.HUP | GLib.IOCondition.IN | GLib.IOCondition.ERR,
                self.socket_glib,
            )
            self.reconnect_time = 5
        except ConnectionError as _error:
            self.schedule_reconnect()

    def socket_glib(self, _fd, condition):
        """Handle new data on socket"""
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
                    recv, _w, _e = select.select((self.websocket.sock,), (), (), 0)
                except websocket.WebSocketConnectionClosedException as e:
                    log.error("Connector Websocket closed : %s", e)
                    self.on_close()
                    break
                except json.decoder.JSONDecodeError as e:
                    log.error("Invalid JSON from Discord : %s", e)
                    log.error("This is probably a modded client...")
                    self.set_state(ConnectionState.DISCORD_INVALID)
                    # It's VERY unlikely this will be fixed in sensible time frame
                    # So set a high retry time to limit wasted CPU
                    self.reconnect_time = 60
                    self.on_close()
                    break
        else:
            self.blank_overlays()
            self.authed = False
            self.set_state(ConnectionState.NO_DISCORD)
            return False
        return True

    def set_state(self, state):
        """Update state and emit"""
        # Do not overwrite a "Modded Discord" message with a disconnected state
        # This allows user to correctly see the reason we have no info to show
        if (
            state == ConnectionState.NO_DISCORD
            and self.state == ConnectionState.DISCORD_INVALID
        ):
            return
        if self.state != state:
            self.state = state
            self.emit("connection-state-changed", state)

    def exit(self):
        """Kills self, works from threads"""
        os.kill(os.getpid(), signal.SIGTERM)
