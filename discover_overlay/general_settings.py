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
# pylint: disable=wrong-import-position
from gi.repository import Gtk


class GeneralSettingsWindow(SettingsWindow):
    """Core Settings Tab"""

    def __init__(self, overlay, overlay2):
        SettingsWindow.__init__(self)
        self.overlay = overlay
        self.overlay2 = overlay2
        self.xshape = None
        self.autostart = None
        self.set_size_request(400, 200)
        self.connect("destroy", self.close_window)
        self.connect("delete-event", self.close_window)
        self.init_config()
        self.a = Autostart("discover_overlay")
        self.placement_window = None

        self.create_gui()

    def read_config(self):
        config = ConfigParser(interpolation=None)
        config.read(self.configFile)
        self.xshape = config.getboolean("general", "xshape", fallback=False)

        # Pass all of our config over to the overlay
        self.overlay.set_force_xshape(self.xshape)
        self.overlay2.set_force_xshape(self.xshape)

    def save_config(self):
        config = ConfigParser(interpolation=None)
        config.read(self.configFile)
        if not config.has_section("general"):
            config.add_section("general")

        config.set("general", "xshape", "%d" % (int(self.xshape)))

        with open(self.configFile, 'w') as file:
            config.write(file)

    def create_gui(self):
        box = Gtk.Grid()

        # Auto start
        autostart_label = Gtk.Label.new("Autostart on boot")
        autostart = Gtk.CheckButton.new()
        autostart.set_active(self.a.is_auto())
        autostart.connect("toggled", self.change_autostart)

        # Force XShape
        xshape_label = Gtk.Label.new("Force XShape")
        xshape = Gtk.CheckButton.new()
        xshape.set_active(self.xshape)
        xshape.connect("toggled", self.change_xshape)

        box.attach(autostart_label, 0, 0, 1, 1)
        box.attach(autostart, 1, 0, 1, 1)
        box.attach(xshape_label, 0, 1, 1, 1)
        box.attach(xshape, 1, 1, 1, 1)

        self.add(box)

    def change_autostart(self, button):
        self.autostart = button.get_active()
        self.a.set_autostart(self.autostart)

    def change_xshape(self, button):
        self.overlay.set_force_xshape(button.get_active())
        self.overlay2.set_force_xshape(button.get_active())
        self.xshape = button.get_active()
        self.save_config()
