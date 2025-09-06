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
"""A Gtk Box with direction"""
import logging
import gi
from .image_getter import get_surface
from .overlay import Direction

gi.require_version("Gtk", "4.0")


from gi.repository import Gtk, GLib, Gdk

log = logging.getLogger(__name__)


class UserBoxLayout(Gtk.LayoutManager):

    def do_allocate(self, widget, width, height, _baseline):
        direction = Direction(widget.overlay.text_side)
        asize = widget.overlay.avatar_size
        img_alloc = Gdk.Rectangle()
        lbl_alloc = Gdk.Rectangle()

        img_alloc.width = img_alloc.height = asize
        if direction == Direction.LTR:
            img_alloc.x = img_alloc.y = lbl_alloc.y = 0
            lbl_alloc.x = asize
            lbl_alloc.height = img_alloc.height = height
            lbl_alloc.width = width - asize
        elif direction == Direction.RTL:
            lbl_alloc.x = img_alloc.y = lbl_alloc.y = 0
            lbl_alloc.height = img_alloc.height = height
            lbl_alloc.width = img_alloc.x = width - asize
        elif direction == Direction.TTB:
            img_alloc.x = img_alloc.y = lbl_alloc.x = 0
            lbl_alloc.y = asize
            lbl_alloc.width = img_alloc.width = width
            lbl_alloc.height = height - asize
        else:
            img_alloc.y = lbl_alloc.height = height - asize
            img_alloc.x = lbl_alloc.x = lbl_alloc.y = 0
            lbl_alloc.width = img_alloc.width = width

        tx = widget.overlay.text_x_align
        if tx == "left":
            widget.label.set_halign(Gtk.Align.START)
        elif tx == "middle":
            widget.label.set_halign(Gtk.Align.CENTER)
        else:
            widget.label.set_halign(Gtk.Align.END)
        ty = widget.overlay.text_y_align
        if ty == "top":
            widget.label.set_valign(Gtk.Align.START)
        elif ty == "middle":
            widget.label.set_valign(Gtk.Align.CENTER)
        else:
            widget.label.set_valign(Gtk.Align.END)

        widget.image.size_allocate(img_alloc, -1)
        widget.label.size_allocate(lbl_alloc, -1)

    def do_measure(self, widget, orientation, for_size):
        direction = Direction(widget.overlay.text_side)

        im_m = widget.image.measure(orientation, for_size)
        lb_m = widget.label.measure(orientation, for_size)

        if (
            orientation == Gtk.Orientation.VERTICAL
            and (direction == Direction.TTB or direction == Direction.BTT)
        ) or (
            orientation == Gtk.Orientation.HORIZONTAL
            and (direction == Direction.LTR or direction == Direction.RTL)
        ):
            return (im_m[0] + lb_m[0], im_m[1] + lb_m[1], -1, -1)
        else:
            return (max(im_m[0], lb_m[0]), max(im_m[1], lb_m[1]), -1, -1)


class UserBox(Gtk.Box):
    def __init__(self, overlay, userid):
        super().__init__()
        self.overlay = overlay
        self.userid = userid

        self.add_css_class("user")

        self.image = Gtk.Image()
        self.label = Gtk.Label()

        self.image.add_css_class("usericon")
        self.label.add_css_class("userlabel")

        self.image.set_halign(Gtk.Align.CENTER)
        self.image.set_valign(Gtk.Align.CENTER)

        self.append(self.image)
        self.append(self.label)

        self.pixbuf = None
        self.pixbuf_requested = False
        self.name = ""

        self.grace_timeout = None

        self.set_layout_manager(UserBoxLayout())

    def update_label(self, user):
        if self.overlay.icon_only:
            self.label.hide()
            return
        self.label.show()

        if len(user["friendlyname"]) < self.overlay.nick_length:
            self.label.set_text(user["friendlyname"])
        else:
            self.label.set_text(
                user["friendlyname"][: (self.overlay.nick_length - 1)] + "\u2026"
            )

    def update_image(self, user):
        if not self.overlay.show_avatar:
            self.image.hide()
            return
        self.image.show()
        # Ensure pixbuf for avatar
        if (
            self.pixbuf is None
            and not self.pixbuf_requested
            and self.overlay.avatar_size > 0
            and user["avatar"]
        ):
            url = (
                f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png"
            )
            get_surface(self.recv_avatar, url, user["id"], self.get_display())
            self.pixbuf_requested = True

        if self.pixbuf:
            self.image.set_from_pixbuf(self.pixbuf)
        elif self.overlay.def_avatar:
            self.image.set_from_pixbuf(self.overlay.def_avatar)

    def recv_avatar(self, _identifier, pix):
        self.pixbuf = pix
        self.pixbuf_requested = False
        self.image.set_from_pixbuf(self.pixbuf)

    def set_talking(self, talking):
        if self.grace_timeout:
            GLib.source_remove(self.grace_timeout)
        if talking:
            self.show()
            self.add_css_class("talking")
        else:
            self.remove_css_class("talking")
            if self.overlay.only_speaking:
                grace = self.overlay.only_speaking_grace_period
                if grace > 0:
                    self.grace_timeout = GLib.timeout_add_seconds(grace, self.grace_cb)
                else:
                    self.hide()

    def grace_cb(self):
        self.hide()


class UserBoxConnection(UserBox):
    def __init__(self, overlay):
        super().__init__(overlay, None)
        self.show_always = False
        self.show_disconnected = True
        self.last = "None"
        self.pix_none = "network-cellular-signal-none"
        self.pix_ok = "network-cellular-signal-ok"
        self.pix_good = "network-cellular-signal-good"
        self.pix_excellent = "network-cellular-signal-excellent"

    def set_show_always(self, show):
        self.show_always = show

    def set_show_only_disconnected(self, show):
        self.show_disconnected = show

    def get_image_name(self):
        level = self.last
        if (
            level == "DISCONNECTED"
            or level == "NO_ROUTE"
            or level == "VOICE_DISCONNECTED"
        ):
            return self.pix_none
        elif (
            level == "ICE_CHECKING"
            or level == "AWAITING_ENDPOINT"
            or level == "AUTHENTICATING"
        ):
            return self.pix_ok
        elif level == "CONNECTING" or level == "VOICE_CONNECTING":
            return self.pix_good
        elif level == "CONNECTED" or level == "VOICE_CONNECTED":
            return self.pix_excellent
        else:
            return ""

    def set_connection(self, level):
        if not level:
            self.hide()
            return
        if level == self.last:
            return

        self.last = level
        if self.should_show():
            self.show()
        else:
            self.hide()
        self.image.set_from_icon_name(self.get_image_name())
        self.update_label(None)

    def should_show(self):
        """Returns True if this should show in overlay, False otherwise"""
        if self.show_always:
            return True
        elif self.show_disconnected and (
            self.last != "CONNECTED" and self.last != "VOICE_CONNECTED"
        ):
            return True
        return False

    def update_image(self, user):
        """Updates the image, assuming there is changed config or info"""
        if not self.overlay.show_avatar:
            self.image.hide()
            return
        self.image.show()

    def update_label(self, user):
        """Updates the label, assuming there is changed config or info"""
        if self.should_show():
            self.show()
        else:
            self.hide()
        if self.overlay.icon_only:
            self.label.hide()
            return
        self.label.show()
        if len(self.last) < self.overlay.nick_length:
            self.label.set_text(self.last)
        else:
            self.label.set_text(self.last[: (self.overlay.nick_length - 1)] + "\u2026")

    def blank(self):
        self.pixbuf = None
        self.hide()


class UserBoxTitle(UserBox):
    def __init__(self, overlay):
        super().__init__(overlay, None)
        self.show_title = False
        self.last = ""

    def set_label(self, label):
        self.last = label
        if not label:
            self.hide()
            return
        if self.show_title:
            self.show()
        if self.overlay.icon_only:
            self.label.hide()
        else:
            self.label.show()
        self.label.set_text(label)

    def set_image(self, image):
        if self.show_title:
            self.show()
        if self.overlay.show_avatar:
            self.image.show()
        self.pixbuf = image
        self.image.set_from_pixbuf(self.pixbuf)

    def blank(self):
        self.pixbuf = None
        self.hide()

    def set_show(self, show):
        self.show_title = show
        if show:
            self.show()
        else:
            self.hide()

    def should_show(self):
        return self.show_title and self.last

    def update_image(self, user):
        if not self.overlay.show_avatar:
            self.image.hide()
            return
        self.image.show()
        self.image.set_from_pixbuf(self.pixbuf)

    def update_label(self, user):
        if self.should_show():
            self.show()
        else:
            self.hide()
        if self.overlay.icon_only:
            self.label.hide()
            return
        self.label.show()
        if self.last:
            if len(self.last) < self.overlay.nick_length:
                self.label.set_text(self.last)
            else:
                self.label.set_text(
                    self.last[: (self.overlay.nick_length - 1)] + "\u2026"
                )
