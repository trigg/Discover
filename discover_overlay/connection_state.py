"""Enum of states of discover connection to discord"""

from enum import Enum


class ConnectionState(Enum):
    """Possible states of service"""

    NO_DISCORD = 0  # We havn't managed to reach Discord on localhost
    DISCORD_INVALID = 1  # Port connection works but turns away RPC.
    NO_VOICE_CHAT = 2  # We're connected but the user is not in a room
    VOICE_CHAT_NOT_CONNECTED = 3  # We've chosen a room but not successfully connected to it yet (or connection has degraded)
    CONNECTED = 4  # Connected and working
