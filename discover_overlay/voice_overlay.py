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
"""Overlay window for voice"""
import random
import gettext
import logging
import locale
import json
import importlib_resources
from time import perf_counter
from .overlay import OverlayWindow, HorzAlign, VertAlign
from .image_getter import get_surface
from .font_helper import font_string_to_css_font_string
from .userbox import UserBox, UserBoxConnection, UserBoxTitle
import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, GLib

log = logging.getLogger(__name__)
with importlib_resources.as_file(
    importlib_resources.files("discover_overlay") / "locales"
) as path:
    t = gettext.translation(
        "default",
        path,
        fallback=True,
    )
    _ = t.gettext


class VoiceOverlayWindow(OverlayWindow):
    """Overlay window for voice"""

    def __init__(self, discover, piggyback=None):
        OverlayWindow.__init__(self, discover, piggyback)
        self.box = Gtk.Box()
        self.connection = UserBoxConnection(self)
        self.title = UserBoxTitle(self)
        self.box.append(self.title)
        self.box.append(self.connection)
        self.box.add_css_class("container")
        self.set_child(self.box)
        self.dummy_data = []
        mostly_false = [False, False, False, False, False, False, False, True]
        for i in range(0, 100):
            speaking = mostly_false[random.randint(0, 7)]
            scream = ""
            if random.randint(0, 20) == 2:
                scream = random.randint(8, 15) * "a"
            name = f"Player {i} {scream}"
            self.dummy_data.append(
                {
                    "id": i,
                    "username": name,
                    "avatar": None,
                    "deaf": mostly_false[random.randint(0, 7)],
                    "mute": mostly_false[random.randint(0, 7)],
                    "speaking": speaking,
                    "lastspoken": (
                        random.randint(2000, 2100)
                        if speaking
                        else random.randint(10, 30)
                    ),
                    "friendlyname": name,
                }
            )
        self.text_x_align = "middle"
        self.text_y_align = "middle"
        self.show_avatar = True
        self.avatar_size = 48
        self.nick_length = 32
        self.text_pad = 6
        self.text_font = None
        self.title_font = None
        self.text_size = 13
        self.text_baseline_adj = 0
        self.icon_spacing = 8
        self.only_speaking = None
        self.highlight_self = None
        self.order = None
        self.def_avatar = None
        self.mute_avatar = None
        self.deaf_avatar = None
        self.overflow = None
        self.use_dummy = False
        self.dummy_count = 10
        self.show_connection = True
        self.show_disconnected = True
        self.border_width = 2
        self.icon_transparency = 0.0
        self.fancy_border = False
        self.only_speaking_grace_period = 0
        self.text_side = 3

        self.fade_out_inactive = True
        self.fade_out_limit = 0.1
        self.inactive_time = 10  # Seconds
        self.inactive_fade_time = 20  # Seconds
        self.fade_start = 0

        self.inactive_timeout = None
        self.fadeout_timeout = None

        self.icon_only = True
        self.talk_col = [0.0, 0.6, 0.0, 0.1]
        self.text_col = [1.0, 1.0, 1.0, 1.0]
        self.text_hili_col = [1.0, 1.0, 1.0, 1.0]
        self.norm_col = [0.0, 0.0, 0.0, 0.5]
        self.wind_col = [0.0, 0.0, 0.0, 0.0]
        self.mute_col = [0.7, 0.0, 0.0, 1.0]
        self.mute_bg_col = [0.0, 0.0, 0.0, 0.5]
        self.hili_col = [0.0, 0.0, 0.0, 0.9]
        self.border_col = [0.0, 0.0, 0.0, 0.0]
        self.avatar_bg_col = [0.0, 0.0, 1.0, 1.0]
        self.userlist = []
        self.horizontal = False
        self.guild_ids = tuple()
        self.force_location()
        get_surface(
            self.recv_avatar, "discover-overlay-default", "def", self.get_display()
        )
        get_surface(
            self.recv_avatar, "microphone-sensitivity-muted", "mute", self.get_display()
        )
        get_surface(self.recv_avatar, "audio-volume-muted", "deaf", self.get_display())
        self.set_title("Discover Voice")
        self.title.set_label(None)
        self.connection.set_connection(None)
        self.title.update_label(None)
        self.connection.update_image(None)
        self.populate()

    def all_users(self, func):
        child = self.box.get_first_child()
        while child:
            user = self.get_user(child.userid)
            func(user, child)
            child = child.get_next_sibling()

    def get_user(self, userid):
        for user in self.dummy_data if self.use_dummy else self.userlist:
            if user["id"] == userid:
                return user
        return None

    def get_user_widget(self, userid):
        child = self.box.get_first_child()
        while child:
            if userid == child.userid:
                return child
            child = child.get_next_sibling()
        return None

    def set_align_x(self, align):
        OverlayWindow.set_align_x(self, align)
        if align == HorzAlign.LEFT:
            self.box.set_halign(Gtk.Align.START)
        elif align == HorzAlign.MIDDLE:
            self.box.set_halign(Gtk.Align.CENTER)
        else:
            self.box.set_halign(Gtk.Align.END)

    def set_align_y(self, align):
        OverlayWindow.set_align_y(self, align)
        if align == VertAlign.TOP:
            self.box.set_valign(Gtk.Align.START)
        elif align == VertAlign.MIDDLE:
            self.box.set_valign(Gtk.Align.CENTER)
        else:
            self.box.set_valign(Gtk.Align.END)

    def populate(self):
        child = self.box.get_last_child()
        self.queue_resize()
        self.box.queue_resize()
        while child:
            child.queue_resize()
            n_child = child.get_prev_sibling()
            if isinstance(child, UserBoxTitle) or isinstance(child, UserBoxConnection):
                child = n_child
                continue
            if child.userid not in self.userlist:
                self.box.remove(child)
            child.hide()
            child = n_child
        connection = self.discover.connection
        self_user_id = None
        if connection and connection.user and "id" in connection.user:
            self_user_id = connection.user["id"]

        # Gather which users to draw
        if (
            self.use_dummy
        ):  # Sorting every frame is an awful idea. Maybe put this off elsewhere?
            users_to_draw = self.sort_list(self.dummy_data.copy()[0 : self.dummy_count])
            userlist = self.dummy_data.copy()
        else:
            users_to_draw = self.userlist.copy()
            userlist = self.userlist.copy()

        now = perf_counter()
        for user in userlist:
            # Update friendly name with nick if possible
            if "nick" in user:
                user["friendlyname"] = user["nick"]
            else:
                user["friendlyname"] = user["username"]

            # Remove users that haven't spoken within the grace period
            if self.only_speaking:
                speaking = "speaking" in user and user["speaking"]

                # Extend timer if mid-speaking
                if self.highlight_self and self_user_id == user["id"]:
                    continue
                if speaking:
                    user["lastspoken"] = perf_counter()
                else:
                    grace = self.only_speaking_grace_period

                    if (
                        grace > 0
                        and (last_spoke := user["lastspoken"])
                        and (now - last_spoke) < grace
                    ):
                        # The user spoke within the grace period, so don't hide
                        # them just yet
                        pass

                    elif user in users_to_draw:
                        users_to_draw.remove(user)

        self.title.update_image(None)
        self.title.update_label(None)
        self.connection.update_image(None)
        self.connection.update_label(None)
        for user in users_to_draw:
            userbox = self.get_user_widget(user["id"])
            if userbox:
                userbox.show()
                continue

            userbox = UserBox(self, user["id"])
            userbox.update_image(user)
            userbox.update_label(user)

            self.box.append(userbox)
            userbox.show()
        self.box.show()

    def set_talking(self, userid, talking):
        log.info("Talking %s %s", userid, talking)
        widget = self.get_user_widget(userid)
        user = self.get_user(userid)
        if user:
            user["talking"] = talking
        if widget:
            widget.set_talking(talking)
        else:
            log.warning("Set talking on missing user")

    def set_mute(self, userid, muted):
        log.info("Mute %s %s", userid, muted)

    def set_deaf(self, userid, deafened):
        log.info("Deaf %s %s", userid, deafened)

    def reset_action_timer(self):
        """Reset time since last voice activity"""
        self.set_css("fade-opacity", "")

        # Remove both fading-out effect and timer set last time this happened
        if self.inactive_timeout:
            GLib.source_remove(self.inactive_timeout)
            self.inactive_timeout = None
        if self.fadeout_timeout:
            GLib.source_remove(self.fadeout_timeout)
            self.fadeout_timeout = None

        # If we're using this feature, schedule a new inactivity timer
        if self.fade_out_inactive:
            self.inactive_timeout = GLib.timeout_add_seconds(
                self.inactive_time, self.overlay_inactive
            )

    def overlay_inactive(self):
        """Timed callback when inactivity limit is hit"""
        self.fade_start = perf_counter()
        # Fade out in 200 steps over X seconds.
        self.fadeout_timeout = GLib.timeout_add(
            self.inactive_fade_time / 200 * 1000, self.overlay_fadeout
        )
        self.inactive_timeout = None
        return False

    def overlay_fadeout(self):
        """Repeated callback after inactivity started"""
        self.populate()
        # There's no guarantee over the granularity of the callback here,
        # so use our time-since to work out how faded out we should be
        # Might look choppy on systems under high cpu usage but that's just how it's going to be
        now = perf_counter()
        time_percent = (now - self.fade_start) / self.inactive_fade_time
        if time_percent >= 1.0:

            fade_opacity = self.fade_out_limit
            self.fadeout_timeout = None
            self.set_css("fade-out", ".container { opacity: %2.2f;}" % (fade_opacity))
            return False

        fade_opacity = self.fade_out_limit + (
            (1.0 - self.fade_out_limit) * (1.0 - time_percent)
        )
        self.set_css("fade-out", ".container { opacity: %2.2f;}" % (fade_opacity))
        return True

    def set_blank(self):
        """Set data to blank and redraw"""
        self.userlist = []
        self.title.set_label(None)
        self.connection.set_connection(None)
        self.title.update_label(None)
        self.connection.update_image(None)
        self.populate()

    def set_fade_out_inactive(self, enabled, fade_time, fade_duration, fade_to):
        """Config option: fade out options"""
        if (
            self.fade_out_inactive != enabled
            or self.inactive_time != fade_time
            or self.inactive_fade_time != fade_duration
            or self.fade_out_limit != fade_to
        ):
            self.fade_out_inactive = enabled
            self.inactive_time = fade_time
            self.inactive_fade_time = fade_duration
            self.fade_out_limit = fade_to
            self.reset_action_timer()

    def set_title_font(self, font):
        """
        Set the font used by the overlay
        """
        self.set_css(
            "font", ".title { font: %s; }" % (font_string_to_css_font_string(font))
        )

    def set_overflow_style(self, overflow):
        """Config option: Change handling of too many users to render"""
        if self.overflow != overflow:
            self.overflow = overflow
            self.populate()

    def set_borders(self):
        width = self.border_width
        col = self.col_to_css(self.border_col)
        talk_col = self.col_to_css(self.talk_col)
        self.set_css(
            "talking-border",
            f"""
            .talking .userlabel, .talking .usericon
            {{ 
              filter: drop-shadow({width}px {width}px 0 {talk_col})
                      drop-shadow(-{width}px -{width}px 0 {talk_col})
                      drop-shadow(-{width}px {width}px 0 {talk_col})
                      drop-shadow({width}px -{width}px 0 {talk_col});
            }}
            .userlabel, .usericon
            {{
              filter: drop-shadow({width}px {width}px 0 {col})
                      drop-shadow(-{width}px -{width}px 0 {col})
                      drop-shadow(-{width}px {width}px 0 {col})
                      drop-shadow({width}px -{width}px 0 {col});
            }}
            .usericon
            {{
                margin: {width}px;
            }}
            """,
        )

    def set_channel_title(self, channel_title):
        """Set title above voice list"""
        self.title.set_label(channel_title)

    def set_channel_icon(self, url):
        """Change the icon for channel"""
        if not url:
            self.title.blank()
        else:
            get_surface(self.recv_avatar, url, "channel", self.get_display())

    def set_user_list(self, userlist, alt):
        """Set the users in list to draw"""
        self.userlist = userlist
        for user in userlist:
            if "nick" in user:
                user["friendlyname"] = user["nick"]
            else:
                user["friendlyname"] = user["username"]
        self.sort_list(self.userlist)
        if alt:
            self.reset_action_timer()
            self.populate()

    def set_connection_status(self, connection):
        """Set if discord has a clean connection to server"""
        self.connection.set_connection(connection["state"])

    def sort_list(self, in_list):
        """Take a userlist and sort it according to config option"""
        if self.order == 1:  # ID Sort
            in_list.sort(key=lambda x: x["id"])
        elif self.order == 2:  # Spoken sort
            in_list.sort(key=lambda x: x["lastspoken"], reverse=True)
            in_list.sort(key=lambda x: x["speaking"], reverse=True)
        else:  # Name sort
            in_list.sort(key=lambda x: locale.strxfrm(x["friendlyname"]))
        return in_list

    def has_content(self):
        """Returns true if overlay has meaningful content to render"""
        if not self.enabled:
            return False
        if self.hidden:
            return False
        if self.use_dummy:
            return True
        return self.userlist

    def recv_avatar(self, identifier, pix):
        """Called when image_getter has downloaded an image"""
        if identifier == "def":
            self.def_avatar = pix
            self.all_users(lambda user, widget: widget.update_image(user))
            return
        elif identifier == "mute":
            self.mute_avatar = pix
            self.all_users(lambda user, widget: widget.update_image(user))
        elif identifier == "deaf":
            self.deaf_avatar = pix
            self.all_users(lambda user, widget: widget.update_image(user))
        elif identifier == "channel":
            self.title.set_image(pix)

    def unused_fn_needed_translations(self):
        """
        These are here to force them to be picked up for translations

        They're fed right through from Discord client as string literals
        """
        _("DISCONNECTED")
        _("NO_ROUTE")
        _("VOICE_DISCONNECTED")
        _("ICE_CHECKING")
        _("AWAITING_ENDPOINT")
        _("AUTHENTICATING")
        _("CONNECTING")
        _("CONNECTED")
        _("VOICE_CONNECTING")
        _("VOICE_CONNECTED")

    def set_config(self, config):
        OverlayWindow.set_config(self, config)

        horizontal = config.getboolean("horizontal", fallback=False)

        self.mute_col = json.loads(config.get("mt_col", fallback="[0.6,0.0,0.0,1.0]"))

        # Text colour
        self.set_css(
            "foreground-color",
            "* { color: "
            + self.col_to_css(config.get("fg_col", fallback="[1.0,1.0,1.0,1.0]"))
            + ";}",
        )
        # Text colour while talking
        self.set_css(
            "talking-text",
            ".talking .userlabel { color: "
            + self.col_to_css(config.get("fg_hi_col", fallback="[1.0,1.0,1.0,1.0]"))
            + ";}",
        )
        self.talk_col = json.loads(config.get("tk_col", fallback="[0.0,0.7,0.0,0.2]"))
        # Background colour
        self.set_css(
            "background-color",
            ".usericon, .userlabel { background-color: "
            + self.col_to_css(config.get("bg_col", fallback="[0.0,0.0,0.0,0.2]"))
            + ";}",
        )
        # Mute/deaf background colour
        self.set_css(
            "mute-background",
            ".mute .userlabel, .mute .usericon { background-color: "
            + self.col_to_css(config.get("mt_bg_col", fallback=[0.0, 0.0, 0.0, 0.5]))
            + ";}",
        )
        self.set_css(
            "talking-background",
            ".talking .userlabel, .talking .usericon { background-color: "
            + self.col_to_css(config.get("hi_col", fallback="[0.0,0.0,0.0,0.5]"))
            + ";}",
        )

        self.border_col = json.loads(config.get("bo_col", fallback="[0.0,0.0,0.0,0.0]"))
        self.set_css(
            "avatar-bg-color",
            ".usericon { background-color: "
            + self.col_to_css(config.get("avatar_bg_col", fallback="[0.0,0.0,0.0,0.0]"))
            + ";}",
        )

        self.avatar_size = config.getint("avatar_size", fallback=48)
        self.set_css(
            "avatar_size",
            ".usericon { -gtk-icon-size:%spx; }" % (self.avatar_size),
        )

        self.nick_length = config.getint("nick_length", fallback=32)

        self.box.set_spacing(config.getint("icon_spacing", fallback=8))

        self.set_css(
            "text_padding",
            ".userlabel { padding: %spx; }"
            % (config.getint("text_padding", fallback=6)),
        )

        self.only_speaking = config.getboolean("only_speaking", fallback=False)

        self.only_speaking_grace_period = config.getint(
            "only_speaking_grace", fallback=0
        )
        self.highlight_self = config.getboolean("highlight_self", fallback=False)
        self.icon_only = config.getboolean("icon_only", fallback=False)

        vert_edge_padding = config.getint("vert_edge_padding", fallback=0)
        self.set_css(
            "vertical-edge",
            ".container { margin-top: %spx; margin-bottom: %spx;}"
            % (vert_edge_padding, vert_edge_padding),
        )
        horz_edge_padding = config.getint("horz_edge_padding", fallback=0)
        self.set_css(
            "horizontal-edge",
            ".container { margin-left: %spx; margin-right: %spx;}"
            % (horz_edge_padding, horz_edge_padding),
        )
        self.order = config.getint("order", fallback=0)

        self.set_hide_on_mouseover(config.getboolean("autohide", fallback=False))
        self.set_mouseover_timer(config.getint("autohide_timer", fallback=1))

        self.box.set_orientation(
            Gtk.Orientation.HORIZONTAL if horizontal else Gtk.Orientation.VERTICAL
        )

        self.connection.set_show_always(
            config.getboolean("show_connection", fallback=False)
        )

        self.title.set_show(config.getboolean("show_title", fallback=False))

        self.text_side = config.getint("text_side", fallback=3)

        self.connection.set_show_only_disconnected(
            config.getboolean("show_disconnected", fallback=False)
        )
        self.border_width = config.getint("border_width", fallback=2)

        self.show_avatar = config.getboolean("show_avatar", fallback=True)

        self.set_css(
            "icon_transparency",
            ".usericon { opacity: %2.2f; }"
            % (config.getfloat("icon_transparency", fallback=1.0)),
        )

        self.use_dummy = config.getboolean("show_dummy", fallback=False)

        self.dummy_count = config.getint("dummy_count", fallback=10)

        self.set_enabled(True)

        font = config.get("font", fallback=None)
        title_font = config.get("title_font", fallback=None)
        if font:
            self.set_font(font)
        if title_font:
            self.set_title_font(title_font)

        self.text_x_align = config.get("text_x_align", fallback="middle")
        self.text_y_align = config.get("text_y_align", fallback="middle")

        self.set_borders()

        self.set_fade_out_inactive(
            config.getboolean("fade_out_inactive", fallback=False),
            config.getint("inactive_time", fallback=10),
            config.getint("inactive_fade_time", fallback=30),
            config.getfloat("fade_out_limit", fallback=0.3),
        )

        self.populate()
