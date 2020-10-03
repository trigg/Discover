import gi
gi.require_version("Gtk", "3.0")
import json
from configparser import ConfigParser
from .draggable_window import DraggableWindow
from .settings import SettingsWindow
from gi.repository import Gtk, Gdk
import logging


class TextSettingsWindow(SettingsWindow):
    def __init__(self, overlay):
        Gtk.Window.__init__(self)
        self.overlay = overlay
        self.set_size_request(400, 200)
        self.connect("destroy", self.close_window)
        self.connect("delete-event", self.close_window)
        self.placement_window = None
        self.init_config()
        self.list_channels_keys = []
        self.ignore_channel_change = False
        self.create_gui()

    def present(self):
        self.show_all()
        if not self.floating:
            self.align_x_widget.show()
            self.align_y_widget.show()
            self.align_monitor_widget.show()
            self.align_placement_widget.hide()
        else:
            self.align_x_widget.hide()
            self.align_y_widget.hide()
            self.align_monitor_widget.hide()
            self.align_placement_widget.show()

        if self.popup_style:
            self.text_time_widget.show()
            self.text_time_label_widget.show()
        else:
            self.text_time_widget.hide()
            self.text_time_label_widget.hide()

        model = monitor_store = Gtk.ListStore(str, bool)
        # for c in self.list_channels_keys:
        #    print(self.list_channels[c])
        #    model.append([self.list_channels[c]["name"]])
        self.channel_lookup = []
        for guild in self.guild_list():
            guild_id, guild_name = guild
            self.channel_lookup.append('0')
            model.append([guild_name, False])
            for c in self.list_channels_keys:
                chan = self.list_channels[c]
                if chan['guild_id'] == guild_id:
                    model.append([chan["name"], True])
                    self.channel_lookup.append(c)

        self.channel_widget.set_model(model)
        self.channel_model = model

        idx = 0
        for c in self.channel_lookup:
            if c == self.channel:
                self.ignore_channel_change = True
                self.channel_widget.set_active(idx)
                self.ignore_channel_change = False
                break
            idx += 1

    def guild_list(self):
        guilds = []
        done = []
        for channel in self.list_channels.values():
            if not channel["guild_id"] in done:
                done.append(channel["guild_id"])
                guilds.append([channel["guild_id"], channel["guild_name"]])
        return guilds

    def set_channels(self, in_list):
        self.list_channels = in_list
        self.list_channels_keys = []
        for key in in_list.keys():
            if in_list[key]["type"] == 0:
                self.list_channels_keys.append(key)
        self.list_channels_keys.sort()

    def read_config(self):
        config = ConfigParser(interpolation=None)
        config.read(self.configFile)
        self.enabled = config.getboolean("text", "enabled", fallback=False)
        self.align_x = config.getboolean("text", "rightalign", fallback=True)
        self.align_y = config.getint("text", "topalign", fallback=2)
        self.monitor = config.get("text", "monitor", fallback="None")
        self.floating = config.getboolean("text", "floating", fallback=True)
        self.floating_x = config.getint("text", "floating_x", fallback=0)
        self.floating_y = config.getint("text", "floating_y", fallback=0)
        self.floating_w = config.getint("text", "floating_w", fallback=400)
        self.floating_h = config.getint("text", "floating_h", fallback=400)
        self.channel = config.get("text", "channel", fallback="0")
        self.font = config.get("text", "font", fallback=None)
        self.bg_col = json.loads(config.get(
            "text", "bg_col", fallback="[0.0,0.0,0.0,0.5]"))
        self.fg_col = json.loads(config.get(
            "text", "fg_col", fallback="[1.0,1.0,1.0,1.0]"))
        self.popup_style = config.getboolean(
            "text", "popup_style", fallback=False)
        self.text_time = config.getint("text", "text_time", fallback=30)
        self.show_attach = config.getboolean(
            "text", "show_attach", fallback=True)

        logging.info(
            "Loading saved channel %s" % (self.channel))

        # Pass all of our config over to the overlay
        self.overlay.set_enabled(self.enabled)
        self.overlay.set_align_x(self.align_x)
        self.overlay.set_align_y(self.align_y)
        self.overlay.set_monitor(self.get_monitor_index(self.monitor))
        self.overlay.set_floating(
            self.floating, self.floating_x, self.floating_y, self.floating_w, self.floating_h)
        self.overlay.set_bg(self.bg_col)
        self.overlay.set_fg(self.fg_col)
        self.overlay.set_popup_style(self.popup_style)
        self.overlay.set_text_time(self.text_time)
        self.overlay.set_show_attach(self.show_attach)

    def save_config(self):
        config = ConfigParser(interpolation=None)
        config.read(self.configFile)
        if not config.has_section("text"):
            config.add_section("text")

        config.set("text", "rightalign", "%d" % (int(self.align_x)))
        config.set("text", "topalign", "%d" % (self.align_y))
        config.set("text", "monitor", self.monitor)
        config.set("text", "enabled", "%d" % (int(self.enabled)))
        config.set("text", "floating", "%s" % (int(self.floating)))
        config.set("text", "floating_x", "%s" % (self.floating_x))
        config.set("text", "floating_y", "%s" % (self.floating_y))
        config.set("text", "floating_w", "%s" % (self.floating_w))
        config.set("text", "floating_h", "%s" % (self.floating_h))
        config.set("text", "channel", self.channel)
        config.set("text", "bg_col", json.dumps(self.bg_col))
        config.set("text", "fg_col", json.dumps(self.fg_col))
        config.set("text", "popup_style", "%s" % (int(self.popup_style)))
        config.set("text", "text_time", "%s" % (int(self.text_time)))
        config.set("text", "show_attach", "%s" % (int(self.show_attach)))

        if self.font:
            config.set("text", "font", self.font)

        with open(self.configFile, 'w') as file:
            config.write(file)

    def create_gui(self):
        box = Gtk.Grid()

        # Enabled
        enabled_label = Gtk.Label.new("Enable")
        enabled = Gtk.CheckButton.new()
        enabled.set_active(self.enabled)
        enabled.connect("toggled", self.change_enabled)

        # Popup Style
        popup_style_label = Gtk.Label.new("Popup Style")
        popup_style = Gtk.CheckButton.new()
        popup_style.set_active(self.popup_style)
        popup_style.connect("toggled", self.change_popup_style)

        # Popup timer
        text_time_label = Gtk.Label.new("Popup timer")
        text_time_adjustment = Gtk.Adjustment.new(
            self.text_time, 8, 9000, 1, 1, 8)
        text_time = Gtk.SpinButton.new(text_time_adjustment, 0, 0)
        text_time.connect("value-changed", self.change_text_time)

        # Font chooser
        font_label = Gtk.Label.new("Font")
        font = Gtk.FontButton()
        if self.font:
            font.set_font(self.font)
        font.connect("font-set", self.change_font)

        # Colours
        bg_col_label = Gtk.Label.new("Background colour")
        bg_col = Gtk.ColorButton.new_with_rgba(
            Gdk.RGBA(self.bg_col[0], self.bg_col[1], self.bg_col[2], self.bg_col[3]))
        fg_col_label = Gtk.Label.new("Text colour")
        fg_col = Gtk.ColorButton.new_with_rgba(
            Gdk.RGBA(self.fg_col[0], self.fg_col[1], self.fg_col[2], self.fg_col[3]))
        bg_col.set_use_alpha(True)
        fg_col.set_use_alpha(True)
        bg_col.connect("color-set", self.change_bg)
        fg_col.connect("color-set", self.change_fg)

        # Monitor & Alignment
        align_label = Gtk.Label.new("Overlay Location")

        align_type_box = Gtk.HBox()
        align_type_edge = Gtk.RadioButton.new_with_label(
            None, "Anchor to edge")
        align_type_floating = Gtk.RadioButton.new_with_label_from_widget(
            align_type_edge, "Floating")
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
        rt = Gtk.CellRendererText()
        monitor.pack_start(rt, True)
        monitor.add_attribute(rt, "text", 0)

        align_x_store = Gtk.ListStore(str)
        align_x_store.append(["Left"])
        align_x_store.append(["Right"])
        align_x = Gtk.ComboBox.new_with_model(align_x_store)
        align_x.set_active(True if self.align_x else False)
        align_x.connect("changed", self.change_align_x)
        rt = Gtk.CellRendererText()
        align_x.pack_start(rt, True)
        align_x.add_attribute(rt, "text", 0)

        align_y_store = Gtk.ListStore(str)
        align_y_store.append(["Top"])
        align_y_store.append(["Middle"])
        align_y_store.append(["Bottom"])
        align_y = Gtk.ComboBox.new_with_model(align_y_store)
        align_y.set_active(self.align_y)
        align_y.connect("changed", self.change_align_y)
        rt = Gtk.CellRendererText()
        align_y.pack_start(rt, True)
        align_y.add_attribute(rt, "text", 0)

        align_placement_button = Gtk.Button.new_with_label("Place Window")

        align_type_edge.connect("toggled", self.change_align_type_edge)
        align_type_floating.connect("toggled", self.change_align_type_floating)
        align_placement_button.connect("pressed", self.change_placement)

        channel_label = Gtk.Label.new("Channel")
        channel = Gtk.ComboBox.new()

        channel.connect("changed", self.change_channel)
        rt = Gtk.CellRendererText()
        #channel.set_row_separator_func(lambda model, path: model[path][1])
        channel.pack_start(rt, True)
        channel.add_attribute(rt, "text", 0)
        channel.add_attribute(rt, 'sensitive', 1)

        # Show Attachments
        show_attach_label = Gtk.Label.new("Show Attachments")
        show_attach = Gtk.CheckButton.new()
        show_attach.set_active(self.show_attach)
        show_attach.connect("toggled", self.change_show_attach)

        self.align_x_widget = align_x
        self.align_y_widget = align_y
        self.align_monitor_widget = monitor
        self.align_placement_widget = align_placement_button
        self.channel_widget = channel
        self.text_time_widget = text_time
        self.text_time_label_widget = text_time_label

        box.attach(enabled_label, 0, 0, 1, 1)
        box.attach(enabled, 1, 0, 1, 1)
        box.attach(popup_style_label, 0, 1, 1, 1)
        box.attach(popup_style, 1, 1, 1, 1)
        box.attach(text_time_label, 0, 2, 1, 1)
        box.attach(text_time, 1, 2, 1, 1)
        box.attach(channel_label, 0, 3, 1, 1)
        box.attach(channel, 1, 3, 1, 1)
        box.attach(font_label, 0, 4, 1, 1)
        box.attach(font, 1, 4, 1, 1)
        box.attach(fg_col_label, 0, 5, 1, 1)
        box.attach(fg_col, 1, 5, 1, 1)
        box.attach(bg_col_label, 0, 6, 1, 1)
        box.attach(bg_col, 1, 6, 1, 1)
        box.attach(align_label, 0, 7, 1, 5)
        #box.attach(align_type_box, 1, 7, 1, 1)
        box.attach(monitor, 1, 8, 1, 1)
        box.attach(align_x, 1, 9, 1, 1)
        box.attach(align_y, 1, 10, 1, 1)
        box.attach(align_placement_button, 1, 11, 1, 1)
        box.attach(show_attach_label, 0, 12, 1, 1)
        box.attach(show_attach, 1, 12, 1, 1)

        self.add(box)

    def change_font(self, button):
        font = button.get_font()
        desc = Pango.FontDescription.from_string(font)
        s = desc.get_size()
        if not desc.get_size_is_absolute():
            s = s / Pango.SCALE
        self.overlay.set_font(desc.get_family(), s)

        self.font = desc.to_string()
        self.save_config()

    def change_channel(self, button):
        if self.ignore_channel_change:
            return
        c = self.channel_lookup[button.get_active()]
        self.channel = c
        self.save_config()

    def change_placement(self, button):
        if self.placement_window:
            (x, y) = self.placement_window.get_position()
            (w, h) = self.placement_window.get_size()
            self.floating_x = x
            self.floating_y = y
            self.floating_w = w
            self.floating_h = h
            self.overlay.set_floating(True, x, y, w, h)
            self.save_config()
            button.set_label("Place Window")

            self.placement_window.close()
            self.placement_window = None
        else:
            self.placement_window = DraggableWindow(
                x=self.floating_x, y=self.floating_y, w=self.floating_w, h=self.floating_h, message="Place & resize this window then press Save!")
            button.set_label("Save this position")

    def change_align_type_edge(self, button):
        if button.get_active():
            self.overlay.set_floating(
                False, self.floating_x, self.floating_y, self.floating_w, self.floating_h)
            self.floating = False
            self.save_config()

            # Re-sort the screen
            self.align_x_widget.show()
            self.align_y_widget.show()
            self.align_monitor_widget.show()
            self.align_placement_widget.hide()

    def change_align_type_floating(self, button):
        if button.get_active():
            self.overlay.set_floating(
                True, self.floating_x, self.floating_y, self.floating_w, self.floating_h)
            self.floating = True
            self.save_config()
            self.align_x_widget.hide()
            self.align_y_widget.hide()
            self.align_monitor_widget.hide()
            self.align_placement_widget.show()

    def change_monitor(self, button):
        display = Gdk.Display.get_default()
        if "get_monitor" in dir(display):
            mon = display.get_monitor(button.get_active())
            m_s = mon.get_model()
            self.overlay.set_monitor(button.get_active())

            self.monitor = m_s
            self.save_config()

    def change_align_x(self, button):
        self.overlay.set_align_x(button.get_active() == 1)

        self.align_x = (button.get_active() == 1)
        self.save_config()

    def change_align_y(self, button):
        self.overlay.set_align_y(button.get_active())

        self.align_y = button.get_active()
        self.save_config()

    def change_enabled(self, button):
        self.overlay.set_enabled(button.get_active())

        self.enabled = button.get_active()
        self.save_config()

    def change_popup_style(self, button):
        self.overlay.set_popup_style(button.get_active())

        self.popup_style = button.get_active()
        self.save_config()

        if button.get_active():
            # We're using popup style
            self.text_time_widget.show()
            self.text_time_label_widget.show()
        else:
            self.text_time_widget.hide()
            self.text_time_label_widget.hide()

    def change_text_time(self, button):
        self.overlay.set_text_time(button.get_value())

        self.text_time = button.get_value()
        self.save_config()

    def get_channel(self):
        return self.channel

    def change_bg(self, button):
        c = button.get_rgba()
        c = [c.red, c.green, c.blue, c.alpha]
        self.overlay.set_bg(c)

        self.bg_col = c
        self.save_config()

    def change_fg(self, button):
        c = button.get_rgba()
        c = [c.red, c.green, c.blue, c.alpha]
        self.overlay.set_fg(c)

        self.fg_col = c
        self.save_config()

    def change_show_attach(self, button):
        self.overlay.set_show_attach(button.get_active())

        self.show_attach = button.get_active()
        self.save_config()
