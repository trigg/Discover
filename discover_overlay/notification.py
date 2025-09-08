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
from .image_getter import get_surface
from .overlay import HorzAlign
from .layout import NotificationLayout

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Pango

log = logging.getLogger(__name__)


class Notification(Gtk.Box):
    """Overlay window for notifications"""

    def __init__(self, overlay, image, title, message, timeout):
        Gtk.Box.__init__(self)
        self.set_layout_manager(NotificationLayout())

        self.overlay = overlay
        self.title = Gtk.Label()
        self.message = Gtk.Label()
        self.image = None

        self.append(self.title)
        self.append(self.message)

        self.title.set_text(title)
        self.message.set_text(message)

        self.title.set_wrap(True)
        self.message.set_wrap(True)

        self.title.set_wrap_mode(Pango.WrapMode.WORD)
        self.message.set_wrap_mode(Pango.WrapMode.WORD)

        self.title.set_justify(Gtk.Justification.RIGHT)
        self.message.set_justify(Gtk.Justification.RIGHT)

        self.add_css_class("notification")
        self.title.add_css_class("title")
        self.message.add_css_class("message")

        self.show()
        self.title.show()
        self.message.show()
        if image:
            if not isinstance(image, str):
                image = f"{image[0]}{image[1]}"
            log.info(image)
            get_surface(self.recv_avatar, image, "channel", self.get_display())

        if timeout:
            GLib.timeout_add_seconds(timeout, self.exit)

    def recv_avatar(self, _ident, pix):
        """A new image touches the notification"""
        if pix and not self.image:
            self.image = Gtk.Image()
            self.append(self.image)
            self.image.add_css_class("image")
            self.image.show()
            self.image.set_from_pixbuf(pix)
            # self.image.set_valign(Gtk.Align.START)
        elif not pix and self.image:
            self.remove(self.image)
            self.image = None
        elif pix and self.image:
            self.image.set_from_pixbuf(pix)
        self.queue_resize()

    def exit(self):
        """Remove self from visible notifications"""
        self.overlay.remove(self)

    def update(self):
        """Change child properties based on config of overlay"""
        align = Gtk.Align.START
        justify = Gtk.Justification.LEFT
        if self.overlay.text_align == HorzAlign.MIDDLE:
            align = Gtk.Align.CENTER
            justify = Gtk.Justification.CENTER
        elif self.overlay.text_align == HorzAlign.RIGHT:
            align = Gtk.Align.END
            justify = Gtk.Justification.RIGHT

        self.title.set_justify(justify)
        self.message.set_justify(justify)
        self.title.set_halign(align)
        self.message.set_halign(align)
