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
import time
import sys
try:
    # pylint: disable=wrong-import-position,wrong-import-order
    import dbus # nopep8
    # pylint: disable=wrong-import-position,wrong-import-order
    from dbus.mainloop.glib import DBusGMainLoop # nopep8
except:
    dbus=None
    pass
import logging
import gi
import pidfile
from .settings_window import MainSettingsWindow
from .voice_overlay import VoiceOverlayWindow
from .text_overlay import TextOverlayWindow
from .notification_overlay import NotificationOverlayWindow
from .discord_connector import DiscordConnector

gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Gtk, GLib, Gio  # nopep8

try:
    from xdg.BaseDirectory import xdg_config_home
except ModuleNotFoundError:
    from xdg import XDG_CONFIG_HOME as xdg_config_home

log = logging.getLogger(__name__)

class Discover:
    """Main application class"""

    def __init__(self, rpc_file, debug_file, args):
        self.ind = None
        self.tray = None
        self.steamos = False
        self.connection = None
        self.show_settings_delay = False
        self.settings = None
        self.notification_messages = []
        self.dbus_notification = None
        self.bus = None

        self.debug_file = debug_file

        self.do_args(args, True)
        if "GAMESCOPE_WAYLAND_DISPLAY" in os.environ:
            log.info(
                "GameScope session detected. Enabling steam and gamescope integration")
            self.steamos = True
            self.show_settings_delay = True
            settings = Gtk.Settings.get_default()
            if settings:
                settings.set_property(
                    "gtk-application-prefer-dark-theme", Gtk.true)

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
        GLib.timeout_add((1000 / 20), self.periodic_run)
        self.rpc_file = rpc_file
        rpc_file = Gio.File.new_for_path(rpc_file)
        monitor = rpc_file.monitor_file(0, None)
        monitor.connect("changed", self.rpc_changed)

        Gtk.main()
    
    def set_about_warning(self, message):
        self.settings.about_settings.set_warning(message)

    def set_dbus_notifications(self, enabled=False):
        if not dbus:
            return
        if not self.bus:
            DBusGMainLoop(set_as_default=True)
            self.bus = dbus.SessionBus()
            self.bus.add_match_string_non_blocking(
                "eavesdrop=true, interface='org.freedesktop.Notifications', member='Notify'")
        if enabled:
            if not self.dbus_notification:
                self.bus.add_message_filter(self.add_notification_message)
                self.dbus_notification = True

    def periodic_run(self, data=None):
        if self.voice_overlay.needsredraw:
            self.voice_overlay.redraw()

        if self.text_overlay and self.text_overlay.needsredraw:
            self.text_overlay.redraw()

        if self.notification_overlay and dbus:
            if self.notification_overlay.enabled:
                # This doesn't really belong in overlay or settings
                now = time.time()
                newlist = []
                oldsize = len(self.notification_messages)
                # Iterate over and remove messages older than 30s
                for message in self.notification_messages:
                    if message['time'] + self.settings.notification_settings.text_time > now:
                        newlist.append(message)
                self.notification_messages = newlist
                # If the list is different than before
                if oldsize != len(newlist):
                    self.notification_overlay.set_content(
                        self.notification_messages, True)
            if self.notification_overlay.needsredraw:
                self.notification_overlay.redraw()
        return True

    def add_notification_message(self, bus, message):
        args = message.get_args_list()
        noti = {"title": "%s" % (args[3]), "body": "%s" % (args[4]),
                "icon": "%s" % (args[2]), "cmd": "%s" % (args[0]), "time": time.time()}
        if len(args) > 6:
            dictionary = args[6]
            if 'image-data' in dictionary:
                noti['icon_raw'] = dictionary['image-data']
            elif 'image_data' in dictionary:
                noti['icon_raw'] = dictionary['image_data']
        self.notification_messages.append(noti)
        self.notification_overlay.set_content(self.notification_messages, True)

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
            print("      --rpc              Send command, not start new instance. Only needed if running in flatpak")
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
            self.steamos = True
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
        self.voice_overlay = VoiceOverlayWindow(self)

        if self.steamos:
            self.text_overlay = TextOverlayWindow(self, self.voice_overlay)
            self.notification_overlay = NotificationOverlayWindow(
                self, self.text_overlay)
        else:
            self.text_overlay = TextOverlayWindow(self)
            self.notification_overlay = NotificationOverlayWindow(self)
        self.menu = self.make_menu()
        self.make_sys_tray_icon(self.menu)
        self.settings = MainSettingsWindow(self)

        if self.steamos:
            # Larger fonts needed
            css = Gtk.CssProvider.new()
            css.load_from_data(bytes("* { font-size:20px; }", "utf-8"))
            self.settings.get_style_context().add_provider(
                css, Gtk.STYLE_PROVIDER_PRIORITY_USER)

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
            log.info("Falling back to Systray : %s", exception)
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

    def hide_settings(self, _obj=None, _data=None):
        """
        Hide settings window
        """
        self.settings.close_window()

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

    def set_show_task(self, visible):
        if self.voice_overlay:
            self.voice_overlay.set_task(visible)
        if self.text_overlay:
            self.text_overlay.set_task(visible)

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
    if "--debug" in line or "-v" in line:
        logging.getLogger().setLevel(0)
        logging.basicConfig(filename=debug_file)

    # Flatpak compat mode
    try:
        if "container" in os.environ and os.environ["container"] == "flatpak":
            if "--rpc" in sys.argv:
                with open(rpc_file, "w") as tfile:
                    tfile.write(line)
                    log.warning("Sent RPC command")
            else:
                logging.getLogger().setLevel(logging.INFO)
                log.info("Flatpak compat mode started")
                Discover(rpc_file, debug_file, line)
            return

        # Normal usage

        try:
            with pidfile.PIDFile(pid_file):
                logging.getLogger().setLevel(logging.INFO)
                Discover(rpc_file, debug_file, line)
        except pidfile.AlreadyRunningError:
            log.warning("Discover overlay is currently running")

            with open(rpc_file, "w") as tfile:
                tfile.write(line)
                log.warning("Sent RPC command")
    except Exception as ex:
        log.error(ex)
        sys.exit(1)
