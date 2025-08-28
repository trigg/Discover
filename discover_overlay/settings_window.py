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
"""Settings window holding all settings tab"""
# pylint: disable=missing-function-docstring
import gettext
import logging
import sys
import os
import json
from configparser import ConfigParser
import gi
import pkg_resources
from .autostart import Autostart, BazziteAutostart
from .draggable_window import DraggableWindow
from .draggable_window_wayland import DraggableWindowWayland

gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Gtk, Gdk, Gio  # nopep8

log = logging.getLogger(__name__)
t = gettext.translation(
    'default', pkg_resources.resource_filename('discover_overlay', 'locales'), fallback=True)
_ = t.gettext


class MainSettingsWindow():
    """Settings class"""

    def __init__(self, config_file, rpc_file, channel_file, args):
        self.args = args
        # Detect Bazzite autostart
        self.alternative_autostart = os.path.exists(
            "/etc/default/discover-overlay")
        # Detect flatpak en
        self.disable_autostart = 'container' in os.environ
        self.icon_name = "discover-overlay"
        self.tray_icon_name = "discover-overlay-tray"

        self.spinning_focus = None
        self.scale_focus = None

        icon_theme = Gtk.IconTheme.get_default()
        icon_theme.add_resource_path(os.path.expanduser(
            '~/.local/share/pipx/venvs/discover-overlay/share/icons'))
        if not icon_theme.has_icon("discover-overlay"):
            log.error("No icon found in theme")
            self.icon_name = 'user-info'
        if not icon_theme.has_icon(self.tray_icon_name):
            log.error("No tray icon found in theme")
            self.tray_icon_name = 'user-info'
        self.steamos = False
        self.voice_placement_window = None
        self.text_placement_window = None
        self.tray = None  # Systemtray as fallback
        self.ind = None  # AppIndicator
        if self.alternative_autostart:
            self.autostart_helper = BazziteAutostart()
        else:
            self.autostart_helper = Autostart("discover_overlay")

        self.autostart_helper_conf = Autostart("discover_overlay_configure")
        self.ind = None
        self.guild_ids = []
        self.channel_ids = []
        self.current_guild = "0"
        self.current_channel = "0"
        self.hidden_overlay = False
        self.voice_floating_x = 0
        self.voice_floating_y = 0
        self.voice_floating_w = 0
        self.voice_floating_h = 0
        self.text_floating_x = 0
        self.text_floating_y = 0
        self.text_floating_w = 0
        self.text_floating_h = 0

        self.menu = self.make_menu()
        self.make_sys_tray_icon(self.menu)

        self.config_file = config_file
        self.rpc_file = rpc_file
        self.channel_file = channel_file

        self.loading_config = False

        builder = Gtk.Builder.new_from_file(pkg_resources.resource_filename(
            'discover_overlay', 'glade/settings.glade'))
        window = builder.get_object("settings_window")
        window.connect("destroy", self.close_window)
        window.connect("delete-event", self.close_window)

        window.set_default_size(1280, 800)

        # Make an array of all named widgets
        self.widget = {}
        for widget in builder.get_objects():
            if widget.find_property("name"):
                name = widget.get_property("name")
                if name == "":
                    log.error("Unnamed widget. All widgets must be named")
                    log.info(widget)
                self.widget[name] = widget

                # Translate labels and buttons
                if name.endswith("_label"):
                    widget.set_label(_(widget.get_label()))
                if name.endswith("_button"):
                    widget.set_label(_(widget.get_label()))
                if name.endswith("_all"):
                    widget.set_label(_(widget.get_label()))

        self.widget['overview_main_text'].set_markup(
            "%s%s (%s)%s%s\n\n%s %s %s %s%s\n\n\n\n\n\n" % (
                "<span size=\"larger\">",
                _("Welcome to Discover Overlay"),
                pkg_resources.get_distribution('discover_overlay').version,
                "</span>\n\n",
                _("Discover-Overlay is a GTK3 overlay written in Python3."
                   " It can be configured to show who is currently talking"
                   " on discord or it can be set to display text and images"
                   " from a preconfigured channel. It is fully customisable"
                   " and can be configured to display anywhere on the screen."
                   " We fully support X11 and wlroots based environments. We "
                   "felt the need to make this project due to the shortcomings"
                   " in support on Linux by the official discord client."),
                _("Please visit our discord"),
                "(<a href=\"https://discord.gg/jRKWMuDy5V\">https://discord.gg/jRKWMuDy5V</a>)",
                _(" for support. Or open an issue on our GitHub "),
                "(<a href=\"https://github.com/trigg/Discover\">",
                "https://github.com/trigg/Discover</a>)"
            )
        )

        screen = window.get_screen()
        screen_type = f"{screen}"
        self.is_wayland = False
        if "Wayland" in screen_type:
            self.is_wayland = True
        self.window = window

        if "GAMESCOPE_WAYLAND_DISPLAY" in os.environ:
            self.steamos = True
            log.info(
                "GameScope session detected. Enabling steam and gamescope integration")
            self.steamos = True
            settings = Gtk.Settings.get_default()
            if settings:
                settings.set_property(
                    "gtk-application-prefer-dark-theme", Gtk.true)
            self.set_steamos_window_size()

            # Larger fonts needed
            css = Gtk.CssProvider.new()
            css.load_from_data(bytes("* { font-size:18px; }", "utf-8"))
            window.get_style_context().add_provider(
                css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        else:
            self.widget['overview_close_button'].hide()

        self.super_focus = Gtk.CssProvider.new()
        self.super_focus.load_from_data(
            bytes(
                """scale { background-color: rgba(100%, 0%, 0%, 0.3); background-image:unset; }
                   spinbutton { background-color: rgba(100%, 0%, 0%, 0.3); background-image:unset;}
                """, "utf-8"))

        # Fill monitor & guild menus
        self.populate_monitor_menus()
        window.get_screen().connect("monitors-changed", self.populate_monitor_menus)

        channel_file = Gio.File.new_for_path(channel_file)
        self.monitor_channel = channel_file.monitor_file(0, None)
        self.monitor_channel.connect("changed", self.populate_guild_menu)

        self.server_handler = self.widget['text_server'].connect(
            'changed', self.text_server_changed)
        self.channel_handler = self.widget['text_channel'].connect(
            'changed', self.text_channel_changed)
        self.hidden_overlay_handler = self.widget['core_hide_overlay'].connect(
            'toggled', self.core_hide_overlay_changed)

        self.read_config()

        self.populate_guild_menu()

        builder.connect_signals(self)
        window.connect('key-press-event', self.keypress_in_settings)

        if '--minimized' in self.args:
            self.start_minimized = True
        if not self.start_minimized or not self.show_sys_tray_icon:
            window.show()

        if self.icon_name != 'discover-overlay':
            self.widget['overview_image'].set_from_icon_name(
                self.icon_name, Gtk.IconSize.DIALOG)
            self.widget['window'].set_default_icon_name(self.icon_name)

    def set_steamos_window_size(self):
        """Set window based on steamos usage"""
        # Huge bunch of assumptions.
        # Gamescope only has one monitor
        # Gamescope has no scale factor
        display = Gdk.Display.get_default()
        if "get_monitor" in dir(display):
            monitor = display.get_monitor(0)
            if monitor:
                geometry = monitor.get_geometry()
                log.info("%d %d", geometry.width, geometry.height)
                self.window.set_size_request(geometry.width, geometry.height)

    def keypress_in_settings(self, window, event):
        """Callback to steal keypresses to assist SteamOS gamepad control"""
        if self.spinning_focus:
            match event.keyval:
                case Gdk.KEY_Right:
                    step = self.spinning_focus.get_increments().step
                    value = self.spinning_focus.get_value()
                    self.spinning_focus.set_value(value + step)
                case Gdk.KEY_Left:
                    step = self.spinning_focus.get_increments().step
                    value = self.spinning_focus.get_value()
                    self.spinning_focus.set_value(value - step)
                case Gdk.KEY_Up:
                    step = self.spinning_focus.get_increments().step
                    value = self.spinning_focus.get_value()
                    self.spinning_focus.set_value(value + step)
                case Gdk.KEY_Down:
                    step = self.spinning_focus.get_increments().step
                    value = self.spinning_focus.get_value()
                    self.spinning_focus.set_value(value - step)
                case Gdk.KEY_space:
                    self.spinning_focus.get_style_context().remove_provider(self.super_focus)
                    self.spinning_focus = None
                case Gdk.KEY_Escape:
                    self.spinning_focus.get_style_context().remove_provider(self.super_focus)

                    self.spinning_focus = None
        elif self.scale_focus:
            match event.keyval:
                case Gdk.KEY_Right:
                    value = self.scale_focus.get_value()
                    self.scale_focus.set_value(value + 0.1)
                case Gdk.KEY_Left:
                    value = self.scale_focus.get_value()
                    self.scale_focus.set_value(value - 0.1)
                case Gdk.KEY_Up:
                    value = self.scale_focus.get_value()
                    self.scale_focus.set_value(value + 0.1)
                case Gdk.KEY_Down:
                    value = self.scale_focus.get_value()
                    self.scale_focus.set_value(value - 0.1)
                case Gdk.KEY_space:
                    self.scale_focus.get_style_context().remove_provider(self.super_focus)
                    self.scale_focus = None
                case Gdk.KEY_Escape:
                    self.scale_focus.get_style_context().remove_provider(self.super_focus)
                    self.scale_focus = None
        else:
            match event.keyval:
                case Gdk.KEY_Left:
                    window.do_move_focus(window, Gtk.DirectionType.LEFT)
                case Gdk.KEY_Right:
                    window.do_move_focus(window, Gtk.DirectionType.RIGHT)
                case Gdk.KEY_Up:
                    window.do_move_focus(window, Gtk.DirectionType.UP)
                case Gdk.KEY_Down:
                    window.do_move_focus(window, Gtk.DirectionType.DOWN)
                case Gdk.KEY_F1:
                    self.widget['notebook'].prev_page()
                case Gdk.KEY_F2:
                    self.widget['notebook'].next_page()
                case Gdk.KEY_Escape:
                    return True
                case Gdk.KEY_space:
                    widget = self.window.get_focus()
                    if widget:
                        # I really want there to be a better way...
                        widget_type = f"{widget}"
                        if 'Gtk.SpinButton' in widget_type:
                            self.spinning_focus = widget

                            widget.get_style_context().add_provider(
                                self.super_focus, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                            return True
                        elif 'Gtk.Scale' in widget_type:
                            self.scale_focus = widget
                            widget.get_style_context().add_provider(
                                self.super_focus, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                            return True
                    return False
                case _:
                    return False
        return True

    def request_channels_from_guild(self, guild_id):
        """Send RPC to overlay to request updated channel list"""
        with open(self.rpc_file, 'w', encoding="utf-8") as f:
            f.write(f"--rpc --guild-request={guild_id}")

    def populate_guild_menu(self, _a=None, _b=None, _c=None, _d=None):
        """Read guild data and repopulate widget.
         Disable signal handling meanwhile to avoid recursive logic"""
        g = self.widget['text_server']
        c = self.widget['text_channel']
        g.handler_block(self.server_handler)
        c.handler_block(self.channel_handler)
        try:
            with open(self.channel_file, "r", encoding="utf-8") as tfile:
                data = tfile.readlines()
                if len(data) >= 1:
                    data = json.loads(data[0])
                    self.guild_ids = []
                    self.channel_ids = []
                    g.remove_all()
                    c.remove_all()
                    for guild in data['guild'].values():
                        g.append_text(guild['name'])
                        self.guild_ids.append(guild['id'])
                        if guild['id'] == self.current_guild and 'channels' in guild:
                            for channel in guild['channels']:
                                c.append_text(channel['name'])
                                self.channel_ids.append(channel['id'])
        except FileNotFoundError:
            pass

        if self.current_guild != "0" and self.current_guild in self.guild_ids:
            g.set_active(self.guild_ids.index(self.current_guild))

        if self.current_channel != "0" and self.current_channel in self.channel_ids:
            c.set_active(self.channel_ids.index(self.current_channel))

        g.handler_unblock(self.server_handler)
        c.handler_unblock(self.channel_handler)

    def populate_monitor_menus(self, _a=None, _b=None):
        """Get Monitor list from GTK and repopulate widget"""
        voice = self.widget['voice_monitor']
        text = self.widget['text_monitor']
        notify = self.widget['notification_monitor']

        v_value = voice.get_active()
        t_value = text.get_active()
        m_value = notify.get_active()

        voice.remove_all()
        text.remove_all()
        notify.remove_all()

        voice.append_text("Any")
        text.append_text("Any")
        notify.append_text("Any")

        display = Gdk.Display.get_default()
        screen = self.window.get_screen()
        if "get_n_monitors" in dir(display):
            count_monitors = display.get_n_monitors()
            if count_monitors >= 1:
                for i in range(0, count_monitors):
                    this_mon = display.get_monitor(i)
                    manufacturer = this_mon.get_manufacturer()
                    model = this_mon.get_model()
                    connector = screen.get_monitor_plug_name(i)
                    monitor_label = f"{manufacturer} {model}\n{connector}"
                    voice.append_text(monitor_label)
                    text.append_text(monitor_label)
                    notify.append_text(monitor_label)

        voice.set_active(v_value)
        text.set_active(t_value)
        notify.set_active(m_value)

    def close_window(self, _widget=None, _event=None):
        """Hide the settings window for use at a later date"""
        self.window.hide()
        if self.ind is None and self.tray is None:
            sys.exit(0)
        if self.ind is not None:
            # pylint: disable=import-outside-toplevel
            from gi.repository import AppIndicator3
            if self.ind.get_status() == AppIndicator3.IndicatorStatus.PASSIVE:
                sys.exit(0)
        return True

    def close_app(self, _widget=None, _event=None):
        """Close the app"""
        sys.exit(0)

    def present_settings(self, _a=None):
        """Show the settings window"""
        self.widget['notebook'].set_current_page(0)
        self.window.show()

    def set_alignment_labels(self, horz):
        """Relabel alignment pulldowns"""
        m1 = self.widget['voice_align_1'].get_model()
        m2 = self.widget['voice_align_2'].get_model()
        i = m1.get_iter_first()
        i2 = m2.get_iter_first()
        if horz:
            m1.set_value(i, 0, _("Top"))
            i = m1.iter_next(i)
            m1.set_value(i, 0, _("Bottom"))

            m2.set_value(i2, 0, _("Left"))
            i2 = m2.iter_next(i2)
            m2.set_value(i2, 0, _("Middle"))
            i2 = m2.iter_next(i2)
            m2.set_value(i2, 0, _("Right"))
        else:
            m1.set_value(i, 0, _("Left"))
            i = m1.iter_next(i)
            m1.set_value(i, 0, _("Right"))

            m2.set_value(i2, 0, _("Top"))
            i2 = m2.iter_next(i2)
            m2.set_value(i2, 0, _("Middle"))
            i2 = m2.iter_next(i2)
            m2.set_value(i2, 0, _("Bottom"))

    def read_config(self):
        """Read config from disk"""
        self.loading_config = True

        # Read config and put into gui
        config = ConfigParser(interpolation=None)
        config.read(self.config_file)

        # Read Voice section

        self.voice_floating_x = config.getfloat(
            "main", "floating_x", fallback=0)
        self.voice_floating_y = config.getfloat(
            "main", "floating_y", fallback=0)
        self.voice_floating_w = config.getfloat(
            "main", "floating_w", fallback=400)
        self.voice_floating_h = config.getfloat(
            "main", "floating_h", fallback=400)

        self.widget['voice_anchor_float'].set_active(
            0 if config.getboolean("main", "floating", fallback=False) else 1)
        self.update_floating_anchor()

        self.widget['voice_align_1'].set_active(
            config.getboolean("main", "rightalign", fallback=False))
        self.widget['voice_align_2'].set_active(
            config.getint("main", "topalign", fallback=1))

        self.widget['voice_monitor'].set_active(
            self.get_monitor_index_from_plug(
                config.get("main", "monitor", fallback="Any")
            )
        )

        font = config.get("main", "font", fallback=None)
        if font:
            self.widget['voice_font'].set_font(font)
        title_font = config.get("main", "title_font", fallback=None)
        if title_font:
            self.widget['voice_title_font'].set_font(title_font)

        self.widget['voice_icon_spacing'].set_value(
            config.getint("main", "icon_spacing", fallback=8))

        self.widget['voice_text_padding'].set_value(
            config.getint("main", "text_padding", fallback=6))

        self.widget['voice_text_vertical_offset'].set_value(
            config.getint("main", "text_baseline_adj", fallback=0))

        self.widget['voice_vertical_padding'].set_value(
            config.getint("main", "vert_edge_padding", fallback=0))

        self.widget['voice_horizontal_padding'].set_value(
            config.getint("main", "horz_edge_padding", fallback=0))

        horz = config.getboolean("main", "horizontal", fallback=False)
        self.set_alignment_labels(horz)
        self.widget['voice_display_horizontally'].set_active(horz)

        self.widget['voice_highlight_self'].set_active(
            config.getboolean("main", "highlight_self", fallback=False))

        self.widget['voice_display_speakers_only'].set_active(
            config.getboolean("main", "only_speaking", fallback=False))

        self.widget['voice_display_speakers_grace_period'].set_value(
            config.getint("main", "only_speaking_grace", fallback=0))

        self.widget['voice_show_test_content'].set_active(
            config.getboolean("main", "show_dummy", fallback=False))

        self.widget['voice_talking_foreground'].set_rgba(self.make_colour(config.get(
            "main", "fg_hi_col", fallback="[1.0,1.0,1.0,1.0]")))

        self.widget['voice_talking_background'].set_rgba(self.make_colour(config.get(
            "main", "hi_col", fallback="[0.0,0.0,0.0,0.5]")))

        self.widget['voice_talking_border'].set_rgba(self.make_colour(config.get(
            "main", "tk_col", fallback="[0.0,0.7,0.0,1.0]")))

        self.widget['voice_idle_foreground'].set_rgba(self.make_colour(config.get(
            "main", "fg_col", fallback="[1.0,1.0,1.0,1.0]")))

        self.widget['voice_idle_background'].set_rgba(self.make_colour(config.get(
            "main", "bg_col", fallback="[0.0,0.0,0.0,0.5]")))

        self.widget['voice_idle_border'].set_rgba(self.make_colour(config.get(
            "main", "bo_col", fallback="[0.0,0.0,0.0,0.0]")))

        self.widget['voice_mute_foreground'].set_rgba(self.make_colour(config.get(
            "main", "mt_col", fallback="[0.6,0.0,0.0,1.0]")))

        self.widget['voice_mute_background'].set_rgba(self.make_colour(config.get(
            "main", "mt_bg_col", fallback="[0.0,0.0,0.0,0.5]")))

        self.widget['voice_avatar_background'].set_rgba(self.make_colour(config.get(
            "main", "avatar_bg_col", fallback="[0.0,0.0,0.0,0.0]")))

        self.widget['voice_avatar_opacity'].set_value(config.getfloat(
            "main", "icon_transparency", fallback=1.0))

        self.widget['voice_nick_length'].set_value(
            config.getint("main", "nick_length", fallback=32))

        self.widget['voice_avatar_size'].set_value(
            config.getint("main", "avatar_size", fallback=48))

        show_name = not config.getboolean("main", "icon_only", fallback=False)
        self.widget['voice_display_icon_only'].set_active(show_name)
        self.voice_show_name_hide_others(show_name)

        self.widget['voice_square_avatar'].set_active(config.getboolean(
            "main", "square_avatar", fallback=True))

        self.widget['voice_fancy_avatar_shapes'].set_active(
            config.getboolean("main", "fancy_border", fallback=True))

        self.widget['voice_order_avatars_by'].set_active(
            config.getint("main", "order", fallback=0))

        self.widget['voice_border_width'].set_value(
            config.getint("main", "border_width", fallback=2))

        self.widget['voice_overflow_style'].set_active(
            config.getint("main", "overflow", fallback=0))

        self.widget['voice_show_title'].set_active(config.getboolean(
            "main", "show_title", fallback=False))

        show_avatar = config.getboolean(
            "main", "show_avatar", fallback=True)
        self.widget['voice_show_avatar'].set_active(show_avatar)
        self.voice_show_avatar_hide_others(show_avatar)

        self.widget['voice_show_connection_status'].set_active(config.getboolean(
            "main", "show_connection", fallback=False))

        self.widget['voice_show_disconnected'].set_active(config.getboolean(
            "main", "show_disconnected", fallback=False))

        self.widget['voice_dummy_count'].set_value(
            config.getint("main", "dummy_count", fallback=50))

        self.widget['voice_inactive_fade'].set_active(
            config.getboolean("main", "fade_out_inactive", fallback=False)
        )
        self.widget['voice_inactive_opacity'].set_value(
            config.getfloat("main", "fade_out_limit", fallback=0.3)
        )
        self.widget['voice_inactive_time'].set_value(
            config.getint("main", "inactive_time", fallback=10)
        )
        self.widget['voice_inactive_fade_time'].set_value(
            config.getint("main", "inactive_fade_time", fallback=30)
        )
        self.widget['voice_hide_mouseover'].set_active(
            config.getboolean("main", "autohide", fallback=False)
        )
        self.widget['voice_show_mouseover'].set_value(
            config.getint("main", "autohide_timer", fallback=5)
        )

        # Read Text section

        self.text_floating_x = config.getfloat(
            "text", "floating_x", fallback=0)
        self.text_floating_y = config.getfloat(
            "text", "floating_y", fallback=0)
        self.text_floating_w = config.getfloat(
            "text", "floating_w", fallback=400)
        self.text_floating_h = config.getfloat(
            "text", "floating_h", fallback=400)

        self.widget['text_enable'].set_active(
            config.getboolean("text", "enabled", fallback=False))

        self.widget['text_popup_style'].set_active(
            config.getboolean("text", "popup_style", fallback=False))

        self.widget['text_popup_time'].set_value(
            config.getint("text", "text_time", fallback=30)
        )

        self.current_guild = config.get("text", "guild", fallback="0")

        self.current_channel = config.get("text", "channel", fallback="0")

        font = config.get("text", "font", fallback=None)
        if font:
            self.widget['text_font'].set_font(font)

        self.widget['text_colour'].set_rgba(self.make_colour(config.get(
            "text", "fg_col", fallback="[1.0,1.0,1.0,1.0]")))

        self.widget['text_background_colour'].set_rgba(self.make_colour(config.get(
            "text", "bg_col", fallback="[0.0,0.0,0.0,0.5]")))

        self.widget['text_monitor'].set_active(
            self.get_monitor_index_from_plug(
                config.get("text", "monitor", fallback="Any")
            )
        )

        self.widget['text_show_attachments'].set_active(config.getboolean(
            "text", "show_attach", fallback=True))

        self.widget['text_line_limit'].set_value(
            config.getint("text", "line_limit", fallback=20))

        self.widget['text_hide_mouseover'].set_active(
            config.getboolean("text", "autohide", fallback=False)
        )
        self.widget['text_show_mouseover'].set_value(
            config.getint("text", "autohide_timer", fallback=5)
        )

        # Read Notification section
        self.widget['notification_enable'].set_active(
            config.getboolean("notification", "enabled", fallback=False))

        self.widget['notification_reverse_order'].set_active(
            config.getboolean("notification", "rev", fallback=False))

        self.widget['notification_popup_timer'].set_value(
            config.getint("notification", "text_time", fallback=10))

        self.widget['notification_limit_popup_width'].set_value(
            config.getint("notification", "limit_width", fallback=400))

        font = config.get("notification", "font", fallback=None)
        if font:
            self.widget['notification_font'].set_font(font)

        self.widget['notification_text_colour'].set_rgba(self.make_colour(config.get(
            "notification", "fg_col", fallback="[1.0,1.0,1.0,1.0]")))
        self.widget['notification_background_colour'].set_rgba(self.make_colour(config.get(
            "notification", "bg_col", fallback="[0.0,0.0,0.0,0.5]")))

        self.widget['notification_monitor'].set_active(
            self.get_monitor_index_from_plug(
                config.get("notification", "monitor", fallback="Any")
            )
        )

        self.widget['notification_align_1'].set_active(config.getboolean(
            "notification", "rightalign", fallback=True))

        self.widget['notification_align_2'].set_active(
            config.getint("notification", "topalign", fallback=2))

        self.widget['notification_show_icon'].set_active(
            config.getboolean("notification", "show_icon", fallback=True))

        self.widget['notification_icon_position'].set_active(config.getboolean(
            "notification", "icon_left", fallback=True))

        self.widget['notification_icon_padding'].set_value(config.getint(
            "notification", "icon_padding", fallback=8))

        self.widget['notification_icon_size'].set_value(config.getint(
            "notification", "icon_size", fallback=32))

        self.widget['notification_padding_between'].set_value(config.getint(
            "notification", "padding", fallback=8))

        self.widget['notification_border_radius'].set_value(config.getint(
            "notification", "border_radius", fallback=8))

        self.widget['notification_show_test_content'].set_active(config.getboolean(
            "notification", "show_dummy", fallback=False))

        # Read Core section

        self.widget['core_run_on_startup'].set_active(
            self.autostart_helper.is_auto())

        self.widget['core_run_conf_on_startup'].set_active(
            self.autostart_helper_conf.is_auto())

        if self.disable_autostart:
            self.widget['core_run_on_startup'].set_sensitive(False)
            self.widget['core_run_conf_on_startup'].set_sensitive(False)

        self.widget['core_force_xshape'].set_active(
            config.getboolean("general", "xshape", fallback=False))

        self.show_sys_tray_icon = config.getboolean(
            "general", "showsystray", fallback=True)
        self.set_sys_tray_icon_visible(self.show_sys_tray_icon)
        self.widget['core_show_tray_icon'].set_active(self.show_sys_tray_icon)

        self.hidden_overlay = config.getboolean(
            "general", "hideoverlay", fallback=False)
        self.update_toggle_overlay()

        self.start_minimized = config.getboolean(
            "general", "start_min", fallback=False)

        self.widget['core_settings_min'].set_active(self.start_minimized)

        self.widget['core_settings_min'].set_sensitive(self.show_sys_tray_icon)

        self.widget['core_audio_assist'].set_active(
            config.getboolean("general", "audio_assist", fallback=False))

        self.loading_config = False

    def make_colour(self, col):
        """Create a Gdk Color from a col tuple"""
        col = json.loads(col)
        return Gdk.RGBA(col[0], col[1], col[2], col[3])

    def parse_guild_ids(self, guild_ids_str):
        """Parse the guild_ids from a str and return them in a list"""
        guild_ids = []
        for guild_id in guild_ids_str.split(","):
            guild_id = guild_id.strip()
            if guild_id != "":
                guild_ids.append(guild_id)
        return guild_ids

    def get_monitor_index_from_plug(self, monitor):
        """Get monitor index from plug name"""
        if not monitor or monitor == "Any":
            return 0
        display = Gdk.Display.get_default()
        screen = self.window.get_screen()
        if "get_n_monitors" in dir(display):
            count_monitors = display.get_n_monitors()
            if count_monitors >= 1:
                for i in range(0, count_monitors):
                    connector = screen.get_monitor_plug_name(i)
                    if connector == monitor:
                        return i+1
        return 0

    def get_monitor_obj(self, idx):
        """Helper function to find the monitor object of the monitor"""
        display = Gdk.Display.get_default()
        return display.get_monitor(idx)

    def make_sys_tray_icon(self, menu):
        """
        Attempt to create an AppIndicator icon, failing that attempt to make
        a systemtray icon
        """
        try:
            gi.require_version('AppIndicator3', '0.1')
            # pylint: disable=import-outside-toplevel
            from gi.repository import AppIndicator3
            self.ind = AppIndicator3.Indicator.new(
                "discover_overlay",
                self.tray_icon_name,
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
            self.ind.set_title(_("Discover Overlay Configuration"))
            # Hide for now since we don't know if it should be shown yet
            self.ind.set_status(AppIndicator3.IndicatorStatus.PASSIVE)
            self.ind.set_menu(menu)
        except (ImportError, ValueError) as exception:
            # Create System Tray
            log.info("Falling back to Systray : %s", exception)
            self.tray = Gtk.StatusIcon.new_from_icon_name(
                self.tray_icon_name)
            self.tray.connect('popup-menu', self.show_menu)
            self.tray.set_title(_("Discover Overlay Configuration"))
            # Hide for now since we don't know if it should be shown yet
            self.tray.set_visible(False)

    def show_menu(self, obj, button, time):
        """Show menu when System Tray icon is clicked"""
        self.menu.show_all()
        self.menu.popup(
            None, None, Gtk.StatusIcon.position_menu, obj, button, time)

    def set_sys_tray_icon_visible(self, visible):
        """Sets whether the tray icon is visible"""
        if self.ind is not None:
            # pylint: disable=import-outside-toplevel
            from gi.repository import AppIndicator3
            self.ind.set_status(
                AppIndicator3.IndicatorStatus.ACTIVE if visible else AppIndicator3.IndicatorStatus.PASSIVE)
        elif self.tray is not None:
            self.tray.set_visible(visible)

    def make_menu(self):
        """Create System Menu"""
        menu = Gtk.Menu()
        settings_opt = Gtk.MenuItem.new_with_label(_("Open Configuration"))
        self.toggle_opt = Gtk.MenuItem.new_with_label(_("Hide Overlay"))
        close_overlay_opt = Gtk.MenuItem.new_with_label(_("Quit Overlay"))
        close_opt = Gtk.MenuItem.new_with_label(_("Quit Configuration"))

        menu.append(settings_opt)
        menu.append(self.toggle_opt)
        menu.append(close_overlay_opt)
        menu.append(close_opt)

        settings_opt.connect("activate", self.present_settings)
        self.toggle_opt.connect("activate", self.toggle_overlay)
        close_overlay_opt.connect("activate", self.close_overlay)
        close_opt.connect("activate", self.close_app)
        menu.show_all()
        return menu

    def toggle_overlay(self, _a=None, _b=None):
        """Toggle overlay visibility"""
        self.hidden_overlay = not self.hidden_overlay
        self.config_set("general", "hideoverlay", f"{self.hidden_overlay}")
        self.update_toggle_overlay()

    def update_toggle_overlay(self, _a=None, _b=None):
        """Update gui to reflect state of overlay visibility"""
        self.widget['core_hide_overlay'].handler_block(
            self.hidden_overlay_handler)

        self.widget['core_hide_overlay'].set_active(self.hidden_overlay)

        self.widget['core_hide_overlay'].handler_unblock(
            self.hidden_overlay_handler)
        if self.hidden_overlay:
            self.toggle_opt.set_label(_("Show Overlay"))
        else:
            self.toggle_opt.set_label(_("Hide Overlay"))

    def close_overlay(self, _a=None, _b=None):
        """Send RPC to tell the overlay to close"""
        with open(self.rpc_file, 'w', encoding="utf-8") as f:
            f.write('--rpc --close')

    def overview_close(self, _button):
        """Gui callback to close overlay. Remove and use close_overlay?"""
        log.info("Quit pressed")
        self.close_overlay()

    def voice_place_window(self, button):
        """Toggle the voice placement"""
        if self.voice_placement_window:
            (pos_x, pos_y, width, height) = self.voice_placement_window.get_coords()
            self.voice_floating_x = pos_x
            self.voice_floating_y = pos_y
            self.voice_floating_w = width
            self.voice_floating_h = height

            config = ConfigParser(interpolation=None)
            config.read(self.config_file)
            if "main" not in config.sections():
                config.add_section("main")
            config.set("main", "floating_x", f"{self.voice_floating_x:f}")
            config.set("main", "floating_y", f"{self.voice_floating_y:f}")
            config.set("main", "floating_w", f"{self.voice_floating_w:f}")
            config.set("main", "floating_h", f"{self.voice_floating_h:f}")

            with open(self.config_file, 'w', encoding="utf-8") as file:
                config.write(file)
            if button:
                button.set_label(_("Place Window"))
            self.voice_placement_window.close()
            self.voice_placement_window = None
            if self.steamos:
                self.window.show()
        else:
            if self.steamos:
                self.window.hide()
            if self.is_wayland or self.steamos:
                self.voice_placement_window = DraggableWindowWayland(
                    pos_x=self.voice_floating_x, pos_y=self.voice_floating_y,
                    width=self.voice_floating_w, height=self.voice_floating_h,
                    message=_("Place & resize this window then press Green!"), settings=self,
                    steamos=self.steamos,
                    monitor=self.widget['voice_monitor'].get_active()-1)
            else:
                self.voice_placement_window = DraggableWindow(
                    pos_x=self.voice_floating_x, pos_y=self.voice_floating_y,
                    width=self.voice_floating_w, height=self.voice_floating_h,
                    message=_("Place & resize this window then press Save!"),
                    settings=self, monitor=self.widget['voice_monitor'].get_active()-1)
                if button:
                    button.set_label(_("Save this position"))

    def text_place_window(self, button):
        """Toggle the text placement"""
        if self.text_placement_window:
            (pos_x, pos_y, width, height) = self.text_placement_window.get_coords()
            self.text_floating_x = pos_x
            self.text_floating_y = pos_y
            self.text_floating_w = width
            self.text_floating_h = height

            config = ConfigParser(interpolation=None)
            config.read(self.config_file)
            if "text" not in config.sections():
                config.add_section("text")
            config.set("text", "floating_x", f"{self.text_floating_x:f}")
            config.set("text", "floating_y", f"{self.text_floating_y:f}")
            config.set("text", "floating_w", f"{self.text_floating_w:f}")
            config.set("text", "floating_h", f"{self.text_floating_h:f}")

            with open(self.config_file, 'w', encoding="utf-8") as file:
                config.write(file)
            if button:
                button.set_label(_("Place Window"))
            self.text_placement_window.close()
            self.text_placement_window = None
            if self.steamos:
                self.window.show()
        else:
            if self.steamos:
                self.window.hide()
            if self.is_wayland or self.steamos:
                self.text_placement_window = DraggableWindowWayland(
                    pos_x=self.text_floating_x, pos_y=self.text_floating_y,
                    width=self.text_floating_w, height=self.text_floating_h,
                    message=_("Place & resize this window then press Green!"), settings=self,
                    steamos=self.steamos,
                    monitor=self.widget['text_monitor'].get_active()-1)
            else:
                self.text_placement_window = DraggableWindow(
                    pos_x=self.text_floating_x, pos_y=self.text_floating_y,
                    width=self.text_floating_w, height=self.text_floating_h,
                    message=_("Place & resize this window then press Save!"),
                    settings=self, monitor=self.widget['text_monitor'].get_active()-1)
                if button:
                    button.set_label(_("Save this position"))

    def change_placement(self, placement_window):
        """Finish window placement"""
        if placement_window == self.text_placement_window:
            self.text_place_window(None)
        elif placement_window == self.voice_placement_window:
            self.voice_place_window(None)

    def text_server_refresh(self, _button):
        """Send RPC to overlay to request a list of text channels"""
        with open(self.rpc_file, 'w', encoding="utf-8") as f:
            f.write('--rpc --refresh-guilds')

    def config_set(self, context, key, value):
        """Write one key to config and save to disk"""
        if self.loading_config:
            return
        config = ConfigParser(interpolation=None)
        config.read(self.config_file)
        if not context in config.sections():
            config.add_section(context)
        config.set(context, key, value)
        with open(self.config_file, 'w', encoding="utf-8") as file:
            config.write(file)

    def config_remove_section(self, context):
        """Remove a section from config and save to disk"""
        if self.loading_config:
            return
        config = ConfigParser(interpolation=None)
        config.read(self.config_file)
        if context in config.sections():
            config.remove_section(context)
        else:
            log.error("Unable to remove section %s", context)
        with open(self.config_file, 'w', encoding="utf-8") as file:
            config.write(file)

    def voice_anchor_float_changed(self, button):
        self.config_set("main", "floating", f"{(button.get_active() == 0)}")
        self.update_floating_anchor()

    def update_floating_anchor(self):
        floating = self.widget['voice_anchor_float'].get_active() == 0

        if floating:
            self.widget['voice_align_1'].hide()
            self.widget['voice_align_2'].hide()
            self.widget['voice_place_window_button'].show()
        else:
            self.widget['voice_align_1'].show()
            self.widget['voice_align_2'].show()
            self.widget['voice_place_window_button'].hide()

    def voice_monitor_changed(self, button):
        screen = self.window.get_screen()
        idx = button.get_active()
        plug = "Any"
        if idx > 0:
            monitor = screen.get_monitor_plug_name(button.get_active()-1)
            if monitor:
                plug = monitor
        self.config_set("main", "monitor", plug)

    def voice_align_1_changed(self, button):
        self.config_set("main", "rightalign", f"{button.get_active()}")

    def voice_align_2_changed(self, button):
        self.config_set("main", "topalign", f"{button.get_active()}")

    def voice_font_changed(self, button):
        self.config_set("main", "font", button.get_font())

    def voice_title_font_changed(self, button):
        self.config_set("main", "title_font", button.get_font())

    def voice_icon_spacing_changed(self, button):
        self.config_set("main", "icon_spacing", f"{int(button.get_value())}")

    def voice_text_padding_changed(self, button):
        self.config_set("main", "text_padding", f"{int(button.get_value())}")

    def voice_text_vertical_offset_changed(self, button):
        self.config_set("main", "text_baseline_adj",
                        f"{int(button.get_value())}")

    def voice_vertical_padding_changed(self, button):
        self.config_set("main", "vert_edge_padding",
                        f"{int(button.get_value())}")

    def voice_horizontal_padding_changed(self, button):
        self.config_set("main", "horz_edge_padding",
                        f"{int(button.get_value())}")

    def voice_display_horizontally_changed(self, button):
        self.config_set("main", "horizontal", f"{button.get_active()}")
        self.set_alignment_labels(button.get_active())

    def voice_highlight_self_changed(self, button):
        self.config_set("main", "highlight_self", f"{button.get_active()}")

    def voice_display_speakers_only(self, button):
        self.config_set("main", "only_speaking", f"{button.get_active()}")

    def voice_display_speakers_grace_period(self, button):
        self.config_set("main", "only_speaking_grace",
                        f"{int(button.get_value())}")

    def voice_toggle_test_content(self, button):
        self.config_set("main", "show_dummy", f"{button.get_active()}")

    def voice_talking_foreground_changed(self, button):
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.config_set("main", "fg_hi_col", json.dumps(colour))

    def voice_talking_background_changed(self, button):
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.config_set("main", "hi_col", json.dumps(colour))

    def voice_talking_border_changed(self, button):
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.config_set("main", "tk_col", json.dumps(colour))

    def voice_idle_foreground_changed(self, button):
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.config_set("main", "fg_col", json.dumps(colour))

    def voice_idle_background_changed(self, button):
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.config_set("main", "bg_col", json.dumps(colour))

    def voice_idle_border_changed(self, button):
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.config_set("main", "bo_col", json.dumps(colour))

    def voice_mute_foreground_changed(self, button):
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.config_set("main", "mt_col", json.dumps(colour))

    def voice_mute_background_changed(self, button):
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.config_set("main", "mt_bg_col", json.dumps(colour))

    def voice_avatar_background_changed(self, button):
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.config_set("main", "avatar_bg_col", json.dumps(colour))

    def voice_avatar_opacity_changed(self, button):
        self.config_set("main", "icon_transparency",
                        f"{button.get_value():.2f}")

    def voice_avatar_size_changed(self, button):
        self.config_set("main", "avatar_size", f"{int(button.get_value())}")

    def voice_nick_length_changed(self, button):
        self.config_set("main", "nick_length", f"{int(button.get_value())}")

    def voice_display_icon_only_changed(self, button):
        self.config_set("main", "icon_only", f"{(not button.get_active())}")
        self.voice_show_name_hide_others(button.get_active())

    def voice_square_avatar_changed(self, button):
        self.config_set("main", "square_avatar", f"{button.get_active()}")

    def voice_fancy_avatar_shapes_changed(self, button):
        self.config_set("main", "fancy_border", f"{button.get_active()}")

    def voice_order_avatars_by_changed(self, button):
        self.config_set("main", "order", f"{button.get_active()}")

    def voice_border_width_changed(self, button):
        self.config_set("main", "border_width", f"{int(button.get_value())}")

    def voice_overflow_style_changed(self, button):
        self.config_set("main", "overflow", f"{int(button.get_active())}")

    def voice_show_title_changed(self, button):
        self.config_set("main", "show_title", f"{button.get_active()}")

    def voice_show_connection_status_changed(self, button):
        self.config_set("main", "show_connection", f"{button.get_active()}")

    def voice_show_disconnected_changed(self, button):
        self.config_set("main", "show_disconnected", f"{button.get_active()}")

    def voice_dummy_count_changed(self, button):
        self.config_set("main", "dummy_count", f"{int(button.get_value())}")

    def voice_show_avatar_changed(self, button):
        self.config_set("main", "show_avatar", f"{button.get_active()}")
        self.voice_show_avatar_hide_others(button.get_active())

    def voice_show_name_hide_others(self, val):
        if val:
            # Show name options
            self.widget['voice_font'].set_sensitive(True)
            self.widget['voice_text_padding'].set_sensitive(True)
            self.widget['voice_text_vertical_offset'].set_sensitive(True)
            self.widget['voice_nick_length'].set_sensitive(True)
        else:
            # Hide name options
            self.widget['voice_font'].set_sensitive(False)
            self.widget['voice_text_padding'].set_sensitive(False)
            self.widget['voice_text_vertical_offset'].set_sensitive(False)
            self.widget['voice_nick_length'].set_sensitive(False)

    def voice_show_avatar_hide_others(self, val):
        if val:
            # Show avatar options
            self.widget['voice_square_avatar'].set_sensitive(True)
            self.widget['voice_fancy_avatar_shapes'].set_sensitive(True)
            self.widget['voice_avatar_size'].set_sensitive(True)
            self.widget['voice_avatar_opacity'].set_sensitive(True)
        else:
            # Hide avatar options
            self.widget['voice_square_avatar'].set_sensitive(False)
            self.widget['voice_fancy_avatar_shapes'].set_sensitive(False)
            self.widget['voice_avatar_size'].set_sensitive(False)
            self.widget['voice_avatar_opacity'].set_sensitive(False)

    def text_enable_changed(self, button):
        self.config_set("text", "enabled", f"{button.get_active()}")

    def text_popup_style_changed(self, button):
        self.config_set("text", "popup_style", f"{button.get_active()}")

    def text_popup_time_changed(self, button):
        self.config_set("text", "text_time", f"{int(button.get_value())}")

    def text_server_changed(self, button):
        if button.get_active() < 0:
            self.config_set("text", "guild", "0")
            return
        guild = self.guild_ids[button.get_active()]
        if guild and self.current_guild != guild:
            self.current_guild = guild
            self.config_set("text", "guild", guild)
            self.request_channels_from_guild(guild)

    def text_channel_changed(self, button):
        if button.get_active() < 0:
            self.config_set("text", "channel", "0")
            return
        channel = self.channel_ids[button.get_active()]
        if channel:
            self.current_channel = channel
            self.config_set("text", "channel", channel)

    def text_font_changed(self, button):
        self.config_set("text", "font", button.get_font())

    def text_colour_changed(self, button):
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.config_set("text", "fg_col", json.dumps(colour))

    def text_background_colour_changed(self, button):
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.config_set("text", "bg_col", json.dumps(colour))

    def text_monitor_changed(self, button):
        screen = self.window.get_screen()
        plug = "Any"
        monitor = None
        if button.get_active()>0:
            monitor = screen.get_monitor_plug_name(button.get_active()-1)
        if monitor:
            plug = monitor
        self.config_set("text", "monitor", plug)

    def text_show_attachments_changed(self, button):
        self.config_set("text", "show_attach", f"{button.get_active()}")

    def text_line_limit_changed(self, button):
        self.config_set("text", "line_limit", f"{int(button.get_value())}")

    def notification_enable_changed(self, button):
        self.config_set("notification", "enabled", f"{button.get_active()}")

    def notification_reverse_order_changed(self, button):
        self.config_set("notification", "rev", f"{button.get_active()}")

    def notification_popup_timer_changed(self, button):
        self.config_set("notification", "text_time",
                        f"{int(button.get_value())}")

    def notification_limit_popup_width_changed(self, button):
        self.config_set("notification", "limit_width",
                        f"{int(button.get_value())}")

    def notification_font_changed(self, button):
        self.config_set("notification", "font", button.get_font())

    def notification_text_colour_changed(self, button):
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.config_set("notification", "fg_col", json.dumps(colour))

    def notification_background_colour_changed(self, button):
        colour = button.get_rgba()
        colour = [colour.red, colour.green, colour.blue, colour.alpha]
        self.config_set("notification", "bg_col", json.dumps(colour))

    def notification_monitor_changed(self, button):
        screen = self.window.get_screen()
        plug = "Any"
        monitor = None
        if button.get_active()>0:
            monitor = screen.get_monitor_plug_name(button.get_active()-1)
        if monitor:
            plug = monitor
        self.config_set("notification", "monitor", plug)

    def notification_align_1_changed(self, button):
        self.config_set("notification", "rightalign", f"{button.get_active()}")

    def notification_align_2_changed(self, button):
        self.config_set("notification", "topalign", f"{button.get_active()}")

    def notification_show_icon(self, button):
        self.config_set("notification", "show_icon", f"{button.get_active()}")

    def notification_icon_position_changed(self, button):
        self.config_set("notification", "icon_left", f"{int(button.get_active() != 1)}")

    def notification_icon_padding_changed(self, button):
        self.config_set("notification", "icon_padding",
                        f"{int(button.get_value())}")

    def notification_icon_size_changed(self, button):
        self.config_set("notification", "icon_size",
                        f"{int(button.get_value())}")

    def notification_padding_between_changed(self, button):
        self.config_set("notification", "padding",
                        f"{int(button.get_value())}")

    def notification_border_radius_changed(self, button):
        self.config_set("notification", "border_radius",
                        f"{int(button.get_value())}")

    def notification_show_test_content_changed(self, button):
        self.config_set("notification", "show_dummy", f"{button.get_active()}")

    def core_run_on_startup_changed(self, button):
        self.autostart_helper.set_autostart(button.get_active())

    def core_run_conf_on_startup_changed(self, button):
        self.autostart_helper_conf.set_autostart(button.get_active())

    def core_force_xshape_changed(self, button):
        self.config_set("general", "xshape", f"{button.get_active()}")

    def core_show_tray_icon_changed(self, button):
        self.set_sys_tray_icon_visible(button.get_active())
        self.config_set("general", "showsystray", f"{button.get_active()}")
        self.widget['core_settings_min'].set_sensitive(button.get_active())

    def core_hide_overlay_changed(self, _button):
        self.toggle_overlay()

    def core_settings_min_changed(self, button):
        self.config_set("general", "start_min", f"{button.get_active()}")

    def core_reset_all(self, _button):
        self.config_remove_section("general")
        self.read_config()

    def voice_reset_all(self, _button):
        self.config_remove_section("main")
        self.read_config()

    def text_reset_all(self, _button):
        self.config_remove_section("text")
        self.read_config()

    def notification_reset_all(self, _button):
        self.config_remove_section("notification")
        self.read_config()

    def voice_hide_mouseover_changed(self, button):
        self.config_set("main", "autohide", f"{button.get_active()}")

    def text_hide_mouseover_changed(self, button):
        self.config_set("text", "autohide", f"{button.get_active()}")

    def voice_mouseover_timeout_changed(self, button):
        self.config_set("main", "autohide_timer", f"{int(button.get_value())}")

    def text_mouseover_timeout_changed(self, button):
        self.config_set("text", "autohide_timer", f"{int(button.get_value())}")

    def inactive_fade_changed(self, button):
        self.config_set("main", "fade_out_inactive", f"{button.get_active()}")

    def inactive_fade_opacity_changed(self, button):
        self.config_set("main", "fade_out_limit",
                        f"{button.get_value():.2f}")

    def inactive_time_changed(self, button):
        self.config_set("main", "inactive_time", f"{int(button.get_value())}")

    def inactive_fade_time_changed(self, button):
        self.config_set("main", "inactive_fade_time",
                        f"{int(button.get_value())}")

    def core_audio_assist_changed(self, button):
        self.config_set("general", "audio_assist", f"{button.get_active()}")
