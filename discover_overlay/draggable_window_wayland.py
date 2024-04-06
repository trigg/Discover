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
import logging
gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position
from gi.repository import Gtk, Gdk  # nopep8
try:
    gi.require_version('GtkLayerShell', '0.1')
    from gi.repository import GtkLayerShell
except (ImportError, ValueError):
    GtkLayerShell = None
    pass

log = logging.getLogger(__name__)


class DraggableWindowWayland(Gtk.Window):
    """A Wayland full-screen window which can be moved and resized"""

    def __init__(self, pos_x=0.0, pos_y=0.0, width=0.1, height=0.1, message="Message", settings=None, steamos=False, monitor=None):
        Gtk.Window.__init__(self, type=Gtk.WindowType.TOPLEVEL)
        if steamos:
            monitor = 0
        self.monitor = monitor
        (screen_x, screen_y, screen_width, screen_height) = self.get_display_coords()
        self.pos_x = pos_x * screen_width
        self.pos_y = pos_y * screen_height
        self.width = max(40, width * screen_width)
        self.height = max(40, height * screen_height)
        self.settings = settings
        self.message = message
        self.set_size_request(50, 50)

        self.connect('draw', self.dodraw)
        self.connect('motion-notify-event', self.drag)
        self.connect('button-press-event', self.button_press)
        self.connect('button-release-event', self.button_release)

        log.info("Starting: %d,%d %d x %d" %
                 (self.pos_x, self.pos_y, self.width, self.height))

        self.set_app_paintable(True)

        self.drag_type = None
        self.drag_x = 0
        self.drag_y = 0
        if GtkLayerShell and not steamos:
            GtkLayerShell.init_for_window(self)
            display = Gdk.Display.get_default()
            if "get_monitor" in dir(display):
                monitor = display.get_monitor(self.monitor)
                if monitor:
                    GtkLayerShell.set_monitor(self, monitor)
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        if steamos:
            self.steamos = steamos
            self.set_steamos_window_size()

        self.show_all()
        self.force_location()

    def set_steamos_window_size(self):
        # Huge bunch of assumptions.
        # Gamescope only has one monitor
        # Gamescope has no scale factor
        display = Gdk.Display.get_default()
        if "get_monitor" in dir(display):
            monitor = display.get_monitor(0)
            if monitor:
                geometry = monitor.get_geometry()
                scale_factor = monitor.get_scale_factor()
                log.info("%d %d" % (geometry.width, geometry.height))
                self.set_size_request(geometry.width, geometry.height)

    def force_location(self):
        """Move the window to previously given co-ords. In wayland just clip to current screen"""
        (screen_x, screen_y, screen_width, screen_height) = self.get_display_coords()
        self.width = min(self.width, screen_width)
        self.height = min(self.height, screen_height)
        self.pos_x = max(0, self.pos_x)
        self.pos_x = min(screen_width - self.width, self.pos_x)
        self.pos_y = max(0, self.pos_y)
        self.pos_y = min(screen_height - self.height, self.pos_y)

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
            elif self.drag_type == 4:
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
                self.settings.change_placement(self)
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

    def get_display_coords(self):
        display = Gdk.Display.get_default()
        if "get_monitor" in dir(display):
            monitor = display.get_monitor(self.monitor)
            if monitor:
                geometry = monitor.get_geometry()
                return (geometry.x, geometry.y, geometry.width, geometry.height)
        return (0, 0, 1920, 1080)  # We're in trouble

    def get_coords(self):
        """Return the position and size of the window"""
        (screen_x, screen_y, screen_width, screen_height) = self.get_display_coords()
        return (float(self.pos_x) / screen_width, float(self.pos_y) / screen_height, float(self.width) / screen_width, float(self.height) / screen_height)
