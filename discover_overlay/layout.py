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
"""Collection of LayoutManagers used throughout"""
import logging
from enum import Enum
import gi

gi.require_version("Gtk", "4.0")


from gi.repository import Gtk, Gdk

log = logging.getLogger(__name__)


class Direction(Enum):
    """Direction of flow"""

    LTR = 0
    RTL = 1
    TTB = 2
    BTT = 3


class VertAlign(Enum):
    """Possible positions for overlay"""

    TOP = 0
    MIDDLE = 1
    BOTTOM = 2


class HorzAlign(Enum):
    """Possible positions for overlay"""

    LEFT = 0
    MIDDLE = 1
    RIGHT = 2


def get_h_align(in_str):
    """Get a HorzAlign or None, from a string"""
    assert isinstance(in_str, str)
    if in_str.lower() == "left":
        return HorzAlign.LEFT
    elif in_str.lower() == "right":
        return HorzAlign.RIGHT
    elif in_str.lower() == "middle":
        return HorzAlign.MIDDLE
    elif in_str.lower() == "none":
        return HorzAlign.LEFT
    log.error("Unknown H Align : %s", in_str)
    return None


def get_v_align(in_str):
    """Get a VertAlign or None, from a string"""
    assert isinstance(in_str, str)
    if in_str.lower() == "top":
        return VertAlign.TOP
    elif in_str.lower() == "bottom":
        return VertAlign.BOTTOM
    elif in_str.lower() == "middle":
        return VertAlign.MIDDLE
    elif in_str.lower() == "none":
        return VertAlign.TOP
    log.error("Unknown V Align : %s", in_str)
    return None


class AmalgamationLayout(Gtk.LayoutManager):
    """A Layout manager to place all child widgets where they request, allowing overlapping"""

    # pylint: disable=W0221
    def do_allocate(self, widget, width, height, _baseline):
        child = widget.get_first_child()
        while child:
            (h_a, v_a) = child.get_align()
            vert = child.measure(Gtk.Orientation.VERTICAL, width)
            horz = child.measure(Gtk.Orientation.HORIZONTAL, height)
            pref_w = horz[0]
            pref_h = vert[0]
            if pref_w > width:
                pref_w = width

            alloc = Gdk.Rectangle()
            if h_a == HorzAlign.LEFT:
                alloc.x = 0
            elif h_a == HorzAlign.MIDDLE:
                alloc.x = width / 2 - int(pref_w / 2)
            else:
                alloc.x = width - pref_w
            if v_a == VertAlign.TOP:
                alloc.y = 0
            elif v_a == HorzAlign.MIDDLE:
                alloc.y = height / 2 - int(pref_h / 2)
            else:
                alloc.y = height - pref_h
            alloc.width = pref_w
            alloc.height = pref_h
            child.size_allocate(alloc, -1)
            child = child.get_next_sibling()

    # pylint: disable=W0221,W0613
    def do_measure(self, widget, orientation, for_size):
        (_screen_x, _screen_y, screen_width, screen_height) = (
            widget.get_parent().get_display_coords()
        )

        if orientation == Gtk.Orientation.VERTICAL:
            return (screen_height, screen_height, -1, -1)
        else:
            return (screen_width, screen_width, -1, -1)


class NotificationLayout(Gtk.LayoutManager):
    """A Layout manager to lay out a single notification widget"""

    # pylint: disable=W0221
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

    # pylint: disable=W0221,W0613
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


class MessageBoxLayout(Gtk.LayoutManager):
    """A Layout manager to lay out a message box, which places messages newest at the bottom and crops at a preset height"""

    # pylint: disable=W0221
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

    # pylint: disable=W0221,W0613
    def do_measure(self, widget, orientation, _for_size):
        if orientation == Gtk.Orientation.VERTICAL:
            return (widget.height_limit, widget.height_limit, -1, -1)
        else:
            return (widget.width_limit, widget.width_limit, -1, -1)


class UserBoxLayout(Gtk.LayoutManager):
    """A Layout manager to lay out a userbox in voice overlay"""

    # pylint: disable=W0221
    def do_allocate(self, widget, width, height, _baseline):
        direction = Direction(widget.overlay.text_side)
        asize = widget.overlay.avatar_size
        img_alloc = Gdk.Rectangle()
        lbl_alloc = Gdk.Rectangle()

        img_alloc.width = img_alloc.height = asize
        if direction == Direction.LTR:
            img_alloc.y = height / 2 - int(asize / 2)
            img_alloc.x = lbl_alloc.y = 0
            lbl_alloc.x = asize
            lbl_alloc.height = height
            lbl_alloc.width = width - asize
        elif direction == Direction.RTL:
            img_alloc.y = height / 2 - int(asize / 2)
            lbl_alloc.x = lbl_alloc.y = 0
            lbl_alloc.height = height
            lbl_alloc.width = img_alloc.x = width - asize
        elif direction == Direction.TTB:
            img_alloc.x = width / 2 - int(asize / 2)
            img_alloc.y = lbl_alloc.x = 0
            lbl_alloc.y = asize
            lbl_alloc.width = width
            lbl_alloc.height = height - asize
        else:
            img_alloc.x = width / 2 - int(asize / 2)
            img_alloc.y = lbl_alloc.height = height - asize
            lbl_alloc.x = lbl_alloc.y = 0
            lbl_alloc.width = width

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
        widget.mute.size_allocate(img_alloc, -1)
        widget.deaf.size_allocate(img_alloc, -1)

    # pylint: disable=W0221,W0613
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
