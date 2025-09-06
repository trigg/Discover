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
import json
import gi
from .overlay import OverlayWindow, get_h_align
from .notification import Notification

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

log = logging.getLogger(__name__)


class NotificationOverlayWindow(OverlayWindow):
    """Overlay window for notifications"""

    def __init__(self, discover, piggyback=None):
        OverlayWindow.__init__(self, discover, piggyback)
        self.box = Gtk.Box()
        self.box.set_orientation(Gtk.Orientation.VERTICAL)
        self.text_spacing = 4
        self.test_content = [
            {
                "icon_url": (
                    "https://cdn.discordapp.com/"
                    "icons/951077080769114172/991abffc0d2a5c040444be4d1a4085f4.webp?size=96"
                ),
                "title": "Title1",
            },
            {"title": "Title2", "body": "Body", "icon": None},
            {
                "icon_url": (
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
                "icon_url": None,
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
                "icon_url": (
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
        self.text_align = "left"
        self.set_title("Discover Notifications")
        self.set_child(self.box)

    def set_blank(self):
        """Set to no data and redraw"""
        pass

    def add_notification_message(self, data):
        """Add new message to dataset"""
        if "data" in data:
            data = data["data"]
        if "body" in data or "title" in data:
            n_not = Notification(
                self,
                data["icon_url"] if "icon_url" in data else None,
                data["title"] if "title" in data else "",
                data["body"] if "body" in data else "",
                self.text_time,
            )
            self.box.append(n_not)
            n_not.show()
            # n_not.set_reveal_child(True)
        else:
            log.error("Malformed message %s", data)

    def set_padding(self, padding):
        """Config option: Padding between notifications, in window-space pixels"""
        self.box.set_spacing(padding)

    def set_icon_padding(self, padding):
        self.icon_pad = padding
        self.update_all()

    def set_border_radius(self, radius):
        self.padding = radius
        """Config option: Radius of the border, in window-space pixels"""
        self.set_css(
            "border-radius", ".notification { border-radius: %spx; }" % (radius)
        )

    def set_icon_size(self, size):
        """Config option: Size of icons, in window-space pixels"""
        if self.icon_size != size:
            self.icon_size = size

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
        self.set_default_size(limit, -1)
        child = self.box.get_first_child()
        while child:
            child.set_size_request(limit, -1)
            child = child.get_next_sibling()

    def recv_icon(self, identifier, pix):
        """Callback from image_getter for icons"""
        self.image_list[identifier] = pix

    def set_fg(self, fg_col):
        """Config option: Set default text colour"""
        self.set_css(
            "text-col",
            ".notification .message, .notification .title { color: %s; }"
            % (self.col_to_css(fg_col)),
        )

    def set_bg(self, bg_col):
        """Config option: Set background colour"""
        self.set_css(
            "background",
            ".notification { background-color: %s; }" % (self.col_to_css(bg_col)),
        )

    def set_show_icon(self, icon):
        """Config option: Set if icons should be shown inline"""
        self.show_icon = icon
        child = self.box.get_first_child()
        while child:
            child.queue_allocate()
            child = child.get_next_sibling()

    def set_reverse_order(self, rev):
        """Config option: Reverse order of messages"""
        if self.reverse_order != rev:
            self.reverse_order = rev

    def set_font(self, font):
        """Config option: Font used to render text"""
        OverlayWindow.set_font(self, font)
        self.update_all()

    def recv_attach(self, identifier, pix):
        """Callback from image_getter for attachments"""
        self.icons[identifier] = pix

    def has_content(self):
        """Return true if this overlay has meaningful content to show"""
        if not self.enabled:
            return False
        if self.hidden:
            return False
        if self.box.get_first_child() is not None:
            return True
        return False

    def sanitize_string(self, string):
        """Sanitize a text message so that it doesn't intefere with Pango's XML format"""
        string = string.replace("&", "&amp;")
        string = string.replace("<", "&lt;")
        string = string.replace(">", "&gt;")
        string = string.replace("'", "&#39;")
        string = string.replace('"', "&#34;")
        return string

    def show_testing(self):
        """Pop up test notifications"""
        for test in self.test_content:
            self.add_notification_message(test)

    def set_text_align(self, text_align):
        log.error("ALIGN CHANGE %s", text_align)
        self.text_align = text_align
        self.update_all()

    def update_all(self):
        child = self.box.get_first_child()
        while child:
            child.update()
            child = child.get_next_sibling()

    def set_config(self, config):
        OverlayWindow.set_config(self, config)
        font = config.get("font", fallback=None)
        self.set_bg(json.loads(config.get("bg_col", fallback="[0.0,0.0,0.0,0.5]")))
        self.set_fg(json.loads(config.get("fg_col", fallback="[1.0,1.0,1.0,1.0]")))
        self.set_text_time(config.getint("text_time", fallback=10))
        self.set_show_icon(config.getboolean("show_icon", fallback=True))
        self.set_reverse_order(config.getboolean("rev", fallback=False))
        self.set_limit_width(config.getint("limit_width", fallback=400))
        self.set_icon_left(config.getboolean("icon_left", fallback=True))
        self.set_icon_size(config.getint("icon_size", fallback=32))
        self.set_padding(config.getint("padding", fallback=8))
        self.set_icon_padding(config.getint("icon_padding", fallback=8))
        self.set_border_radius(config.getint("border_radius", fallback=8))
        self.set_text_align(get_h_align(config.get("text_align", fallback="left")))

        show_dummy = config.getboolean("show_dummy", fallback=False)
        if show_dummy:
            self.show_testing()
            self.discover.config_set("notification", "show_dummy", "False")

        if font:
            self.set_font(font)

        self.set_monitor(config.get("monitor", fallback="Any"))
        self.set_enabled(config.getboolean("enabled", fallback=False))
