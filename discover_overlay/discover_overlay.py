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
import os
import sys
import logging
import gi
import pidfile
from .settings_window import MainSettingsWindow
from .voice_overlay import VoiceOverlayWindow
from .text_overlay import TextOverlayWindow
from .discord_connector import DiscordConnector
gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Gtk, GLib, Gio

try:
    from xdg.BaseDirectory import xdg_config_home
except ModuleNotFoundError:
    from xdg import XDG_CONFIG_HOME as xdg_config_home


class Discover:
    """Main application class"""

    def __init__(self, rpc_file, debug_file, args):
        self.ind = None
        self.tray = None
        self.steamos = False
        self.show_settings_delay=False
        self.settings = None

        self.debug_file = debug_file

        self.do_args(args, True)
        if "GAMESCOPE_WAYLAND_DISPLAY" in os.environ:
            logging.info("GameScope session detected. Enabling steam and gamescope integration")
            self.steamos = True
            self.show_settings_delay = True
            Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", Gtk.true)

        self.create_gui()

        self.connection = DiscordConnector(
            self,
            self.settings.text_settings,
            self.settings.voice_settings,
            self.text_overlay,
            self.voice_overlay
        )

        self.settings.text_settings.add_connector(self.connection)
        self.connection.connect()
        GLib.timeout_add((1000 / 60), self.connection.do_read)
        self.rpc_file = rpc_file
        rpc_file = Gio.File.new_for_path(rpc_file)
        monitor = rpc_file.monitor_file(0, None)
        monitor.connect("changed", self.rpc_changed)

        Gtk.main()

    def do_args(self, data, normal_close):
        """
        Read in arg list from command or RPC and act accordingly
        """
        if "--help" in data or "-h" in data:
            print("Usage: discover-overlay [OPTIONS]... ")
            print("Show an X11 or wlroots overlay with information")
            print("from Discord client")
            print("")
            print("  -c, --configure        Open configuration window")
            print("  -x, --close            Close currently running instance")
            print("  -v, --debug            Verbose output for aid in debugging")
            print("  -h, --help             This screen")
            print("      --hide             Hide overlay")
            print("      --show             Show overlay")
            print("      --nolock           Do not use Lock or RPC. Helps for running in unpriviledged container")
            print("")
            print("For gamescope compatibility ensure ENV has 'GDK_BACKEND=x11'")
            if normal_close:
                sys.exit(0)
        if "--configure" in data or "-c" in data:
            if self.settings:
                self.show_settings()
            else:
                self.show_settings_delay = True
        if "--close" in data or "-x" in data:
            sys.exit(0)
        if "--steamos" in data or "-s" in data:
            self.steamos=True
        if "--hide" in data:
            if self.voice_overlay:
                self.voice_overlay.set_hidden(True)
            if self.text_overlay:
                self.text_overlay.set_hidden(True)
        if "--show" in data:
            if self.voice_overlay:
                self.voice_overlay.set_hidden(False)
            if self.text_overlay:
                self.text_overlay.set_hidden(False)
        if "--debug" in data or "-v" in data:
            logging.getLogger().setLevel(0)
            logging.basicConfig(filename=self.debug_file)

    def rpc_changed(self, _a=None, _b=None, _c=None, _d=None):
        """
        Called when the RPC file has been altered
        """
        with open(self.rpc_file, "r") as tfile:
            data = tfile.readlines()
            if len(data) >= 1:
                self.do_args(data[0], False)

    def create_gui(self):
        """
        Create Systray & associated menu, overlays & settings windows
        """
        if self.steamos:
            self.text_overlay = None
        else:
            self.text_overlay = TextOverlayWindow(self)
        self.voice_overlay = VoiceOverlayWindow(self)
        self.menu = self.make_menu()
        self.make_sys_tray_icon(self.menu)
        self.settings = MainSettingsWindow(self)

        if self.steamos:
            # Larger fonts needed
            css = Gtk.CssProvider.new()
            css.load_from_data(bytes("* { font-size:20px; }", "utf-8"))
            self.settings.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def make_sys_tray_icon(self, menu):
        """
        Attempt to create an AppIndicator icon, failing that attempt to make
        a systemtray icon
        """
        if self.steamos:
            return
        try:
            gi.require_version('AppIndicator3', '0.1')
            # pylint: disable=import-outside-toplevel
            from gi.repository import AppIndicator3
            self.ind = AppIndicator3.Indicator.new(
                "discover_overlay",
                "discover-overlay-tray",
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
            # Hide for now since we don't know if it should be shown yet
            self.ind.set_status(AppIndicator3.IndicatorStatus.PASSIVE)
            self.ind.set_menu(menu)
        except (ImportError, ValueError) as exception:
            # Create System Tray
            logging.info("Falling back to Systray : %s", exception)
            self.tray = Gtk.StatusIcon.new_from_icon_name(
                "discover-overlay-tray")
            self.tray.connect('popup-menu', self.show_menu)
            # Hide for now since we don't know if it should be shown yet
            self.tray.set_visible(False)

    def make_menu(self):
        """
        Create System Menu
        """
        menu = Gtk.Menu()
        settings_opt = Gtk.MenuItem.new_with_label("Settings")
        close_opt = Gtk.MenuItem.new_with_label("Close")

        menu.append(settings_opt)
        menu.append(close_opt)

        settings_opt.connect("activate", self.show_settings)
        close_opt.connect("activate", self.close)
        menu.show_all()
        return menu

    def show_menu(self, obj, button, time):
        """
        Show menu when System Tray icon is clicked
        """
        self.menu.show_all()
        self.menu.popup(
            None, None, Gtk.StatusIcon.position_menu, obj, button, time)

    def show_settings(self, _obj=None, _data=None):
        """
        Show settings window
        """
        self.settings.present_settings()

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

    def set_sys_tray_icon_visible(self, visible):
        """
        Sets whether the tray icon is visible
        """
        if self.ind is not None:
            # pylint: disable=import-outside-toplevel
            from gi.repository import AppIndicator3
            self.ind.set_status(
                AppIndicator3.IndicatorStatus.ACTIVE if visible else AppIndicator3.IndicatorStatus.PASSIVE)
        elif self.tray is not None:
            self.tray.set_visible(visible)


def entrypoint():
    """
    Entry Point.

    Check for PID & RPC.

    If an overlay is already running then pass the args along and close

    Otherwise start up the overlay!
    """
    config_dir = os.path.join(xdg_config_home, "discover_overlay")
    os.makedirs(config_dir, exist_ok=True)
    line = ""
    for arg in sys.argv[1:]:
        line = "%s %s" % (line, arg)

    pid_file = os.path.join(config_dir, "discover_overlay.pid")
    rpc_file = os.path.join(config_dir, "discover_overlay.rpc")
    debug_file = os.path.join(config_dir, "output.txt")
    if "--nolock" in sys.argv:
        logging.getLogger().setLevel(logging.INFO)
        logging.info("Nolock mode chosen")
        Discover(rpc_file, debug_file, line)
        return
    try:
        with pidfile.PIDFile(pid_file):
            logging.getLogger().setLevel(logging.INFO)
            Discover(rpc_file, debug_file, line)
    except pidfile.AlreadyRunningError:
        logging.warning("Discover overlay is currently running")

        with open(rpc_file, "w") as tfile:
            tfile.write(line)
            logging.warning("Sent RPC command")
