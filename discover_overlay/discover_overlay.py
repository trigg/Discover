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

    def __init__(self, rpc_file, args):
        self.ind = None
        self.tray = None

        self.create_gui()
        self.connection = DiscordConnector(
            self.settings.text_settings, self.settings.voice_settings,
            self.text_overlay, self.voice_overlay)
        self.settings.text_settings.add_connector(self.connection)
        self.connection.connect()
        GLib.timeout_add((1000 / 60), self.connection.do_read)
        self.rpc_file = rpc_file
        rpc_file = Gio.File.new_for_path(rpc_file)
        monitor = rpc_file.monitor_file(0, None)
        monitor.connect("changed", self.rpc_changed)
        self.do_args(args)

        Gtk.main()

    def do_args(self, data):
        if "--help" in data:
            pass
        elif "--about" in data:
            pass
        elif "--configure" in data:
            self.show_settings()
        elif "--close" in data:
            sys.exit(0)

    def rpc_changed(self, _a=None, _b=None, _c=None, _d=None):
        with open(self.rpc_file, "r") as tfile:
            data = tfile.readlines()
            if len(data) >= 1:
                self.do_args(data[0])

    def create_gui(self):
        self.voice_overlay = VoiceOverlayWindow(self)
        self.text_overlay = TextOverlayWindow(self)
        self.menu = self.make_menu()
        self.make_sys_tray_icon(self.menu)
        self.settings = MainSettingsWindow(
            self.text_overlay, self.voice_overlay)

    def make_sys_tray_icon(self, menu):
        # Create AppIndicator
        try:
            gi.require_version('AppIndicator3', '0.1')
            # pylint: disable=import-outside-toplevel
            from gi.repository import AppIndicator3
            self.ind = AppIndicator3.Indicator.new(
                "discover_overlay",
                "discover-overlay",
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
            self.ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self.ind.set_menu(menu)
        except (ImportError, ValueError) as exception:
            # Create System Tray
            logging.info("Falling back to Systray : %s", exception)
            self.tray = Gtk.StatusIcon.new_from_icon_name("discover-overlay")
            self.tray.connect('popup-menu', self.show_menu)

    def make_menu(self):
        # Create System Menu
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
        self.menu.show_all()
        self.menu.popup(
            None, None, Gtk.StatusIcon.position_menu, obj, button, time)

    def show_settings(self, _obj=None, _data=None):
        self.settings.present_settings()

    def close(self, _a=None, _b=None, _c=None):
        Gtk.main_quit()


def entrypoint():
    configDir = os.path.join(xdg_config_home, "discover_overlay")
    os.makedirs(configDir, exist_ok=True)
    line = ""
    for arg in sys.argv[1:]:
        line = "%s %s" % (line, arg)
    pid_file = os.path.join(configDir, "discover_overlay.pid")
    rpc_file = os.path.join(configDir, "discover_overlay.rpc")
    try:
        with pidfile.PIDFile(pid_file):
            logging.getLogger().setLevel(logging.INFO)
            Discover(rpc_file, line)
    except pidfile.AlreadyRunningError:
        logging.warning("Discover overlay is currently running")

        with open(rpc_file, "w") as tfile:
            tfile.write(line)
            logging.warning("Sent RPC command")
