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
import gi
import time
from .image_getter import get_surface
from .overlay import HorzAlign

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Pango

log = logging.getLogger(__name__)


class MessageBoxLayout(Gtk.LayoutManager):

    def do_allocate(self, widget, width, height, _baseline):
        y = height
        child = widget.get_last_child()
        while child:
            alloc = Gdk.Rectangle()
            measure = child.measure(Gtk.Orientation.VERTICAL, width)
            alloc.x = 0
            alloc.y = y - measure[0]
            y -= measure[0]
            alloc.width = width
            alloc.height = measure[0]
            child.size_allocate(alloc, -1)
            child = child.get_prev_sibling()

    def do_measure(self, widget, orientation, _for_size):
        if orientation == Gtk.Orientation.VERTICAL:
            return (widget.overlay.height_limit, widget.overlay.height_limit, -1, -1)
        else:
            return (widget.overlay.width_limit, widget.overlay.width_limit, -1, -1)


class MessageBox(Gtk.Box):
    def __init__(self, overlay):
        Gtk.Box.__init__(self)
        self.overlay = overlay
        self.set_layout_manager(MessageBoxLayout())
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.add_css_class("messagebox")


class Message(Gtk.Box):
    """Overlay window for notifications"""

    def __init__(self, overlay, message):
        Gtk.Box.__init__(self)
        self.skip = False
        self.overlay = overlay
        self.message = message

        self.image = None
        self.label = Gtk.Label()
        self.label.add_css_class("message")
        # self.label.set_use_markup(True)
        self.label.set_wrap(True)
        self.label.set_markup(
            "%s:%s" % (message["nick"], self.make_line(message["content"]))
        )
        self.append(self.label)
        if overlay.popup_style:
            hide_time = message["time"] + overlay.text_time
            now = time.time()
            timeout = hide_time - now
            if timeout > 0:
                GLib.timeout_add_seconds(timeout, self.exit)
            else:
                self.skip = True

    def exit(self):
        self.overlay.box.remove(self)
        self.overlay.update()

    def make_line(self, message):
        """Decode a recursive JSON object into pango markup."""
        ret = ""
        if isinstance(message, list):
            for inner_message in message:
                ret = f"{ret}{self.make_line(inner_message)}"
        elif isinstance(message, str):
            ret = GLib.markup_escape_text(message)
        elif message["type"] == "strong":
            ret = f"<b>{self.make_line(message['content'])}</b>"
        elif message["type"] == "text":
            ret = GLib.markup_escape_text(message["content"])
        elif message["type"] == "link":
            ret = f"<u>{self.make_line(message['content'])}</u>"
        elif message["type"] == "emoji":
            if "surrogate" in message:
                # ['src'] is SVG URL
                # ret = msg
                ret = message["surrogate"]
            else:
                ret = "`"
        elif (
            message["type"] == "inlineCode"
            or message["type"] == "codeBlock"
            or message["type"] == "blockQuote"
        ):
            ret = f"<span font_family=\"monospace\" background=\"#0004\">{self.make_line(message['content'])}</span>"
        elif message["type"] == "u":
            ret = f"<u>{self.make_line(message['content'])}</u>"
        elif message["type"] == "em":
            ret = f"<i>{self.make_line(message['content'])}</i>"
        elif message["type"] == "s":
            ret = f"<s>{self.make_line(message['content'])}</s>"
        elif message["type"] == "channel":
            ret = self.make_line(message["content"])
        elif message["type"] == "mention":
            ret = self.make_line(message["content"])
        elif message["type"] == "br":
            ret = "\n"
        else:
            pass
        return ret
