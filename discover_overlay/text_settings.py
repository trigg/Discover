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
"""Text setting tab on settings window"""
import json
import logging
from configparser import ConfigParser
import gi
from .settings import SettingsWindow

gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Gtk, Gdk


GUILD_DEFAULT_VALUE = "0"


class TextSettingsWindow(SettingsWindow):
    """Text setting tab on settings window"""

    def __init__(self, overlay):
        SettingsWindow.__init__(self)
        self.overlay = overlay

        self.placement_window = None
        self.init_config()
        self.list_channels_keys = []
        self.list_channels = {}
        self.list_guilds_keys = []
        self.list_guilds = {}
        self.ignore_channel_change = False
        self.ignore_guild_change = False
        self.channel_lookup = None
        self.channel_model = None
        self.connector = None
        self.guild_lookup = None
        self.guild_model = None
        self.guild_widget = None
        self.align_x = None
        self.align_y = None
        self.monitor = None
        self.floating = None
        self.channel = None
        self.guild = None
        self.font = None
        self.bg_col = None
        self.fg_col = None
        self.popup_style = None
        self.text_time = None
        self.show_attach = None
        self.enabled = None

        self.set_size_request(400, 200)
        self.connect("destroy", self.close_window)
        self.connect("delete-event", self.close_window)
        if overlay:
            self.init_config()
            self.create_gui()

    def update_channel_model(self):
        """
        Update the Channel selector.

        Populate with all channels from guild.
        Leave empty if guild is unselected
        """
        # Potentially organize channels by their group/parent_id
        # https://discord.com/developers/docs/resources/channel#channel-object-channel-structure
        c_model = Gtk.ListStore(str, bool)
        self.channel_lookup = []

        # If a guild is specified, populate channel list with every channel from *just that guild*
        if self.guild != GUILD_DEFAULT_VALUE:
            for position in self.list_channels_keys:
                chan = self.list_channels[position]
                channel_key = chan["id"]
                if chan['guild_id'] == self.guild:
                    c_model.append([chan["name"], True])
                    self.channel_lookup.append(channel_key)

        self.channel_widget.set_model(c_model)
        self.channel_model = c_model

        idx = 0
        for channel in self.channel_lookup:
            if channel == self.channel:
                self.ignore_channel_change = True
                self.channel_widget.set_active(idx)
                self.ignore_channel_change = False
                break
            idx += 1

    def add_connector(self, conn):
        """
        Add the discord_connector reference

        If the user has previously selected a text channel then tell it to subscribe
        """
        self.connector = conn
        if self.channel:
            self.connector.start_listening_text(self.channel)

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

        if self.popup_style:
            self.text_time_widget.show()
            self.text_time_label_widget.show()
        else:
            self.text_time_widget.hide()
            self.text_time_label_widget.hide()

        g_model = Gtk.ListStore(str, bool)
        self.guild_lookup = []

        for guild in self.guild_list():
            guild_id, guild_name = guild
            self.guild_lookup.append(guild_id)
            g_model.append([guild_name, True])

        self.guild_widget.set_model(g_model)
        self.guild_model = g_model
        self.update_channel_model()

        idxg = 0
        for guild_id in self.guild_lookup:
            if guild_id == self.guild:
                self.ignore_guild_change = True
                self.guild_widget.set_active(idxg)
                self.ignore_guild_change = False
                break
            idxg += 1

        if self.guild is not None:
            self.connector.request_text_rooms_for_guild(self.guild)

    def guild_list(self):
        """
        Return a list of all guilds
        """
        guilds = []
        done = []
        for guild in self.list_guilds.values():
            if not guild["id"] in done:
                done.append(guild["id"])
                guilds.append([guild["id"], guild["name"]])
        return guilds

    def set_channels(self, in_list):
        """
        Set the contents of list_channels
        """
        self.list_channels = in_list
        self.list_channels_keys = []
        for (key, _value) in enumerate(in_list):
            # Filter for only text channels
            # https://discord.com/developers/docs/resources/channel#channel-object-channel-types
            if in_list[key] is not None and in_list[key]["type"] == 0:
                self.list_channels_keys.append(key)
        self.list_channels_keys.sort()
        self.update_channel_model()

    def set_guilds(self, in_list):
        """
        Set the contents of list_guilds
        """
        self.list_guilds = in_list
        self.list_guilds_keys = []
        for key in in_list.keys():
            self.list_guilds_keys.append(key)
        self.list_guilds_keys.sort()

    def read_config(self):
        """
        Read in the 'text' section of the config
        """
        if not self.overlay:
            return
        config = ConfigParser(interpolation=None)
        config.read(self.config_file)
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
        self.guild = config.get("text", "guild", fallback=GUILD_DEFAULT_VALUE)
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
        self.autohide = config.getboolean("text", "autohide", fallback=False)

        logging.info(
            "Loading saved channel %s", self.channel)

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
        self.overlay.set_popup_style(self.popup_style)
        self.overlay.set_text_time(self.text_time)
        self.overlay.set_show_attach(self.show_attach)
        self.overlay.set_hide_on_mouseover(self.autohide)

    def save_config(self):
        """
        Save the current settings to the 'text' section of the config
        """
        config = ConfigParser(interpolation=None)
        config.read(self.config_file)
        if not config.has_section("text"):
            config.add_section("text")

        config.set("text", "rightalign", "%d" % (int(self.align_x)))
        config.set("text", "topalign", "%d" % (self.align_y))
        config.set("text", "monitor", self.monitor)
        config.set("text", "enabled", "%d" % (int(self.enabled)))
        config.set("text", "floating", "%s" % (int(self.floating)))
        config.set("text", "floating_x", "%s" % (int(self.floating_x)))
        config.set("text", "floating_y", "%s" % (int(self.floating_y)))
        config.set("text", "floating_w", "%s" % (int(self.floating_w)))
        config.set("text", "floating_h", "%s" % (int(self.floating_h)))
        config.set("text", "channel", self.channel)
        config.set("text", "guild", self.guild)
        config.set("text", "bg_col", json.dumps(self.bg_col))
        config.set("text", "fg_col", json.dumps(self.fg_col))
        config.set("text", "popup_style", "%s" % (int(self.popup_style)))
        config.set("text", "text_time", "%s" % (int(self.text_time)))
        config.set("text", "show_attach", "%s" % (int(self.show_attach)))

        if self.font:
            config.set("text", "font", self.font)

        with open(self.config_file, 'w') as file:
            config.write(file)

    def create_gui(self):
        """
        Prepare the gui
        """
        box = Gtk.Grid()

        # Enabled
        enabled_label = Gtk.Label.new("Enable")
        enabled = Gtk.CheckButton.new()
        enabled.set_active(self.enabled)
        enabled.connect("toggled", self.change_enabled)

        # Autohide
        autohide_label = Gtk.Label.new("Hide on mouseover")
        autohide = Gtk.CheckButton.new()
        autohide.set_active(self.autohide)
        autohide.connect("toggled", self.change_hide_on_mouseover)

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
        renderer_text = Gtk.CellRendererText()
        monitor.pack_start(renderer_text, True)
        monitor.add_attribute(renderer_text, "text", 0)

        align_x_store = Gtk.ListStore(str)
        align_x_store.append(["Left"])
        align_x_store.append(["Right"])
        align_x = Gtk.ComboBox.new_with_model(align_x_store)
        align_x.set_active(True if self.align_x else False)
        align_x.connect("changed", self.change_align_x)
        renderer_text = Gtk.CellRendererText()
        align_x.pack_start(renderer_text, True)
        align_x.add_attribute(renderer_text, "text", 0)

        align_y_store = Gtk.ListStore(str)
        align_y_store.append(["Top"])
        align_y_store.append(["Middle"])
        align_y_store.append(["Bottom"])
        align_y = Gtk.ComboBox.new_with_model(align_y_store)
        align_y.set_active(self.align_y)
        align_y.connect("changed", self.change_align_y)
        renderer_text = Gtk.CellRendererText()
        align_y.pack_start(renderer_text, True)
        align_y.add_attribute(renderer_text, "text", 0)

        align_placement_button = Gtk.Button.new_with_label("Place Window")

        align_type_edge.connect("toggled", self.change_align_type_edge)
        align_type_floating.connect("toggled", self.change_align_type_floating)
        align_placement_button.connect("pressed", self.change_placement)

        channel_label = Gtk.Label.new("Channel")
        channel = Gtk.ComboBox.new()

        channel.connect("changed", self.change_channel)
        renderer_text = Gtk.CellRendererText()
        channel.pack_start(renderer_text, True)
        channel.add_attribute(renderer_text, "text", 0)
        channel.add_attribute(renderer_text, 'sensitive', 1)

        guild_label = Gtk.Label.new("Server")
        guild = Gtk.ComboBox.new()

        guild.connect("changed", self.change_guild)
        renderer_text = Gtk.CellRendererText()
        guild.pack_start(renderer_text, True)
        guild.add_attribute(renderer_text, "text", 0)
        guild.add_attribute(renderer_text, 'sensitive', 1)

        # Show Attachments
        show_attach_label = Gtk.Label.new("Show Attachments")
        show_attach = Gtk.CheckButton.new()
        show_attach.set_active(self.show_attach)
        show_attach.connect("toggled", self.change_show_attach)

        self.align_x_widget = align_x
        self.align_y_widget = align_y
        self.align_monitor_widget = monitor
        self.align_placement_widget = align_placement_button
        self.guild_widget = guild
        self.channel_widget = channel
        self.text_time_widget = text_time
        self.text_time_label_widget = text_time_label

        box.attach(enabled_label, 0, 0, 1, 1)
        box.attach(enabled, 1, 0, 1, 1)
        #box.attach(autohide_label, 0, 1, 1, 1)
        #box.attach(autohide, 1, 1, 1, 1)
        box.attach(popup_style_label, 0, 2, 1, 1)
        box.attach(popup_style, 1, 2, 1, 1)
        box.attach(text_time_label, 0, 3, 1, 1)
        box.attach(text_time, 1, 3, 1, 1)
        box.attach(guild_label, 0, 4, 1, 1)
        box.attach(guild, 1, 4, 1, 1)

        box.attach(channel_label, 0, 5, 1, 1)
        box.attach(channel, 1, 5, 1, 1)
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
        box.attach(show_attach_label, 0, 14, 1, 1)
        box.attach(show_attach, 1, 14, 1, 1)

        self.add(box)

    def change_font(self, button):
        """
        Font settings changed
        """
        font = button.get_font()
        self.overlay.set_font(font)

        self.font = font
        self.save_config()

    def change_channel(self, button):
        """
        Channel setting changed
        """
        if self.ignore_channel_change:
            return

        channel = self.channel_lookup[button.get_active()]
        self.connector.start_listening_text(channel)
        self.channel = channel
        self.save_config()

    def change_guild(self, button):
        """
        Guild setting changed
        """
        if self.ignore_guild_change:
            return
        guild_id = self.guild_lookup[button.get_active()]
        self.guild = guild_id
        self.save_config()
        # self.update_channel_model()
        self.connector.request_text_rooms_for_guild(self.guild)

    def change_popup_style(self, button):
        """
        Popup style setting changed
        """
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
        """
        Popup style setting changed
        """
        self.overlay.set_text_time(button.get_value())

        self.text_time = button.get_value()
        self.save_config()

    def get_channel(self):
        """
        Return selected channel
        """
        return self.channel

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

    def change_show_attach(self, button):
        """
        Attachment setting changed
        """
        self.overlay.set_show_attach(button.get_active())

        self.show_attach = button.get_active()
        self.save_config()
