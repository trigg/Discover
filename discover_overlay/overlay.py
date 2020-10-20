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
"""Overlay parent class. Helpful if we need more overlay types without copy-and-pasting too much code"""
import sys
import logging
import gi
import cairo
gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position
from gi.repository import Gtk, Gdk
try:
    from gi.repository import GtkLayerShell
except ImportError:
    pass


class OverlayWindow(Gtk.Window):
    """Overlay parent class. Helpful if we need more overlay types without copy-and-pasting too much code"""

    def detect_type(self):
        window = Gtk.Window()
        screen = window.get_screen()
        screen_type = "%s" % (screen)
        self.is_wayland = False
        if "Wayland" in screen_type:
            self.is_wayland = True
            return Gtk.WindowType.TOPLEVEL
        return Gtk.WindowType.POPUP

    def __init__(self):
        Gtk.Window.__init__(self, type=self.detect_type())
        screen = self.get_screen()
        self.compositing = False
        self.text_font = None
        self.text_size = None
        self.x = None
        self.y = None
        self.w = None
        self.h = None

        self.set_size_request(50, 50)
        self.connect('draw', self.overlay_draw)
        # Set RGBA
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if not self.get_display().supports_input_shapes():
            logging.info(
                "Input shapes not available. Quitting")
            sys.exit(1)
        if visual:
            # Set the visual even if we can't use it right now
            self.set_visual(visual)
        if screen.is_composited():
            self.compositing = True

        self.set_app_paintable(True)
        self.set_untouchable()
        self.set_skip_pager_hint(True)
        self.set_skip_taskbar_hint(True)
        self.set_keep_above(True)
        self.set_decorated(True)
        self.set_accept_focus(False)
        self.set_wayland_state()

        self.show_all()
        self.monitor = 0
        self.align_right = True
        self.align_vert = 1
        self.floating = False
        self.force_xshape = False
        self.context = None

    def set_wayland_state(self):
        if self.is_wayland:
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)

    def overlay_draw(self, _w, context, data=None):
        pass

    def set_font(self, name, size):
        self.text_font = name
        self.text_size = size
        self.redraw()

    def set_floating(self, floating, x, y, w, h):
        self.floating = floating
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.force_location()

    def set_untouchable(self):
        (w, h) = self.get_size()
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        surface_ctx = cairo.Context(surface)
        surface_ctx.set_source_rgba(0.0, 0.0, 0.0, 0.0)
        surface_ctx.set_operator(cairo.OPERATOR_SOURCE)
        surface_ctx.paint()
        reg = Gdk.cairo_region_create_from_surface(surface)
        self.input_shape_combine_region(reg)
        # self.shape_combine_region(reg)

    def unset_shape(self):
        self.get_window().shape_combine_region(None, 0, 0)

    def force_location(self):
        if not self.is_wayland:
            self.set_decorated(False)
            self.set_keep_above(True)
            display = Gdk.Display.get_default()
            if "get_monitor" in dir(display):
                monitor = display.get_monitor(self.monitor)
                geometry = monitor.get_geometry()
                scale_factor = monitor.get_scale_factor()
                if not self.floating:
                    w = scale_factor * geometry.width
                    h = scale_factor * geometry.height
                    x = geometry.x
                    y = geometry.y
                    self.resize(w, h)
                    self.move(x, y)
                else:
                    self.move(self.x, self.y)
                    self.resize(self.w, self.h)
            else:
                if not self.floating:
                    screen = display.get_default_screen()
                    w = screen.width()
                    h = screen.height()
                    x = 0
                    y = 0
                else:
                    self.move(self.x, self.y)
                    self.resize(self.w, self.h)

        if not self.floating:
            (w, h) = self.get_size()
            self.w = w
            self.h = h
        self.redraw()

    def redraw(self):
        gdkwin = self.get_window()
        if not self.floating:
            (w, h) = self.get_size()
            self.w = w
            self.h = h

        if gdkwin:
            if not self.compositing or self.force_xshape:
                (w, h) = self.get_size()
                surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
                surface_ctx = cairo.Context(surface)
                self.overlay_draw(None, surface_ctx)
                reg = Gdk.cairo_region_create_from_surface(surface)
                gdkwin.shape_combine_region(reg, 0, 0)
            else:
                gdkwin.shape_combine_region(None, 0, 0)
        self.queue_draw()

    def set_monitor(self, idx=None, mon=None):
        self.monitor = idx
        if self.is_wayland:
            if mon:
                GtkLayerShell.set_monitor(self, mon)
        self.force_location()
        self.redraw()

    def set_align_x(self, b):
        self.align_right = b
        self.force_location()
        self.redraw()

    def set_align_y(self, i):
        self.align_vert = i
        self.force_location()
        self.redraw()

    def col(self, c, a=1.0):
        self.context.set_source_rgba(c[0], c[1], c[2], c[3] * a)

    def set_force_xshape(self, force):
        self.force_xshape = force
