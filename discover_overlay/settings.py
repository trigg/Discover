import gi
gi.require_version("Gtk", "3.0")
import sys
import os
from gi.repository import Gtk, Gdk
import logging


try:
    from xdg.BaseDirectory import xdg_config_home
except ModuleNotFoundError:
    from xdg import XDG_CONFIG_HOME as xdg_config_home


class SettingsWindow(Gtk.Window):
    def init_config(self):
        self.configDir = os.path.join(xdg_config_home, "discover_overlay")
        os.makedirs(self.configDir, exist_ok=True)
        self.configFile = os.path.join(self.configDir, "config.ini")
        self.read_config()

    def close_window(self, a=None, b=None):
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
            "Could not find monitor : %s" % (name))
        return 0

    def present(self):
        self.show_all()
