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
"""Overlay window for text"""
import logging
import re
import json
import gi
from .overlay import OverlayWindow
from .message import Message, MessageBox

gi.require_version("Gtk", "4.0")

from gi.repository import Pango, Gtk

log = logging.getLogger(__name__)


class TextOverlayWindow(OverlayWindow):
    """Overlay window for text"""

    def __init__(self, discover, piggyback=None):
        OverlayWindow.__init__(self, discover, piggyback)
        self.box = MessageBox(self)
        self.text_spacing = 4
        self.text_font = None
        self.text_size = 13
        self.text_time = None
        self.show_attach = None
        self.popup_style = None
        self.line_limit = 100
        # 0, 0, self.text_size, self.text_size)
        self.pango_rect = Pango.Rectangle()
        self.pango_rect.width = self.text_size * Pango.SCALE
        self.pango_rect.height = self.text_size * Pango.SCALE

        self.connected = True
        self.bg_col = [0.0, 0.6, 0.0, 0.1]
        self.fg_col = [1.0, 1.0, 1.0, 1.0]
        self.attachment = {}

        self.image_list = []
        self.img_finder = re.compile(r"`")
        self.warned_filetypes = []
        self.set_title("Discover Text")
        self.width_limit = 500
        self.height_limit = 300
        self.set_child(self.box)
        if self.popup_style and not self.has_content():
            self.hide()

    def set_blank(self):
        """Set contents blank and redraw"""
        child = self.box.get_first_child()
        while child:
            n_child = child.get_next_sibling()
            self.box.remove(child)
            child = n_child
        if self.popup_style and not self.has_content():
            self.hide()

    def new_line(self, message):
        """Add a new message to text overlay. Does not sanity check the data"""
        message = Message(self, message)
        if not message.skip:
            self.box.append(message)
        if self.has_content():
            self.show()

    def set_text_time(self, timer):
        """Config option: Time before messages disappear from overlay"""
        if self.text_time != timer:
            self.text_time = timer
            self.set_blank()

    def set_fg(self, fg_col):
        """Config option: Sets the text colour"""
        if self.fg_col != fg_col:
            self.fg_col = fg_col

    def set_bg(self, bg_col):
        """Config option: Set the background colour"""
        if self.bg_col != bg_col:
            self.bg_col = bg_col

    def set_show_attach(self, attachment):
        """Config option: Show image attachments"""
        if self.attachment != attachment:
            self.show_attach = attachment

    def set_popup_style(self, boolean):
        """Config option: Messages should disappear after being shown for some time"""
        if self.popup_style != boolean:
            self.popup_style = boolean
            self.set_blank()

    def set_font(self, font):
        """Config option: Set font used for rendering"""
        if self.text_font != font:
            self.text_font = font

            self.pango_rect = Pango.Rectangle()
            font = Pango.FontDescription(self.text_font)
            self.pango_rect.width = font.get_size() * Pango.SCALE
            self.pango_rect.height = font.get_size() * Pango.SCALE

    def set_line_limit(self, limit):
        """Config option: Limit number of lines rendered"""
        if self.line_limit != limit:
            self.line_limit = limit

    def recv_attach(self, identifier, pix):
        """Callback from image_getter"""
        self.attachment[identifier] = pix

    def has_content(self):
        """Returns true if overlay has meaningful content to render"""
        if self.piggyback and self.piggyback.has_content():
            return True
        if not self.enabled:
            return False
        if self.hidden:
            return False
        return self.box.get_first_child() is not None

    def update(self):
        """Call when removing a message automatically, allows hiding of overlay when empty"""
        if not self.has_content():
            self.hide()

    def set_config(self, config):
        OverlayWindow.set_config(self, config)
        self.set_enabled(config.getboolean("enabled", fallback=False))

        channel = config.get("channel", fallback="0")
        guild = config.get("guild", fallback="0")
        self.discover.connection.set_text_channel(channel, guild)

        font = config.get("font", fallback=None)

        self.set_css(
            "background",
            ".messagebox { background-color: %s; }"
            % (self.col_to_css(config.get("bg_col", fallback="[0.0,0.0,0.0,0.5]"))),
        )
        self.set_css(
            "text-color",
            ".messagebox .message { color: %s; }"
            % (self.col_to_css(config.get("fg_col", fallback="[1.0,1.0,1.0,1.0]"))),
        )
        self.set_popup_style(config.getboolean("popup_style", fallback=False))
        self.set_text_time(config.getint("text_time", fallback=30))
        self.set_show_attach(config.getboolean("show_attach", fallback=True))
        self.set_line_limit(config.getint("line_limit", fallback=20))
        self.set_hide_on_mouseover(config.getboolean("autohide", fallback=False))
        self.set_mouseover_timer(config.getint("autohide_timer", fallback=1))

        self.width_limit = config.getint("width_limit", fallback=500)
        self.height_limit = config.getint("height_limit", fallback=300)
        self.set_size_request(self.width_limit, self.height_limit)
        self.box.set_size_request(self.width_limit, self.height_limit)
        self.set_monitor(config.get("monitor", fallback="Any"))

        if font:
            self.set_font(font)
