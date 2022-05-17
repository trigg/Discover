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
"""Overview setting tab on settings window"""
import gettext
import json
import logging
import pkg_resources
from configparser import ConfigParser
import gi
import sys
from .settings import SettingsWindow

log = logging.getLogger(__name__)
t = gettext.translation('default', pkg_resources.resource_filename(
    'discover_overlay', 'locales'))
_ = t.gettext

gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Gtk, Gdk, GLib  # nopep8


GUILD_DEFAULT_VALUE = "0"


class AboutSettingsWindow(Gtk.Grid):
    """Basic overview and a nicer looking landing page for Steam Deck"""

    def __init__(self, discover):
        Gtk.Grid.__init__(self)
        self.discover = discover
        self.create_gui()

    def create_gui(self):
        """
        Prepare the gui
        """
        spacing_box_1 = Gtk.Box()
        spacing_box_1.set_size_request(60, 60)
        self.attach(spacing_box_1, 1, 0, 1, 1)

        icon = Gtk.Image.new_from_icon_name("discover-overlay-tray", 256)
        icon.set_pixel_size(128)
        self.attach(icon, 1, 1, 1, 1)

        spacing_box_2 = Gtk.Box()
        spacing_box_2.set_size_request(60, 60)
        self.attach(spacing_box_2, 1, 2, 1, 1)

        blurb = Gtk.Label.new(None)
        message = "<span size=\"larger\">%s (%s)</span>\n\n%s\n\n%s (<a href=\"https://discord.gg/jRKWMuDy5V\">https://discord.gg/jRKWMuDy5V</a>) %s (<a href=\"https://github.com/trigg/Discover\">https://github.com/trigg/Discover</a>)\n\n\n\n\n\n" % (
            _("Welcome to Discover Overlay"),
            pkg_resources.get_distribution('discover_overlay').version,
            _("Discover-Overlay is a GTK3 overlay written in Python3. It can be configured to show who is currently talking on discord or it can be set to display text and images from a preconfigured channel. It is fully customisable and can be configured to display anywhere on the screen. We fully support X11 and wlroots based environments. We felt the need to make this project due to the shortcomings in support on Linux by the official discord client."),
            _("Please visit our discord"),
            _(" for support. Or open an issue on our GitHub ")
        )
        blurb.set_markup(message)
        blurb.set_line_wrap(True)
        self.attach(blurb, 1, 3, 1, 1)

        killapp = Gtk.Button.new_with_label(_("Close overlay"))
        killapp.connect("pressed", self.close_app)
        self.attach(killapp, 1, 5, 1, 1)

        self.set_column_homogeneous(True)

    def close_app(self, button):
        log.info("Quit pressed")
        sys.exit(0)

    def present_settings(self):
        self.show_all()
