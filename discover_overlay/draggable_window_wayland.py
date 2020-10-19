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
"""A Wayland full-screen window which can be moved and resized"""
import cairo
import gi
gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position
from gi.repository import Gtk, Gdk
try:
    from gi.repository import GtkLayerShell
except ImportError:
    pass


class DraggableWindowWayland(Gtk.Window):
    """A Wayland full-screen window which can be moved and resized"""

    def __init__(self, x=0, y=0, w=300, h=300, message="Message", settings=None):
        Gtk.Window.__init__(self, type=Gtk.WindowType.TOPLEVEL)
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

        self.set_app_paintable(True)
        self.monitor = 0

        self.drag_type = None
        self.drag_x = 0
        self.drag_y = 0
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)

        self.show_all()
        # self.force_location()

    def force_location(self):
        """Move the window to previously given co-ords. In wayland just clip to current screen"""
        (size_x, size_y) = self.get_size()
        if self.x < 0:
            self.x = 0
        if self.y < 0:
            self.y = 0
        if self.x + self.w > size_x:
            self.x = size_x - self.w
        if self.y + self.h > size_y:
            self.y = size_y - self.h
        self.queue_draw()

    def drag(self, _w, event):
        """Called by GTK while mouse is moving over window. Used to resize and move"""
        if event.state & Gdk.ModifierType.BUTTON1_MASK:
            if self.drag_type == 1:
                # Center is move
                self.x += event.x - self.drag_x
                self.y += event.y - self.drag_y
                self.drag_x = event.x
                self.drag_y = event.y

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

    def button_press(self, _w, event):
        """Called when a mouse button is pressed on this window"""
        px = event.x - self.x
        py = event.y - self.y

        if not self.drag_type:
            self.drag_type = 1
            # Where in the window did we press?
            if px < 20 and py < 20:
                self.settings.change_placement(None)
            if py > self.h - 32:
                self.drag_type += 2
            if px > self.w - 32:
                self.drag_type += 1
            self.drag_x = event.x
            self.drag_y = event.y

    def button_release(self, _w, _event):
        """Called when a mouse button is released"""
        self.drag_type = None

    def dodraw(self, _widget, context):
        """Draw our window. For wayland we're secretly a fullscreen app and need to draw only a single rectangle of the overlay"""
        context.translate(self.x, self.y)
        context.save()
        context.rectangle(0, 0, self.w, self.h)
        context.clip()

        context.set_source_rgba(1.0, 1.0, 0.0, 0.7)
        # Don't layer drawing over each other, always replace
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        # Get size of window

        # Draw text
        context.set_source_rgba(0.0, 0.0, 0.0, 1.0)
        _xb, _yb, width, height, _dx, _dy = context.text_extents(self.message)
        context.move_to(self.w / 2 - width / 2, self.h / 2 - height / 2)
        context.show_text(self.message)

        # Draw resizing edges
        context.set_source_rgba(0.0, 0.0, 1.0, 0.5)
        context.rectangle(self.w - 32, 0, 32, self.h)
        context.fill()

        context.rectangle(0, self.h - 32, self.w, 32)
        context.fill()

        # Draw Done!
        context.set_source_rgba(0.0, 1.0, 0.0, 0.5)
        context.rectangle(0, 0, 20, 20)
        context.fill()
        context.restore()

    def get_coords(self):
        """Return the position and size of the window"""
        return (self.x, self.y, self.w, self.h)
