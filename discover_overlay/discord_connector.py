import websocket
import select
import time
import json
import re
import sys
import requests
import logging
import calendar


class DiscordConnector:
    def __init__(self, text_settings, voice_settings, text_overlay, voice_overlay):
        self.text_settings = text_settings
        self.text_overlay = text_overlay
        self.voice_settings = voice_settings
        self.voice_overlay = voice_overlay
        self.ws = None
        self.access_token = "none"
        # TODO Magic number
        self.oauth_token = "207646673902501888"
        self.access_delay = 0
        self.warn_connection = True
        self.error_connection = True

        self.guilds = {}
        self.channels = {}
        self.user = {}
        self.userlist = {}
        self.in_room = []
        self.current_voice = "0"
        self.current_text = "0"
        self.list_altered = False
        self.text_altered = False
        self.last_connection = ""
        self.text = []
        self.authed = False

    def get_access_token_stage1(self):
        global oauth_token
        self.ws.send("{\"cmd\":\"AUTHORIZE\",\"args\":{\"client_id\":\"%s\",\"scopes\":[\"rpc\",\"messages.read\"],\"prompt\":\"none\"},\"nonce\":\"deadbeef\"}" % (
            self.oauth_token))

    def get_access_token_stage2(self, code1):
        url = "https://streamkit.discord.com/overlay/token"
        myobj = {"code": code1}
        x = requests.post(url, json=myobj)
        try:
            j = json.loads(x.text)
        except:
            j = {}
        if "access_token" in j:
            self.access_token = j["access_token"]
            self.req_auth()
        else:
            sys.exit(1)

    def set_channel(self, channel, need_req=True):
        if not channel:
            self.current_voice = "0"
            return
        if channel != self.current_voice:
            cn = self.channels[channel]['name']
            logging.info(
                "Joined room: %s" % (cn))
            self.current_voice = channel
            if need_req:
                self.req_channel_details(channel)

    def set_text_channel(self, channel, need_req=True):
        if not channel:
            self.current_text = "0"
            return
        if channel != self.current_text:
            self.current_text = channel
            logging.info(
                "Changing text room: %s" % (channel))
            if need_req:
                self.req_channel_details(channel)

    def set_in_room(self, userid, present):
        if present:
            if userid not in self.in_room:
                self.in_room.append(userid)
        else:
            if userid in self.in_room:
                self.in_room.remove(userid)

    def add_text(self, message):
        utc_time = time.strptime(
            message["timestamp"], "%Y-%m-%dT%H:%M:%S.%f%z")
        t = time.time()
        epoch_time = calendar.timegm(utc_time)
        un = message["author"]["username"]
        if "nick" in message and message['nick'] and len(message["nick"]) > 1:
            un = message["nick"]
        ac = "#ffffff"
        if "author_color" in message:
            ac = message["author_color"]

        self.text.append({'id': message["id"],
                          'content': self.get_message_from_message(message),
                          'nick': un,
                          'nick_col': ac,
                          'time': epoch_time,
                          'attach': self.get_attachment_from_message(message),
                          })
        self.text_altered = True

    def update_text(self, message_in):
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
        global text, text_altered
        for idx in range(0, len(self.text)):
            message = self.text[idx]
            if message['id'] == message_in['id']:
                del self.text[idx]
                self.text_altered = True
                return

    def get_message_from_message(self, message):
        if "content_parsed" in message:
            return message["content_parsed"]
        elif "content" in message and len(message["content"]) > 0:
            return message["content"]
        elif len(message["embeds"]) == 1:
            if "rawDescription" in message["embeds"][0]:
                return message["embeds"][0]["rawDescription"]
            if "author" in message["embeds"][0]:
                return message["embeds"][0]["author"]["name"]
        elif len(message["attachments"]) == 1:
            return ""
        return ""

    def get_attachment_from_message(self, message):
        if len(message["attachments"]) == 1:
            return message["attachments"]
        return None

    def update_user(self, user):
        if user["id"] in self.userlist:
            if not "mute" in user and "mute" in self.userlist[user["id"]]:
                user["mute"] = self.userlist[user["id"]]["mute"]
            if not "deaf" in user and "deaf" in self.userlist[user["id"]]:
                user["deaf"] = self.userlist[user["id"]]["deaf"]
            if not "speaking" in user and "speaking" in self.userlist[user["id"]]:
                user["speaking"] = self.userlist[user["id"]]["speaking"]
            if self.userlist[user["id"]]["avatar"] != user["avatar"]:
                self.voice_overlay.delete_avatar(user["id"])
        self.userlist[user["id"]] = user

    def on_message(self, message):
        j = json.loads(message)
        if j["cmd"] == "AUTHORIZE":
            self.get_access_token_stage2(j["data"]["code"])
            return
        elif j["cmd"] == "DISPATCH":
            if j["evt"] == "READY":
                self.req_auth()
            elif j["evt"] == "VOICE_STATE_UPDATE":
                self.list_altered = True
                thisuser = j["data"]["user"]
                un = j["data"]["user"]["username"]
                mute = j["data"]["voice_state"]["mute"] or j["data"]["voice_state"]["self_mute"] or j["data"]["voice_state"]["suppress"]
                deaf = j["data"]["voice_state"]["deaf"] or j["data"]["voice_state"]["self_deaf"]
                thisuser["mute"] = mute
                thisuser["deaf"] = deaf
                self.update_user(thisuser)
            elif j["evt"] == "VOICE_STATE_CREATE":
                self.list_altered = True
                self.update_user(j["data"]["user"])
                # If someone joins any voice room grab it fresh from server
                self.req_channel_details(self.current_voice)
                un = j["data"]["user"]["username"]
                if j["data"]["user"]["id"] == self.user["id"]:
                    self.find_user()
            elif j["evt"] == "VOICE_STATE_DELETE":
                self.list_altered = True
                self.set_in_room(j["data"]["user"]["id"], False)
                if j["data"]["user"]["id"] == self.user["id"]:
                    self.in_room = []
                    self.sub_all_voice()
                else:
                    un = j["data"]["user"]["username"]
            elif j["evt"] == "SPEAKING_START":
                self.list_altered = True
                # It's only possible to get alerts for the room you're in
                self.set_channel(j["data"]["channel_id"])
                self.userlist[j["data"]["user_id"]]["speaking"] = True
                self.set_in_room(j["data"]["user_id"], True)
            elif j["evt"] == "SPEAKING_STOP":
                self.list_altered = True
                # It's only possible to get alerts for the room you're in
                self.set_channel(j["data"]["channel_id"])
                if j["data"]["user_id"] in self.userlist:
                    self.userlist[j["data"]["user_id"]]["speaking"] = False
                self.set_in_room(j["data"]["user_id"], True)
            elif j["evt"] == "VOICE_CHANNEL_SELECT":
                self.set_channel(j["data"]["channel_id"])
            elif j["evt"] == "VOICE_CONNECTION_STATUS":
                # VOICE_CONNECTED > CONNECTING > AWAITING_ENDPOINT > DISCONNECTED
                self.last_connection = j["data"]["state"]
            elif j["evt"] == "MESSAGE_CREATE":
                if self.current_text == j["data"]["channel_id"]:
                    self.add_text(j["data"]["message"])
            elif j["evt"] == "MESSAGE_UPDATE":
                if self.current_text == j["data"]["channel_id"]:
                    self.update_text(j["data"]["message"])
            elif j["evt"] == "MESSAGE_DELETE":
                if self.current_text == j["data"]["channel_id"]:
                    self.delete_text(j["data"]["message"])
            else:
                logging.info(j)
            return
        elif j["cmd"] == "AUTHENTICATE":
            if j["evt"] == "ERROR":
                self.get_access_token_stage1()
                return
            else:
                self.req_guilds()
                self.user = j["data"]["user"]
                logging.info(
                    "ID is %s" % (self.user["id"]))
                logging.info(
                    "Logged in as %s" % (self.user["username"]))
                self.authed = True
                return
        elif j["cmd"] == "GET_GUILDS":
            for guild in j["data"]["guilds"]:
                self.req_channels(guild["id"])
                self.guilds[guild["id"]] = guild
            return
        elif j["cmd"] == "GET_CHANNELS":
            self.guilds[j['nonce']]["channels"] = j["data"]["channels"]
            for channel in j["data"]["channels"]:
                channel['guild_id'] = j['nonce']
                channel['guild_name'] = self.guilds[j['nonce']]["name"]
                self.channels[channel["id"]] = channel
                if channel["type"] == 2:
                    self.req_channel_details(channel["id"])
            self.check_guilds()
            self.sub_all_voice_guild(j["nonce"])
            self.sub_all_text_guild(j["nonce"])
            return
        elif j["cmd"] == "SUBSCRIBE":
            return
        elif j["cmd"] == "GET_CHANNEL":
            if j["evt"] == "ERROR":
                logging.info(
                    "Could not get room")
                return
            for voice in j["data"]["voice_states"]:
                if voice["user"]["id"] == self.user["id"]:
                    self.set_channel(j["data"]["id"], False)
            if j["data"]["id"] == self.current_voice:
                self.list_altered = True
                self.in_room = []
                for voice in j["data"]["voice_states"]:
                    self.update_user(voice["user"])
                    self.set_in_room(voice["user"]["id"], True)
            if self.current_text == j["data"]["id"]:
                self.text = []
                for message in j["data"]["messages"]:
                    self.add_text(message)
            return
        logging.info(j)

    def check_guilds(self):
        # Check if all of the guilds contain a channel
        for guild in self.guilds.values():
            if "channels" not in guild:
                return
        # All guilds are filled!
        self.on_connected()

    def on_connected(self):
        for guild in self.guilds.values():
            channels = ""
            for channel in guild["channels"]:
                channels = channels + " " + channel["name"]
            logging.info(
                u"%s: %s" % (guild["name"], channels))
        self.sub_server()
        self.find_user()

    def on_error(self, error):
        logging.error("ERROR : %s" % (error))

    def on_close(self):
        logging.info("Connection closed")
        self.ws = None

    def req_auth(self):
        self.ws.send("{\"cmd\":\"AUTHENTICATE\",\"args\":{\"access_token\":\"%s\"},\"nonce\":\"deadbeef\"}" % (
            self.access_token))

    def req_guilds(self):
        self.ws.send("{\"cmd\":\"GET_GUILDS\",\"args\":{},\"nonce\":\"3333\"}")

    def req_channels(self, guild):
        self.ws.send("{\"cmd\":\"GET_CHANNELS\",\"args\":{\"guild_id\":\"%s\"},\"nonce\":\"%s\"}" % (
            guild, guild))

    def req_channel_details(self, channel):
        self.ws.send("{\"cmd\":\"GET_CHANNEL\",\"args\":{\"channel_id\":\"%s\"},\"nonce\":\"%s\"}" % (
            channel, channel))

    def find_user(self):
        for channel in self.channels:
            if self.channels[channel]["type"] == 2:
                self.req_channel_details(channel)

    def sub_raw(self, cmd, channel, nonce):
        self.ws.send("{\"cmd\":\"SUBSCRIBE\",\"args\":{%s},\"evt\":\"%s\",\"nonce\":\"%s\"}" % (
            channel, cmd, nonce))

    def sub_server(self):
        # Experimental
        self.sub_raw("VOICE_CHANNEL_SELECT", "", "VOICE_CHANNEL_SELECT")
        self.sub_raw("VOICE_CONNECTION_STATUS", "", "VOICE_CONNECTION_STATUS")
        #sub_raw(ws,"ACTIVITY_JOIN", "","ACTIVITY_JOIN")
        #sub_raw(ws,"ACTIVITY_JOIN_REQUEST", "","ACTIVITY_JOIN_REQUEST")
        #sub_raw(ws,"ACTIVITY_SPECTATE", "", "ACTIVITY_SPECTATE")
        # sub_raw(ws,"ACTIVITY_INVITE","","ACTIVITY_INVITE")
        #sub_raw(ws,"GAME_JOIN", "", "GAME_JOIN")
        #sub_raw(ws,"GAME_SPECTATE", "", "GAME_SPECTATE")
        #sub_raw(ws,"VOICE_SETTINGS_UPDATE", "", "VOICE_SETTINGS_UPDATE")
        #sub_raw(ws,"GUILD_STATUS", "\"guild_id\":\"147073008450666496\"", "GUILD_STATUS")

    def sub_channel(self, cmd, channel):
        self.sub_raw(cmd, "\"channel_id\":\"%s\"" % (channel), channel)

    def sub_text_channel(self, channel):
        self.sub_channel("MESSAGE_CREATE", channel)
        self.sub_channel("MESSAGE_UPDATE", channel)
        self.sub_channel("MESSAGE_DELETE", channel)

    def sub_voice_channel(self, channel):
        self.sub_channel("VOICE_STATE_CREATE", channel)
        self.sub_channel("VOICE_STATE_UPDATE", channel)
        self.sub_channel("VOICE_STATE_DELETE", channel)
        self.sub_channel("SPEAKING_START", channel)
        self.sub_channel("SPEAKING_STOP", channel)

    def sub_all_voice_guild(self, gid):
        for channel in self.guilds[gid]["channels"]:
            if channel["type"] == 2:
                self.sub_voice_channel(channel["id"])

    def sub_all_text_guild(self, gid):
        for channel in self.guilds[gid]["channels"]:
            if channel["type"] == 0:
                self.sub_text_channel(channel["id"])

    def sub_all_voice(self):
        for guild in self.guilds:
            self.sub_all_voice_guild(guild)

    def sub_all_text(self):
        for guild in self.guilds:
            self.sub_all_text_guild(guild)

    def do_read(self):
        # Ensure connection
        if not self.ws:
            self.connect()
            if self.warn_connection:
                logging.info(
                    "Unable to connect to Discord client")
                self.warn_connection = False
            return True
        # Recreate a list of users in current room
        newlist = []
        for userid in self.in_room:
            newlist.append(self.userlist[userid])
        self.voice_overlay.set_user_list(newlist, self.list_altered)
        self.voice_overlay.set_connection(self.last_connection)
        list_altered = False
        # Update text list
        if self.text_overlay.popup_style:
            self.text_altered = True
        if self.text_altered:
            self.text_overlay.set_text_list(self.text, self.text_altered)
            self.text_altered = False
        # Update text channels
        self.text_settings.set_channels(self.channels)
        # Check for changed channel
        if self.authed:
            self.set_text_channel(self.text_settings.get_channel())

        # Poll socket for new information
        r, w, e = select.select((self.ws.sock,), (), (), 0)
        while r:
            try:
                # Recieve & send to on_message
                msg = self.ws.recv()
                self.on_message(msg)
                r, w, e = select.select((self.ws.sock,), (), (), 0)
            except websocket._exceptions.WebSocketConnectionClosedException:
                self.on_close()
                return True
        return True

    def connect(self):
        if self.ws:
            return
        try:
            self.ws = websocket.create_connection("ws://127.0.0.1:6463/?v=1&client_id=%s" % (self.oauth_token),
                                                  origin="https://streamkit.discord.com")
        except Exception as e:
            if self.error_connection:
                logging.error(e)
                self.error_connection = False
            pass
