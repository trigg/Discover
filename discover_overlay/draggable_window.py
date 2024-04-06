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
import logging
gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position
from gi.repository import Gtk, Gdk  # nopep8

log = logging.getLogger(__name__)


class DraggableWindow(Gtk.Window):
    """An X11 window which can be moved and resized"""

    def __init__(self, pos_x=0.0, pos_y=0.0, width=0.1, height=0.1, message="Message", settings=None, monitor=None):
        Gtk.Window.__init__(self, type=Gtk.WindowType.POPUP)
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

        self.drag_type = None
        self.drag_x = 0
        self.drag_y = 0
        self.force_location()
        self.show_all()

    def force_location(self):
        """
        Move the window to previously given co-ords.
        Also double check sanity on layer & decorations
        """
        self.set_decorated(False)
        self.set_keep_above(True)

        (screen_x, screen_y, screen_width, screen_height) = self.get_display_coords()

        self.width = min(self.width, screen_width)
        self.height = min(self.height, screen_height)
        self.pos_x = max(0, self.pos_x)
        self.pos_x = min(screen_width - self.width, self.pos_x)
        self.pos_y = max(0, self.pos_y)
        self.pos_y = min(screen_height - self.height, self.pos_y)

        self.move(self.pos_x + screen_x, self.pos_y + screen_y)
        self.resize(self.width, self.height)

    def drag(self, _w, event):
        """Called by GTK while mouse is moving over window. Used to resize and move"""
        if event.state & Gdk.ModifierType.BUTTON1_MASK:
            if self.drag_type == 1:
                # Center is move
                (screen_x, screen_y, screen_width,
                 screen_height) = self.get_display_coords()
                self.pos_x = (event.x_root - screen_x) - self.drag_x
                self.pos_y = (event.y_root - screen_y) - self.drag_y
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

    def button_press(self, _widget, event):
        """Called when a mouse button is pressed on this window"""
        (width, height) = self.get_size()
        if not self.drag_type:
            self.drag_type = 1
            # Where in the window did we press?
            if event.y > height - 32:
                self.drag_type += 2
            if event.x > width - 32:
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
        (window_width, window_height) = self.get_size()

        # Draw text
        context.set_source_rgba(0.0, 0.0, 0.0, 1.0)
        _xb, _yb, text_width, text_height, _dx, _dy = context.text_extents(
            self.message)
        context.move_to(window_width / 2 - text_width / 2,
                        window_height / 2 - text_height / 2)
        context.show_text(self.message)

        # Draw resizing edges
        context.set_source_rgba(0.0, 0.0, 1.0, 0.5)
        context.rectangle(window_width - 32, 0, 32, window_height)
        context.fill()

        context.rectangle(0, window_height - 32, window_width, 32)
        context.fill()

    def get_display_coords(self):
        display = Gdk.Display.get_default()
        if "get_monitor" in dir(display):
            monitor = display.get_monitor(self.monitor)
            if monitor:
                geometry = monitor.get_geometry()
                return (geometry.x, geometry.y, geometry.width, geometry.height)
        return (0, 0, 1920, 1080)  # We're in trouble

    def get_coords(self):
        """Return window position and size"""
        (screen_x, screen_y, screen_width, screen_height) = self.get_display_coords()
        scale = self.get_scale_factor()
        (pos_x, pos_y) = self.get_position()
        pos_x = float(max(0, pos_x - screen_x))
        pos_y = float(max(0, pos_y - screen_y))
        (width, height) = self.get_size()
        width = float(width)
        height = float(height)
        pos_x = pos_x / scale
        pos_y = pos_y / scale
        return (pos_x / screen_width, pos_y / screen_height, width / screen_width, height / screen_height)
