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
"""Main application class"""

import gettext
import os
import sys
import re
import traceback
import logging
import signal
import importlib_resources
from configparser import ConfigParser, RawConfigParser
from ctypes import CDLL
from _version import __version__

CDLL("libgtk4-layer-shell.so")

import gi

from .overlay import OverlayWindow
from .settings_window import Settings
from .voice_overlay import VoiceOverlayWindow
from .text_overlay import TextOverlayWindow
from .notification_overlay import NotificationOverlayWindow
from .discord_connector import DiscordConnector
from .audio_assist import DiscoverAudioAssist

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gio

try:
    from xdg.BaseDirectory import xdg_config_home
except ModuleNotFoundError:
    from xdg import XDG_CONFIG_HOME as xdg_config_home

log = logging.getLogger(__name__)
with importlib_resources.as_file(
    importlib_resources.files("discover_overlay") / "locales"
) as path:
    t = gettext.translation(
        "default",
        path,
        fallback=True,
    )
    _ = t.gettext


class Discover:
    """Main application class"""

    def __init__(self, rpc_file, config_file, channel_file, debug_file, args):
        unsupported_desktops = ["gnome", "weston", "gamescope"]
        if os.getenv("XDG_SESSION_DESKTOP", "none").lower() in unsupported_desktops:
            log.warning(
                "GTK Layer Shell is not supported on this Wayland compositor. Removing WAYLAND_DISPLAY to fallback to X11"
            )
            os.unsetenv("WAYLAND_DISPLAY")
        # pylint: disable=E1120
        Gtk.init()
        self.mix_settings = False
        self.ind = None
        self.tray = None
        self.steamos = False
        self.connection = None
        self.show_settings_delay = False
        self.settings = None

        self.debug_file = debug_file
        self.channel_file = channel_file
        self.config_file = config_file
        self.rpc_file = rpc_file
        self.skip_config_read = False

        self.do_args(args, True)
        if "GAMESCOPE_WAYLAND_DISPLAY" in os.environ:
            log.info(
                "GameScope session detected. Enabling steam and gamescope integration"
            )
            self.steamos = True
            self.show_settings_delay = True
            self.mix_settings = True

            # pylint: disable=E1120
            settings = Gtk.Settings.get_default()
            if settings:
                settings.set_property("gtk-application-prefer-dark-theme", True)

        self.create_gui()

        self.connection = DiscordConnector(self)

        self.connection.connect()
        self.audio_assist = DiscoverAudioAssist(self)

        rpc_file_gio = Gio.File.new_for_path(rpc_file)
        monitor = rpc_file_gio.monitor_file(0, None)
        monitor.connect("changed", self.rpc_changed)

        config_file = Gio.File.new_for_path(config_file)
        monitor_config = config_file.monitor_file(0, None)
        monitor_config.connect("changed", self.config_changed)

        self.config_changed()

        # pylint: disable=E1120
        while len(Gtk.Window.get_toplevels()) > 0:
            GLib.MainContext.iteration(GLib.MainContext.default(), True)

    def do_args(self, data, normal_close):
        """
        Read in arg list from command or RPC and act accordingly
        """
        if "--help" in data or "-h" in data:
            print(_("Usage") + ": discover-overlay [OPTIONS]... ")
            print(_("Show an X11 or wlroots overlay with information"))
            print(_("from Discord client"))
            print("")
            print("  -c, --configure        ", _("Open configuration window"))
            print("  -x, --close            ", _("Close currently running instance"))
            print("  -v, --debug            ", _("Verbose output for aid in debugging"))
            print("  -h, --help             ", _("This screen"))
            print("      --hide             ", _("Hide overlay"))
            print("      --show             ", _("Show overlay"))
            print(
                "      --rpc              ", _("Send command, not start new instance.")
            )
            print("      --mute             ", _("Set own user to mute"))
            print("      --unmute           ", _("Set unmuted"))
            print("      --toggle-mute           ", _("Toggle muted"))
            print("      --deaf             ", _("Set own user to deafened"))
            print("      --undeaf           ", _("Unset user deafened state"))
            print("      --toggle-deaf           ", _("Toggle deaf"))
            print(
                "      --moveto=XX        ",
                _("Move the user into voice room, by Room ID"),
            )
            print(
                "      --minimized        ",
                _(
                    "If tray icon is enabled, start with only tray icon and no configuration window"
                ),
            )
            print("")
            print(_("For gamescope compatibility ensure ENV has 'GDK_BACKEND=x11'"))
            if normal_close:
                sys.exit(0)
        if "--close" in data or "-x" in data:
            self.exit()
        if "--steamos" in data or "-s" in data:
            self.steamos = True
        if "--hide" in data:
            self.config_set("general", "hideoverlay", "True")
        if "--show" in data:
            self.config_set("general", "hideoverlay", "False")
        if "--mute" in data:
            if self.connection:
                self.connection.set_mute(True)
        if "--unmute" in data:
            if self.connection:
                self.connection.set_mute(False)
        if "--deaf" in data:
            if self.connection:
                self.connection.set_deaf(True)
        if "--undeaf" in data:
            if self.connection:
                self.connection.set_deaf(False)
        if "--toggle-mute" in data:
            if self.connection:
                self.connection.set_mute(not self.connection.muted)
        if "--toggle-deaf" in data:
            if self.connection:
                self.connection.set_deaf(not self.connection.deafened)
        if "--refresh-guilds" in data:
            if self.connection:
                self.connection.req_guilds()
        pattern = re.compile("--moveto=([0-9]+)")
        if any((match := pattern.match(x)) for x in data):
            if self.connection:
                self.connection.change_voice_room(match.group(1))
        guild_pattern = re.compile("--guild-request=([0-9]+)")
        if any((match := guild_pattern.match(x)) for x in data):
            if self.connection:
                self.connection.request_text_rooms_for_guild(match.group(1))

    def exit(self):
        """Kills self, works from threads"""
        os.kill(os.getpid(), signal.SIGTERM)

    def config_set(self, context, key, value):
        """Set a config value and save to disk. Avoid re-reading automatically"""
        config = self.config()
        self.skip_config_read = True
        if not context in config.sections():
            config.add_section(context)
        config.set(context, key, value)
        with open(self.config_file, "w", encoding="utf-8") as file:
            config.write(file)
        self.skip_config_read = False

    def config(self):
        """Read config from disk"""
        config = ConfigParser(interpolation=None)
        config.read(self.config_file)
        return config

    def rpc_changed(self, _a=None, _b=None, _c=None, _d=None):
        """
        Called when the RPC file has been altered
        """
        with open(self.rpc_file, "r", encoding="utf-8") as tfile:
            data = tfile.readlines()
            if len(data) >= 1:
                self.do_args(data[0].strip().split(" "), False)

    def config_changed(self, _a=None, _b=None, _c=None, _d=None):
        """
        Called when the config file has been altered
        """
        if self.skip_config_read:
            log.warning("Config skipped")
            return
        # Read new config
        config = self.config()

        hidden = config.getboolean("general", "hideoverlay", fallback=False)

        if not config.has_section("main"):
            config["main"] = {}
        voice_section = config["main"]
        if self.voice_overlay_window:
            self.voice_overlay_window.set_config(voice_section)
            self.voice_overlay_window.set_hidden(hidden)
        self.voice_overlay.set_config(voice_section)

        # Set Text overlay options
        if not config.has_section("text"):
            config["text"] = {}
        text_section = config["text"]
        if self.text_overlay_window:
            self.text_overlay_window.set_config(text_section)
            self.text_overlay_window.set_hidden(hidden)
        self.text_overlay.set_config(text_section)

        # Set Notification overlay options
        if not config.has_section("notification"):
            config["notification"] = {}
        notification_section = config["notification"]
        if self.notification_overlay_window:
            self.notification_overlay_window.set_config(notification_section)
            self.notification_overlay_window.set_hidden(hidden)
        self.notification_overlay.set_config(notification_section)

        if self.one_window:
            self.one_window.set_hidden(hidden)

        self.audio_assist.set_enabled(
            config.getboolean("general", "audio_assist", fallback=False)
        )

    def parse_guild_ids(self, guild_ids_str):
        """Parse the guild_ids from a str and return them in a list"""
        guild_ids = []
        for guild_id in guild_ids_str.split(","):
            guild_id = guild_id.strip()
            if guild_id != "":
                guild_ids.append(guild_id)
        return guild_ids

    def create_gui(self):
        """
        Create Systray & associated menu, overlays & settings windows
        """
        self.one_window = self.voice_overlay_window = self.text_overlay_window = (
            self.notification_overlay_window
        ) = None

        if self.steamos:
            self.one_window = OverlayWindow(self)
            self.voice_overlay = VoiceOverlayWindow(self)
            self.text_overlay = TextOverlayWindow(self)
            self.notification_overlay = NotificationOverlayWindow(self)
            self.one_window.merged_overlay(
                [self.voice_overlay, self.text_overlay, self.notification_overlay]
            )
        else:
            self.voice_overlay_window = OverlayWindow(self)
            self.voice_overlay = VoiceOverlayWindow(self)
            self.voice_overlay_window.overlay(self.voice_overlay)

            self.text_overlay_window = OverlayWindow(self)
            self.text_overlay = TextOverlayWindow(self)
            self.text_overlay_window.overlay(self.text_overlay)

            self.notification_overlay_window = OverlayWindow(self)
            self.notification_overlay = NotificationOverlayWindow(self)
            self.notification_overlay_window.overlay(self.notification_overlay)

        if self.mix_settings:
            app = Settings(
                "io.github.trigg.discover_overlay",
                Gio.ApplicationFlags.FLAGS_NONE,
                self.config_file,
                self.rpc_file,
                self.channel_file,
                sys.argv[1:],
            )
            app.connect("activate", app.start)

    def close(self, _a=None, _b=None, _c=None):
        """
        End of the program
        """
        sys.exit()

    def set_mute_async(self, mute):
        """Set mute status from another thread"""
        if mute is not None:
            GLib.idle_add(self.connection.set_mute, mute)

    def set_deaf_async(self, deaf):
        """Set deaf status from another thread"""
        if deaf is not None:
            GLib.idle_add(self.connection.set_deaf, deaf)


def entrypoint():
    """
    Entry Point.

    Find all needed file locations and read args

    if '--rpc' simply pass them over the rpc file

    if '-c' or '--configure' start the config window only

    otherwise start overlay
    """

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    # Find Config directory
    config_dir = os.path.join(xdg_config_home, "discover_overlay")
    os.makedirs(config_dir, exist_ok=True)

    # Find RPC, Channel info, config and debug files
    rpc_file = os.path.join(config_dir, "discover_overlay.rpc")
    channel_file = os.path.join(config_dir, "channels.rpc")
    config_file = os.path.join(config_dir, "config.ini")
    debug_file = os.path.join(config_dir, "output.txt")

    # Prepare logger
    logging.getLogger().setLevel(logging.INFO)
    log_format = "%(levelname)s - %(name)s - %(message)s"
    if "--debug" in sys.argv or "-v" in sys.argv:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.basicConfig(filename=debug_file, format=log_format)
    else:
        logging.basicConfig(format=log_format)
    log.info(
        "Starting Discover Overlay: %s",
        __version__,
    )

    # Hedge against the bet gamescope ships with some WAYLAND_DISPLAY
    # Compatibility and we're not ready yet
    if "GAMESCOPE_WAYLAND_DISPLAY" in os.environ:
        os.environ["GDK_BACKEND"] = "x11"
        os.unsetenv("WAYLAND_DISPLAY")

    # Catch any errors and log them
    try:
        if "--rpc" in sys.argv:
            # Send command to overlay
            line = ""
            for arg in sys.argv[1:]:
                line = f"{line} {arg}"
            with open(rpc_file, "w", encoding="utf-8") as tfile:
                tfile.write(line)
                log.warning("Sent RPC command")
        else:
            if "-c" in sys.argv or "--configure" in sys.argv:
                # Show config window
                app = Settings(
                    "io.github.trigg.discover_overlay",
                    Gio.ApplicationFlags.FLAGS_NONE,
                    config_file,
                    rpc_file,
                    channel_file,
                    sys.argv[1:],
                )
                app.connect("activate", app.start)
                app.run()
            else:
                # Tell any other running overlay to close
                with open(rpc_file, "w", encoding="utf-8") as tfile:
                    tfile.write("--close")
                # Show the overlay
                Discover(rpc_file, config_file, channel_file, debug_file, sys.argv[1:])
        return
    # pylint: disable=W0718
    except Exception as ex:
        log.error(ex)
        log.error(traceback.format_exc())
        sys.exit(1)
