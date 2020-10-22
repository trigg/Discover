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
    gi.require_version('GtkLayerShell', '0.1')
    from gi.repository import GtkLayerShell
except (ImportError, ValueError):
    pass


class DraggableWindowWayland(Gtk.Window):
    """A Wayland full-screen window which can be moved and resized"""

    def __init__(self, pos_x=0, pos_y=0, width=300, height=300, message="Message", settings=None):
        Gtk.Window.__init__(self, type=Gtk.WindowType.TOPLEVEL)
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.width = max(100, width)
        self.height = max(100, height)
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
        self.pos_x = max(0, self.pos_x)
        self.pos_x = min(size_x - self.width, self.pos_x)
        self.pos_y = max(0, self.pos_y)
        self.pos_y = min(size_y - self.height, self.pos_y)
        self.queue_draw()

    def drag(self, _w, event):
        """Called by GTK while mouse is moving over window. Used to resize and move"""
        if event.state & Gdk.ModifierType.BUTTON1_MASK:
            if self.drag_type == 1:
                # Center is move
                self.pos_x += event.x - self.drag_x
                self.pos_y += event.y - self.drag_y
                self.drag_x = event.x
                self.drag_y = event.y

                self.force_location()
            elif self.drag_type == 2:
                # Right edge
                self.width += event.x - self.drag_x
                self.drag_x = event.x
                self.force_location()
            elif self.drag_type == 3:
                # Bottom edge
                self.height += event.y - self.drag_y
                self.drag_y = event.y
                self.force_location()
            else:
                # Bottom Right
                self.width += event.x - self.drag_x
                self.height += event.y - self.drag_y
                self.drag_x = event.x
                self.drag_y = event.y
                self.force_location()

    def button_press(self, _w, event):
        """Called when a mouse button is pressed on this window"""
        press_x = event.x - self.pos_x
        press_y = event.y - self.pos_y

        if not self.drag_type:
            self.drag_type = 1
            # Where in the window did we press?
            if press_x < 20 and press_y < 20:
                self.settings.change_placement(None)
            if press_y > self.height - 32:
                self.drag_type += 2
            if press_x > self.width - 32:
                self.drag_type += 1
            self.drag_x = event.x
            self.drag_y = event.y

    def button_release(self, _w, _event):
        """Called when a mouse button is released"""
        self.drag_type = None

    def dodraw(self, _widget, context):
        """
        Draw our window. For wayland we're secretly a
        fullscreen app and need to draw only a single
        rectangle of the overlay
        """
        context.translate(self.pos_x, self.pos_y)
        context.save()
        context.rectangle(0, 0, self.width, self.height)
        context.clip()

        context.set_source_rgba(1.0, 1.0, 0.0, 0.7)
        # Don't layer drawing over each other, always replace
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        # Get size of window

        # Draw text
        context.set_source_rgba(0.0, 0.0, 0.0, 1.0)
        _xb, _yb, width, height, _dx, _dy = context.text_extents(self.message)
        context.move_to(self.width / 2 - width / 2,
                        self.height / 2 - height / 2)
        context.show_text(self.message)

        # Draw resizing edges
        context.set_source_rgba(0.0, 0.0, 1.0, 0.5)
        context.rectangle(self.width - 32, 0, 32, self.height)
        context.fill()

        context.rectangle(0, self.height - 32, self.width, 32)
        context.fill()

        # Draw Done!
        context.set_source_rgba(0.0, 1.0, 0.0, 0.5)
        context.rectangle(0, 0, 20, 20)
        context.fill()
        context.restore()

    def get_coords(self):
        """Return the position and size of the window"""
        return (self.pos_x, self.pos_y, self.width, self.height)
