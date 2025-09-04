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
"""Notification window for text"""
import logging
import time
import json
import gi
from .image_getter import get_surface
from .overlay import OverlayWindow

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

log = logging.getLogger(__name__)


class NotificationOverlayWindow(OverlayWindow):
    """Overlay window for notifications"""

    def __init__(self, discover, piggyback=None):
        OverlayWindow.__init__(self, discover, piggyback)
        self.text_spacing = 4
        self.content = []
        self.test_content = [
            {
                "icon": (
                    "https://cdn.discordapp.com/"
                    "icons/951077080769114172/991abffc0d2a5c040444be4d1a4085f4.webp?size=96"
                ),
                "title": "Title1",
            },
            {"title": "Title2", "body": "Body", "icon": None},
            {
                "icon": (
                    "https://cdn.discordapp.com/"
                    "icons/951077080769114172/991abffc0d2a5c040444be4d1a4085f4.webp?size=96"
                ),
                "title": "Title 3",
                "body": (
                    "Lorem ipsum dolor sit amet, consectetur adipiscing elit,"
                    " sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
                    "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris "
                    "nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in "
                    "reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla "
                    "pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa "
                    "qui officia deserunt mollit anim id est laborum."
                ),
            },
            {
                "icon": None,
                "title": "Title 3",
                "body": (
                    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, "
                    "sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
                    "Ut enim ad minim veniam, quis nostrud exercitation ullamco "
                    "laboris nisi ut aliquip ex ea commodo consequat. Duis aute "
                    "irure dolor in reprehenderit in voluptate velit esse cillum "
                    "dolore eu fugiat nulla pariatur. Excepteur sint occaecat "
                    "cupidatat non proident, sunt in culpa qui officia deserunt "
                    "mollit anim id est laborum."
                ),
            },
            {
                "icon": (
                    "https://cdn.discordapp.com/"
                    "avatars/147077941317206016/6a6935192076489fa6dc1eb5dafbf6e7.webp?size=128"
                ),
                "title": "PM",
                "body": "Birdy test",
            },
        ]
        self.text_font = None
        self.text_size = 13
        self.text_time = None
        self.show_icon = None

        self.connected = True
        self.bg_col = [0.0, 0.6, 0.0, 0.1]
        self.fg_col = [1.0, 1.0, 1.0, 1.0]
        self.icons = []
        self.reverse_order = False
        self.padding = 10
        self.border_radius = 5
        self.limit_width = 100
        self.testing = False
        self.icon_size = 64
        self.icon_pad = 16
        self.icon_left = True

        self.image_list = {}
        self.warned_filetypes = []
        self.set_title("Discover Notifications")

    def set_blank(self):
        """Set to no data and redraw"""
        self.content = []

    def tick(self):
        """Remove old messages from dataset"""
        now = time.time()
        newlist = []
        oldsize = len(self.content)
        # Iterate over and remove messages older than 30s
        for message in self.content:
            if message["time"] + self.text_time > now:
                newlist.append(message)
        self.content = newlist
        # If there is still content to remove
        if len(newlist) > 0 or oldsize != len(newlist):
            pass

    def add_notification_message(self, data):
        """Add new message to dataset"""
        noti = None
        data = data["data"]
        message_id = data["message"]["id"]
        for message in self.content:
            if message["id"] == message_id:
                return
        if "body" in data and "title" in data:
            if "icon_url" in data:
                noti = {
                    "icon": data["icon_url"],
                    "title": data["title"],
                    "body": data["body"],
                    "time": time.time(),
                    "id": message_id,
                }
            else:
                noti = {
                    "title": data["title"],
                    "body": data["body"],
                    "time": time.time(),
                    "id": message_id,
                }

        if noti:
            self.content.append(noti)
            self.get_all_images()

    def set_padding(self, padding):
        """Config option: Padding between notifications, in window-space pixels"""
        if self.padding != padding:
            self.padding = padding

    def set_border_radius(self, radius):
        """Config option: Radius of the border, in window-space pixels"""
        if self.border_radius != radius:
            self.border_radius = radius

    def set_icon_size(self, size):
        """Config option: Size of icons, in window-space pixels"""
        if self.icon_size != size:
            self.icon_size = size
            self.image_list = {}
            self.get_all_images()

    def set_icon_pad(self, pad):
        """Config option: Padding between icon and message, in window-space pixels"""
        if self.icon_pad != pad:
            self.icon_pad = pad

    def set_icon_left(self, left):
        """Config option: Icon on left or right of text"""
        if self.icon_left != left:
            self.icon_left = left

    def set_text_time(self, timer):
        """Config option: Duration that a message will be visible for, in seconds"""
        self.text_time = timer
        self.timer_after_draw = timer

    def set_limit_width(self, limit):
        """Config option: Word wrap limit, in window-space pixels"""
        if self.limit_width != limit:
            self.limit_width = limit

    def get_all_images(self):
        """Return a list of all downloaded images"""
        the_list = self.content
        if self.testing:
            the_list = self.test_content
        for line in the_list:
            icon = line["icon"]

            if icon and icon not in self.image_list:
                get_surface(self.recv_icon, icon, icon, self.get_display())

    def recv_icon(self, identifier, pix):
        """Callback from image_getter for icons"""
        self.image_list[identifier] = pix

    def set_fg(self, fg_col):
        """Config option: Set default text colour"""
        if self.fg_col != fg_col:
            self.fg_col = fg_col

    def set_bg(self, bg_col):
        """Config option: Set background colour"""
        if self.bg_col != bg_col:
            self.bg_col = bg_col

    def set_show_icon(self, icon):
        """Config option: Set if icons should be shown inline"""
        if self.show_icon != icon:
            self.show_icon = icon
            self.get_all_images()

    def set_reverse_order(self, rev):
        """Config option: Reverse order of messages"""
        if self.reverse_order != rev:
            self.reverse_order = rev

    def set_font(self, font):
        """Config option: Font used to render text"""
        if self.text_font != font:
            self.text_font = font

    def recv_attach(self, identifier, pix):
        """Callback from image_getter for attachments"""
        self.icons[identifier] = pix

    def has_content(self):
        """Return true if this overlay has meaningful content to show"""
        if not self.enabled:
            return False
        if self.hidden:
            return False
        if self.testing:
            return self.test_content
        return self.content

    def sanitize_string(self, string):
        """Sanitize a text message so that it doesn't intefere with Pango's XML format"""
        string = string.replace("&", "&amp;")
        string = string.replace("<", "&lt;")
        string = string.replace(">", "&gt;")
        string = string.replace("'", "&#39;")
        string = string.replace('"', "&#34;")
        return string

    def set_testing(self, testing):
        """Toggle placeholder images for testing"""
        self.testing = testing
        self.get_all_images()

    def set_config(self, config):
        OverlayWindow.set_config(self, config)
        self.set_enabled(config.getboolean("enabled", fallback=False))

        font = config.get("font", fallback=None)
        self.set_bg(json.loads(config.get("bg_col", fallback="[0.0,0.0,0.0,0.5]")))
        self.set_fg(json.loads(config.get("fg_col", fallback="[1.0,1.0,1.0,1.0]")))
        self.set_text_time(config.getint("text_time", fallback=10))
        self.set_show_icon(config.getboolean("show_icon", fallback=True))
        self.set_reverse_order(config.getboolean("rev", fallback=False))
        self.set_limit_width(config.getint("limit_width", fallback=400))
        self.set_icon_left(config.getboolean("icon_left", fallback=True))
        self.set_icon_pad(config.getint("icon_padding", fallback=8))
        self.set_icon_size(config.getint("icon_size", fallback=32))
        self.set_padding(config.getint("padding", fallback=8))
        self.set_border_radius(config.getint("border_radius", fallback=8))
        self.set_testing(config.getboolean("show_dummy", fallback=False))

        if font:
            self.set_font(font)

        self.set_monitor(config.get("monitor", fallback="Any"))
