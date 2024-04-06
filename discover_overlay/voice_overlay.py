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
import math
import cairo
import sys
import locale
import pkg_resources
from time import perf_counter
from .overlay import OverlayWindow
from .image_getter import get_surface, draw_img_to_rect, draw_img_to_mask
# pylint: disable=wrong-import-order
import gi
gi.require_version("Gtk", "3.0")
gi.require_version('PangoCairo', '1.0')
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Pango, PangoCairo, GLib  # nopep8

log = logging.getLogger(__name__)

t = gettext.translation(
    'default', pkg_resources.resource_filename('discover_overlay', 'locales'), fallback=True)
_ = t.gettext


class VoiceOverlayWindow(OverlayWindow):
    """Overlay window for voice"""

    def __init__(self, discover, piggyback=None):
        OverlayWindow.__init__(self, discover, piggyback)

        self.avatars = {}
        self.avatar_masks = {}

        # Cache for when somebody last spoke, used for "only_speaking" grace period
        self.speaker_cache = {}

        self.dummy_data = []
        mostly_false = [False, False, False, False, False, False, False, True]
        for i in range(0, 100):
            speaking = mostly_false[random.randint(0, 7)]
            scream = ''
            if random.randint(0, 20) == 2:
                scream = random.randint(8, 15)*'a'
            name = "Player %d %s" % (i, scream)
            self.dummy_data.append({
                "id": i,
                "username": name,
                "avatar": None,
                "mute": False,
                "deaf": mostly_false[random.randint(0, 7)],
                "mute": mostly_false[random.randint(0, 7)],
                "speaking": speaking,
                'lastspoken': random.randint(2000, 2100) if speaking else random.randint(10, 30),
                'friendlyname': name,
            })
        self.show_avatar = True
        self.avatar_size = 48
        self.nick_length = 32
        self.text_pad = 6
        self.text_font = None
        self.title_font = None
        self.text_size = 13
        self.text_baseline_adj = 0
        self.icon_spacing = 8
        self.vert_edge_padding = 0
        self.horz_edge_padding = 0
        self.only_speaking = None
        self.highlight_self = None
        self.order = None
        self.def_avatar = None
        self.channel_icon = None
        self.channel_mask = None
        self.channel_icon_url = None
        self.overflow = None
        self.use_dummy = False
        self.dummy_count = 10
        self.show_title = True
        self.show_connection = True
        self.show_disconnected = True
        self.channel_title = ""
        self.border_width = 2
        self.icon_transparency = 0.0
        self.fancy_border = False

        self.fade_out_inactive = True
        self.fade_out_limit = 0.1
        self.inactive_time = 10  # Seconds
        self.inactive_fade_time = 20  # Seconds
        self.fade_opacity = 1.0
        self.fade_start = 0

        self.inactive_timeout = None
        self.fadeout_timeout = None

        self.round_avatar = True
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
        self.connection_status = "DISCONNECTED"
        self.horizontal = False
        self.guild_ids = tuple()
        self.force_location()
        get_surface(self.recv_avatar,
                    "discover-overlay-default",
                    'def', self.avatar_size)
        self.set_title("Discover Voice")
        self.redraw()

    def reset_action_timer(self):
        # Reset time since last voice activity
        self.fade_opacity = 1.0

        # Remove both fading-out effect and timer set last time this happened
        if self.inactive_timeout:
            GLib.source_remove(self.inactive_timeout)
            self.inactive_timeout = None
        if self.fadeout_timeout:
            GLib.source_remove(self.fadeout_timeout)
            self.fadeout_timeout = None

        # If we're using this feature, schedule a new iactivity timer
        if self.fade_out_inactive:
            self.inactive_timeout = GLib.timeout_add_seconds(
                self.inactive_time, self.overlay_inactive)

    def overlay_inactive(self):
        # Inactivity has hit the first threshold, start fading out
        self.fade_start = perf_counter()
        # Fade out in 200 steps over X seconds.
        self.fadeout_timeout = GLib.timeout_add(
            self.inactive_fade_time/200 * 1000, self.overlay_fadeout)
        self.inactive_timeout = None
        return False

    def overlay_fadeout(self):
        self.set_needs_redraw()
        # There's no guarantee over the granularity of the callback here, so use our time-since to work out how faded out we should be
        # Might look choppy on systems under high cpu usage but that's just how it's going to be
        now = perf_counter()
        time_percent = (now - self.fade_start) / self.inactive_fade_time
        if time_percent >= 1.0:
            self.fade_opacity = self.fade_out_limit
            self.fadeout_timeout = None
            return False

        self.fade_opacity = self.fade_out_limit + \
            ((1.0 - self.fade_out_limit) * (1.0 - time_percent))
        return True

    def col(self, col, alpha=1.0):
        """
        Convenience function to set the cairo context next colour. Altered to account for fade-out function
        """
        if alpha == None:
            self.context.set_source_rgba(col[0], col[1], col[2], col[3])
        else:
            self.context.set_source_rgba(
                col[0], col[1], col[2], col[3] * alpha * self.fade_opacity)

    def set_icon_transparency(self, trans):
        if self.icon_transparency != trans:
            self.icon_transparency = trans
            self.set_needs_redraw()

    def set_blank(self):
        self.userlist = []
        self.channel_icon = None
        self.channel_icon_url = None
        self.channel_title = None
        self.connection_status = "DISCONNECTED"
        self.set_needs_redraw()

    def set_fade_out_inactive(self, enabled, fade_time, fade_duration, fade_to):
        if self.fade_out_inactive != enabled or self.inactive_time != fade_time or self.inactive_fade_time != fade_duration or self.fade_out_limit != fade_to:
            self.fade_out_inactive = enabled
            self.inactive_time = fade_time
            self.inactive_fade_time = fade_duration
            self.fade_out_limit = fade_to
            self.reset_action_timer()

    def set_title_font(self, font):
        if self.title_font != font:
            self.title_font = font
            self.set_needs_redraw()

    def set_show_connection(self, show_connection):
        if self.show_connection != show_connection:
            self.show_connection = show_connection
            self.set_needs_redraw()

    def set_show_avatar(self, show_avatar):
        if self.show_avatar != show_avatar:
            self.show_avatar = show_avatar
            self.set_needs_redraw()

    def set_show_title(self, show_title):
        if self.show_title != show_title:
            self.show_title = show_title
            self.set_needs_redraw()

    def set_show_disconnected(self, show_disconnected):
        if self.show_disconnected != show_disconnected:
            self.show_disconnected = show_disconnected
            self.set_needs_redraw()

    def set_show_dummy(self, show_dummy):
        """
        Toggle use of dummy userdata to help choose settings
        """
        if self.use_dummy != show_dummy:
            self.use_dummy = show_dummy
            self.set_needs_redraw()

    def set_dummy_count(self, dummy_count):
        if self.dummy_count != dummy_count:
            self.dummy_count = dummy_count
            self.set_needs_redraw()

    def set_overflow(self, overflow):
        """
        How should excessive numbers of users be dealt with?
        """
        if self.overflow != overflow:
            self.overflow = overflow
            self.set_needs_redraw()

    def set_bg(self, background_colour):
        """
        Set the background colour
        """
        if self.norm_col != background_colour:
            self.norm_col = background_colour
            self.set_needs_redraw()

    def set_fg(self, foreground_colour):
        """
        Set the text colour
        """
        if self.text_col != foreground_colour:
            self.text_col = foreground_colour
            self.set_needs_redraw()

    def set_tk(self, talking_colour):
        """
        Set the border colour for users who are talking
        """
        if self.talk_col != talking_colour:
            self.talk_col = talking_colour
            self.set_needs_redraw()

    def set_mt(self, mute_colour):
        """
        Set the colour of mute and deafen logos
        """
        if self.mute_col != mute_colour:
            self.mute_col = mute_colour
            self.set_needs_redraw()

    def set_mute_bg(self, mute_bg_col):
        """
        Set the background colour for mute/deafen icon
        """
        if self.mute_bg_col != mute_bg_col:
            self.mute_bg_col = mute_bg_col
            self.set_needs_redraw()

    def set_avatar_bg_col(self, avatar_bg_col):
        """
        Set Avatar background colour
        """
        if self.avatar_bg_col != avatar_bg_col:
            self.avatar_bg_col = avatar_bg_col
            self.set_needs_redraw()

    def set_hi(self, highlight_colour):
        """
        Set the colour of background for speaking users
        """
        if self.hili_col != highlight_colour:
            self.hili_col = highlight_colour
            self.set_needs_redraw()

    def set_fg_hi(self, highlight_colour):
        """
        Set the colour of background for speaking users
        """
        if self.text_hili_col != highlight_colour:
            self.text_hili_col = highlight_colour
            self.set_needs_redraw()

    def set_bo(self, border_colour):
        """
        Set the colour for idle border
        """
        if self.border_col != border_colour:
            self.border_col = border_colour
            self.set_needs_redraw()

    def set_avatar_size(self, size):
        """
        Set the size of the avatar icons
        """
        if self.avatar_size != size:
            self.avatar_size = size
            self.set_needs_redraw()

    def set_nick_length(self, size):
        """
        Set the length of nickname
        """
        if self.nick_length != size:
            self.nick_length = size
            self.set_needs_redraw()

    def set_icon_spacing(self, i):
        """
        Set the spacing between avatar icons
        """
        if self.icon_spacing != i:
            self.icon_spacing = i
            self.set_needs_redraw()

    def set_text_padding(self, i):
        """
        Set padding between text and border
        """
        if self.text_pad != i:
            self.text_pad = i
            self.set_needs_redraw()

    def set_text_baseline_adj(self, i):
        """
        Set padding between text and border
        """
        if self.text_baseline_adj != i:
            self.text_baseline_adj = i
            self.set_needs_redraw()

    def set_vert_edge_padding(self, i):
        """
        Set padding between top/bottom of screen and overlay contents
        """
        if self.vert_edge_padding != i:
            self.vert_edge_padding = i
            self.set_needs_redraw()

    def set_horz_edge_padding(self, i):
        """
        Set padding between left/right of screen and overlay contents
        """
        if self.horz_edge_padding != i:
            self.horz_edge_padding = i
            self.set_needs_redraw()

    def set_square_avatar(self, i):
        """
        Set if the overlay should crop avatars to a circle or show full square image
        """
        if self.round_avatar == i:
            self.round_avatar = not i
            self.set_needs_redraw()

    def set_fancy_border(self, border):
        """
        Sets if border should wrap around non-square avatar images
        """
        if self.fancy_border != border:
            self.fancy_border = border
            self.set_needs_redraw()

    def set_only_speaking(self, only_speaking):
        """
        Set if overlay should only show people who are talking
        """
        if self.only_speaking != only_speaking:
            self.only_speaking = only_speaking
            self.set_needs_redraw()

    def set_only_speaking_grace_period(self, grace_period):
        """
        Set grace period before hiding people who are not talking
        """
        self.only_speaking_grace_period = grace_period
        self.timer_after_draw = grace_period

    def set_highlight_self(self, highlight_self):
        """
        Set if the overlay should highlight the user
        """
        if self.highlight_self != highlight_self:
            self.highlight_self = highlight_self
            self.set_needs_redraw()

    def set_order(self, i):
        """
        Set the method used to order avatar icons & names
        """
        if self.order != i:
            self.order = i
            self.sort_list(self.userlist)
            self.set_needs_redraw()

    def set_icon_only(self, i):
        """
        Set if the overlay should draw only the icon
        """
        if self.icon_only != i:
            self.icon_only = i
            self.set_needs_redraw()

    def set_border_width(self, width):
        if self.border_width != width:
            self.border_width = width
            self.set_needs_redraw()

    def set_horizontal(self, horizontal=False):
        if self.horizontal != horizontal:
            self.horizontal = horizontal
            self.set_needs_redraw()

    def set_guild_ids(self, guild_ids=tuple()):
        if self.discover.connection:
            for _id in guild_ids:
                if _id not in self.guild_ids:
                    self.discover.connection.req_channels(_id)
        self.guild_ids = guild_ids

    def set_wind_col(self):
        """
        Use window colour to draw
        """
        self.col(self.wind_col, None)

    def set_norm_col(self):
        """
        Use background colour to draw
        """
        self.col(self.norm_col)

    def set_talk_col(self, alpha=1.0):
        """
        Use talking colour to draw
        """
        self.col(self.talk_col, alpha)

    def set_mute_col(self):
        """
        Use mute colour to draw
        """
        self.col(self.mute_col)

    def set_channel_title(self, channel_title):
        """
        Set title above voice list
        """
        if self.channel_title != channel_title:
            self.channel_title = channel_title
            self.set_needs_redraw()

    def set_channel_icon(self, url):
        """
        Change the icon for channel
        """
        if not url:
            self.channel_icon = None
            self.channel_icon_url = None
        else:
            get_surface(self.recv_avatar, url, "channel",
                        self.avatar_size)
            self.channel_icon_url = url

    def set_user_list(self, userlist, alt):
        """
        Set the users in list to draw
        """
        self.userlist = userlist
        for user in userlist:
            if "nick" in user:
                user["friendlyname"] = user["nick"]
            else:
                user["friendlyname"] = user["username"]
        self.sort_list(self.userlist)
        if alt:
            self.reset_action_timer()
            self.set_needs_redraw()

    def set_connection_status(self, connection):
        """
        Set if discord has a clean connection to server
        """
        if self.connection_status != connection['state']:
            self.connection_status = connection['state']
            self.set_needs_redraw()

    def sort_list(self, in_list):
        if self.order == 1:  # ID Sort
            in_list.sort(key=lambda x: x["id"])
        elif self.order == 2:  # Spoken sort
            in_list.sort(key=lambda x: x["lastspoken"], reverse=True)
            in_list.sort(key=lambda x: x["speaking"], reverse=True)
        else:  # Name sort
            in_list.sort(key=lambda x: locale.strxfrm(x['friendlyname']))
        return in_list

    def has_content(self):
        if not self.enabled:
            return False
        if self.hidden:
            return False
        if self.use_dummy:
            return True
        return self.userlist

    def overlay_draw(self, w, context, data=None):
        """
        Draw the Overlay
        """
        self.context = context
        context.set_antialias(cairo.ANTIALIAS_GOOD)
        # Get size of window
        (width, height) = self.get_size()

        # Make background transparent
        self.set_wind_col()
        # Don't layer drawing over each other, always replace
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        context.save()
        if self.piggyback:
            self.piggyback.overlay_draw(w, context, data)
        (floating_x, floating_y, floating_width,
         floating_height) = self.get_floating_coords()
        if self.is_wayland or self.piggyback_parent or self.discover.steamos:
            # Special case!
            # The window is full-screen regardless of what the user has selected.
            # We need to set a clip and a transform to imitate original behaviour
            # Used in wlroots & gamescope

            if self.floating:
                context.new_path()
                context.translate(floating_x, floating_y)
                context.rectangle(0, 0, floating_width, floating_height)
                context.clip()

        context.set_operator(cairo.OPERATOR_OVER)
        if not self.show_disconnected and self.connection_status == "DISCONNECTED" and not self.use_dummy:
            return

        connection = self.discover.connection
        if not connection:
            return
        self_user = connection.user

        # Gather which users to draw
        users_to_draw = self.userlist[:]
        userlist = self.userlist
        if self.use_dummy:  # Sorting every frame is an awful idea. Maybe put this off elsewhere?
            users_to_draw = self.sort_list(self.dummy_data[0:self.dummy_count])
            userlist = self.dummy_data
        for user in userlist:
            # Bad object equality here, so we need to reassign
            if "id" in self_user and user["id"] == self_user["id"]:
                self_user = user

            # Update friendly name with nick if possible
            if "nick" in user:
                user["friendlyname"] = user["nick"]
            else:
                user["friendlyname"] = user["username"]

            # Remove users that haven't spoken within the grace period
            if self.only_speaking:
                speaking = "speaking" in user and user["speaking"]

                # Update the speaker cache
                if speaking:
                    self.speaker_cache[user["username"]] = perf_counter()

                if not speaking:
                    grace = self.only_speaking_grace_period

                    if (
                        grace > 0
                        and (last_spoke := self.speaker_cache.get(user["username"]))
                        and (perf_counter() - last_spoke) < grace
                    ):
                        # The user spoke within the grace period, so don't hide
                        # them just yet
                        pass

                    elif user in users_to_draw:
                        users_to_draw.remove(user)

        if self.highlight_self:
            if self_user in users_to_draw:
                users_to_draw.remove(self_user)
                users_to_draw.insert(0, self_user)

        avatar_size = self.avatar_size if self.show_avatar else 0
        line_height = self.avatar_size
        avatars_per_row = sys.maxsize

        # Calculate height needed to show overlay
        doTitle = False
        doConnection = False
        if self.show_connection:
            users_to_draw.insert(0, None)
            doConnection = True
        if self.show_title and self.channel_title:
            users_to_draw.insert(0, None)
            doTitle = True

        if self.horizontal:
            needed_width = (len(users_to_draw) * line_height) + \
                (len(users_to_draw) + 1) * self.icon_spacing

            if needed_width > width:
                if self.overflow == 1:  # Wrap
                    avatars_per_row = int(
                        width / (avatar_size+self.icon_spacing))
                elif self.overflow == 2:  # Shrink
                    available_size = width / len(users_to_draw)
                    avatar_size = available_size - self.icon_spacing
                    if avatar_size < 8:
                        avatar_size = 8

            current_y = 0 + self.vert_edge_padding
            offset_y = avatar_size + self.icon_spacing
            if self.align_right:  # A lie. Align bottom
                current_y = self.height - avatar_size - self.vert_edge_padding
                offset_y = -(avatar_size + self.icon_spacing)
            rows_to_draw = []
            while len(users_to_draw) > 0:
                row = []
                for i in range(0, min(avatars_per_row, len(users_to_draw))):
                    row.append(users_to_draw.pop(0))
                rows_to_draw.append(row)
            for row in rows_to_draw:
                needed_width = (len(row) * (line_height + self.icon_spacing))
                current_x = 0 + self.horz_edge_padding
                if self.align_vert == 1:
                    current_x = (width / 2) - (needed_width) / 2
                elif self.align_vert == 2:
                    current_x = width - needed_width - self.horz_edge_padding

                for user in row:
                    if not user:
                        if doTitle:
                            doTitle = False
                            text_width = self.draw_title(
                                context, current_x, current_y, avatar_size, line_height)
                        elif doConnection:
                            text_width = self.draw_connection(
                                context, current_x, current_y, avatar_size, line_height)
                            doConnection = False
                    else:
                        self.draw_avatar(context, user, current_x,
                                         current_y, avatar_size, line_height)
                    current_x += avatar_size + self.icon_spacing
                current_y += offset_y
        else:
            needed_height = ((len(users_to_draw)+0) * line_height) + \
                (len(users_to_draw) + 1) * self.icon_spacing

            if needed_height > height:
                if self.overflow == 1:  # Wrap
                    avatars_per_row = int(
                        height / (avatar_size + self.icon_spacing))
                elif self.overflow == 2:  # Shrink
                    available_size = height / len(users_to_draw)
                    avatar_size = available_size - self.icon_spacing
                    if avatar_size < 8:
                        avatar_size = 8

            current_x = 0 + self.horz_edge_padding
            offset_x_mult = 1
            offset_x = avatar_size + self.horz_edge_padding
            if self.align_right:
                offset_x_mult = -1
                current_x = floating_width - avatar_size - self.horz_edge_padding

            # Choose where to start drawing
            current_y = 0 + self.vert_edge_padding
            if self.align_vert == 1:
                current_y = (height / 2) - (needed_height / 2)
            elif self.align_vert == 2:
                current_y = height - needed_height - self.vert_edge_padding

            cols_to_draw = []
            while len(users_to_draw) > 0:
                col = []
                for i in range(0, min(avatars_per_row, len(users_to_draw))):
                    col.append(users_to_draw.pop(0))
                cols_to_draw.append(col)
            for col in cols_to_draw:
                needed_height = (len(col) * (line_height + self.icon_spacing))
                current_y = 0 + self.vert_edge_padding
                if self.align_vert == 1:
                    current_y = (height/2) - (needed_height / 2)
                elif self.align_vert == 2:
                    current_y = height - needed_height - self.vert_edge_padding
                largest_text_width = 0
                for user in col:
                    if not user:
                        if doTitle:
                            # Draw header
                            text_width = self.draw_title(
                                context, current_x, current_y, avatar_size, line_height)
                            largest_text_width = max(
                                text_width, largest_text_width)
                            current_y += line_height + self.icon_spacing
                            doTitle = False
                        elif doConnection:
                            # Draw header
                            text_width = self.draw_connection(
                                context, current_x, current_y, avatar_size, line_height)
                            largest_text_width = max(
                                text_width, largest_text_width)
                            current_y += line_height + self.icon_spacing
                            doConnection = False

                    else:
                        text_width = self.draw_avatar(
                            context, user, current_x, current_y, avatar_size, line_height)
                        largest_text_width = max(
                            text_width, largest_text_width)
                        current_y += line_height + self.icon_spacing
                if largest_text_width > 0:
                    largest_text_width += self.text_pad
                else:
                    largest_text_width = self.icon_spacing
                current_x += offset_x_mult * (offset_x + largest_text_width)

        context.restore()
        self.context = None

    def recv_avatar(self, identifier, pix, mask):
        """
        Called when image_getter has downloaded an image
        """
        if identifier == 'def':
            self.def_avatar = pix
            self.def_avatar_mask = mask
        elif identifier == 'channel':
            self.channel_icon = pix
            self.channel_mask = mask
        else:
            self.avatars[identifier] = pix
            self.avatar_masks[identifier] = mask
        self.set_needs_redraw()

    def delete_avatar(self, identifier):
        """
        Remove avatar image
        """
        if identifier in self.avatars:
            del self.avatars[identifier]

    def draw_title(self, context, pos_x, pos_y, avatar_size, line_height):
        """
        Draw title at given Y position. Includes both text and image based on settings
        """
        tw = 0
        if not self.horizontal and not self.icon_only:
            title = self.channel_title
            if self.use_dummy:
                title = "Dummy Title"
            tw = self.draw_text(
                context, title,
                pos_x,
                pos_y,
                self.text_col,
                self.norm_col,
                avatar_size,
                line_height,
                self.title_font
            )
        if self.channel_icon:
            self.draw_avatar_pix(context, self.channel_icon, self.channel_mask,
                                 pos_x, pos_y, None, avatar_size)
        else:
            self.blank_avatar(context, pos_x, pos_y, avatar_size)
            if self.channel_icon_url:
                get_surface(self.recv_avatar, self.channel_icon_url, "channel",
                            self.avatar_size)
        return tw

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

    def draw_connection(self, context, pos_x, pos_y, avatar_size, line_height):
        """
        Draw title at given Y position. Includes both text and image based on settings
        """
        tw = 0
        if not self.horizontal and not self.icon_only:
            tw = self.draw_text(
                context, _(self.connection_status),
                pos_x,
                pos_y,
                self.text_col,
                self.norm_col,
                avatar_size,
                line_height,
                self.text_font
            )
        self.blank_avatar(context, pos_x, pos_y, avatar_size)
        self.draw_connection_icon(context, pos_x, pos_y, avatar_size)
        return tw

    def draw_avatar(self, context, user, pos_x, pos_y, avatar_size, line_height):
        """
        Draw avatar at given Y position. Includes both text and image based on settings
        """
        # Ensure pixbuf for avatar
        if user["id"] not in self.avatars and user["avatar"] and avatar_size > 0:
            url = "https://cdn.discordapp.com/avatars/%s/%s.png" % (
                user['id'], user['avatar'])
            get_surface(self.recv_avatar, url, user["id"],
                        self.avatar_size)

            # Set the key with no value to avoid spamming requests
            self.avatars[user["id"]] = None
            self.avatar_masks[user["id"]] = None

        colour = None
        mute = False
        deaf = False
        bg_col = None
        fg_col = None
        tw = 0

        if "mute" in user and user["mute"]:
            mute = True
        if "deaf" in user and user["deaf"]:
            deaf = True
        if "speaking" in user and user["speaking"] and not deaf and not mute:
            colour = self.talk_col
        if "speaking" in user and user["speaking"] and not deaf and not mute:
            bg_col = self.hili_col
            fg_col = self.text_hili_col
        else:
            bg_col = self.norm_col
            fg_col = self.text_col

        pix = None
        mask = None
        if user["id"] in self.avatars:
            pix = self.avatars[user["id"]]
            mask = self.avatar_masks[user["id"]]
        if not self.horizontal:
            if not self.icon_only:
                tw = self.draw_text(
                    context, user["friendlyname"],
                    pos_x,
                    pos_y,
                    fg_col,
                    bg_col,
                    avatar_size,
                    line_height,
                    self.text_font
                )
        self.draw_avatar_pix(context, pix, mask, pos_x,
                             pos_y, colour, avatar_size)
        if deaf:
            self.draw_deaf(context, pos_x, pos_y,
                           self.mute_bg_col, avatar_size)
        elif mute:
            self.draw_mute(context, pos_x, pos_y,
                           self.mute_bg_col, avatar_size)
        return tw

    def draw_text(self, context, string, pos_x, pos_y, tx_col, bg_col, avatar_size, line_height, font):
        """
        Draw username & background at given position
        """
        if self.nick_length < 32 and len(string) > self.nick_length:
            string = string[:(self.nick_length-1)] + u"\u2026"

        context.save()
        layout = self.create_pango_layout(string)
        layout.set_auto_dir(True)
        layout.set_markup(string, -1)
        (floating_x, floating_y, floating_width,
         floating_height) = self.get_floating_coords()
        layout.set_width(Pango.SCALE * floating_width)
        layout.set_spacing(Pango.SCALE * 3)
        if font:
            font = Pango.FontDescription(font)
            layout.set_font_description(font)
        (_ink_rect, logical_rect) = layout.get_pixel_extents()
        text_height = logical_rect.height
        text_width = logical_rect.width

        self.col(tx_col)
        height_offset = (line_height / 2) - (text_height / 2)
        text_y_offset = height_offset + self.text_baseline_adj

        if self.align_right:
            context.move_to(0, 0)
            self.col(bg_col)
            context.rectangle(
                pos_x - text_width - (self.text_pad * 2),
                pos_y + height_offset - self.text_pad,
                text_width + (self.text_pad * 4),
                text_height + (self.text_pad * 2)
            )
            context.fill()

            self.col(tx_col)
            context.move_to(
                pos_x - text_width - self.text_pad,
                pos_y + text_y_offset
            )
            PangoCairo.show_layout(self.context, layout)
        else:
            context.move_to(0, 0)
            self.col(bg_col)
            context.rectangle(
                pos_x - (self.text_pad * 2) + avatar_size,
                pos_y + height_offset - self.text_pad,
                text_width + (self.text_pad * 4),
                text_height + (self.text_pad * 2)
            )
            context.fill()

            self.col(tx_col)
            context.move_to(
                pos_x + self.text_pad + avatar_size,
                pos_y + text_y_offset
            )
            PangoCairo.show_layout(self.context, layout)
        context.restore()
        return text_width

    def blank_avatar(self, context, pos_x, pos_y, avatar_size):
        context.save()
        if self.round_avatar:
            context.arc(pos_x + (avatar_size / 2), pos_y +
                        (avatar_size / 2), avatar_size / 2, 0, 2 * math.pi)
            context.clip()
        self.col(self.avatar_bg_col)
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.rectangle(pos_x, pos_y, avatar_size, avatar_size)
        context.fill()
        context.restore()

    def draw_avatar_pix(self, context, pixbuf, mask, pos_x, pos_y, border_colour, avatar_size):
        """
        Draw avatar image at given position
        """
        if not self.show_avatar:
            return
        # Empty the space for this
        self.blank_avatar(context, pos_x, pos_y, avatar_size)

        # fallback default or fallback further to no image here
        if not pixbuf:
            pixbuf = self.def_avatar
            if not pixbuf:
                return
        if not mask:
            mask = self.def_avatar_mask
            if not mask:
                return

        # Draw the "border" by doing a scaled-up copy in a flat colour
        if border_colour:
            self.col(border_colour)
            if self.fancy_border:
                context.set_operator(cairo.OPERATOR_SOURCE)
                for off_x in range(-self.border_width, self.border_width+1):
                    for off_y in range(-self.border_width, self.border_width+1):
                        context.save()
                        if self.round_avatar:
                            context.new_path()
                            context.arc(pos_x + off_x + (avatar_size / 2), pos_y + off_y +
                                        (avatar_size / 2), avatar_size / 2, 0, 2 * math.pi)
                            context.clip()
                        draw_img_to_mask(mask, context, pos_x + off_x, pos_y + off_y,
                                         avatar_size, avatar_size)
                        context.restore()
            else:
                if self.round_avatar:
                    context.new_path()
                    context.arc(pos_x + (avatar_size / 2), pos_y +
                                (avatar_size / 2), avatar_size / 2 + (self.border_width/2.0), 0, 2 * math.pi)
                    context.set_line_width(self.border_width)
                    context.stroke()
                else:
                    context.new_path()
                    context.rectangle(pos_x - (self.border_width/2), pos_y - (self.border_width/2),
                                      avatar_size + self.border_width, avatar_size + self.border_width)
                    context.set_line_width(self.border_width)

                    context.stroke()

            # Cut the image back out
            context.save()
            if self.round_avatar:
                context.new_path()
                context.arc(pos_x + (avatar_size / 2), pos_y +
                            (avatar_size / 2), avatar_size / 2, 0, 2 * math.pi)
                context.clip()
            self.col([0.0, 0.0, 0.0, 0.0])
            context.set_operator(cairo.OPERATOR_SOURCE)
            draw_img_to_mask(mask, context, pos_x, pos_y,
                             avatar_size, avatar_size)
            context.restore()
        # Draw the image
        context.save()
        if self.round_avatar:
            context.new_path()
            context.arc(pos_x + (avatar_size / 2), pos_y +
                        (avatar_size / 2), avatar_size / 2, 0, 2 * math.pi)
            context.clip()
        context.set_operator(cairo.OPERATOR_OVER)
        draw_img_to_rect(pixbuf, context, pos_x, pos_y,
                         avatar_size, avatar_size, False, False, 0, 0, self.fade_opacity * self.icon_transparency)
        context.restore()

    def draw_mute(self, context, pos_x, pos_y, bg_col, avatar_size):
        """
        Draw Mute logo
        """
        if avatar_size <= 0:
            return
        context.save()
        context.translate(pos_x, pos_y)
        context.scale(avatar_size, avatar_size)

        # Add a dark background
        context.set_operator(cairo.OPERATOR_ATOP)
        context.rectangle(0.0, 0.0, 1.0, 1.0)
        self.col(bg_col, None)
        context.fill()
        context.set_operator(cairo.OPERATOR_OVER)

        self.set_mute_col()
        context.save()

        # Clip Strike-through
        context.new_path()
        context.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        context.set_line_width(0.1)
        context.move_to(0.0, 0.0)
        context.line_to(1.0, 0.0)
        context.line_to(1.0, 1.0)
        context.line_to(0.0, 1.0)
        context.line_to(0.0, 0.0)
        context.close_path()
        context.new_sub_path()
        context.arc(0.9, 0.1, 0.05, 1.25 * math.pi, 2.25 * math.pi)
        context.arc(0.1, 0.9, 0.05, .25 * math.pi, 1.25 * math.pi)
        context.close_path()
        context.clip()

        # Center
        context.set_line_width(0.07)
        context.arc(0.5, 0.3, 0.1, math.pi, 2 * math.pi)
        context.arc(0.5, 0.5, 0.1, 0, math.pi)
        context.close_path()
        context.fill()

        context.set_line_width(0.05)

        # Stand rounded
        context.arc(0.5, 0.5, 0.15, 0, 1.0 * math.pi)
        context.stroke()

        # Stand vertical
        context.move_to(0.5, 0.65)
        context.line_to(0.5, 0.75)
        context.stroke()

        # Stand horizontal
        context.move_to(0.35, 0.75)
        context.line_to(0.65, 0.75)
        context.stroke()

        context.restore()
        # Strike through
        context.arc(0.7, 0.3, 0.035, 1.25 * math.pi, 2.25 * math.pi)
        context.arc(0.3, 0.7, 0.035, .25 * math.pi, 1.25 * math.pi)
        context.close_path()
        context.fill()
        context.set_fill_rule(cairo.FILL_RULE_WINDING)

        context.restore()

    def draw_deaf(self, context, pos_x, pos_y, bg_col, avatar_size):
        """
        Draw deaf logo
        """
        if avatar_size <= 0:
            return
        context.save()
        context.translate(pos_x, pos_y)
        context.scale(avatar_size, avatar_size)

        # Add a dark background
        context.set_operator(cairo.OPERATOR_ATOP)
        context.rectangle(0.0, 0.0, 1.0, 1.0)
        self.col(bg_col, None)
        context.fill()
        context.set_operator(cairo.OPERATOR_OVER)

        self.set_mute_col()
        context.save()

        # Clip Strike-through
        context.new_path()
        context.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        context.set_line_width(0.1)
        context.move_to(0.0, 0.0)
        context.line_to(1.0, 0.0)
        context.line_to(1.0, 1.0)
        context.line_to(0.0, 1.0)
        context.line_to(0.0, 0.0)
        context.close_path()
        context.new_sub_path()
        context.arc(0.9, 0.1, 0.05, 1.25 * math.pi, 2.25 * math.pi)
        context.arc(0.1, 0.9, 0.05, .25 * math.pi, 1.25 * math.pi)
        context.close_path()
        context.clip()

        # Top band
        context.arc(0.5, 0.5, 0.2, 1.0 * math.pi, 0)
        context.stroke()

        # Left band
        context.arc(0.28, 0.65, 0.075, 1.5 * math.pi, 0.5 * math.pi)
        context.move_to(0.3, 0.5)
        context.line_to(0.3, 0.75)
        context.stroke()

        # Right band
        context.arc(0.72, 0.65, 0.075, 0.5 * math.pi, 1.5 * math.pi)
        context.move_to(0.7, 0.5)
        context.line_to(0.7, 0.75)
        context.stroke()

        context.restore()
        # Strike through
        context.arc(0.7, 0.3, 0.035, 1.25 * math.pi, 2.25 * math.pi)
        context.arc(0.3, 0.7, 0.035, .25 * math.pi, 1.25 * math.pi)
        context.close_path()
        context.fill()
        context.set_fill_rule(cairo.FILL_RULE_WINDING)

        context.restore()

    def draw_connection_icon(self, context, pos_x, pos_y, avatar_size):
        context.save()
        context.translate(pos_x, pos_y)
        context.scale(avatar_size, avatar_size)

        bars = 0
        s = self.connection_status
        if s == "DISCONNECTED" or s == "NO_ROUTE" or s == "VOICE_DISCONNECTED":
            bars = 0
            self.col([1.0, 0.0, 0.0, 1.0])
        elif s == "ICE_CHECKING" or s == "AWAITING_ENDPOINT" or s == "AUTHENTICATING":
            bars = 1
            self.col([1.0, 0.0, 0.0, 1.0])
        elif s == "CONNECTING" or s == "CONNECTED" or s == "VOICE_CONNECTING":
            bars = 2
            self.col([1.0, 1.0, 0.0, 1.0])
        elif s == "VOICE_CONNECTED":
            bars = 3
            self.col([0.0, 1.0, 0.0, 1.0])
        context.set_line_width(0.1)

        if bars >= 1:
            context.move_to(0.3, 0.8)
            context.line_to(0.3, 0.6)
            context.stroke()
        if bars >= 2:
            context.move_to(0.5, 0.8)
            context.line_to(0.5, 0.4)
            context.stroke()
        if bars == 3:
            context.move_to(0.7, 0.8)
            context.line_to(0.7, 0.2)
            context.stroke()
        context.restore()
