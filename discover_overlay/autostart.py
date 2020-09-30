import sys
import os
import logging
try:
    from xdg.BaseDirectory import xdg_config_home, xdg_data_home
except ModuleNotFoundError:
    from xdg import XDG_CONFIG_HOME as xdg_config_home
    from xdg import XDG_DATA_HOME as xdg_data_home


class Autostart:
    def __init__(self, app_name):
        if not app_name.endswith(".desktop"):
            app_name = "%s.desktop" % (app_name)
        self.app_name = app_name
        self.auto_locations = [os.path.join(
            xdg_config_home, 'autostart/'), '/etc/xdg/autostart/']
        self.desktop_locations = [os.path.join(
            xdg_data_home, 'applications/'), '/usr/share/applications/']
        self.auto = self.find_auto()
        self.desktop = self.find_desktop()
        logging.info("Autostart info : desktop %s auto %s" %
                     (self.desktop, self.auto))

    def find_auto(self):
        for p in self.auto_locations:
            file = os.path.join(p, self.app_name)
            if os.path.exists(file):
                return file
        return None

    def find_desktop(self):
        for p in self.desktop_locations:
            file = os.path.join(p, self.app_name)
            if os.path.exists(file):
                return file
        return None

    def set_autostart(self, b):
        if b and not self.auto:
            # Enable
            d = os.path.join(xdg_config_home, 'autostart')
            self.auto = os.path.join(d, self.app_name)
            os.symlink(self.desktop, self.auto)
            pass
        elif not b and self.auto:
            # Disable
            if os.path.islink(self.auto):
                os.remove(self.auto)
            pass

    def is_auto(self):
        return True if self.auto else False
