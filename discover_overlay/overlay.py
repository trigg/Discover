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
from ctypes import CDLL

CDLL("libgtk4-layer-shell.so")
from enum import Enum
import logging
import gi
import cairo
from Xlib.display import Display
from Xlib import X, Xatom
from ewmh import EWMH
from .css_helper import font_string_to_css_font_string

gi.require_version("Gtk", "4.0")
gi.require_version("GdkWayland", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")

from gi.repository import Gtk, Gdk, GLib, GdkX11, GdkWayland, Gtk4LayerShell

log = logging.getLogger(__name__)


class Direction(Enum):
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
    log.error("Unknown V Align : %s", in_str)
    return None


class AmalgamationLayout(Gtk.LayoutManager):

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

    def do_measure(self, widget, orientation, for_size):
        (screen_x, screen_y, screen_width, screen_height) = (
            widget.get_parent().get_display_coords()
        )

        if orientation == Gtk.Orientation.VERTICAL:
            return (screen_height, screen_height, -1, -1)
        else:
            return (screen_width, screen_width, -1, -1)


class OverlayWindow(Gtk.Window):
    """
    Overlay parent class. Helpful if we need more overlay
    types without copy-and-pasting too much code
    """

    def __init__(self, discover):
        Gtk.Window.__init__(self)
        self.css_prov = {}

        self.set_css(
            "transparent_background", "window { background-color: rgba(0,0,0,0.0); }"
        )
        self.is_xatom_set = False

        self.widget = None
        self.amalgamation = None

        self.discover = discover
        self.pos_x = None
        self.pos_y = None
        self.width = None
        self.height = None
        self.hidden = False
        self.enabled = False
        self.width_limit = -1
        self.height_limit = -1
        self.hide_on_mouseover = True
        if not self.get_display().supports_input_shapes():
            log.info("Input shapes not available. Quitting")
            self.discover.exit()

        self.horzalign = HorzAlign.LEFT
        self.vertalign = VertAlign.TOP
        self.monitor = "Any"
        self.context = None

        self.redraw_id = None
        self.draw_blank = False
        self.timeout_mouse_over = 1

        self.timer_after_draw = None

        self.get_display().connect("setting-changed", self.screen_changed)
        # TODO Find compositor-change for GTK4. Currently only checks once at start
        # self.connect("composited-changed", self.check_composite)

        self.get_display().get_monitors().connect("items-changed", self.screen_changed)

        # TODO Find monitor resize hook for GTK4
        # self.get_display().connect("size-changed", self.screen_changed)

        # TODO GTK4 mouse events
        # if self.get_window():
        #    self.get_window().set_events(self.get_window().get_events()
        #                                 | Gdk.EventMask.ENTER_NOTIFY_MASK)
        # self.connect("enter-notify-event", self.mouseover)
        # self.connect("leave-notify-event", self.mouseout)

        # TODO Find size-allocate for GTK4
        # self.connect("size-allocate", self.set_untouchable)
        self.mouse_over_timer = None

        # It shouldn't be possible, but let's not leave
        # this process hanging if it happens
        self.connect("destroy", self.window_exited)

    def remove_css(self, cssid):
        """Removes a CSS Rule by id"""
        if id in self.css_prov:
            self.get_style_context().remove_provider(self.css_prov[id])
            del self.css_prov[cssid]

    def set_css(self, cssid, rules):
        """Create or update a CSS rule by id"""
        if id not in self.css_prov:

            # pylint: disable=E1120
            css = Gtk.CssProvider.new()
            # log.info("Adding rule : %s", rules)
            css.load_from_data(bytes(rules, "utf-8"))
            self.get_style_context().add_provider_for_display(
                self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER
            )
            self.css_prov[cssid] = css
        else:
            log.info("Updating rule : %s", rules)
            self.css_prov[cssid].load_from_data(bytes(rules, "utf-8"))

    def window_exited(self, _window=None):
        """Window closed. Exit app"""
        self.discover.exit()

    def set_x11_window_location(self, x, y):
        """Set Window location using X11"""
        if isinstance(self.get_surface(), GdkX11.X11Surface):
            display = Display()
            topw = display.create_resource_object(
                "window", self.get_surface().get_xid()
            )

            topw.configure(x=x, y=y)
            screen = display.screen()
            ewmh = EWMH(display, screen.root)
            ewmh.setWmState(topw, 1, "_NET_WM_STATE_ABOVE")
            display.flush()
            display.sync()
        else:
            log.warning("Unable to set X11 location")

    def set_gamescope_xatom(self, enabled):
        """Set Gamescope XAtom to identify self as an overlay candidate"""

        if enabled == self.is_xatom_set:
            return
        self.is_xatom_set = enabled
        display = Display()
        atom = display.intern_atom("GAMESCOPE_EXTERNAL_OVERLAY")
        # pylint: disable=E1101
        if isinstance(self.get_surface(), GdkX11.X11Surface):
            topw = display.create_resource_object(
                "window", self.get_surface().get_xid()
            )

            topw.change_property(atom, Xatom.CARDINAL, 32, [enabled], X.PropModeReplace)
            log.info("Setting GAMESCOPE_EXTERNAL_OVERLAY to %s", enabled)
            display.sync()
        else:
            log.warning("Unable to set GAMESCOPE_EXTERNAL_OVERLAY")

    def set_wayland_state(self):
        """
        If wayland is in use then attempt to set up a Gtk4LayerShell
        """
        # pylint: disable=E1120
        if not Gtk4LayerShell.is_supported():
            log.error("Desktop session has no LayerShell support. Exiting")
            self.discover.exit()
            return
        if not Gtk4LayerShell.is_layer_window(self):
            Gtk4LayerShell.init_for_window(self)
        Gtk4LayerShell.set_layer(self, Gtk4LayerShell.Layer.OVERLAY)
        if not isinstance(self.horzalign, HorzAlign):
            log.error("Invalid y align : %s", self.horzalign)
        if not isinstance(self.vertalign, VertAlign):
            log.error("Invalid x align : %s", self.vertalign)
        Gtk4LayerShell.set_anchor(
            self, Gtk4LayerShell.Edge.LEFT, self.horzalign == HorzAlign.LEFT
        )
        Gtk4LayerShell.set_anchor(
            self, Gtk4LayerShell.Edge.RIGHT, self.horzalign == HorzAlign.RIGHT
        )
        Gtk4LayerShell.set_anchor(
            self, Gtk4LayerShell.Edge.BOTTOM, self.vertalign == VertAlign.BOTTOM
        )
        Gtk4LayerShell.set_anchor(
            self, Gtk4LayerShell.Edge.TOP, self.vertalign == VertAlign.TOP
        )

    def has_content(self):
        """Return true if overlay has meaningful content"""
        return False

    def set_font(self, font):
        """
        Set the font used by the overlay
        """
        self.set_css("font", "* { font: %s; }" % (font_string_to_css_font_string(font)))

    def css_changed(self, change):
        Gtk.Window.css_changed(self, change)
        self.set_untouchable()

    def set_untouchable(
        self, _a=None, _b=None, _c=None
    ):  # Throw away args to allow size_allocate
        """
        Create a custom input shape and tell it that all of the window is a cut-out
        This allows us to have a window above everything but that never gets clicked on
        """
        surface = self.get_surface()
        display = self.get_display()
        if surface:

            bb_region = cairo.Region()
            if not display.is_composited() or self.hide_on_mouseover:
                # TODO Add bounding boxes of all labels and images in widget tree
                # bb_region = bb_region.union()
                pass

            surface.set_input_region(bb_region)
            if not display.is_composited():
                # TODO Maybe XLib + XShape
                log.error("Unable to set XShape - exiting")
                self.discover.exit()

    def set_hide_on_mouseover(self, hide):
        """Set if the overlay should hide when mouse moves over it"""
        if self.hide_on_mouseover != hide:
            self.hide_on_mouseover = hide
            if self.hide_on_mouseover:
                pass
            else:
                self.set_untouchable()

    def set_mouseover_timer(self, time):
        """Set the time until the overlay reappears after mouse over"""
        self.timeout_mouse_over = time

    def force_location(self):
        """
        On X11 enforce the location and sane defaults
        On Wayland just store for later
        On Gamescope enforce size of display but only if it's the primary overlay
        """
        self.show()
        (screen_x, screen_y, screen_width, screen_height) = self.get_display_coords()
        self.set_decorated(True)
        self.set_can_focus(False)
        # chosen_width = self.width_limit if self.width_limit > 0 else screen_width/4
        # chosen_height = self.height_limit if self.height_limit > 0 else screen_height/4
        # self.set_size_request(chosen_width, chosen_height)
        surface = self.get_surface()
        if isinstance(surface, GdkWayland.WaylandSurface):
            self.set_wayland_state()
        elif isinstance(surface, GdkX11.X11Surface):
            if not self.get_display().is_composited():
                log.error("Unable to function without compositor")
                self.discover.exit()
            surface.set_skip_pager_hint(True)
            surface.set_skip_taskbar_hint(True)
            self.set_decorated(False)
            self.set_size_request(screen_width, screen_height)
            self.set_x11_window_location(screen_x, screen_y)
        else:
            log.error("Unknown windowing system. %s, Exiting", surface)
            self.discover.exit()
        self.set_untouchable()

    def get_display_coords(self):
        """Get screen space co-ordinates of the monitor"""
        monitor = self.get_monitor_from_plug()
        if not monitor:
            monitor = self.get_display().get_monitors()[0]
        if monitor:
            geometry = monitor.get_geometry()
            return (geometry.x, geometry.y, geometry.width, geometry.height)
        log.error("No monitor found! This is going to go badly")
        return (0, 0, 1920, 1080)

    def set_hidden(self, hidden):
        """Set if the overlay should be hidden"""
        self.hidden = hidden
        self.set_enabled(self.enabled)

    def set_monitor(self, idx=None):
        """
        Set the monitor this overlay should display on.
        """
        plug_name = f"{idx}"
        if self.monitor != plug_name:
            self.monitor = plug_name
            if isinstance(self.get_surface(), GdkWayland.WaylandSurface):
                monitor = self.get_monitor_from_plug()
                if monitor:
                    Gtk4LayerShell.set_monitor(self, monitor)
                else:
                    self.hide()
                    self.set_wayland_state()
                    if self.has_content():
                        self.show()
                self.set_untouchable()
            self.force_location()

    def get_monitor_from_plug(self):
        """Return a GDK Monitor filtered by plug name
        (HDMI-1, eDP-1, VGA etc)"""
        if not self.monitor or self.monitor == "Any":
            return None

        # pylint: disable=E1120
        display = self.get_display()
        monitors = display.get_monitors()
        for monitor in monitors:
            if self.monitor == monitor.get_connector():
                return monitor
        log.warning("Unable to find monitor for : %s : Using Any", self.monitor)
        return None

    def set_align_x(self, align: HorzAlign):
        """
        Set the alignment
        """
        if not isinstance(align, HorzAlign):
            log.error("Unable to set Align X %s", align)
            return

        self.horzalign = align
        self.force_location()

    def set_align_y(self, align: VertAlign):
        """
        Set the veritcal alignment
        """
        if not isinstance(align, VertAlign):
            log.error("Unable to set Align Y %s", align)
            return

        self.vertalign = align
        self.force_location()

    def set_enabled(self, enabled):
        """
        Set if this overlay should be visible
        """
        self.enabled = enabled
        if self.discover.steamos:
            self.set_gamescope_xatom(1 if enabled else 0)
        if enabled and not self.hidden:
            self.present()
            self.show()
        else:
            self.hide()

    def screen_changed(self, _screen=None, a_=None, _b=None, _c=None):
        """Callback to set monitor to display on"""
        if not self.get_display().is_composited():
            log.error("Unable to function without compositor")
            self.discover.exit()
        self.set_monitor(self.monitor)

    def mouseover(self, _a=None, _b=None):
        """Callback when mouseover occurs, hides overlay"""
        self.draw_blank = True
        self.hide()
        GLib.timeout_add_seconds(self.timeout_mouse_over, self.mouseout_timed)
        return True

    def mouseout(self, _a=None, _b=None):
        """Callback when mouseout occurs, sets a timer to show overlay"""
        return True

    def mouseout_timed(self, _a=None, _b=None):
        """Callback a short while after mouseout occured, shows overlay"""
        self.show()
        return False

    def set_config(self, config):
        """Set the configuration of this overlay from the given config section"""
        # Set Voice overlay options
        x_align = get_h_align(config.get("x_align", fallback="none"))
        if x_align is None:
            right_align = config.getboolean("rightalign", fallback=True)
            if right_align:
                x_align = HorzAlign.RIGHT
            else:
                x_align = HorzAlign.LEFT
        self.set_align_x(x_align)

        y_align = get_v_align(config.get("y_align", fallback="none"))
        if y_align is None:
            top_align = config.getint("topalign", fallback=1)
            if top_align == 0:
                y_align = VertAlign.TOP
            elif top_align == 1:
                y_align = VertAlign.MIDDLE
            else:
                y_align = VertAlign.BOTTOM
        self.set_align_y(y_align)

        self.set_monitor(config.get("monitor", fallback="Any"))

        self.set_hide_on_mouseover(config.getboolean("autohide", fallback=False))
        self.set_mouseover_timer(config.getint("autohide_timer", fallback=1))
        self.set_enabled(config.getboolean("enabled", fallback=True))

        self.set_visibility()

    def overlay(self, widget):
        self.widget = widget
        self.set_child(widget)

    def merged_overlay(self, widget_list):
        self.amalgamation = widget_list
        box = Gtk.Box()
        for widget in self.amalgamation:
            box.append(widget)
        self.set_child(box)
        box.set_layout_manager(AmalgamationLayout())

        # We won't receive config in this mode
        box.show()
        self.set_enabled(True)

    def set_visibility(self):
        if self.should_show():
            self.show()
        else:
            self.hide()

    def should_show(self):
        """Should this show? Returns true if the overlay should be shown to user"""
        if not self.enabled:
            return False
        if self.hidden:
            return False
        if self.widget and self.widget.should_show():
            return True
        if self.amalgamation:
            for widget in self.amalgamation:
                if widget.should_show():
                    return True
        return False
