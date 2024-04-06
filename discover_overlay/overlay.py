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
import os
import sys
import logging
import gi
import cairo
import Xlib
from Xlib.display import Display
from Xlib import X, Xatom
gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Gtk, Gdk, GLib  # nopep8
try:
    gi.require_version('GtkLayerShell', '0.1')
    from gi.repository import GtkLayerShell
except (ImportError, ValueError):
    pass

log = logging.getLogger(__name__)


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

    def __init__(self, discover, piggyback=None):
        Gtk.Window.__init__(self, type=self.detect_type())
        self.is_xatom_set = False

        self.discover = discover
        screen = self.get_screen()
        self.text_font = None
        self.text_size = None
        self.pos_x = None
        self.pos_y = None
        self.width = None
        self.height = None
        self.hidden = False
        self.enabled = False
        self.set_size_request(50, 50)
        self.hide_on_mouseover = True
        self.connect('draw', self.overlay_draw_pre)
        # Set RGBA
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if not self.get_display().supports_input_shapes():
            log.info(
                "Input shapes not available. Quitting")
            sys.exit(1)
        if visual:
            # Set the visual even if we can't use it right now
            self.set_visual(visual)

        self.set_app_paintable(True)
        self.set_untouchable()
        self.set_skip_pager_hint(True)
        self.set_skip_taskbar_hint(True)
        self.set_keep_above(True)
        self.set_decorated(True)
        self.set_accept_focus(False)
        self.set_wayland_state()
        self.piggyback = None
        self.piggyback_parent = None
        if not piggyback:
            self.show_all()
            if discover.steamos:
                self.set_gamescope_xatom(1)
        self.monitor = 0
        self.align_right = True
        self.align_vert = 1
        self.floating = False
        self.force_xshape = False
        self.context = None

        self.redraw_id = None
        self.draw_blank = False
        self.timeout_mouse_over = 1

        self.timer_after_draw = None
        if piggyback:
            self.set_piggyback(piggyback)

        self.get_screen().connect("composited-changed", self.check_composite)
        self.get_screen().connect("monitors-changed", self.screen_changed)
        self.get_screen().connect("size-changed", self.screen_changed)
        if self.get_window():
            self.get_window().set_events(self.get_window().get_events()
                                         | Gdk.EventMask.ENTER_NOTIFY_MASK)
        self.connect("enter-notify-event", self.mouseover)
        self.connect("leave-notify-event", self.mouseout)
        self.mouse_over_timer = None

        # It shouldn't be possible, but let's not leave
        # this process hanging if it happens
        self.connect('destroy', self.window_exited)

    def window_exited(self, window=None):
        sys.exit(1)

    def set_gamescope_xatom(self, enabled):
        if self.piggyback_parent:
            return

        if enabled == self.is_xatom_set:
            return
        self.is_xatom_set = enabled
        display = Display()
        atom = display.intern_atom("GAMESCOPE_EXTERNAL_OVERLAY")
        opaq = display.intern_atom("_NET_WM_WINDOW_OPACITY")

        if self.get_toplevel().get_window():
            topw = display.create_resource_object(
                "window", self.get_toplevel().get_window().get_xid())

            topw.change_property(atom,
                                 Xatom.CARDINAL, 32,
                                 [enabled], X.PropModeReplace)
            log.info("Setting GAMESCOPE_EXTERNAL_OVERLAY to %s", enabled)
            display.sync()
        else:
            log.warn("Unable to set GAMESCOPE_EXTERNAL_OVERLAY")

    def set_wayland_state(self):
        """
        If wayland is in use then attempt to set up a GtkLayerShell
        """
        if self.is_wayland:
            if not GtkLayerShell.is_supported():
                log.info(
                    "GTK Layer Shell is not supported on this wayland compositor")
                log.info("Currently not possible: Gnome, Weston")
                sys.exit(0)
            if not GtkLayerShell.is_layer_window(self):
                GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)

    def set_piggyback(self, other_overlay):
        other_overlay.piggyback = self
        self.piggyback_parent = other_overlay

    def has_content(self):
        return False

    def overlay_draw_pre(self, _w, context, data=None):
        content = self.has_content()
        if self.piggyback and self.piggyback.has_content():
            content = True
        if self.discover.steamos:
            if not content:
                self.set_gamescope_xatom(0)
            else:
                if not self.hidden and self.enabled:
                    self.set_gamescope_xatom(1)
        # If we're hiding on mouseover, allow mouse-in
        if self.hide_on_mouseover:
            # We've mouse-overed
            if self.draw_blank:
                self.set_untouchable()
                context.set_source_rgba(0.0, 0.0, 0.0, 0.0)
                context.set_operator(cairo.OPERATOR_SOURCE)
                context.paint()
                return
            else:
                (width, height) = self.get_size()
                surface = cairo.ImageSurface(
                    cairo.FORMAT_ARGB32, width, height)
                surface_ctx = cairo.Context(surface)
                self.overlay_draw(None, surface_ctx)
                reg = Gdk.cairo_region_create_from_surface(surface)
                self.input_shape_combine_region(reg)

        self.overlay_draw(_w, context, data)

    def overlay_draw(self, _w, context, data=None):
        """
        Draw overlay
        """

    def set_font(self, font):
        """
        Set the font used by the overlay
        """
        if self.text_font != font:
            self.text_font = font
            self.set_needs_redraw()

    def set_floating(self, floating, pos_x, pos_y, width, height):
        """
        Set if the window is floating and what dimensions to use
        """
        if width > 1.0 and height > 1.0:
            # Old data.
            (screen_x, screen_y, screen_width,
             screen_height) = self.get_display_coords()
            pos_x = float(pos_x) / screen_width
            pos_y = float(pos_y) / screen_height
            width = float(width) / screen_width
            height = float(height) / screen_height

        if self.floating != floating or self.pos_x != pos_x or self.pos_y != pos_y or self.width != width or self.height != height:
            # Special case for Cinnamon desktop : see https://github.com/trigg/Discover/issues/322
            if 'XDG_SESSION_DESKTOP' in os.environ and os.environ['XDG_SESSION_DESKTOP'] == 'cinnamon':
                floating = True

            self.floating = floating
            self.pos_x = pos_x
            self.pos_y = pos_y
            self.width = width
            self.height = height
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

    def set_hide_on_mouseover(self, hide):
        if self.hide_on_mouseover != hide:
            self.hide_on_mouseover = hide
            if self.hide_on_mouseover:
                self.set_needs_redraw()
            else:
                self.set_untouchable()

    def set_mouseover_timer(self, time):
        self.timeout_mouse_over = time

    def unset_shape(self):
        """
        Remove XShape (not input shape)
        """
        if self.get_window():
            self.get_window().shape_combine_region(None, 0, 0)

    def force_location(self):
        """
        On X11 enforce the location and sane defaults
        On Wayland just store for later
        On Gamescope enforce size of display but only if it's the primary overlay
        """
        if self.discover.steamos and not self.piggyback_parent:
            (floating_x, floating_y, floating_width,
             floating_height) = self.get_floating_coords()
            self.resize(floating_width, floating_height)
            self.set_needs_redraw()
            return
        if not self.is_wayland:
            self.set_decorated(False)
            self.set_keep_above(True)

            (floating_x, floating_y, floating_width,
             floating_height) = self.get_floating_coords()
            self.resize(floating_width, floating_height)
            self.move(floating_x, floating_y)

        self.set_needs_redraw()

    def get_display_coords(self):
        if self.piggyback_parent:
            return self.piggyback_parent.get_display_coords()
        display = Gdk.Display.get_default()
        if "get_monitor" in dir(display):
            if self.monitor == None or self.monitor < 0:
                monitor = display.get_monitor(0)
            else:
                monitor = display.get_monitor(self.monitor)
            if monitor:
                geometry = monitor.get_geometry()
                return (geometry.x, geometry.y, geometry.width, geometry.height)
        log.warn("No monitor found! This is going to go badly")
        return (0, 0, 1920, 1080)  # We're in trouble

    def get_floating_coords(self):
        (screen_x, screen_y, screen_width, screen_height) = self.get_display_coords()
        if self.floating:
            if self.pos_x == None or self.pos_y == None or self.width == None or self.height == None:
                log.error("No usable floating position")

            if not self.is_wayland:
                return (screen_x + self.pos_x * screen_width, screen_y + self.pos_y * screen_height, self.width * screen_width, self.height * screen_height)
            return (self.pos_x * screen_width, self.pos_y * screen_height, self.width * screen_width, self.height * screen_height)
        else:
            return (0, 0, screen_width, screen_height)

    def set_needs_redraw(self, be_pushy=False):
        if (not self.hidden and self.enabled) or be_pushy:
            if self.piggyback_parent:
                self.piggyback_parent.set_needs_redraw(be_pushy=True)

            if self.redraw_id == None:
                self.redraw_id = GLib.idle_add(self.redraw)
            else:
                log.debug("Already awaiting paint")

            # If this overlay has data that expires after draw, plan for that here
            if self.timer_after_draw != None:
                GLib.timeout_add_seconds(self.timer_after_draw, self.redraw)

    def redraw(self):
        """
        Request a redraw.
        If we're using XShape (optionally or forcibly) then render the image into the shape
        so that we only cut out clear sections
        """
        self.redraw_id = None
        gdkwin = self.get_window()
        if self.piggyback_parent:
            self.piggyback_parent.redraw()
            return
        if gdkwin:
            compositing = self.get_screen().is_composited()
            if not compositing or self.force_xshape:
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
        self.redraw_id = None
        return False

    def set_hidden(self, hidden):
        self.hidden = hidden
        self.set_enabled(self.enabled)

    def set_monitor(self, idx=None):
        """
        Set the monitor this overlay should display on.
        """
        if type(idx) is str:
            idx = 0
        if self.monitor != idx:
            self.monitor = idx
            if self.is_wayland:
                display = Gdk.Display.get_default()
                if "get_monitor" in dir(display):
                    monitor = display.get_monitor(self.monitor)
                    if monitor:
                        GtkLayerShell.set_monitor(self, monitor)
                    else:
                        self.hide()
                        self.set_wayland_state()
                        self.show()
                else:
                    log.error("No get_monitor in display")
                self.set_untouchable()
            self.force_location()
            self.set_needs_redraw()

    def set_align_x(self, align_right):
        """
        Set the alignment (True for right, False for left)
        """
        if self.align_right != align_right:
            self.align_right = align_right
            self.force_location()
            self.set_needs_redraw()

    def set_align_y(self, align_vert):
        """
        Set the veritcal alignment
        """
        if self.align_vert != align_vert:
            self.align_vert = align_vert
            self.force_location()
            self.set_needs_redraw()

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

        if self.is_wayland or self.discover.steamos:
            # Wayland and XShape are a bad idea unless you're a fan on artifacts
            self.force_xshape = False

    def set_enabled(self, enabled):
        """
        Set if this overlay should be visible
        """
        self.enabled = enabled
        if self.piggyback_parent or self.piggyback:
            self.set_needs_redraw()

            if not self.piggyback_parent:
                self.set_gamescope_xatom(1 if enabled else 0)
            return
        if enabled and not self.hidden:
            self.show_all()
            self.set_untouchable()
        else:
            self.hide()

    def set_task(self, visible):
        self.set_skip_pager_hint(not visible)
        self.set_skip_taskbar_hint(not visible)

    def check_composite(self, _a=None, _b=None):
        # Called when an X11 session switched compositing on or off
        self.redraw()

    def screen_changed(self, screen=None):
        self.set_monitor(self.monitor)

    def mouseover(self, a=None, b=None):
        self.draw_blank = True
        self.set_needs_redraw()
        return True

    def mouseout(self, a=None, b=None):
        GLib.timeout_add_seconds(self.timeout_mouse_over, self.mouseout_timed)
        return True

    def mouseout_timed(self, a=None, b=None):
        self.draw_blank = False
        self.set_needs_redraw()
        return False
