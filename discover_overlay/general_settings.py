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
"""Core Settings Tab"""
from configparser import ConfigParser
import gi
from .settings import SettingsWindow
from .autostart import Autostart
gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Gtk


class GeneralSettingsWindow(SettingsWindow):
    """Core Settings Tab"""

    def __init__(self, discover):
        SettingsWindow.__init__(self)
        self.discover = discover
        self.xshape = None
        self.show_sys_tray_icon = None
        self.set_size_request(400, 200)
        self.connect("destroy", self.close_window)
        self.connect("delete-event", self.close_window)
        self.init_config()
        self.autostart_helper = Autostart("discover_overlay")
        self.placement_window = None

        self.create_gui()

    def read_config(self):
        """
        Read in the 'general' section of config and set overlays
        """
        config = ConfigParser(interpolation=None)
        config.read(self.config_file)
        self.xshape = config.getboolean("general", "xshape", fallback=False)
        self.show_sys_tray_icon = config.getboolean("general", "showsystray", fallback=True)

        # Pass all of our config over to the overlay
        self.discover.set_force_xshape(self.xshape)
        self.discover.set_sys_tray_icon_visible(self.show_sys_tray_icon)

    def save_config(self):
        """
        Save the 'general' section of config
        """
        config = ConfigParser(interpolation=None)
        config.read(self.config_file)
        if not config.has_section("general"):
            config.add_section("general")

        config.set("general", "xshape", "%d" % (int(self.xshape)))
        config.set("general", "showsystray", "yes" if self.show_sys_tray_icon else "no")

        with open(self.config_file, 'w') as file:
            config.write(file)

    def create_gui(self):
        """
        Prepare the GUI
        """
        box = Gtk.Grid()

        # Auto start
        autostart_label = Gtk.Label.new("Autostart on boot")
        autostart = Gtk.CheckButton.new()
        autostart.set_active(self.autostart_helper.is_auto())
        autostart.connect("toggled", self.change_autostart)

        # Force XShape
        xshape_label = Gtk.Label.new("Force XShape")
        xshape = Gtk.CheckButton.new()
        xshape.set_active(self.xshape)
        xshape.connect("toggled", self.change_xshape)

        # Show sys tray
        show_sys_tray_icon_label = Gtk.Label.new("Show tray icon")
        show_sys_tray_icon = Gtk.CheckButton.new()
        show_sys_tray_icon.set_active(self.show_sys_tray_icon)
        show_sys_tray_icon.connect("toggled", self.change_show_sys_tray_icon)

        box.attach(autostart_label, 0, 0, 1, 1)
        box.attach(autostart, 1, 0, 1, 1)
        box.attach(xshape_label, 0, 1, 1, 1)
        box.attach(xshape, 1, 1, 1, 1)
        box.attach(show_sys_tray_icon_label, 0, 2, 1, 1)
        box.attach(show_sys_tray_icon, 1, 2, 1, 1)

        self.add(box)

    def change_autostart(self, button):
        """
        Autostart setting changed
        """
        autostart = button.get_active()
        self.autostart_helper.set_autostart(autostart)

    def change_xshape(self, button):
        """
        XShape setting changed
        """
        self.discover.set_force_xshape(button.get_active())
        self.xshape = button.get_active()
        self.save_config()

    def change_show_sys_tray_icon(self, button):
        """
        Show tray icon setting changed
        """
        self.discover.set_sys_tray_icon_visible(button.get_active())
        self.show_sys_tray_icon = button.get_active()
        self.save_config()
