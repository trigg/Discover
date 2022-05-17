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
"""Notification setting tab on settings window"""
import gettext
import json
import pkg_resources
from configparser import ConfigParser
import gi
from .settings import SettingsWindow

gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Gtk, Gdk  # nopep8


GUILD_DEFAULT_VALUE = "0"
t = gettext.translation(
    'default', pkg_resources.resource_filename('discover_overlay', 'locales'))
_ = t.gettext


class NotificationSettingsWindow(SettingsWindow):
    """Notification setting tab on settings window"""

    def __init__(self, overlay, discover):
        SettingsWindow.__init__(self, discover)
        self.overlay = overlay

        self.placement_window = None
        self.init_config()
        self.align_x = None
        self.align_y = None
        self.monitor = None
        self.floating = None
        self.font = None
        self.bg_col = None
        self.fg_col = None
        self.text_time = None
        self.show_icon = None
        self.enabled = None
        self.limit_width = None
        self.icon_left = None
        self.padding = None
        self.icon_padding = None
        self.icon_size = None
        self.border_radius = None

        self.set_size_request(400, 200)
        self.connect("destroy", self.close_window)
        self.connect("delete-event", self.close_window)
        if overlay:
            self.init_config()
            self.create_gui()

    def present_settings(self):
        """
        Show contents of tab and update lists
        """
        if not self.overlay:
            return
        self.show_all()
        if not self.floating:
            self.align_x_widget.show()
            self.align_y_widget.show()
            self.align_monitor_widget.show()
            self.align_placement_widget.hide()
        else:
            self.align_x_widget.hide()
            self.align_y_widget.hide()
            self.align_monitor_widget.show()
            self.align_placement_widget.show()

    def read_config(self):
        """
        Read in the 'text' section of the config
        """
        if not self.overlay:
            return
        config = ConfigParser(interpolation=None)
        config.read(self.config_file)
        self.enabled = config.getboolean(
            "notification", "enabled", fallback=False)
        self.align_x = config.getboolean(
            "notification", "rightalign", fallback=True)
        self.align_y = config.getint("notification", "topalign", fallback=2)
        self.monitor = config.get("notification", "monitor", fallback="None")
        self.floating = config.getboolean(
            "notification", "floating", fallback=False)
        self.floating_x = config.getint(
            "notification", "floating_x", fallback=0)
        self.floating_y = config.getint(
            "notification", "floating_y", fallback=0)
        self.floating_w = config.getint(
            "notification", "floating_w", fallback=400)
        self.floating_h = config.getint(
            "notification", "floating_h", fallback=400)
        self.font = config.get("notification", "font", fallback=None)
        self.bg_col = json.loads(config.get(
            "notification", "bg_col", fallback="[0.0,0.0,0.0,0.5]"))
        self.fg_col = json.loads(config.get(
            "notification", "fg_col", fallback="[1.0,1.0,1.0,1.0]"))
        self.text_time = config.getint(
            "notification", "text_time", fallback=10)
        self.show_icon = config.getboolean(
            "notification", "show_icon", fallback=True)
        self.reverse_order = config.getboolean(
            "notification", "rev", fallback=False)
        self.limit_width = config.getint(
            "notification", "limit_width", fallback=400)
        self.icon_left = config.getboolean(
            "notification", "icon_left", fallback=True)
        self.icon_padding = config.getint(
            "notification", "icon_padding", fallback=8)
        self.icon_size = config.getint(
            "notification", "icon_size", fallback=32)
        self.padding = config.getint(
            "notification", "padding", fallback=8)
        self.border_radius = config.getint(
            "notification", "border_radius", fallback=8)

        # Pass all of our config over to the overlay
        self.overlay.set_enabled(self.enabled)
        self.overlay.set_align_x(self.align_x)
        self.overlay.set_align_y(self.align_y)
        self.overlay.set_monitor(self.get_monitor_index(
            self.monitor), self.get_monitor_obj(self.monitor))
        self.overlay.set_floating(
            self.floating, self.floating_x, self.floating_y, self.floating_w, self.floating_h)
        self.overlay.set_bg(self.bg_col)
        self.overlay.set_fg(self.fg_col)
        self.overlay.set_text_time(self.text_time)
        self.overlay.set_show_icon(self.show_icon)
        self.overlay.set_reverse_order(self.reverse_order)
        self.overlay.set_limit_width(self.limit_width)
        self.overlay.set_icon_left(self.icon_left)
        self.overlay.set_icon_size(self.icon_size)
        self.overlay.set_icon_pad(self.icon_padding)
        self.overlay.set_padding(self.padding)
        self.overlay.set_border_radius(self.border_radius)
        if self.font:
            self.overlay.set_font(self.font)

    def save_config(self):
        """
        Save the current settings to the 'text' section of the config
        """
        config = ConfigParser(interpolation=None)
        config.read(self.config_file)
        if not config.has_section("notification"):
            config.add_section("notification")

        config.set("notification", "rightalign", "%d" % (int(self.align_x)))
        config.set("notification", "topalign", "%d" % (self.align_y))
        config.set("notification", "monitor", self.monitor)
        config.set("notification", "enabled", "%d" % (int(self.enabled)))
        config.set("notification", "floating", "%s" % (int(self.floating)))
        config.set("notification", "floating_x", "%s" % (int(self.floating_x)))
        config.set("notification", "floating_y", "%s" % (int(self.floating_y)))
        config.set("notification", "floating_w", "%s" % (int(self.floating_w)))
        config.set("notification", "floating_h", "%s" % (int(self.floating_h)))
        config.set("notification", "bg_col", json.dumps(self.bg_col))
        config.set("notification", "fg_col", json.dumps(self.fg_col))
        config.set("notification", "text_time", "%s" % (int(self.text_time)))
        config.set("notification", "show_icon", "%s" %
                   (int(self.show_icon)))
        config.set("notification", "rev", "%s" %
                   (int(self.reverse_order)))
        config.set("notification", "limit_width", "%d" %
                   (int(self.limit_width)))
        config.set("notification", "icon_left", "%d" % (int(self.icon_left)))
        config.set("notification", "icon_padding", "%d" %
                   (int(self.icon_padding)))
        config.set("notification", "icon_size", "%d" % (int(self.icon_size)))
        config.set("notification", "padding", "%d" % (int(self.padding)))
        config.set("notification", "border_radius", "%d" %
                   (int(self.border_radius)))

        if self.font:
            config.set("notification", "font", self.font)

        with open(self.config_file, 'w') as file:
            config.write(file)

    def create_gui(self):
        """
        Prepare the gui
        """
        box = Gtk.Grid()

        # Enabled
        enabled_label = Gtk.Label.new(_("Enable"))
        enabled = Gtk.CheckButton.new()
        enabled.set_active(self.enabled)
        enabled.connect("toggled", self.change_enabled)

        # Enabled
        testing_label = Gtk.Label.new(_("Show test content"))
        testing = Gtk.CheckButton.new()
        testing.connect("toggled", self.change_testing)

        # Order
        reverse_label = Gtk.Label.new(_("Reverse Order"))
        reverse = Gtk.CheckButton.new()
        reverse.set_active(self.reverse_order)
        reverse.connect("toggled", self.change_reverse_order)

        # Popup timer
        text_time_label = Gtk.Label.new(_("Popup timer"))
        text_time_adjustment = Gtk.Adjustment.new(
            self.text_time, 8, 9000, 1, 1, 8)
        text_time = Gtk.SpinButton.new(text_time_adjustment, 0, 0)
        text_time.connect("value-changed", self.change_text_time)

        # Limit width
        limit_width_label = Gtk.Label.new(_("Limit popup width"))
        limit_width_adjustment = Gtk.Adjustment.new(
            self.limit_width, 100, 9000, 1, 1, 8)
        limit_width = Gtk.SpinButton.new(limit_width_adjustment, 0, 0)
        limit_width.connect("value-changed", self.change_limit_width)

        # Font chooser
        font_label = Gtk.Label.new(_("Font"))
        font = Gtk.FontButton()
        if self.font:
            font.set_font(self.font)
        font.connect("font-set", self.change_font)

        # Icon alignment
        align_icon_label = Gtk.Label.new(_("Icon position"))
        align_icon_store = Gtk.ListStore(str)
        align_icon_store.append([_("Left")])
        align_icon_store.append([_("Right")])
        align_icon = Gtk.ComboBox.new_with_model(align_icon_store)
        align_icon.set_active(not self.icon_left)
        align_icon.connect("changed", self.change_icon_left)
        renderer_text = Gtk.CellRendererText()
        align_icon.pack_start(renderer_text, True)
        align_icon.add_attribute(renderer_text, "text", 0)

        # Colours
        bg_col_label = Gtk.Label.new(_("Background colour"))
        bg_col = Gtk.ColorButton.new_with_rgba(
            Gdk.RGBA(self.bg_col[0], self.bg_col[1], self.bg_col[2], self.bg_col[3]))
        fg_col_label = Gtk.Label.new(_("Text colour"))
        fg_col = Gtk.ColorButton.new_with_rgba(
            Gdk.RGBA(self.fg_col[0], self.fg_col[1], self.fg_col[2], self.fg_col[3]))
        bg_col.set_use_alpha(True)
        fg_col.set_use_alpha(True)
        bg_col.connect("color-set", self.change_bg)
        fg_col.connect("color-set", self.change_fg)

        # Monitor & Alignment
        align_label = Gtk.Label.new(_("Overlay Location"))

        align_type_box = Gtk.HBox()
        align_type_edge = Gtk.RadioButton.new_with_label(
            None, _("Anchor to edge"))
        align_type_floating = Gtk.RadioButton.new_with_label_from_widget(
            align_type_edge, _("Floating"))
        if self.floating:
            align_type_floating.set_active(True)
        align_type_box.add(align_type_edge)
        align_type_box.add(align_type_floating)

        monitor_store = Gtk.ListStore(str)
        display = Gdk.Display.get_default()
        if "get_n_monitors" in dir(display):
            for i in range(0, display.get_n_monitors()):
                monitor_store.append([display.get_monitor(i).get_model()])
        monitor = Gtk.ComboBox.new_with_model(monitor_store)
        monitor.set_active(self.get_monitor_index(self.monitor))
        monitor.connect("changed", self.change_monitor)
        renderer_text = Gtk.CellRendererText()
        monitor.pack_start(renderer_text, True)
        monitor.add_attribute(renderer_text, "text", 0)

        align_x_store = Gtk.ListStore(str)
        align_x_store.append([_("Left")])
        align_x_store.append([_("Right")])
        align_x = Gtk.ComboBox.new_with_model(align_x_store)
        align_x.set_active(True if self.align_x else False)
        align_x.connect("changed", self.change_align_x)
        renderer_text = Gtk.CellRendererText()
        align_x.pack_start(renderer_text, True)
        align_x.add_attribute(renderer_text, "text", 0)

        align_y_store = Gtk.ListStore(str)
        align_y_store.append([_("Top")])
        align_y_store.append([_("Middle")])
        align_y_store.append([_("Bottom")])
        align_y = Gtk.ComboBox.new_with_model(align_y_store)
        align_y.set_active(self.align_y)
        align_y.connect("changed", self.change_align_y)
        renderer_text = Gtk.CellRendererText()
        align_y.pack_start(renderer_text, True)
        align_y.add_attribute(renderer_text, "text", 0)

        align_placement_button = Gtk.Button.new_with_label(_("Place Window"))

        align_type_edge.connect("toggled", self.change_align_type_edge)
        align_type_floating.connect("toggled", self.change_align_type_floating)
        align_placement_button.connect("pressed", self.change_placement)

        # Show Icons
        show_icon_label = Gtk.Label.new(_("Show Icon"))
        show_icon = Gtk.CheckButton.new()
        show_icon.set_active(self.show_icon)
        show_icon.connect("toggled", self.change_show_icon)

        # Icon Padding
        icon_padding_label = Gtk.Label.new(_("Icon padding"))
        icon_padding_adjustment = Gtk.Adjustment.new(
            self.icon_padding, 0, 150, 1, 1, 8)
        icon_padding = Gtk.SpinButton.new(icon_padding_adjustment, 0, 0)
        icon_padding.connect("value-changed", self.change_icon_pad)

        # Icon Size
        icon_size_label = Gtk.Label.new(_("Icon size"))
        icon_size_adjustment = Gtk.Adjustment.new(
            self.icon_size, 0, 128, 1, 1, 8)
        icon_size = Gtk.SpinButton.new(icon_size_adjustment, 0, 0)
        icon_size.connect("value-changed", self.change_icon_size)

        # Padding
        padding_label = Gtk.Label.new(_("Notification padding"))
        padding_adjustment = Gtk.Adjustment.new(
            self.padding, 0, 150, 1, 1, 8)
        padding = Gtk.SpinButton.new(padding_adjustment, 0, 0)
        padding.connect("value-changed", self.change_padding)

        # Border Radius
        border_radius_label = Gtk.Label.new(_("Border radius"))
        border_radius_adjustment = Gtk.Adjustment.new(
            self.border_radius, 0, 50, 1, 1, 8)
        border_radius = Gtk.SpinButton.new(border_radius_adjustment, 0, 0)
        border_radius.connect(
            "value-changed", self.change_border_radius)

        self.align_x_widget = align_x
        self.align_y_widget = align_y
        self.align_monitor_widget = monitor
        self.align_placement_widget = align_placement_button
        self.text_time_widget = text_time
        self.text_time_label_widget = text_time_label

        box.attach(enabled_label, 0, 0, 1, 1)
        box.attach(enabled, 1, 0, 1, 1)
        box.attach(reverse_label, 0, 1, 1, 1)
        box.attach(reverse, 1, 1, 1, 1)
        box.attach(text_time_label, 0, 3, 1, 1)
        box.attach(text_time, 1, 3, 1, 1)
        box.attach(limit_width_label, 0, 4, 1, 1)
        box.attach(limit_width, 1, 4, 1, 1)

        box.attach(font_label, 0, 6, 1, 1)
        box.attach(font, 1, 6, 1, 1)
        box.attach(fg_col_label, 0, 7, 1, 1)
        box.attach(fg_col, 1, 7, 1, 1)
        box.attach(bg_col_label, 0, 8, 1, 1)
        box.attach(bg_col, 1, 8, 1, 1)
        box.attach(align_label, 0, 9, 1, 5)
        #box.attach(align_type_box, 1, 8, 1, 1)
        box.attach(monitor, 1, 10, 1, 1)
        box.attach(align_x, 1, 11, 1, 1)
        box.attach(align_y, 1, 12, 1, 1)
        box.attach(align_placement_button, 1, 13, 1, 1)
        box.attach(show_icon_label, 0, 14, 1, 1)
        box.attach(show_icon, 1, 14, 1, 1)
        box.attach(align_icon_label, 0, 15, 1, 1)
        box.attach(align_icon, 1, 15, 1, 1)
        box.attach(icon_padding_label, 0, 16, 1, 1)
        box.attach(icon_padding, 1, 16, 1, 1)
        box.attach(icon_size_label, 0, 17, 1, 1)
        box.attach(icon_size, 1, 17, 1, 1)
        box.attach(padding_label, 0, 18, 1, 1)
        box.attach(padding, 1, 18, 1, 1)
        box.attach(border_radius_label, 0, 19, 1, 1)
        box.attach(border_radius, 1, 19, 1, 1)
        box.attach(testing_label, 0, 20, 1, 1)
        box.attach(testing, 1, 20, 1, 1)

        self.add(box)

    def change_padding(self, button):
        """
        Padding between notifications changed
        """
        self.overlay.set_padding(button.get_value())
        self.padding = button.get_value()

        self.save_config()

    def change_border_radius(self, button):
        """
        Border radius changed
        """
        self.overlay.set_border_radius(button.get_value())
        self.border_radius = button.get_value()

        self.save_config()

    def change_icon_size(self, button):
        """
        Icon size changed
        """
        self.overlay.set_icon_size(button.get_value())
        self.icon_size = button.get_value()

        self.save_config()

    def change_icon_pad(self, button):
        """
        Icon padding changed
        """
        self.overlay.set_icon_pad(button.get_value())
        self.icon_pad = button.get_value()

        self.save_config()

    def change_icon_left(self, button):
        """
        Icon alignment changed
        """
        self.overlay.set_icon_left(button.get_active() != 1)
        self.icon_left = (button.get_active() != 1)

        self.save_config()

    def change_font(self, button):
        """
        Font settings changed
        """
        font = button.get_font()
        self.overlay.set_font(font)

        self.font = font
        self.save_config()

    def change_text_time(self, button):
        """
        Popup style setting changed
        """
        self.overlay.set_text_time(button.get_value())

        self.text_time = button.get_value()
        self.save_config()

    def change_limit_width(self, button):
        """
        Popup width limiter
        """
        self.overlay.set_limit_width(button.get_value())
        self.limit_width = button.get_value()
        self.save_config()

    def change_bg(self, button):
        """
        Background colour changed
        """
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.overlay.set_bg(colour)

        self.bg_col = colour
        self.save_config()

    def change_fg(self, button):
        """
        Foreground colour changed
        """
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.overlay.set_fg(colour)

        self.fg_col = colour
        self.save_config()

    def change_show_icon(self, button):
        """
        Icon setting changed
        """
        self.overlay.set_show_icon(button.get_active())

        self.show_icon = button.get_active()
        self.save_config()

    def change_reverse_order(self, button):
        """
        Reverse Order changed
        """
        self.overlay.set_reverse_order(button.get_active())

        self.reverse_order = button.get_active()
        self.save_config()

    def change_testing(self, button):
        self.overlay.set_testing(button.get_active())

    def change_enabled(self, button):
        """
        Overlay active state toggled
        """
        self.overlay.set_enabled(button.get_active())
        self.enabled = button.get_active()
        self.save_config()
