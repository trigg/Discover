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

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

log = logging.getLogger(__name__)


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
        self.label.set_wrap(True)
        self.label.set_markup(f"{GLib.markup_escape_text(message["nick"])}:{self.make_line(message["content"])}")
        self.append(self.label)
        if overlay.popup_style:
            hide_time = message["time"] + overlay.text_time
            now = time.time()
            timeout = hide_time - now
            if timeout > 0:
                GLib.timeout_add_seconds(timeout, self.exit)
            else:
                self.skip = True

    def update(self):
        """Something has changed. Check for attachments, edits to text..."""
        # TODO Update

    def exit(self):
        """Remove self from overlay"""
        self.overlay.remove(self)
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
