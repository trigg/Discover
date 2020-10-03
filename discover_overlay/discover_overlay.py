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
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
import select
from .voice_settings import VoiceSettingsWindow
from .text_settings import TextSettingsWindow
from .voice_overlay import VoiceOverlayWindow
from .text_overlay import TextOverlayWindow
from .discord_connector import DiscordConnector
from .autostart import Autostart
import logging


class Discover:
    def __init__(self):
        self.a = Autostart("discover_overlay")
        # a.set_autostart(True)
        self.create_gui()
        self.connection = DiscordConnector(
            self.text_settings, self.voice_settings,
            self.text_overlay, self.voice_overlay)
        self.connection.connect()
        GLib.timeout_add((1000 / 60), self.connection.do_read)

        try:
            Gtk.main()
        except:
            pass

    def create_gui(self):
        self.voice_overlay = VoiceOverlayWindow(self)
        self.text_overlay = TextOverlayWindow(self)
        self.menu = self.make_menu()
        self.make_sys_tray_icon(self.menu)
        self.voice_settings = VoiceSettingsWindow(self.voice_overlay)
        self.text_settings = TextSettingsWindow(self.text_overlay)

    def make_sys_tray_icon(self, menu):
        # Create AppIndicator
        try:
            gi.require_version('AppIndicator3', '0.1')
            from gi.repository import AppIndicator3
            self.ind = AppIndicator3.Indicator.new(
                "discover_overlay",
                "discover-overlay",
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
            self.ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self.ind.set_menu(menu)
        except Exception as e:
            # Create System Tray
            logging.info("Falling back to Systray : %s" % (e))
            self.tray = Gtk.StatusIcon.new_from_icon_name("discover_overlay")
            self.tray.connect('popup-menu', self.show_menu)

    def make_menu(self):
        # Create System Menu
        menu = Gtk.Menu()
        vsettings_opt = Gtk.MenuItem.new_with_label("Voice Settings")
        tsettings_opt = Gtk.MenuItem.new_with_label("Text Settings")
        autostart_opt = Gtk.CheckMenuItem("Start on boot")
        autostart_opt.set_active(self.a.is_auto())
        close_opt = Gtk.MenuItem.new_with_label("Close")

        menu.append(vsettings_opt)
        menu.append(tsettings_opt)
        menu.append(autostart_opt)
        menu.append(close_opt)

        vsettings_opt.connect("activate", self.show_vsettings)
        tsettings_opt.connect("activate", self.show_tsettings)
        autostart_opt.connect("toggled", self.toggle_auto)
        close_opt.connect("activate", self.close)
        menu.show_all()
        return menu

    def toggle_auto(self, button):
        self.a.set_autostart(button.get_active())

    def show_menu(self, obj, button, time):
        self.menu.show_all()
        self.menu.popup(
            None, None, Gtk.StatusIcon.position_menu, obj, button, time)

    def show_vsettings(self, obj=None, data=None):
        self.voice_settings.present()

    def show_tsettings(self, obj=None, data=None):
        self.text_settings.present()

    def close(self, a=None, b=None, c=None):
        Gtk.main_quit()


def entrypoint():
    logging.getLogger().setLevel(logging.INFO)
    discover = Discover()
