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
Types and conversions for talking RPC to Discord
"""
from enum import Enum, IntEnum
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field, asdict, is_dataclass
import json
import logging

log = logging.getLogger(__name__)


class RPCCmd(str, Enum):
    """
    Known Discord Client RPC Commands
    """

    DISPATCH = "DISPATCH"
    AUTHORIZE = "AUTHORIZE"
    AUTHENTICATE = "AUTHENTICATE"
    GET_GUILD = "GET_GUILD"
    GET_GUILDS = "GET_GUILDS"
    GET_CHANNEL = "GET_CHANNEL"
    GET_CHANNELS = "GET_CHANNELS"
    SET_USER_VOICE_SETTINGS = "SET_USER_VOICE_SETTINGS"
    GET_SELECTED_VOICE_CHANNEL = "GET_SELECTED_VOICE_CHANNEL"
    SELECT_TEXT_CHANNEL = "SELECT_TEXT_CHANNEL"
    GET_VOICE_SETTINGS = "GET_VOICE_SETTINGS"
    SET_VOICE_SETTINGS = "SET_VOICE_SETTINGS"
    SET_CERTIFIED_DEVICES = "SET_CERTIFIED_DEVICES"
    SET_ACTIVITY = "SET_ACTIVITY"
    SEND_ACTIVITY_JOIN_INVITE = "SEND_ACTIVITY_JOIN_INVITE"
    CLOSE_ACTIVITY_REQUEST = "CLOSE_ACTIVITY_REQUEST"
    SUBSCRIBE = "SUBSCRIBE"
    UNSUBSCRIBE = "UNSUBSCRIBE"
    SELECT_VOICE_CHANNEL = "SELECT_VOICE_CHANNEL"


class RPCEvent(str, Enum):
    """
    Known Discord Client RPC Events
    """

    READY = "READY"
    ERROR = "ERROR"
    CURRENT_USER_UPDATE = "CURRENT_USER_UPDATE"
    RELATIONSHIP_UPDATE = "RELATIONSHIP_UPDATE"
    GUILD_STATUS = "GUILD_STATUS"
    GUILD_CREATE = "GUILD_CREATE"
    CHANNEL_CREATE = "CHANNEL_CREATE"
    VOICE_CHANNEL_SELECT = "VOICE_CHANNEL_SELECT"
    VOICE_STATE_CREATE = "VOICE_STATE_CREATE"
    VOICE_STATE_UPDATE = "VOICE_STATE_UPDATE"
    VOICE_STATE_DELETE = "VOICE_STATE_DELETE"
    VOICE_SETTINGS_UPDATE = "VOICE_SETTINGS_UPDATE"
    VOICE_CONNECTION_STATUS = "VOICE_CONNECTION_STATUS"
    SPEAKING_START = "SPEAKING_START"
    SPEAKING_STOP = "SPEAKING_STOP"
    MESSAGE_CREATE = "MESSAGE_CREATE"
    MESSAGE_UPDATE = "MESSAGE_UPDATE"
    MESSAGE_DELETE = "MESSAGE_DELETE"
    NOTIFICATION_CREATE = "NOTIFICATION_CREATE"
    ACTIVITY_JOIN = "ACTIVITY_JOIN"
    ACTIVITY_SPECTATE = "ACTIVITY_SPECTATE"
    ACTIVITY_JOIN_REQUEST = "ACTIVITY_JOIN_REQUEST"
    ACTIVITY_INVITE = "ACTIVITY_INVITE"
    ENTITLEMENT_CREATE = "ENTITLEMENT_CREATE"
    ENTITLEMENT_DELETE = "ENTITLEMENT_DELETE"


class ChannelType(IntEnum):
    """
    Known Discord Client channel types
    """

    GUILD_TEXT = 0
    DM = 1
    GUILD_VOICE = 2
    GROUP_DM = 3


@dataclass
class RPCUser:
    """
    Data representation of a user
    """

    id: str
    username: str
    discriminator: str
    avatar: Optional[str] = None
    bot: bool = False

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            id=str(d.get("id")),
            username=str(d.get("username")),
            discriminator=str(d.get("discriminator")),
            avatar=d.get("avatar"),
            bot=bool(d.get("bot", False)),
        )


@dataclass
class RPCAuthorizeData:
    """
    Data for Authorize packet
    """

    code: str

    @classmethod
    def from_dict(cls, d: dict):
        return cls(code=str(d.get("code")))


@dataclass
class RPCAuthenticateData:
    """
    Data for Authenticate packet
    """

    user: RPCUser
    scopes: List[str]
    expires: str
    access_token: str
    application: List[Dict[str, Any]]

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            user=RPCUser.from_dict(d.get("user", {})),
            scopes=list(d.get("scopes", [])),
            expires=str(d.get("expires")),
            access_token=str(d.get("access_token")),
            application=d.get("application", []),
        )


@dataclass
class VoiceState:
    """
    Data for users voice state
    """

    mute: bool = False
    deaf: bool = False
    self_mute: bool = False
    self_deaf: bool = False
    suppress: bool = False

    @classmethod
    def is_muted(cls):
        return cls.mute or cls.self_mute or cls.suppress

    @classmethod
    def is_deaf(cls):
        return cls.deaf or cls.self_deaf

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            mute=bool(d.get("mute")),
            deaf=bool(d.get("deaf")),
            self_mute=bool(d.get("self_mute")),
            self_deaf=bool(d.get("self_deaf")),
            suppress=bool(d.get("suppress")),
        )


@dataclass
class ChannelVoiceStateData:
    """
    Data around voice states for a user
    """

    voice_state: VoiceState
    user: RPCUser
    nick: Optional[str] = None
    volume: int = 100

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            voice_state=VoiceState.from_dict(d.get("voice_state")),
            user=RPCUser.from_dict(d.get("user")),
            nick=d.get("nick"),
            volume=int(d.get("volume")),
        )


@dataclass
class RPCChannelData:
    """
    Data for a channel. Could be voice or text.
    """

    id: str
    name: str
    type: ChannelType
    guild_id: Optional[str] = None
    topic: Optional[str] = None
    bitrate: Optional[int] = None
    user_limit: Optional[int] = None
    position: Optional[int] = None
    voice_states: Optional[List[ChannelVoiceStateData]] = field(default_factory=list)
    messages: Optional[List[Dict[str, Any]]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict):
        if "type" not in d:
            raise ValidationError("Missing 'type' inside channel.")

        return cls(
            id=str(d.get("id")),
            name=str(d.get("name")),
            type=ChannelType(d["type"]),
            guild_id=d.get("guild_id"),
            topic=d.get("topic"),
            bitrate=None if d["bitrate"] is None else int(d["bitrate"]),
            user_limit=int(d["user_limit"]),
            position=int(d["position"]),
            voice_states=[
                ChannelVoiceStateData.from_dict(vs) for vs in d.get("voice_states", [])
            ],
            messages=d.get("messages", []),
        )


@dataclass
class RPCGuildData:
    """
    Data for one guild
    """

    id: str
    name: str
    icon_url: Optional[str] = None
    members: List[RPCUser] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            id=str(d.get("id")),
            name=str(d.get("name")),
            icon_url=d.get("icon_url"),
            members=[RPCUser.from_dict(m) for m in d.get("members", [])],
        )


@dataclass
class RPCGuildsData:
    """
    Data for a list of guilds
    """

    guilds: List[RPCGuildData] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict):
        raw_guilds = d.get("guilds")
        parsed_guilds = (
            [RPCGuildData.from_dict(g) for g in raw_guilds if isinstance(g, dict)]
            if isinstance(raw_guilds, list)
            else []
        )

        return cls(guilds=parsed_guilds)


@dataclass
class RPCPartialChannelData:
    """
    Representation of a partial channel object.
    """

    id: str
    name: str
    type: int

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            id=str(d.get("id")),
            name=str(d.get("name")),
            type=int(d.get("type")),
        )


@dataclass
class RPCChannelsData:
    """
    Data for a list of partial channels.
    """

    channels: List[RPCPartialChannelData] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            channels=[RPCPartialChannelData.from_dict(c) for c in d.get("channels", [])]
        )


@dataclass
class RPCVoiceChannelSelectData:
    """
    Data for a Voice channel select packet
    """

    channel_id: Optional[str] = None
    guild_id: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            channel_id=d.get("channel_id"),
            guild_id=d.get("guild_id"),
        )


@dataclass
class RPCAvailableDevice:
    """
    Data for one avaiable audio device
    """

    id: str
    name: str

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            id=str(d.get("id", "")),
            name=str(d.get("name", "")),
        )


@dataclass
class RPCDeviceSettings:
    """
    Data for settings around one audio device
    """

    device_id: str
    volume: int
    available_devices: List[RPCAvailableDevice] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict):
        devices = [
            RPCAvailableDevice(id=str(dev.get("id")), name=str(dev.get("name")))
            for dev in d.get("available_devices")
        ]
        return cls(
            device_id=str(d.get("device_id")),
            volume=int(d.get("volume")),
            available_devices=devices,
        )


@dataclass
class RPCVoiceMode:
    """
    Data around voice settings for a device
    """

    type: str
    auto_threshold: bool = True
    threshold: float = -60.0
    shortcut: List[Any] = field(default_factory=list)
    delay: int = 20

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            type=str(d.get("type")),
            auto_threshold=bool(d.get("auto_threshold")),
            threshold=float(d.get("threshold")),
            shortcut=list(d.get("shortcut")),
            delay=int(d.get("delay")),
        )


@dataclass
class RPCVoiceSettings:
    """
    Data for all devices and user voice settings
    """

    input: RPCDeviceSettings
    output: RPCDeviceSettings
    mode: RPCVoiceMode
    automatic_gain_control: bool = True
    echo_cancellation: bool = True
    noise_suppression: bool = True
    qos: bool = False
    silence_warning: bool = True
    deaf: bool = False
    mute: bool = False

    @classmethod
    def from_dict(cls, d: dict):
        """Maps nested payload elements into dot-accessible dataclass structures safely."""
        return cls(
            input=RPCDeviceSettings.from_dict(d.get("input")),
            output=RPCDeviceSettings.from_dict(d.get("output")),
            mode=RPCVoiceMode.from_dict(d.get("mode")),
            automatic_gain_control=bool(d.get("automatic_gain_control")),
            echo_cancellation=bool(d.get("echo_cancellation")),
            noise_suppression=bool(d.get("noise_suppression")),
            qos=bool(d.get("qos")),
            silence_warning=bool(d.get("silence_warning")),
            deaf=bool(d.get("deaf")),
            mute=bool(d.get("mute")),
        )


@dataclass
class RPCSubscriptionData:
    """
    Data about one RPC Subscription to events
    """

    evt: str

    @classmethod
    def from_dict(cls, d: dict):
        return cls(evt=str(d.get("evt", "")))


@dataclass
class RPCSpeakingData:
    """
    Data around a talking stop or start event
    """

    user_id: str
    channel_id: str

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            user_id=str(d.get("user_id", "")),
            channel_id=str(d.get("channel_id", "")),
        )


@dataclass
class RPCMessageData:
    """
    Data around a text message
    """

    channel_id: str
    message: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            channel_id=str(d.get("channel_id", "")),
            message=d.get("message", {}),
        )


@dataclass
class RPCMessageDeleteData:
    """
    Data for a message delete message
    """

    id: str
    channel_id: str

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            id=str(d.get("id", "")),
            channel_id=str(d.get("channel_id", "")),
        )


@dataclass
class RPCNotificationData:
    """
    Data for a notification
    """

    channel_id: str
    icon_url: str
    title: str
    message: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            channel_id=str(d.get("channel_id", "")),
            icon_url=str(d.get("icon_url", "")),
            title=str(d.get("title", "")),
            message=d.get("message", {}),
        )


@dataclass
class RPCAnyData:
    """
    For those data structures we don't actually care to handle
    """

    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(extra=d if isinstance(d, dict) else {"value": d})


@dataclass
class RPCVoiceStateEventData:
    voice_state: VoiceState
    user: RPCUser
    nick: Optional[str] = None
    volume: int = 100
    mute: bool = False
    pan: Dict[str, float] = field(default_factory=lambda: {"left": 1.0, "right": 1.0})

    @classmethod
    def from_dict(cls, d: dict):
        raw_pan = d.get("pan", {})
        return cls(
            voice_state=VoiceState.from_dict(d.get("voice_state", {})),
            user=RPCUser.from_dict(d.get("user", {})),
            nick=d.get("nick"),
            volume=int(d.get("volume", 100)),
            mute=bool(d.get("mute", False)),
            pan={
                "left": float(raw_pan.get("left", 1.0)),
                "right": float(raw_pan.get("right", 1.0)),
            },
        )


class RPCVoiceConnectionState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    AWAITING_ENDPOINT = "AWAITING_ENDPOINT"
    AUTHENTICATING = "AUTHENTICATING"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    VOICE_DISCONNECTED = "VOICE_DISCONNECTED"
    VOICE_CONNECTING = "VOICE_CONNECTING"
    VOICE_CONNECTED = "VOICE_CONNECTED"
    NO_ROUTE = "NO_ROUTE"
    ICE_CHECKING = "ICE_CHECKING"


@dataclass
class RPCPingMetric:
    time: int
    value: float

    @classmethod
    def from_dict(cls, data: Union[dict, float, int]):
        if isinstance(data, dict):
            return cls(
                time=int(data.get("time")),
                value=float(data.get("value")),
            )
        return cls(time=0, value=float(data))


@dataclass
class RPCVoiceConnectionStatusData:
    state: RPCVoiceConnectionState
    hostname: str
    pings: List[RPCPingMetric] = field(default_factory=list)
    average_ping: float = 0.0

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            state=RPCVoiceConnectionState(d["state"]),
            hostname=str(d.get("hostname")),
            pings=[RPCPingMetric.from_dict(p) for p in d.get("pings", [])],
            average_ping=float(d.get("average_ping", 0.0)),
        )


@dataclass
class RPCFrame:
    """
    Entire message container
    """

    cmd: RPCCmd
    nonce: Optional[str] = None
    evt: Optional[RPCEvent] = None
    data: Optional[
        Union[
            RPCChannelData,
            RPCVoiceChannelSelectData,
            RPCAuthorizeData,
            RPCAuthenticateData,
            RPCGuildData,
            RPCChannelData,
            RPCGuildsData,
            RPCChannelsData,
            RPCVoiceSettings,
            RPCAnyData,
            RPCSubscriptionData,
            RPCUser,
            RPCVoiceStateEventData,
            RPCVoiceConnectionStatusData,
            RPCSpeakingData,
            RPCMessageData,
            RPCMessageDeleteData,
            RPCNotificationData,
        ]
    ] = None
    args: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:

        def factory(kv_pairs):
            return {k: v for k, v in kv_pairs if v is not None}

        raw_dict = asdict(self, dict_factory=factory)

        if isinstance(raw_dict.get("cmd"), Enum):
            raw_dict["cmd"] = raw_dict["cmd"].value
        if isinstance(raw_dict.get("evt"), Enum):
            raw_dict["evt"] = raw_dict["evt"].value

        return json.dumps(raw_dict)


class ValidationError(Exception):
    """
    Something isn't right.
    """

    pass


# Line up events and commands with expected data shape

CMD_DATA_REGISTRY = {
    RPCCmd.AUTHORIZE: RPCAuthorizeData,
    RPCCmd.AUTHENTICATE: RPCAuthenticateData,
    RPCCmd.GET_GUILD: RPCGuildData,
    RPCCmd.GET_GUILDS: RPCGuildsData,
    RPCCmd.GET_CHANNEL: RPCChannelData,
    RPCCmd.GET_CHANNELS: RPCChannelsData,
    RPCCmd.SET_USER_VOICE_SETTINGS: RPCVoiceSettings,
    RPCCmd.GET_SELECTED_VOICE_CHANNEL: RPCChannelData,
    RPCCmd.SELECT_TEXT_CHANNEL: RPCChannelData,
    RPCCmd.GET_VOICE_SETTINGS: RPCVoiceSettings,
    RPCCmd.SET_VOICE_SETTINGS: RPCVoiceSettings,
    RPCCmd.SET_CERTIFIED_DEVICES: RPCAnyData,
    RPCCmd.SET_ACTIVITY: RPCAnyData,
    RPCCmd.SEND_ACTIVITY_JOIN_INVITE: RPCAnyData,
    RPCCmd.CLOSE_ACTIVITY_REQUEST: RPCAnyData,
    RPCCmd.SUBSCRIBE: RPCSubscriptionData,
    RPCCmd.UNSUBSCRIBE: RPCSubscriptionData,
    RPCCmd.SELECT_VOICE_CHANNEL: RPCChannelData,
}

EVENT_DATA_REGISTRY = {
    RPCEvent.READY: RPCAnyData,
    RPCEvent.ERROR: RPCAnyData,
    RPCEvent.CURRENT_USER_UPDATE: RPCUser,
    RPCEvent.RELATIONSHIP_UPDATE: RPCAnyData,
    RPCEvent.GUILD_STATUS: RPCGuildData,
    RPCEvent.GUILD_CREATE: RPCGuildData,
    RPCEvent.CHANNEL_CREATE: RPCChannelData,
    RPCEvent.VOICE_CHANNEL_SELECT: RPCVoiceChannelSelectData,
    RPCEvent.VOICE_STATE_CREATE: RPCVoiceStateEventData,
    RPCEvent.VOICE_STATE_UPDATE: RPCVoiceStateEventData,
    RPCEvent.VOICE_STATE_DELETE: RPCVoiceStateEventData,
    RPCEvent.VOICE_SETTINGS_UPDATE: RPCVoiceSettings,
    RPCEvent.VOICE_CONNECTION_STATUS: RPCVoiceConnectionStatusData,
    RPCEvent.SPEAKING_START: RPCSpeakingData,
    RPCEvent.SPEAKING_STOP: RPCSpeakingData,
    RPCEvent.MESSAGE_CREATE: RPCMessageData,
    RPCEvent.MESSAGE_UPDATE: RPCMessageData,
    RPCEvent.MESSAGE_DELETE: RPCMessageDeleteData,
    RPCEvent.NOTIFICATION_CREATE: RPCNotificationData,
    RPCEvent.ACTIVITY_JOIN: RPCAnyData,
    RPCEvent.ACTIVITY_SPECTATE: RPCAnyData,
    RPCEvent.ACTIVITY_JOIN_REQUEST: RPCAnyData,
    RPCEvent.ACTIVITY_INVITE: RPCAnyData,
    RPCEvent.ENTITLEMENT_CREATE: RPCAnyData,
    RPCEvent.ENTITLEMENT_DELETE: RPCAnyData,
}


def validate(raw: str) -> RPCFrame:
    """
    Checks a given JSON string is a valid RPC Frame
    """
    try:
        data_map = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Not JSON: {e}")

    if "cmd" not in data_map:
        raise ValidationError("Missing: 'cmd'")

    try:
        cmd_enum = RPCCmd(data_map["cmd"])
    except ValueError:
        raise ValidationError(f"Unknown Command: {data_map['cmd']}")

    evt_enum = None
    if "evt" in data_map and data_map["evt"] is not None:
        try:
            evt_enum = RPCEvent(data_map["evt"])
        except ValueError:
            log.warning(f"Unknown Event: {data_map['evt']}")

    parsed_data = data_map.get("data")

    if isinstance(parsed_data, dict):
        expected_type = EVENT_DATA_REGISTRY.get(evt_enum) or CMD_DATA_REGISTRY.get(
            cmd_enum
        )

        if expected_type:
            try:
                if hasattr(expected_type, "from_dict"):
                    parsed_data = expected_type.from_dict(parsed_data)
                else:
                    parsed_data = expected_type(**parsed_data)
            except (TypeError, KeyError, ValueError) as e:
                raise ValidationError(
                    f"Data did not match expectation {expected_type.__name__}: {e}"
                )

    return RPCFrame(
        cmd=cmd_enum,
        nonce=data_map.get("nonce"),
        evt=evt_enum,
        data=parsed_data,
        args=data_map.get("args"),
    )


class DataclassEncoder(json.JSONEncoder):
    """Turns validated types back into JSON"""

    def default(self, o):
        if is_dataclass(o):
            return asdict(o)
        return super().default(o)
