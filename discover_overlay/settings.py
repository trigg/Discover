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
"""
Settings tab parent class. Helpful if we need more
overlay types without copy-and-pasting too much code
"""
import os
import logging
import gi
from .draggable_window import DraggableWindow
from .draggable_window_wayland import DraggableWindowWayland
gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Gtk, Gdk


try:
    from xdg.BaseDirectory import xdg_config_home
except ModuleNotFoundError:
    from xdg import XDG_CONFIG_HOME as xdg_config_home


class SettingsWindow(Gtk.VBox):
    """
    Settings tab parent class. Helpful if we need more
    overlay types without copy-and-pasting too much code
    """

    def __init__(self):
        Gtk.VBox.__init__(self)
        self.placement_window = None
        self.config_dir = None
        self.config_file = None
        self.overlay = None
        self.floating = None
        self.floating_x = None
        self.floating_y = None
        self.floating_w = None
        self.floating_h = None
        self.align_x_widget = None
        self.align_y_widget = None
        self.align_monitor_widget = None
        self.align_placement_widget = None
        self.monitor = None
        self.align_x = None
        self.align_y = None
        self.enabled = None
        self.autohide = None

    def init_config(self):
        """
        Locate the config and then read
        """
        self.config_dir = os.path.join(xdg_config_home, "discover_overlay")
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_file = os.path.join(self.config_dir, "config.ini")
        self.read_config()

    def close_window(self, _a=None, _b=None):
        """
        Helper to ensure we don't lose changes to floating windows
        Hide for later
        """
        if self.placement_window:
            (pos_x, pos_y) = self.placement_window.get_position()
            (width, height) = self.placement_window.get_size()
            self.floating_x = pos_x
            self.floating_y = pos_y
            self.floating_w = width
            self.floating_h = height
            self.overlay.set_floating(True, pos_x, pos_y, width, height)
            self.save_config()
            self.placement_window.close()
            self.placement_window = None
        self.hide()
        return True

    def get_monitor_index(self, name):
        """
        Helper function to find the index number of the monitor
        """
        display = Gdk.Display.get_default()
        if "get_n_monitors" in dir(display):
            for i in range(0, display.get_n_monitors()):
                if display.get_monitor(i).get_model() == name:
                    return i
        logging.info(
            "Could not find monitor : %s", name)
        return 0

    def get_monitor_obj(self, name):
        """
        Helper function to find the monitor object of the monitor
        """
        display = Gdk.Display.get_default()
        if "get_n_monitors" in dir(display):
            for i in range(0, display.get_n_monitors()):
                if display.get_monitor(i).get_model() == name:
                    return display.get_monitor(i)
        logging.info(
            "Could not find monitor : %s", name)
        return None

    def present_settings(self):
        """
        Show settings
        """
        self.show_all()

    def read_config(self):
        """
        Stub called when settings are needed to be read
        """

    def save_config(self):
        """
        Stub called when settings are needed to be written
        """

    def change_placement(self, button):
        """
        Placement window button pressed.
        """
        if self.placement_window:
            (pos_x, pos_y, width, height) = self.placement_window.get_coords()
            self.floating_x = pos_x
            self.floating_y = pos_y
            self.floating_w = width
            self.floating_h = height
            self.overlay.set_floating(True, pos_x, pos_y, width, height)
            self.save_config()
            if not self.overlay.is_wayland:
                button.set_label("Place Window")

            self.placement_window.close()
            self.placement_window = None
        else:
            if self.overlay.is_wayland:
                self.placement_window = DraggableWindowWayland(
                    pos_x=self.floating_x, pos_y=self.floating_y,
                    width=self.floating_w, height=self.floating_h,
                    message="Place & resize this window then press Green!", settings=self)
            else:
                self.placement_window = DraggableWindow(
                    pos_x=self.floating_x, pos_y=self.floating_y,
                    width=self.floating_w, height=self.floating_h,
                    message="Place & resize this window then press Save!", settings=self)
            if not self.overlay.is_wayland:
                button.set_label("Save this position")

    def change_align_type_edge(self, button):
        """
        Alignment setting changed
        """
        if button.get_active():
            self.overlay.set_floating(
                False, self.floating_x, self.floating_y, self.floating_w, self.floating_h)
            self.floating = False
            self.save_config()

            # Re-sort the screen
            self.align_x_widget.show()
            self.align_y_widget.show()
            self.align_monitor_widget.show()
            self.align_placement_widget.hide()

    def change_align_type_floating(self, button):
        """
        Alignment setting changed
        """
        if button.get_active():
            self.overlay.set_floating(
                True, self.floating_x, self.floating_y, self.floating_w, self.floating_h)
            self.floating = True
            self.save_config()
            self.align_x_widget.hide()
            self.align_y_widget.hide()
            self.align_monitor_widget.hide()
            self.align_placement_widget.show()

    def change_monitor(self, button):
        """
        Alignment setting changed
        """
        display = Gdk.Display.get_default()
        if "get_monitor" in dir(display):
            mon = display.get_monitor(button.get_active())
            m_s = mon.get_model()
            self.overlay.set_monitor(button.get_active(), mon)

            self.monitor = m_s
            self.save_config()

    def change_align_x(self, button):
        """
        Alignment setting changed
        """
        self.overlay.set_align_x(button.get_active() == 1)

        self.align_x = (button.get_active() == 1)
        self.save_config()

    def change_align_y(self, button):
        """
        Alignment setting changed
        """
        self.overlay.set_align_y(button.get_active())

        self.align_y = button.get_active()
        self.save_config()

    def change_enabled(self, button):
        """
        Overlay active state toggled
        """
        self.overlay.set_enabled(button.get_active())

        self.enabled = button.get_active()
        self.save_config()

    def change_hide_on_mouseover(self, button):
        """
        Autohide setting changed
        """
        self.overlay.set_hide_on_mouseover(button.get_active())
        self.autohide = button.get_active()
        self.save_config()
