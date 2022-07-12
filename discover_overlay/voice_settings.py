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
"""Voice setting tab on settings window"""
import gettext
import json
import pkg_resources
from configparser import ConfigParser
import gi
from .settings import SettingsWindow
gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Gtk, Gdk  # nopep8

t = gettext.translation(
    'default', pkg_resources.resource_filename('discover_overlay', 'locales'), fallback=True)
_ = t.gettext


def parse_guild_ids(guild_ids_str):
    """Parse the guild_ids from a str and return them in a list"""
    guild_ids = []
    for guild_id in guild_ids_str.split(","):
        guild_id = guild_id.strip()
        if guild_id != "":
            guild_ids.append(guild_id)
    return guild_ids


def guild_ids_to_string(guild_ids):
    """Put the guild ids into a comma seperated string."""
    return ", ".join(str(_id) for _id in guild_ids)


class VoiceSettingsWindow(SettingsWindow):
    """Voice setting tab on settings window"""

    def __init__(self, overlay, discover):
        SettingsWindow.__init__(self, discover)
        self.overlay = overlay
        self.set_size_request(400, 200)
        self.connect("destroy", self.close_window)
        self.connect("delete-event", self.close_window)
        self.placement_window = None
        self.align_x = None
        self.align_y = None
        self.bg_col = None
        self.fg_col = None
        self.tk_col = None
        self.mt_col = None
        self.mute_bg_col = None
        self.hi_col = None
        self.bo_col = None
        self.avatar_bg_col = None
        self.t_hi_col = None
        self.avatar_size = None
        self.icon_spacing = None
        self.text_padding = None
        self.text_baseline_adj = None
        self.font = None
        self.title_font = None
        self.square_avatar = None
        self.only_speaking = None
        self.highlight_self = None
        self.icon_only = None
        self.monitor = None
        self.vert_edge_padding = None
        self.horz_edge_padding = None
        self.floating = None
        self.order = None
        self.horizontal = None
        self.guild_ids = None
        self.overflow = None
        self.guild_filter_string = ""
        self.warned = False
        self.show_dummy = False
        self.dummy_count = 10
        self.show_connection = None
        self.show_title = None
        self.show_disconnected = None
        self.border_width = 2
        self.icon_transparency = 1.0
        self.fancy_border = False

        self.init_config()
        self.create_gui()

    def present_settings(self):
        """
        Show tab
        """
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
        Read 'main' section of the config file
        """
        config = ConfigParser(interpolation=None)
        config.read(self.config_file)
        self.align_x = config.getboolean("main", "rightalign", fallback=False)
        self.align_y = config.getint("main", "topalign", fallback=1)
        self.bg_col = json.loads(config.get(
            "main", "bg_col", fallback="[0.0,0.0,0.0,0.5]"))
        self.fg_col = json.loads(config.get(
            "main", "fg_col", fallback="[1.0,1.0,1.0,1.0]"))
        self.t_hi_col = json.loads(config.get(
            "main", "fg_hi_col", fallback="[1.0,1.0,1.0,1.0]"))
        self.tk_col = json.loads(config.get(
            "main", "tk_col", fallback="[0.0,0.7,0.0,1.0]"))
        self.mt_col = json.loads(config.get(
            "main", "mt_col", fallback="[0.6,0.0,0.0,1.0]"))
        self.mute_bg_col = json.loads(config.get(
            "main", "mt_bg_col", fallback="[0.0,0.0,0.0,0.5]"))
        self.hi_col = json.loads(config.get(
            "main", "hi_col", fallback="[0.0,0.0,0.0,0.5]"))
        self.bo_col = json.loads(config.get(
            "main", "bo_col", fallback="[0.0,0.0,0.0,0.0]"))
        self.avatar_bg_col = json.loads(config.get(
            "main", "avatar_bg_col", fallback="[0.0,0.0,0.0,0.0]"))
        self.avatar_size = config.getint("main", "avatar_size", fallback=48)
        self.icon_spacing = config.getint("main", "icon_spacing", fallback=8)
        self.text_padding = config.getint("main", "text_padding", fallback=6)
        self.text_baseline_adj = config.getint(
            "main", "text_baseline_adj", fallback=0)
        self.font = config.get("main", "font", fallback=None)
        self.title_font = config.get("main", "title_font", fallback=None)
        self.square_avatar = config.getboolean(
            "main", "square_avatar", fallback=True)
        self.only_speaking = config.getboolean(
            "main", "only_speaking", fallback=False)
        self.highlight_self = config.getboolean(
            "main", "highlight_self", fallback=False)
        self.icon_only = config.getboolean(
            "main", "icon_only", fallback=False)
        self.monitor = config.get("main", "monitor", fallback="None")
        self.vert_edge_padding = config.getint(
            "main", "vert_edge_padding", fallback=0)
        self.horz_edge_padding = config.getint(
            "main", "horz_edge_padding", fallback=0)
        self.floating = config.getboolean("main", "floating", fallback=False)
        self.floating_x = config.getint("main", "floating_x", fallback=0)
        self.floating_y = config.getint("main", "floating_y", fallback=0)
        self.floating_w = config.getint("main", "floating_w", fallback=400)
        self.floating_h = config.getint("main", "floating_h", fallback=400)
        self.order = config.getint("main", "order", fallback=0)
        self.autohide = config.getboolean("text", "autohide", fallback=False)
        self.horizontal = config.getboolean(
            "main", "horizontal", fallback=False)
        self.guild_ids = parse_guild_ids(
            config.get("main", "guild_ids", fallback=""))
        self.overflow = config.getint("main", "overflow", fallback=0)
        self.show_connection = config.getboolean(
            "main", "show_connection", fallback=False)
        self.show_title = config.getboolean(
            "main", "show_title", fallback=False)
        self.show_disconnected = config.getboolean(
            "main", "show_disconnected", fallback=False)
        self.border_width = config.getint("main", "border_width", fallback=2)
        self.icon_transparency = config.getfloat(
            "main", "icon_transparency", fallback=1.0)
        self.fancy_border = config.getboolean("main",
            "fancy_border", fallback=True)

        # Pass all of our config over to the overlay
        self.overlay.set_align_x(self.align_x)
        self.overlay.set_align_y(self.align_y)
        self.overlay.set_bg(self.bg_col)
        self.overlay.set_fg(self.fg_col)
        self.overlay.set_tk(self.tk_col)
        self.overlay.set_mt(self.mt_col)
        self.overlay.set_mute_bg(self.mute_bg_col)
        self.overlay.set_hi(self.hi_col)
        self.overlay.set_bo(self.bo_col)
        self.overlay.set_avatar_bg_col(self.avatar_bg_col)
        self.overlay.set_fg_hi(self.t_hi_col)
        self.overlay.set_avatar_size(self.avatar_size)
        self.overlay.set_icon_spacing(self.icon_spacing)
        self.overlay.set_text_padding(self.text_padding)
        self.overlay.set_text_baseline_adj(self.text_baseline_adj)
        self.overlay.set_square_avatar(self.square_avatar)
        self.overlay.set_only_speaking(self.only_speaking)
        self.overlay.set_highlight_self(self.highlight_self)
        self.overlay.set_icon_only(self.icon_only)
        self.overlay.set_monitor(self.get_monitor_index(
            self.monitor), self.get_monitor_obj(self.monitor))
        self.overlay.set_vert_edge_padding(self.vert_edge_padding)
        self.overlay.set_horz_edge_padding(self.horz_edge_padding)
        self.overlay.set_order(self.order)
        self.overlay.set_hide_on_mouseover(self.autohide)
        self.overlay.set_horizontal(self.horizontal)
        self.overlay.set_guild_ids(self.guild_ids)
        self.overlay.set_overflow(self.overflow)
        self.overlay.set_enabled(True)
        self.overlay.set_show_connection(self.show_connection)
        self.overlay.set_show_title(self.show_title)
        self.overlay.set_show_disconnected(self.show_disconnected)
        self.overlay.set_border_width(self.border_width)
        self.overlay.set_icon_transparency(self.icon_transparency)
        self.overlay.set_fancy_border(self.fancy_border)

        self.overlay.set_floating(
            self.floating, self.floating_x, self.floating_y, self.floating_w, self.floating_h)

        if self.font:
            self.overlay.set_font(self.font)
        if self.title_font:
            self.overlay.set_title_font(self.title_font)

    def save_config(self):
        """
        Write settings out to the 'main' section of the config file
        """
        config = ConfigParser(interpolation=None)
        config.read(self.config_file)
        if not config.has_section("main"):
            config.add_section("main")

        config.set("main", "rightalign", "%d" % (int(self.align_x)))
        config.set("main", "topalign", "%d" % (self.align_y))
        config.set("main", "bg_col", json.dumps(self.bg_col))
        config.set("main", "fg_col", json.dumps(self.fg_col))
        config.set("main", "tk_col", json.dumps(self.tk_col))
        config.set("main", "mt_col", json.dumps(self.mt_col))
        config.set("main", "mt_bg_col", json.dumps(self.mute_bg_col))
        config.set("main", "hi_col", json.dumps(self.hi_col))
        config.set("main", "fg_hi_col", json.dumps(self.t_hi_col))
        config.set("main", "bo_col", json.dumps(self.bo_col))
        config.set("main", "avatar_bg_col", json.dumps(self.avatar_bg_col))

        config.set("main", "avatar_size", "%d" % (self.avatar_size))
        config.set("main", "icon_spacing", "%d" % (self.icon_spacing))
        config.set("main", "text_padding", "%d" % (self.text_padding))
        config.set("main", "text_baseline_adj", "%d" %
                   (self.text_baseline_adj))
        if self.font:
            config.set("main", "font", self.font)
        if self.title_font:
            config.set("main", "title_font", self.title_font)
        config.set("main", "square_avatar", "%d" % (int(self.square_avatar)))
        config.set("main", "only_speaking", "%d" % (int(self.only_speaking)))
        config.set("main", "highlight_self", "%d" % (int(self.highlight_self)))
        config.set("main", "icon_only", "%d" % (int(self.icon_only)))
        config.set("main", "monitor", self.monitor)
        config.set("main", "vert_edge_padding", "%d" %
                   (self.vert_edge_padding))
        config.set("main", "horz_edge_padding", "%d" %
                   (self.horz_edge_padding))
        config.set("main", "floating", "%s" % (int(self.floating)))
        config.set("main", "floating_x", "%s" % (int(self.floating_x)))
        config.set("main", "floating_y", "%s" % (int(self.floating_y)))
        config.set("main", "floating_w", "%s" % (int(self.floating_w)))
        config.set("main", "floating_h", "%s" % (int(self.floating_h)))
        config.set("main", "order", "%s" % (self.order))
        config.set("main", "horizontal", "%s" % (self.horizontal))
        config.set("main", "guild_ids", "%s" %
                   guild_ids_to_string(self.guild_ids))
        config.set("main", "overflow", "%s" % (int(self.overflow)))
        config.set("main", "show_connection", "%d" %
                   (int(self.show_connection)))
        config.set("main", "show_title", "%d" % (int(self.show_title)))
        config.set("main", "show_disconnected", "%d" %
                   (int(self.show_disconnected)))
        config.set("main", "border_width", "%s" % (int(self.border_width)))
        config.set("main", "icon_transparency", "%.2f" %
                   (self.icon_transparency))
        config.set("main", "fancy_border", "%d" % (int(self.fancy_border)))

        with open(self.config_file, 'w') as file:
            config.write(file)

    def create_gui(self):
        """
        Prepare the gui
        """
        outer_box = Gtk.Grid()
        outer_box.set_row_spacing(64)
        outer_box.set_column_spacing(64)

        monitor_box = Gtk.Grid()
        alignment_box = Gtk.Grid(row_homogeneous=True)
        colour_box = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        avatar_box = Gtk.Grid(row_homogeneous=True)
        dummy_box = Gtk.Grid(row_homogeneous=True)

        colour_box.set_row_spacing(8)
        colour_box.set_column_spacing(8)

        avatar_box.set_column_spacing(8)
        alignment_box.set_column_spacing(8)

        outer_box.attach(monitor_box, 0, 0, 1, 1)
        outer_box.attach(alignment_box, 0, 1, 1, 1)
        outer_box.attach(colour_box, 1, 0, 1, 1)
        outer_box.attach(avatar_box, 1, 1, 1, 1)
        outer_box.attach(dummy_box, 0, 2, 2, 1)

        # Autohide
        # autohide_label = Gtk.Label.new("Hide on mouseover")
        # autohide = Gtk.CheckButton.new()
        # autohide.set_active(self.autohide)
        # autohide.connect("toggled", self.change_hide_on_mouseover)

        # Font chooser
        font_label = Gtk.Label.new(_("Font"))
        font_label.set_xalign(0)
        font = Gtk.FontButton()
        if self.font:
            font.set_font(self.font)
        font.connect("font-set", self.change_font)
        alignment_box.attach(font_label, 0, 0, 1, 1)
        alignment_box.attach(font, 1, 0, 1, 1)

        # Title Font chooser
        title_font_label = Gtk.Label.new(_("Title Font"))
        title_font_label.set_xalign(0)
        title_font = Gtk.FontButton()
        if self.title_font:
            title_font.set_font(self.title_font)
        title_font.connect("font-set", self.change_title_font)
        alignment_box.attach(title_font_label, 0, 1, 1, 1)
        alignment_box.attach(title_font, 1, 1, 1, 1)

        # Colours
        bg_col = Gtk.ColorButton.new_with_rgba(
            Gdk.RGBA(self.bg_col[0], self.bg_col[1], self.bg_col[2], self.bg_col[3]))
        fg_col = Gtk.ColorButton.new_with_rgba(
            Gdk.RGBA(self.fg_col[0], self.fg_col[1], self.fg_col[2], self.fg_col[3]))
        tk_col = Gtk.ColorButton.new_with_rgba(
            Gdk.RGBA(self.tk_col[0], self.tk_col[1], self.tk_col[2], self.tk_col[3]))
        mt_col = Gtk.ColorButton.new_with_rgba(
            Gdk.RGBA(self.mt_col[0], self.mt_col[1], self.mt_col[2], self.mt_col[3]))
        mute_bg_col = Gtk.ColorButton.new_with_rgba(
            Gdk.RGBA(self.mute_bg_col[0], self.mute_bg_col[1], self.mute_bg_col[2], self.mute_bg_col[3]))
        hi_col = Gtk.ColorButton.new_with_rgba(
            Gdk.RGBA(
                self.hi_col[0],
                self.hi_col[1],
                self.hi_col[2],
                self.hi_col[3]))
        t_hi_col = Gtk.ColorButton.new_with_rgba(
            Gdk.RGBA(
                self.t_hi_col[0],
                self.t_hi_col[1],
                self.t_hi_col[2],
                self.t_hi_col[3]))
        bo_col = Gtk.ColorButton.new_with_rgba(
            Gdk.RGBA(
                self.bo_col[0],
                self.bo_col[1],
                self.bo_col[2],
                self.bo_col[3]
            )
        )
        avatar_bg_col = Gtk.ColorButton.new_with_rgba(
            Gdk.RGBA(
                self.avatar_bg_col[0],
                self.avatar_bg_col[1],
                self.avatar_bg_col[2],
                self.avatar_bg_col[3]

            )
        )
        bg_col.set_use_alpha(True)
        fg_col.set_use_alpha(True)
        tk_col.set_use_alpha(True)
        mt_col.set_use_alpha(True)
        mute_bg_col.set_use_alpha(True)
        hi_col.set_use_alpha(True)
        t_hi_col.set_use_alpha(True)
        bo_col.set_use_alpha(True)
        avatar_bg_col.set_use_alpha(True)
        bg_col.connect("color-set", self.change_bg)
        fg_col.connect("color-set", self.change_fg)
        tk_col.connect("color-set", self.change_tk)
        mt_col.connect("color-set", self.change_mt)
        mute_bg_col.connect("color-set", self.change_mute_bg)
        hi_col.connect("color-set", self.change_hi)
        t_hi_col.connect("color-set", self.change_t_hi)
        bo_col.connect("color-set", self.change_bo)
        avatar_bg_col.connect("color-set", self.change_avatar_bg)

        text_label = Gtk.Label.new(_("Foreground"))
        background_label = Gtk.Label.new(_("Background"))
        talking_label = Gtk.Label.new(_("Talking"))
        idle_label = Gtk.Label.new(_("Idle"))
        border_label = Gtk.Label.new(_("Border"))
        mute_label = Gtk.Label.new(_("Mute"))
        avatar_label = Gtk.Label.new(_("Avatar"))

        colour_box.attach(text_label, 1, 0, 1, 1)
        colour_box.attach(background_label, 2, 0, 1, 1)
        colour_box.attach(border_label, 3, 0, 1, 1)
        colour_box.attach(talking_label, 0, 1, 1, 1)
        colour_box.attach(idle_label, 0, 2, 1, 1)
        colour_box.attach(mute_label, 0, 4, 1, 1)
        colour_box.attach(avatar_label, 0, 5, 1, 1)

        colour_box.attach(bg_col, 2, 2, 1, 1)
        colour_box.attach(hi_col, 2, 1, 1, 1)
        colour_box.attach(fg_col, 1, 2, 1, 1)
        colour_box.attach(t_hi_col, 1, 1, 1, 1)
        colour_box.attach(tk_col, 3, 1, 1, 1)
        colour_box.attach(bo_col, 3, 2, 1, 1)
        colour_box.attach(mute_bg_col, 2, 4, 1, 1)
        colour_box.attach(mt_col, 1, 4, 1, 1)
        colour_box.attach(avatar_bg_col, 2, 5, 1, 1)

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

        self.align_x_store = Gtk.ListStore(str)
        self.align_x_store.append([_("Left")])
        self.align_x_store.append([_("Right")])
        align_x = Gtk.ComboBox.new_with_model(self.align_x_store)
        align_x.set_active(True if self.align_x else False)
        align_x.connect("changed", self.change_align_x)
        renderer_text = Gtk.CellRendererText()
        align_x.pack_start(renderer_text, True)
        align_x.add_attribute(renderer_text, "text", 0)

        self.align_y_store = Gtk.ListStore(str)
        self.align_y_store.append([_("Top")])
        self.align_y_store.append([_("Middle")])
        self.align_y_store.append([_("Bottom")])
        align_y = Gtk.ComboBox.new_with_model(self.align_y_store)
        align_y.set_active(self.align_y)
        align_y.connect("changed", self.change_align_y)
        renderer_text = Gtk.CellRendererText()
        align_y.pack_start(renderer_text, True)
        align_y.add_attribute(renderer_text, "text", 0)

        align_placement_button = Gtk.Button.new_with_label(_("Place Window"))

        align_type_edge.connect("toggled", self.change_align_type_edge)
        align_type_floating.connect("toggled", self.change_align_type_floating)
        align_placement_button.connect("pressed", self.change_placement)

        self.align_x_widget = align_x
        self.align_y_widget = align_y
        self.align_monitor_widget = monitor
        self.align_placement_widget = align_placement_button

        monitor_box.attach(align_label, 0, 0, 2, 1)
        monitor_box.attach(align_type_box, 1, 1, 1, 1)
        monitor_box.attach(monitor, 1, 2, 1, 1)
        monitor_box.attach(align_x, 1, 3, 1, 1)
        monitor_box.attach(align_y, 1, 4, 1, 1)
        monitor_box.attach(align_placement_button, 1, 5, 1, 1)

        # Avatar size
        avatar_size_label = Gtk.Label.new(_("Avatar size"))
        avatar_size_label.set_xalign(0)
        avatar_adjustment = Gtk.Adjustment.new(
            self.avatar_size, 8, 128, 1, 1, 8)
        avatar_size = Gtk.SpinButton.new(avatar_adjustment, 0, 0)
        avatar_size.connect("value-changed", self.change_avatar_size)

        avatar_box.attach(avatar_size_label, 0, 1, 1, 1)
        avatar_box.attach(avatar_size, 1, 1, 1, 1)

        # Avatar shape
        square_avatar_label = Gtk.Label.new(_("Square Avatar"))
        square_avatar_label.set_xalign(0)
        square_avatar = Gtk.CheckButton.new()
        square_avatar.set_active(self.square_avatar)
        square_avatar.connect("toggled", self.change_square_avatar)

        avatar_box.attach(square_avatar_label, 0, 3, 1, 1)
        avatar_box.attach(square_avatar, 1, 3, 1, 1)

        # Fancy Avatar shapes
        fancy_avatar_label = Gtk.Label.new(_("Fancy Avatar shapes"))
        fancy_avatar_label.set_xalign(0)
        fancy_avatar = Gtk.CheckButton.new()
        fancy_avatar.set_active(self.fancy_border)
        fancy_avatar.connect("toggled", self.change_fancy_avatar)

        avatar_box.attach(fancy_avatar_label, 0, 4, 1, 1)
        avatar_box.attach(fancy_avatar, 1 , 4, 1, 1)

        # Display icon only
        icon_only_label = Gtk.Label.new(_("Display Icon Only"))
        icon_only_label.set_xalign(0)
        icon_only = Gtk.CheckButton.new()
        icon_only.set_active(self.icon_only)
        icon_only.connect("toggled", self.change_icon_only)

        avatar_box.attach(icon_only_label, 0, 2, 1, 1)
        avatar_box.attach(icon_only, 1, 2, 1, 1)

        # Display Speaker only
        only_speaking_label = Gtk.Label.new(_("Display Speakers Only"))
        only_speaking_label.set_xalign(0)
        only_speaking = Gtk.CheckButton.new()
        only_speaking.set_active(self.only_speaking)
        only_speaking.connect("toggled", self.change_only_speaking)

        alignment_box.attach(only_speaking_label, 0, 9, 1, 1)
        alignment_box.attach(only_speaking, 1, 9, 1, 1)

        # Highlight self
        highlight_self_label = Gtk.Label.new(_("Highlight Self"))
        highlight_self_label.set_xalign(0)
        highlight_self = Gtk.CheckButton.new()
        highlight_self.set_active(self.highlight_self)
        highlight_self.connect("toggled", self.change_highlight_self)

        alignment_box.attach(highlight_self_label, 0, 8, 1, 1)
        alignment_box.attach(highlight_self, 1, 8, 1, 1)

        # Order avatars
        order_label = Gtk.Label.new(_("Order Avatars By"))
        order_label.set_xalign(0)
        order_store = Gtk.ListStore(str)
        order_store.append([_("Alphabetically")])
        order_store.append([_("ID")])
        order_store.append([_("Last Spoken")])
        order = Gtk.ComboBox.new_with_model(order_store)
        order.set_active(self.order)
        order.connect("changed", self.change_order)
        renderer_text = Gtk.CellRendererText()
        order.pack_start(renderer_text, True)
        order.add_attribute(renderer_text, "text", 0)

        avatar_box.attach(order_label, 0, 6, 1, 1)
        avatar_box.attach(order, 1, 6, 1, 1)

        # Icon spacing
        icon_spacing_label = Gtk.Label.new(_("Icon Spacing"))
        icon_spacing_label.set_xalign(0)
        icon_spacing_adjustment = Gtk.Adjustment.new(
            self.icon_spacing, 0, 64, 1, 1, 0)
        icon_spacing = Gtk.SpinButton.new(icon_spacing_adjustment, 0, 0)
        icon_spacing.connect("value-changed", self.change_icon_spacing)

        alignment_box.attach(icon_spacing_label, 0, 2, 1, 1)
        alignment_box.attach(icon_spacing, 1, 2, 1, 1)

        # Text padding
        text_padding_label = Gtk.Label.new(_("Text Padding"))
        text_padding_label.set_xalign(0)
        text_padding_adjustment = Gtk.Adjustment.new(
            self.text_padding, 0, 64, 1, 1, 0)
        text_padding = Gtk.SpinButton.new(text_padding_adjustment, 0, 0)
        text_padding.connect("value-changed", self.change_text_padding)

        alignment_box.attach(text_padding_label, 0, 3, 1, 1)
        alignment_box.attach(text_padding, 1, 3, 1, 1)

        # Text Baseline Adjustment
        text_baseline_label = Gtk.Label.new(_("Text Vertical Offset"))
        text_baseline_label.set_xalign(0)
        text_baseline_adjustment = Gtk.Adjustment.new(
            self.text_baseline_adj, -32, 32, 1, 1, 0)
        text_baseline = Gtk.SpinButton.new(text_baseline_adjustment, 0, 0)
        text_baseline.connect("value-changed", self.change_text_baseline)

        alignment_box.attach(text_baseline_label, 0, 4, 1, 1)
        alignment_box.attach(text_baseline, 1, 4, 1, 1)

        # Edge padding
        vert_edge_padding_label = Gtk.Label.new(_("Vertical Edge Padding"))
        vert_edge_padding_label.set_xalign(0)
        vert_edge_padding_adjustment = Gtk.Adjustment.new(
            self.vert_edge_padding, 0, 1000, 1, 1, 0)
        vert_edge_padding = Gtk.SpinButton.new(
            vert_edge_padding_adjustment, 0, 0)
        vert_edge_padding.connect(
            "value-changed", self.change_vert_edge_padding)

        alignment_box.attach(vert_edge_padding_label, 0, 5, 1, 1)
        alignment_box.attach(vert_edge_padding, 1, 5, 1, 1)

        horz_edge_padding_label = Gtk.Label.new(_("Horizontal Edge Padding"))
        horz_edge_padding_adjustment = Gtk.Adjustment.new(
            self.horz_edge_padding, 0, 1000, 1, 1, 0)
        horz_edge_padding = Gtk.SpinButton.new(
            horz_edge_padding_adjustment, 0, 0)
        horz_edge_padding.connect(
            "value-changed", self.change_horz_edge_padding)

        alignment_box.attach(horz_edge_padding_label, 0, 6, 1, 1)
        alignment_box.attach(horz_edge_padding, 1, 6, 1, 1)

        # Border width
        border_width_label = Gtk.Label.new(_("Talking border width"))
        border_width_label.set_xalign(0)
        border_width_adjustment = Gtk.Adjustment.new(
            self.border_width, 2, 100, 1, 1, 0)
        border_width = Gtk.SpinButton.new(border_width_adjustment, 0, 0)
        border_width.connect("value-changed", self.change_border_width)

        avatar_box.attach(border_width_label, 0, 7, 1, 1)
        avatar_box.attach(border_width, 1, 7, 1, 1)

        # Icon Transparency
        icon_transparency_label = Gtk.Label.new(_("Icon Opacity"))
        icon_transparency_label.set_xalign(0)
        icon_transparency_adjustment = Gtk.Adjustment.new(
            self.icon_transparency, 0.5, 1.0, 0.01, 0.1, 0.0)
        icon_transparency = Gtk.HScale.new(icon_transparency_adjustment)
        icon_transparency.connect(
            "value-changed", self.change_icon_transparency)

        avatar_box.attach(icon_transparency_label, 0, 0, 1, 1)
        avatar_box.attach(icon_transparency, 1, 0, 1, 1)

        # Display icon horizontally
        horizontal_label = Gtk.Label.new(_("Display Horizontally"))
        horizontal_label.set_xalign(0)
        horizontal = Gtk.CheckButton.new()
        horizontal.set_active(self.horizontal)
        horizontal.connect("toggled", self.change_horizontal)

        alignment_box.attach(horizontal_label, 0, 7, 1, 1)
        alignment_box.attach(horizontal, 1, 7, 1, 1)

        # Overflow
        overflow_label = Gtk.Label.new(_("Overflow style"))
        overflow_label.set_xalign(0)
        overflow_store = Gtk.ListStore(str)
        overflow_store.append([_("None")])
        overflow_store.append([_("Wrap")])
        overflow_store.append([_("Shrink")])
        overflow = Gtk.ComboBox.new_with_model(overflow_store)
        overflow.set_active(self.overflow)
        overflow.connect("changed", self.change_overflow)
        renderer_text = Gtk.CellRendererText()
        overflow.pack_start(renderer_text, True)
        overflow.add_attribute(renderer_text, "text", 0)

        avatar_box.attach(overflow_label, 0, 8, 1, 1)
        avatar_box.attach(overflow, 1, 8, 1, 1)

        # Show Title
        show_title_label = Gtk.Label.new(_("Show Title"))
        show_title_label.set_xalign(0)
        show_title = Gtk.CheckButton.new()
        show_title.set_active(self.show_title)
        show_title.connect("toggled", self.change_show_title)

        avatar_box.attach(show_title_label, 0, 9, 1, 1)
        avatar_box.attach(show_title, 1, 9, 1, 1)

        # Show Connection
        show_connection_label = Gtk.Label.new(_("Show Connection Status"))
        show_connection_label.set_xalign(0)
        show_connection = Gtk.CheckButton.new()
        show_connection.set_active(self.show_connection)
        show_connection.connect("toggled", self.change_show_connection)

        avatar_box.attach(show_connection_label, 0, 10, 1, 1)
        avatar_box.attach(show_connection, 1, 10, 1, 1)

        # Show Disconnected
        show_disconnected_label = Gtk.Label.new(_("Show while disconnected"))
        show_disconnected_label.set_xalign(0)
        show_disconnected = Gtk.CheckButton.new()
        show_disconnected.set_active(self.show_disconnected)
        show_disconnected.connect("toggled", self.change_show_disconnected)

        avatar_box.attach(show_disconnected_label, 0, 11, 1, 1)
        avatar_box.attach(show_disconnected, 1, 11, 1, 1)

        # use dummy
        dummy_label = Gtk.Label.new(_("Show test content"))
        dummy_label.set_xalign(0)
        dummy = Gtk.CheckButton.new()
        dummy.set_active(self.show_dummy)
        dummy.connect("toggled", self.change_dummy_data)

        dummy_box.attach(dummy_label, 0, 0, 1, 1)
        dummy_box.attach(dummy, 1, 0, 1, 1)

        # Dummy count
        dummy_count_label = Gtk.Label.new(_("Dummy count"))
        dummy_count_label.set_xalign(0)
        dummy_count_adjustment = Gtk.Adjustment.new(
            self.dummy_count, 0, 100, 1, 1, 0)
        dummy_count = Gtk.SpinButton.new(
            dummy_count_adjustment, 0, 0)
        dummy_count.connect(
            "value-changed", self.change_dummy_count)

        dummy_box.attach(dummy_count_label, 2, 0, 1, 1)
        dummy_box.attach(dummy_count, 3, 0, 1, 1)

        self.add(outer_box)

        self.set_orientated_names()

    def change_font(self, button):
        """
        Font settings changed
        """
        font = button.get_font()
        self.overlay.set_font(font)

        self.font = font
        self.save_config()

    def change_title_font(self, button):
        """
        Font settings changed
        """
        title_font = button.get_font()
        self.overlay.set_title_font(title_font)

        self.title_font = title_font
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
        Text colour changed
        """
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.overlay.set_fg(colour)

        self.fg_col = colour
        self.save_config()

    def change_tk(self, button):
        """
        Talking colour changed
        """
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.overlay.set_tk(colour)

        self.tk_col = colour
        self.save_config()

    def change_mt(self, button):
        """
        Mute colour changed
        """
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.overlay.set_mt(colour)

        self.mt_col = colour
        self.save_config()
    
    def change_mute_bg(self, button):
        """
        Mute background colour changed
        """
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.overlay.set_mute_bg(colour)

        self.mute_bg_col = colour
        self.save_config()
    
    def change_avatar_bg(self, button):
        """
        Avatar background colour changed
        """
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.overlay.set_avatar_bg_col(colour)

        self.avatar_bg_col = colour
        self.save_config()        

    def change_hi(self, button):
        """
        Speaking background colour changed
        """
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.overlay.set_hi(colour)

        self.hi_col = colour
        self.save_config()

    def change_t_hi(self, button):
        """
        Speaking background colour changed
        """
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.overlay.set_fg_hi(colour)

        self.t_hi_col = colour
        self.save_config()

    def change_bo(self, button):
        """
        Idle border colour changed
        """
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.overlay.set_bo(colour)

        self.bo_col = colour
        self.save_config()

    def change_avatar_size(self, button):
        """
        Avatar size setting changed
        """
        self.overlay.set_avatar_size(button.get_value())

        self.avatar_size = button.get_value()
        self.save_config()

    def change_icon_spacing(self, button):
        """
        Inter-icon spacing changed
        """
        self.overlay.set_icon_spacing(button.get_value())

        self.icon_spacing = int(button.get_value())
        self.save_config()

    def change_text_padding(self, button):
        """
        Text padding changed
        """
        self.overlay.set_text_padding(button.get_value())

        self.text_padding = button.get_value()
        self.save_config()

    def change_text_baseline(self, button):
        """
        Text baseline changed
        """
        self.overlay.set_text_baseline_adj(button.get_value())

        self.text_baseline_adj = button.get_value()
        self.save_config()

    def change_vert_edge_padding(self, button):
        """
        Vertical padding changed
        """
        self.overlay.set_vert_edge_padding(button.get_value())

        self.vert_edge_padding = button.get_value()
        self.save_config()

    def change_horz_edge_padding(self, button):
        """
        Horizontal padding changed
        """
        self.overlay.set_horz_edge_padding(button.get_value())

        self.horz_edge_padding = button.get_value()
        self.save_config()

    def change_square_avatar(self, button):
        """
        Square avatar setting changed
        """
        self.overlay.set_square_avatar(button.get_active())

        self.square_avatar = button.get_active()
        self.save_config()

    def change_fancy_avatar(self, button):
        """
        Fancy avatar border shapes changed
        """
        self.overlay.set_fancy_border(button.get_active())
        self.fancy_avatar = button.get_active()
        self.save_config() 

    def change_only_speaking(self, button):
        """
        Show only speaking users setting changed
        """
        self.overlay.set_only_speaking(button.get_active())

        self.only_speaking = button.get_active()
        self.save_config()

    def change_highlight_self(self, button):
        """
        Highlight self setting changed
        """
        self.overlay.set_highlight_self(button.get_active())

        self.highlight_self = button.get_active()
        self.save_config()

    def change_icon_only(self, button):
        """
        Icon only setting changed
        """
        self.overlay.set_icon_only(button.get_active())

        self.icon_only = button.get_active()
        self.save_config()

    def change_order(self, button):
        """
        Order user setting changed
        """
        self.overlay.set_order(button.get_active())

        self.order = button.get_active()
        self.save_config()

    def change_horizontal(self, button):
        """
        Horizontal layout setting changed
        """
        self.overlay.set_horizontal(button.get_active())

        self.horizontal = button.get_active()
        self.save_config()
        self.set_orientated_names()

    def change_dummy_data(self, button):
        self.overlay.set_show_dummy(button.get_active())
        self.show_dummy = button.get_active()
        if self.show_dummy:
            self.overlay.set_enabled(True)
            self.overlay.set_hidden(False)

    def change_dummy_count(self, button):
        self.overlay.set_dummy_count(int(button.get_value()))
        self.dummy_count = button.get_value()

    def change_overflow(self, button):
        self.overlay.set_overflow(button.get_active())
        self.overflow = button.get_active()
        self.save_config()

    def change_show_title(self, button):
        self.overlay.set_show_title(button.get_active())
        self.show_title = button.get_active()
        self.save_config()

    def change_show_connection(self, button):
        self.overlay.set_show_connection(button.get_active())
        self.show_connection = button.get_active()
        self.save_config()

    def change_show_disconnected(self, button):
        self.overlay.set_show_disconnected(button.get_active())
        self.show_disconnected = button.get_active()
        self.save_config()

    def change_border_width(self, button):
        self.overlay.set_border_width(button.get_value())
        self.border_width = button.get_value()
        self.save_config()

    def change_icon_transparency(self, button):
        self.overlay.set_icon_transparency(button.get_value())
        self.icon_transparency = button.get_value()
        self.save_config()

    def on_guild_selection_changed(self, tree, number, selection):
        model, treeiter = tree.get_selection().get_selected()
        if treeiter is not None:
            model[treeiter][0] = not model[treeiter][0]
            if model[treeiter][0]:
                self.add_guild(model[treeiter][3])
            else:
                self.remove_guild(model[treeiter][3])

    def add_guild(self, guild):
        self.guild_ids.append(guild)
        self.overlay.set_guild_ids(self.guild_ids)
        self.save_config()

    def remove_guild(self, guild):
        self.guild_ids.remove(guild)
        self.overlay.set_guild_ids(self.guild_ids)
        self.save_config()

    def change_guild_ids(self, input):
        """
        Guild IDs replaced
        """
        self.guild_ids = parse_guild_ids(input.get_text())
        self.overlay.set_guild_ids(self.guild_ids)
        self.save_config()

    def guild_filter_changed(self, entry):
        """
        Change the filter string for guilds
        """
        self.guild_filter_string = entry.get_text()
        self.guild_ids_filter.refilter()

    def guild_filter_func(self, model, iter, data):
        """
        Decide if a guild is shown in the list of guilds
        """
        if self.guild_filter_string in model[iter][2]:
            return True
        return False

    def set_orientated_names(self):
        i = self.align_x_store.get_iter_first()
        i2 = self.align_y_store.get_iter_first()
        if self.horizontal:
            self.align_x_store.set_value(i, 0, _("Top"))
            i = self.align_x_store.iter_next(i)
            self.align_x_store.set_value(i, 0, _("Bottom"))

            self.align_y_store.set_value(i2, 0, _("Left"))
            i2 = self.align_y_store.iter_next(i2)
            self.align_y_store.set_value(i2, 0, _("Middle"))
            i2 = self.align_y_store.iter_next(i2)
            self.align_y_store.set_value(i2, 0, _("Right"))
        else:
            self.align_x_store.set_value(i, 0, _("Left"))
            i = self.align_x_store.iter_next(i)
            self.align_x_store.set_value(i, 0, _("Right"))

            self.align_y_store.set_value(i2, 0, _("Top"))
            i2 = self.align_y_store.iter_next(i2)
            self.align_y_store.set_value(i2, 0, _("Middle"))
            i2 = self.align_y_store.iter_next(i2)
            self.align_y_store.set_value(i2, 0, _("Bottom"))
