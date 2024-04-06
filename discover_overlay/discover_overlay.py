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
import time
import sys
import re
import traceback
import logging
import pkg_resources
import json
import signal
import gi
from configparser import ConfigParser

from .settings_window import MainSettingsWindow
from .voice_overlay import VoiceOverlayWindow
from .text_overlay import TextOverlayWindow
from .notification_overlay import NotificationOverlayWindow
from .discord_connector import DiscordConnector
from .audio_assist import DiscoverAudioAssist

gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Gtk, GLib, Gio, Gdk  # nopep8

try:
    from xdg.BaseDirectory import xdg_config_home
except ModuleNotFoundError:
    from xdg import XDG_CONFIG_HOME as xdg_config_home

log = logging.getLogger(__name__)
t = gettext.translation(
    'default', pkg_resources.resource_filename('discover_overlay', 'locales'), fallback=True)
_ = t.gettext


class Discover:
    """Main application class"""

    def __init__(self, rpc_file, config_file, channel_file, debug_file, args):
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

        self.do_args(args, True)
        if "GAMESCOPE_WAYLAND_DISPLAY" in os.environ:
            log.info(
                "GameScope session detected. Enabling steam and gamescope integration")
            self.steamos = True
            self.show_settings_delay = True
            self.mix_settings = True
            settings = Gtk.Settings.get_default()
            if settings:
                settings.set_property(
                    "gtk-application-prefer-dark-theme", Gtk.true)

        self.create_gui()

        self.connection = DiscordConnector(self)

        self.connection.connect()
        self.audio_assist = DiscoverAudioAssist(self)

        rpc_file = Gio.File.new_for_path(rpc_file)
        monitor = rpc_file.monitor_file(0, None)
        monitor.connect("changed", self.rpc_changed)

        config_file = Gio.File.new_for_path(config_file)
        monitor_config = config_file.monitor_file(0, None)
        monitor_config.connect("changed", self.config_changed)

        self.config_changed()

        Gtk.main()

    def do_args(self, data, normal_close):
        """
        Read in arg list from command or RPC and act accordingly
        """
        if "--help" in data or "-h" in data:
            print("%s: discover-overlay [OPTIONS]... " % (_("Usage")))
            print(_("Show an X11 or wlroots overlay with information"))
            print(_("from Discord client"))
            print("")
            print("  -c, --configure        ", _("Open configuration window"))
            print("  -x, --close            ",
                  _("Close currently running instance"))
            print("  -v, --debug            ",
                  _("Verbose output for aid in debugging"))
            print("  -h, --help             ", _("This screen"))
            print("      --hide             ", _("Hide overlay"))
            print("      --show             ", _("Show overlay"))
            print("      --rpc              ",
                  _("Send command, not start new instance."))
            print("      --mute             ", _("Set own user to mute"))
            print("      --unmute           ", _("Set unmuted"))
            print("      --deaf             ", _("Set own user to deafened"))
            print("      --undeaf           ", _("Unset user deafened state"))
            print("      --moveto=XX        ",
                  _("Move the user into voice room, by Room ID"))
            print("      --minimized        ",
                  _("If tray icon is enabled, start with only tray icon and no configuration window"))
            print("")
            print(_("For gamescope compatibility ensure ENV has 'GDK_BACKEND=x11'"))
            if normal_close:
                sys.exit(0)
        if "--close" in data or "-x" in data:
            sys.exit(0)
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

    def config_set(self, context, key, value):
        config = self.config()
        if not context in config.sections():
            config.add_section(context)
        config.set(context, key, value)
        with open(self.config_file, 'w') as file:
            config.write(file)

    def config(self):
        config = ConfigParser(interpolation=None)
        config.read(self.config_file)
        return config

    def rpc_changed(self, _a=None, _b=None, _c=None, _d=None):
        """
        Called when the RPC file has been altered
        """
        with open(self.rpc_file, "r") as tfile:
            data = tfile.readlines()
            if len(data) >= 1:
                self.do_args(data[0].strip().split(" "), False)

    def config_changed(self, _a=None, _b=None, _c=None, _d=None):
        """
        Called when the config file has been altered
        """
        # Read new config
        config = self.config()

        # Set Voice overlay options
        self.voice_overlay.set_align_x(config.getboolean(
            "main", "rightalign", fallback=False))
        self.voice_overlay.set_align_y(
            config.getint("main", "topalign", fallback=1))
        self.voice_overlay.set_bg(json.loads(config.get(
            "main", "bg_col", fallback="[0.0,0.0,0.0,0.5]")))
        self.voice_overlay.set_fg(json.loads(config.get(
            "main", "fg_col", fallback="[1.0,1.0,1.0,1.0]")))
        self.voice_overlay.set_fg_hi(json.loads(config.get(
            "main", "fg_hi_col", fallback="[1.0,1.0,1.0,1.0]")))
        self.voice_overlay.set_tk(json.loads(config.get(
            "main", "tk_col", fallback="[0.0,0.7,0.0,1.0]")))
        self.voice_overlay.set_mt(json.loads(config.get(
            "main", "mt_col", fallback="[0.6,0.0,0.0,1.0]")))
        self.voice_overlay.set_mute_bg(json.loads(config.get(
            "main", "mt_bg_col", fallback="[0.0,0.0,0.0,0.5]")))
        self.voice_overlay.set_hi(json.loads(config.get(
            "main", "hi_col", fallback="[0.0,0.0,0.0,0.5]")))
        self.voice_overlay.set_bo(json.loads(config.get(
            "main", "bo_col", fallback="[0.0,0.0,0.0,0.0]")))
        self.voice_overlay.set_avatar_bg_col(json.loads(config.get(
            "main", "avatar_bg_col", fallback="[0.0,0.0,0.0,0.0]")))
        self.voice_overlay.set_avatar_size(
            config.getint("main", "avatar_size", fallback=48))
        self.voice_overlay.set_nick_length(
            config.getint("main", "nick_length", fallback=32))
        self.voice_overlay.set_icon_spacing(
            config.getint("main", "icon_spacing", fallback=8))
        self.voice_overlay.set_text_padding(
            config.getint("main", "text_padding", fallback=6))
        self.voice_overlay.set_text_baseline_adj(config.getint(
            "main", "text_baseline_adj", fallback=0))
        font = config.get("main", "font", fallback=None)
        title_font = config.get("main", "title_font", fallback=None)
        self.voice_overlay.set_square_avatar(config.getboolean(
            "main", "square_avatar", fallback=True))
        self.voice_overlay.set_only_speaking(config.getboolean(
            "main", "only_speaking", fallback=False))
        self.voice_overlay.set_only_speaking_grace_period(config.getint(
            "main", "only_speaking_grace", fallback=0))
        self.voice_overlay.set_highlight_self(config.getboolean(
            "main", "highlight_self", fallback=False))
        self.voice_overlay.set_icon_only(config.getboolean(
            "main", "icon_only", fallback=False))
        monitor = 0
        try:
            monitor = config.getint("main", "monitor", fallback=0)
        except:
            pass
        self.voice_overlay.set_vert_edge_padding(config.getint(
            "main", "vert_edge_padding", fallback=0))
        self.voice_overlay.set_horz_edge_padding(config.getint(
            "main", "horz_edge_padding", fallback=0))
        floating = config.getboolean("main", "floating", fallback=False)
        floating_x = config.getfloat("main", "floating_x", fallback=0.0)
        floating_y = config.getfloat("main", "floating_y", fallback=0.0)
        floating_w = config.getfloat("main", "floating_w", fallback=0.1)
        floating_h = config.getfloat("main", "floating_h", fallback=0.1)
        self.voice_overlay.set_order(
            config.getint("main", "order", fallback=0))
        self.voice_overlay.set_hide_on_mouseover(
            config.getboolean("main", "autohide", fallback=False))
        self.voice_overlay.set_mouseover_timer(
            config.getint("main", "autohide_timer", fallback=1))

        self.voice_overlay.set_horizontal(config.getboolean(
            "main", "horizontal", fallback=False))
        self.voice_overlay.set_guild_ids(self.parse_guild_ids(
            config.get("main", "guild_ids", fallback="")))
        self.voice_overlay.set_overflow(
            config.getint("main", "overflow", fallback=0))
        self.voice_overlay.set_show_connection(config.getboolean(
            "main", "show_connection", fallback=False))
        self.voice_overlay.set_show_title(config.getboolean(
            "main", "show_title", fallback=False))
        self.voice_overlay.set_show_disconnected(config.getboolean(
            "main", "show_disconnected", fallback=False))
        self.voice_overlay.set_border_width(
            config.getint("main", "border_width", fallback=2))
        self.voice_overlay.set_icon_transparency(config.getfloat(
            "main", "icon_transparency", fallback=1.0))
        self.voice_overlay.set_show_avatar(
            config.getboolean("main", "show_avatar", fallback=True))
        self.voice_overlay.set_fancy_border(config.getboolean("main",
                                                              "fancy_border", fallback=True))
        self.voice_overlay.set_show_dummy(config.getboolean("main",
                                                            "show_dummy", fallback=False))
        self.voice_overlay.set_dummy_count(config.getint("main",
                                                         "dummy_count", fallback=10))

        self.voice_overlay.set_monitor(monitor)

        self.voice_overlay.set_enabled(True)

        self.voice_overlay.set_floating(
            floating, floating_x, floating_y, floating_w, floating_h)

        if font:
            self.voice_overlay.set_font(font)
        if title_font:
            self.voice_overlay.set_title_font(title_font)

        self.voice_overlay.set_fade_out_inactive(
            config.getboolean("main", "fade_out_inactive", fallback=False),
            config.getint("main", "inactive_time", fallback=10),
            config.getint("main", "inactive_fade_time", fallback=30),
            config.getfloat("main", "fade_out_limit", fallback=0.3)
        )

        # Set Text overlay options
        self.text_overlay.set_enabled(config.getboolean(
            "text", "enabled", fallback=False))
        self.text_overlay.set_align_x(config.getboolean(
            "text", "rightalign", fallback=True))
        self.text_overlay.set_align_y(
            config.getint("text", "topalign", fallback=2))
        monitor = 0
        try:
            monitor = config.getint("text", "monitor", fallback=0)
        except:
            pass
        floating = config.getboolean("text", "floating", fallback=True)
        floating_x = config.getfloat("text", "floating_x", fallback=0.0)
        floating_y = config.getfloat("text", "floating_y", fallback=0.0)
        floating_w = config.getfloat("text", "floating_w", fallback=0.1)
        floating_h = config.getfloat("text", "floating_h", fallback=0.1)

        channel = config.get("text", "channel", fallback="0")
        guild = config.get("text", "guild", fallback="0")
        self.connection.set_text_channel(channel, guild)

        self.font = config.get("text", "font", fallback=None)
        self.text_overlay.set_bg(json.loads(config.get(
            "text", "bg_col", fallback="[0.0,0.0,0.0,0.5]")))
        self.text_overlay.set_fg(json.loads(config.get(
            "text", "fg_col", fallback="[1.0,1.0,1.0,1.0]")))
        self.text_overlay.set_popup_style(config.getboolean(
            "text", "popup_style", fallback=False))
        self.text_overlay.set_text_time(
            config.getint("text", "text_time", fallback=30))
        self.text_overlay.set_show_attach(config.getboolean(
            "text", "show_attach", fallback=True))
        self.text_overlay.set_line_limit(
            config.getint("text", "line_limit", fallback=20))
        self.text_overlay.set_hide_on_mouseover(
            config.getboolean("text", "autohide", fallback=False))
        self.text_overlay.set_mouseover_timer(
            config.getint("text", "autohide_timer", fallback=1))

        self.text_overlay.set_monitor(monitor)
        self.text_overlay.set_floating(
            floating, floating_x, floating_y, floating_w, floating_h)

        if self.font:
            self.text_overlay.set_font(self.font)

        # Set Notification overlay options
        self.notification_overlay.set_enabled(config.getboolean(
            "notification", "enabled", fallback=False))
        self.notification_overlay.set_align_x(config.getboolean(
            "notification", "rightalign", fallback=True))
        self.notification_overlay.set_align_y(
            config.getint("notification", "topalign", fallback=2))
        monitor = 0
        try:
            monitor = config.getint("notification", "monitor", fallback=0)
        except:
            pass
        floating = config.getboolean(
            "notification", "floating", fallback=False)
        floating_x = config.getfloat(
            "notification", "floating_x", fallback=0.0)
        floating_y = config.getfloat(
            "notification", "floating_y", fallback=0.0)
        floating_w = config.getfloat(
            "notification", "floating_w", fallback=0.1)
        floating_h = config.getfloat(
            "notification", "floating_h", fallback=0.1)
        font = config.get("notification", "font", fallback=None)
        self.notification_overlay.set_bg(json.loads(config.get(
            "notification", "bg_col", fallback="[0.0,0.0,0.0,0.5]")))
        self.notification_overlay.set_fg(json.loads(config.get(
            "notification", "fg_col", fallback="[1.0,1.0,1.0,1.0]")))
        self.notification_overlay.set_text_time(config.getint(
            "notification", "text_time", fallback=10))
        self.notification_overlay.set_show_icon(config.getboolean(
            "notification", "show_icon", fallback=True))
        self.notification_overlay.set_reverse_order(config.getboolean(
            "notification", "rev", fallback=False))
        self.notification_overlay.set_limit_width(config.getint(
            "notification", "limit_width", fallback=400))
        self.notification_overlay.set_icon_left(config.getboolean(
            "notification", "icon_left", fallback=True))
        self.notification_overlay.set_icon_pad(config.getint(
            "notification", "icon_padding", fallback=8))
        self.notification_overlay.set_icon_size(config.getint(
            "notification", "icon_size", fallback=32))
        self.notification_overlay.set_padding(config.getint(
            "notification", "padding", fallback=8))
        self.notification_overlay.set_border_radius(config.getint(
            "notification", "border_radius", fallback=8))
        self.notification_overlay.set_testing(config.getboolean(
            "notification", "show_dummy", fallback=False))
        self.font = config.get("notification", "font", fallback=None)

        if self.font:
            self.notification_overlay.set_font(self.font)

        self.notification_overlay.set_monitor(monitor)
        self.notification_overlay.set_floating(
            floating, floating_x, floating_y, floating_w, floating_h)
        if self.font:
            self.notification_overlay.set_font(self.font)

        # Set Core settings
        self.set_force_xshape(
            config.getboolean("general", "xshape", fallback=False))

        hidden = config.getboolean("general", "hideoverlay", fallback=False)
        self.voice_overlay.set_hidden(hidden)
        self.text_overlay.set_hidden(hidden)
        self.notification_overlay.set_hidden(hidden)

        self.audio_assist.set_enabled(config.getboolean(
            "general", "audio_assist", fallback=False))

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
        self.voice_overlay = VoiceOverlayWindow(self)

        if self.steamos:
            self.text_overlay = TextOverlayWindow(self, self.voice_overlay)
            self.notification_overlay = NotificationOverlayWindow(
                self, self.text_overlay)
        else:
            self.text_overlay = TextOverlayWindow(self)
            self.notification_overlay = NotificationOverlayWindow(self)

        if self.mix_settings:
            MainSettingsWindow(
                self.config_file, self.rpc_file, self.channel_file, [])

    def toggle_show(self, _obj=None):
        if self.voice_overlay:
            hide = not self.voice_overlay.hidden
            self.voice_overlay.set_hidden(hide)
            if self.text_overlay:
                self.text_overlay.set_hidden(hide)
            if self.notification_overlay:
                self.notification_overlay.set_hidden(hide)

    def close(self, _a=None, _b=None, _c=None):
        """
        End of the program
        """
        Gtk.main_quit()

    def set_force_xshape(self, force):
        """
        Set if XShape should be forced
        """
        self.voice_overlay.set_force_xshape(force)
        if self.text_overlay:
            self.text_overlay.set_force_xshape(force)
        if self.notification_overlay:
            self.notification_overlay.set_force_xshape(force)

    def set_show_task(self, visible):
        if self.voice_overlay:
            self.voice_overlay.set_task(visible)
        if self.text_overlay:
            self.text_overlay.set_task(visible)
        if self.notification_overlay:
            self.notification_overlay.set_task(visible)

    def set_mute_async(self, mute):
        if mute != None:
            GLib.idle_add(self.connection.set_mute, mute)

    def set_deaf_async(self, deaf):
        if deaf != None:
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
    FORMAT = "%(levelname)s - %(name)s - %(message)s"
    if "--debug" in sys.argv or "-v" in sys.argv:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.basicConfig(filename=debug_file, format=FORMAT)
    else:
        logging.basicConfig(format=FORMAT)
    log = logging.getLogger(__name__)
    log.info("Starting Discover Overlay: %s",
             pkg_resources.get_distribution('discover_overlay').version)

    # Hedge against the bet gamescope ships with some WAYLAND_DISPLAY
    # Compatibility and we're not ready yet
    if 'GAMESCOPE_WAYLAND_DISPLAY' in os.environ:
        os.unsetenv("WAYLAND_DISPLAY")

    # Catch any errors and log them
    try:
        if "--rpc" in sys.argv:
            # Send command to overlay
            line = ""
            for arg in sys.argv[1:]:
                line = "%s %s" % (line, arg)
            with open(rpc_file, "w") as tfile:
                tfile.write(line)
                log.warning("Sent RPC command")
        else:
            if "-c" in sys.argv or "--configure" in sys.argv:
                # Show config window
                settings = MainSettingsWindow(
                    config_file, rpc_file, channel_file, sys.argv[1:])
                Gtk.main()
            else:
                # Tell any other running overlay to close
                with open(rpc_file, "w") as tfile:
                    tfile.write("--close")
                # Show the overlay
                Discover(rpc_file, config_file, channel_file,
                         debug_file, sys.argv[1:])
        return

    except Exception as ex:
        log.error(ex)
        log.error(traceback.format_exc())
        sys.exit(1)
