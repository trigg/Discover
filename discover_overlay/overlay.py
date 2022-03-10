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
"""
Overlay parent class. Helpful if we need more overlay
types without copy-and-pasting too much code
"""
import sys
import logging
import gi
import cairo
import Xlib
from Xlib.display import Display
from Xlib import X, Xatom
gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Gtk, Gdk
try:
    gi.require_version('GtkLayerShell', '0.1')
    from gi.repository import GtkLayerShell
except (ImportError, ValueError):
    pass


class OverlayWindow(Gtk.Window):
    """
    Overlay parent class. Helpful if we need more overlay
    types without copy-and-pasting too much code
    """

    def detect_type(self):
        """
        Helper function to determine if Wayland is being used and return the Window type needed
        """
        window = Gtk.Window()
        screen = window.get_screen()
        screen_type = "%s" % (screen)
        self.is_wayland = False
        if "Wayland" in screen_type:
            self.is_wayland = True
            return Gtk.WindowType.TOPLEVEL
        return Gtk.WindowType.POPUP

    def __init__(self, discover):
        Gtk.Window.__init__(self, type=self.detect_type())
        self.discover = discover
        screen = self.get_screen()
        self.compositing = False
        self.text_font = None
        self.text_size = None
        self.pos_x = None
        self.pos_y = None
        self.width = None
        self.height = None
        self.needsredraw = True
        self.hidden = False
        self.enabled = False

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
        if discover.steamos:
            self.floating = False
            display = Display()
            atom = display.intern_atom("GAMESCOPE_EXTERNAL_OVERLAY")
            opaq = display.intern_atom("_NET_WM_WINDOW_OPACITY")

            topw = display.create_resource_object("window", self.get_toplevel().get_window().get_xid())

            topw.change_property(atom,
                                 Xatom.CARDINAL,32,
                                 [1], X.PropModeReplace)
            # Keep for reference, but appears to be unnecessary
            #topw.change_property(opaq,
            #                     Xatom.CARDINAL,16,
            #                     [0xffff], X.PropModeReplace)

            logging.info("Setting STEAM_EXTERNAL_OVERLAY")
            display.sync()
        self.monitor = 0
        self.align_right = True
        self.align_vert = 1
        self.floating = False
        self.force_xshape = False
        self.context = None
        self.autohide=False

    def set_wayland_state(self):
        """
        If wayland is in use then attempt to set up a GtkLayerShell
        I have no idea how this should register a fail for Weston/KDE/Gnome
        """
        if self.is_wayland:
            if not GtkLayerShell.is_supported():
                logging.info("GTK Layer Shell is not supported on this wayland compositor")
                logging.info("Currently not possible: Gnome, Plasma, Weston")
                sys.exit(0)
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)

    def overlay_draw(self, _w, context, data=None):
        """
        Draw overlay
        """

    def set_font(self, font):
        """
        Set the font used by the overlay
        """
        self.text_font = font
        self.needsredraw=True
        logging.info("set_font redraw")

    def set_floating(self, floating, pos_x, pos_y, width, height):
        """
        Set if the window is floating and what dimensions to use
        """
        
        self.floating = floating
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.width = width
        self.height = height
        if self.discover.steamos:
            self.floating = False
        self.force_location()

    def set_untouchable(self):
        """
        Create a custom input shape and tell it that all of the window is a cut-out
        This allows us to have a window above everything but that never gets clicked on
        """
        (width, height) = self.get_size()
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        surface_ctx = cairo.Context(surface)
        surface_ctx.set_source_rgba(0.0, 0.0, 0.0, 0.0)
        surface_ctx.set_operator(cairo.OPERATOR_SOURCE)
        surface_ctx.paint()
        reg = Gdk.cairo_region_create_from_surface(surface)
        self.input_shape_combine_region(reg)

    def unset_shape(self):
        """
        Remove XShape (not input shape)
        """
        self.get_window().shape_combine_region(None, 0, 0)

    def force_location(self):
        """
        On X11 enforce the location and sane defaults
        On Wayland just store for later
        """
        if not self.is_wayland:
            self.set_decorated(False)
            self.set_keep_above(True)
            display = Gdk.Display.get_default()
            if "get_monitor" in dir(display):
                monitor = display.get_monitor(self.monitor)
                geometry = monitor.get_geometry()
                scale_factor = monitor.get_scale_factor()
                if not self.floating:
                    width = geometry.width
                    height = geometry.height
                    pos_x = geometry.x
                    pos_y = geometry.y
                    self.resize(width, height)
                    self.move(pos_x, pos_y)
                else:
                    self.move(self.pos_x, self.pos_y)
                    self.resize(self.width, self.height)
            else:
                if self.floating:
                    self.move(self.pos_x, self.pos_y)
                    self.resize(self.width, self.height)

        if not self.floating:
            (width, height) = self.get_size()
            self.width = width
            self.height = height
        self.needsredraw = True

    def redraw(self):
        """
        Request a redraw.
        If we're using XShape (optionally or forcibly) then render the image into the shape
        so that we only cut out clear sections
        """
        self.needsredraw = False
        gdkwin = self.get_window()
        if not self.floating:
            (width, height) = self.get_size()
            self.width = width
            self.height = height
        if gdkwin:
            if not self.compositing or self.force_xshape:
                (width, height) = self.get_size()
                surface = cairo.ImageSurface(
                    cairo.FORMAT_ARGB32, width, height)
                surface_ctx = cairo.Context(surface)
                self.overlay_draw(None, surface_ctx)
                reg = Gdk.cairo_region_create_from_surface(surface)
                gdkwin.shape_combine_region(reg, 0, 0)
            else:
                gdkwin.shape_combine_region(None, 0, 0)
        self.queue_draw()

    def set_hidden(self, hidden):
        self.hidden = hidden
        self.set_enabled(self.enabled)

    def set_monitor(self, idx=None, mon=None):
        """
        Set the monitor this overlay should display on.
        """
        self.monitor = idx
        if self.is_wayland:
            if mon:
                GtkLayerShell.set_monitor(self, mon)
        self.force_location()
        self.needsredraw = True
        logging.info("set_monitor redraw")


    def set_align_x(self, align_right):
        """
        Set the alignment (True for right, False for left)
        """
        self.align_right = align_right
        self.force_location()
        self.needsredraw = True
        logging.info("set_align_x redraw")


    def set_align_y(self, align_vert):
        """
        Set the veritcal alignment
        """
        self.align_vert = align_vert
        self.force_location()
        self.needsredraw = True
        logging.info("set_align_y redraw")


    def col(self, col, alpha=1.0):
        """
        Convenience function to set the cairo context next colour
        """
        self.context.set_source_rgba(col[0], col[1], col[2], col[3] * alpha)

    def set_force_xshape(self, force):
        """
        Set if XShape should be forced
        """
        self.force_xshape = force

        if self.is_wayland:
            # Wayland and XShape are a bad idea unless you're a fan on artifacts
            self.force_xshape = False

    def set_enabled(self, enabled):
        """
        Set if this overlay should be visible
        """
        self.enabled = enabled
        if enabled and not self.hidden:
            self.show_all()
        else:
            self.hide()

    def set_hide_on_mouseover(self, hide):
        """
        Set Mouseover hide
        """
        self.autohide = hide
