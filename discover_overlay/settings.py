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
"""Settings tab parent class. Helpful if we need more overlay types without copy-and-pasting too much code"""
import os
import logging
import gi
gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position
from gi.repository import Gtk, Gdk


try:
    from xdg.BaseDirectory import xdg_config_home
except ModuleNotFoundError:
    from xdg import XDG_CONFIG_HOME as xdg_config_home


class SettingsWindow(Gtk.VBox):
    """Settings tab parent class. Helpful if we need more overlay types without copy-and-pasting too much code"""

    def __init__(self):
        Gtk.VBox.__init__(self)
        self.placement_window = None
        self.configDir = None
        self.configFile = None
        self.overlay = None
        self.floating_x = None
        self.floating_y = None
        self.floating_w = None
        self.floating_h = None

    def init_config(self):
        self.configDir = os.path.join(xdg_config_home, "discover_overlay")
        os.makedirs(self.configDir, exist_ok=True)
        self.configFile = os.path.join(self.configDir, "config.ini")
        self.read_config()

    def close_window(self, _a=None, _b=None):
        if self.placement_window:
            (x, y) = self.placement_window.get_position()
            (w, h) = self.placement_window.get_size()
            self.floating_x = x
            self.floating_y = y
            self.floating_w = w
            self.floating_h = h
            self.overlay.set_floating(True, x, y, w, h)
            self.save_config()
            self.placement_window.close()
            self.placement_window = None
        self.hide()
        return True

    def get_monitor_index(self, name):
        display = Gdk.Display.get_default()
        if "get_n_monitors" in dir(display):
            for i in range(0, display.get_n_monitors()):
                if display.get_monitor(i).get_model() == name:
                    return i
        logging.info(
            "Could not find monitor : %s", name)
        return 0

    def get_monitor_obj(self, name):
        display = Gdk.Display.get_default()
        if "get_n_monitors" in dir(display):
            for i in range(0, display.get_n_monitors()):
                if display.get_monitor(i).get_model() == name:
                    return display.get_monitor(i)
        logging.info(
            "Could not find monitor : %s", name)
        return None

    def present_settings(self):
        self.show_all()

    def read_config(self):
        pass

    def save_config(self):
        pass
