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
t = gettext.translation(
    'default', pkg_resources.resource_filename('discover_overlay', 'locales'))
_ = t.gettext


class Discover:
    """Main application class"""

    def __init__(self, rpc_file, debug_file, args):
        self.ind = None
        self.tray = None
        self.steamos = False
        self.connection = None
        self.show_settings_delay = False
        self.settings = None

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

    def periodic_run(self, data=None):
        if self.voice_overlay.needsredraw:
            self.voice_overlay.redraw()

        if self.text_overlay:
            self.text_overlay.tick()
            if self.text_overlay.needsredraw:
                self.text_overlay.redraw()

        if self.notification_overlay and self.notification_overlay.enabled:
            self.notification_overlay.tick()
            if self.notification_overlay.needsredraw:
                self.notification_overlay.redraw()
        return True

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
                  _("Send command, not start new instance. Only needed if running in flatpak"))
            print("      --mute             ", _("Set own user to mute"))
            print("      --unmute           ", _("Set unmuted"))
            print("      --deaf             ", _("Set own user to deafened"))
            print("      --undeaf           ", _("Unset user deafened state"))
            print("      --moveto=XX        ",
                  _("Move the user into voice room, by Room ID"))
            print("")
            print(_("For gamescope compatibility ensure ENV has 'GDK_BACKEND=x11'"))
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
        pattern = re.compile("--moveto=([0-9]+)")
        if any((match := pattern.match(x)) for x in data):
            if self.connection:
                self.connection.change_voice_room(match.group(1))

    def rpc_changed(self, _a=None, _b=None, _c=None, _d=None):
        """
        Called when the RPC file has been altered
        """
        with open(self.rpc_file, "r") as tfile:
            data = tfile.readlines()
            if len(data) >= 1:
                self.do_args(data[0].split(" "), False)

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
        settings_opt = Gtk.MenuItem.new_with_label(_("Settings"))
        close_opt = Gtk.MenuItem.new_with_label(_("Close"))

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

    # Flatpak compat mode
    try:
        if "container" in os.environ and os.environ["container"] == "flatpak":
            if "--rpc" in sys.argv:
                with open(rpc_file, "w") as tfile:
                    tfile.write(line)
                    log.warning("Sent RPC command")
            else:
                log.info("Flatpak compat mode started")
                with open(rpc_file, "w") as tfile:
                    tfile.write("--close")
                Discover(rpc_file, debug_file, sys.argv[1:])
            return

        # Normal usage

        try:
            with pidfile.PIDFile(pid_file):
                Discover(rpc_file, debug_file, sys.argv[1:])
        except pidfile.AlreadyRunningError:
            log.warning("Discover overlay is currently running")

            with open(rpc_file, "w") as tfile:
                tfile.write(line)
                log.warning("Sent RPC command")
    except Exception as ex:
        log.error(ex)
        log.error(traceback.format_exc())
        sys.exit(1)
