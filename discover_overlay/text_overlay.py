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
import gi
import cairo
from .css_helper import col_to_css, font_string_to_css_font_string
from .message import Message
from .layout import MessageBoxLayout
from .overlay import HorzAlign, VertAlign, get_h_align, get_v_align

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

log = logging.getLogger(__name__)


class TextOverlayWindow(Gtk.Box):
    """Overlay window for text"""

    def __init__(self, discover):
        Gtk.Box.__init__(self)
        self.set_layout_manager(MessageBoxLayout())
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.add_css_class("messagebox")
        self.discover = discover

        self.text_time = None
        self.show_attach = None
        self.popup_style = None

        self.width_limit = 500
        self.height_limit = 300
        self.align_x = HorzAlign.RIGHT
        self.align_y = VertAlign.BOTTOM
        self.show()

    def set_blank(self):
        """Set contents blank and redraw"""
        child = self.get_first_child()
        while child:
            n_child = child.get_next_sibling()
            self.remove(child)
            child = n_child
        self.get_root().set_visibility()

    def new_line(self, message):
        """Add a new message to text overlay. Does not sanity check the data"""
        message = Message(self, message)
        if not message.skip:
            self.append(message)
        self.get_root().set_visibility()

    def set_text_time(self, timer):
        """Config option: Time before messages disappear from overlay"""
        if self.text_time != timer:
            self.text_time = timer
            self.set_blank()

    def set_show_attach(self, attachment):
        """Config option: Show image attachments"""
        if self.show_attach != attachment:
            self.show_attach = attachment
            self.update_all()

    def set_font(self, font):
        """
        Set the font used by the overlay
        """
        self.set_css("font", "* { font: %s; }" % (font_string_to_css_font_string(font)))

    def set_popup_style(self, boolean):
        """Config option: Messages should disappear after being shown for some time"""
        if self.popup_style != boolean:
            self.popup_style = boolean
            self.set_blank()

    def should_show(self):
        """Returns true if overlay has meaningful content to render"""
        return self.get_first_child() is not None

    def update(self):
        """Call when removing a message automatically, allows hiding of overlay when empty"""
        self.get_root().set_visibility()

    def update_all(self):
        """Tell all messages we've had something changed"""
        child = self.get_first_child()
        while child:
            child.update()
            child = child.get_next_sibling()

    def set_config(self, config):
        """Set self and children from config"""
        channel = config.get("channel", fallback="0")
        guild = config.get("guild", fallback="0")
        self.discover.connection.set_text_channel(channel, guild)

        font = config.get("font", fallback=None)

        self.set_css(
            "background",
            ".messagebox { background-color: %s; }"
            % (col_to_css(config.get("bg_col", fallback="[0.0,0.0,0.0,0.5]"))),
        )
        self.set_css(
            "text-color",
            ".messagebox .message { color: %s; }"
            % (col_to_css(config.get("fg_col", fallback="[1.0,1.0,1.0,1.0]"))),
        )
        self.set_popup_style(config.getboolean("popup_style", fallback=False))
        self.set_text_time(config.getint("text_time", fallback=30))
        self.set_show_attach(config.getboolean("show_attach", fallback=True))

        self.width_limit = config.getint("width_limit", fallback=500)
        self.height_limit = config.getint("height_limit", fallback=300)
        self.set_size_request(self.width_limit, self.height_limit)
        self.align_x = get_h_align(config.get("align_x", "right"))
        self.align_y = get_v_align(config.get("align_y", "bottom"))

        if font:
            self.set_font(font)

    def set_css(self, css_id, rule):
        """Set a CSS Rule on window"""
        self.get_root().set_css(css_id, rule)

    def get_align(self):
        """Get alignment requested"""
        return (self.align_x, self.align_y)

    def get_boxes(self):
        """Return a bounding box of this window"""
        return [
            # pylint: disable=E1101
            cairo.RectangleInt(
                x=0, y=0, width=self.width_limit, height=self.height_limit
            )
        ]
