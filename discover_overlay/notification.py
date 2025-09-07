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

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Pango

log = logging.getLogger(__name__)


class NotificationLayout(Gtk.LayoutManager):

    def do_allocate(self, widget, width, height, _baseline):
        asize = widget.overlay.icon_size
        padding = widget.overlay.padding
        i_padding = widget.overlay.icon_pad
        if not widget.overlay.show_icon:
            asize = 0
            i_padding = 0
        if not widget.image:
            asize = 0
            i_padding = 0
        img_alloc = Gdk.Rectangle()
        lbl_alloc = Gdk.Rectangle()
        ttl_alloc = Gdk.Rectangle()
        img_alloc.x = lbl_alloc.x = ttl_alloc.x = padding
        img_alloc.y = lbl_alloc.y = ttl_alloc.y = padding
        width = width - (padding * 2)
        height = height - (padding * 2)

        text_width = width - (asize + i_padding)

        [t_min, _t_nat, _t_bl, _t_nat_bl] = widget.title.measure(
            Gtk.Orientation.VERTICAL, text_width
        )
        [l_min, _l_nat, _l_bl, _l_nat_bl] = widget.message.measure(
            Gtk.Orientation.VERTICAL, text_width
        )
        split = t_min
        if height < t_min + l_min:
            log.error("height %s : %s %s", height, t_min, l_min)
        split = (height) * ((t_min) / (t_min + l_min))

        img_alloc.width = asize
        img_alloc.height = asize

        lbl_alloc.height = height - split
        ttl_alloc.height = split
        lbl_alloc.y += split

        lbl_alloc.width = ttl_alloc.width = text_width

        if widget.overlay.icon_left:
            ttl_alloc.x += asize + i_padding
            lbl_alloc.x += asize + i_padding
        else:
            img_alloc.x += text_width + i_padding

        if widget.image:
            widget.image.size_allocate(img_alloc, -1)
        widget.title.size_allocate(ttl_alloc, -1)
        widget.message.size_allocate(lbl_alloc, -1)

    def do_measure(self, widget, orientation, for_size):
        asize = widget.overlay.icon_size
        padding = widget.overlay.padding
        i_padding = widget.overlay.icon_pad
        if not widget.overlay.show_icon:
            asize = 0
            i_padding = 0
        im_m = [0, 0, 0, 0]
        if not widget.image:
            asize = 0
            i_padding = 0
        else:
            im_m = [asize, asize, 0, 0]
        for_size = for_size - (padding * 2) - i_padding
        if orientation == Gtk.Orientation.VERTICAL:
            lb_m = widget.message.measure(orientation, for_size - asize)
            tt_m = widget.title.measure(orientation, for_size - asize)
            return (
                max(im_m[0], lb_m[0] + tt_m[0]) + (padding * 2),
                max(im_m[1], lb_m[1] + tt_m[1]) + (padding * 2),
                -1,
                -1,
            )
        else:
            lb_m = widget.message.measure(orientation, for_size)
            tt_m = widget.title.measure(orientation, for_size)
            return (
                im_m[0] + max(lb_m[0], tt_m[0]) + (padding * 2) + i_padding,
                im_m[1] + max(lb_m[1], tt_m[1]) + (padding * 2) + i_padding,
                -1,
                -1,
            )


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
                image = "%s%s" % (image[0], image[1])
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
