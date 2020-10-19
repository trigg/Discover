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
"""An X11 window which can be moved and resized"""
import gi
import cairo
gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position
from gi.repository import Gtk, Gdk


class DraggableWindow(Gtk.Window):
    """An X11 window which can be moved and resized"""

    def __init__(self, x=0, y=0, w=300, h=300, message="Message", settings=None):
        Gtk.Window.__init__(self, type=Gtk.WindowType.POPUP)
        if w < 100:
            w = 100
        if h < 100:
            h = 100
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.settings = settings
        self.message = message
        self.set_size_request(50, 50)

        self.connect('draw', self.dodraw)
        self.connect('motion-notify-event', self.drag)
        self.connect('button-press-event', self.button_press)
        self.connect('button-release-event', self.button_release)

        self.compositing = False
        # Set RGBA
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            # Set the visual even if we can't use it right now
            self.set_visual(visual)
        if screen.is_composited():
            self.compositing = True

        self.set_app_paintable(True)
        self.monitor = 0

        self.drag_type = None
        self.drag_x = 0
        self.drag_y = 0
        self.force_location()
        self.show_all()

    def force_location(self):
        """Move the window to previously given co-ords. Also double check sanity on layer & decorations"""

        self.set_decorated(False)
        self.set_keep_above(True)
        self.move(self.x, self.y)
        self.resize(self.w, self.h)

    def drag(self, _w, event):
        """Called by GTK while mouse is moving over window. Used to resize and move"""
        if event.state & Gdk.ModifierType.BUTTON1_MASK:
            if self.drag_type == 1:
                # Center is move
                self.x = event.x_root - self.drag_x
                self.y = event.y_root - self.drag_y
                self.force_location()
            elif self.drag_type == 2:
                # Right edge
                self.w += event.x - self.drag_x
                self.drag_x = event.x
                self.force_location()
            elif self.drag_type == 3:
                # Bottom edge
                self.h += event.y - self.drag_y
                self.drag_y = event.y
                self.force_location()
            else:
                # Bottom Right
                self.w += event.x - self.drag_x
                self.h += event.y - self.drag_y
                self.drag_x = event.x
                self.drag_y = event.y
                self.force_location()

    def button_press(self, w, event):
        """Called when a mouse button is pressed on this window"""
        (w, h) = self.get_size()
        if not self.drag_type:
            self.drag_type = 1
            # Where in the window did we press?
            if event.y > h - 32:
                self.drag_type += 2
            if event.x > w - 32:
                self.drag_type += 1
            self.drag_x = event.x
            self.drag_y = event.y

    def button_release(self, _w, _event):
        """Called when a mouse button is released"""
        self.drag_type = None

    def dodraw(self, _widget, context):
        """Draw our window."""
        context.set_source_rgba(1.0, 1.0, 0.0, 0.7)
        # Don't layer drawing over each other, always replace
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        context.set_operator(cairo.OPERATOR_OVER)
        # Get size of window
        (sw, sh) = self.get_size()

        # Draw text
        context.set_source_rgba(0.0, 0.0, 0.0, 1.0)
        _xb, _yb, w, h, _dx, _dy = context.text_extents(self.message)
        context.move_to(sw / 2 - w / 2, sh / 2 - h / 2)
        context.show_text(self.message)

        # Draw resizing edges
        context.set_source_rgba(0.0, 0.0, 1.0, 0.5)
        context.rectangle(sw - 32, 0, 32, sh)
        context.fill()

        context.rectangle(0, sh - 32, sw, 32)
        context.fill()

    def get_coords(self):
        """Return window position and size"""
        (x, y) = self.get_position()
        (w, h) = self.get_size()
        return (x, y, w, h)
