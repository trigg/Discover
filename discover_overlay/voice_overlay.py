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
import logging
import math
import cairo
import sys
from .overlay import OverlayWindow
from .image_getter import get_surface, draw_img_to_rect
# pylint: disable=wrong-import-order
import gi
gi.require_version("Gtk", "3.0")
gi.require_version('PangoCairo', '1.0')
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Pango, PangoCairo  # nopep8
import random

log = logging.getLogger(__name__)


class VoiceOverlayWindow(OverlayWindow):
    """Overlay window for voice"""

    def __init__(self, discover, piggyback=None):
        OverlayWindow.__init__(self, discover, piggyback)

        self.avatars = {}

        self.dummy_data = []
        mostly_false = [False, False, False, False, False, False, False, True]
        for i in range(0,100):
            speaking = mostly_false[random.randint(0,7)]
            scream = ''
            if random.randint(0,20)==2:
                scream = random.randint(8,15)*'a'
            name = "Player %d %s" % (i, scream)
            self.dummy_data.append({
                "id": i,
                "username": name,
                "avatar": None,
                "mute": False,
                "deaf": mostly_false[random.randint(0,7)],
                "mute": mostly_false[random.randint(0,7)],
                "speaking": speaking ,
                'lastspoken': random.randint(2000,2100) if speaking else random.randint(10,30),
                'friendlyname': name,
            })
        self.avatar_size = 48
        self.text_pad = 6
        self.text_font = None
        self.text_size = 13
        self.text_baseline_adj = 0
        self.icon_spacing = 8
        self.vert_edge_padding = 0
        self.horz_edge_padding = 0
        self.only_speaking = None
        self.highlight_self = None
        self.order = None
        self.def_avatar = None
        self.overflow = None
        self.use_dummy = False
        self.dummy_count = 10

        self.round_avatar = True
        self.icon_only = True
        self.talk_col = [0.0, 0.6, 0.0, 0.1]
        self.text_col = [1.0, 1.0, 1.0, 1.0]
        self.text_hili_col = [1.0, 1.0, 1.0, 1.0]
        self.norm_col = [0.0, 0.0, 0.0, 0.5]
        self.wind_col = [0.0, 0.0, 0.0, 0.0]
        self.mute_col = [0.7, 0.0, 0.0, 1.0]
        self.hili_col = [0.0, 0.0, 0.0, 0.9]
        self.border_col = [0.0, 0.0, 0.0, 0.0]
        self.userlist = []
        self.connected = False
        self.horizontal = False
        self.guild_ids = tuple()
        self.force_location()
        get_surface(self.recv_avatar,
                    "share/icons/hicolor/256x256/apps/discover-overlay-default.png",
                    'def', self.avatar_size)
        self.set_title("Discover Voice")
        self.redraw()

    def set_show_dummy(self, show_dummy):
        """
        Toggle use of dummy userdata to help choose settings
        """
        self.use_dummy = show_dummy
        self.needsredraw = True

    def set_dummy_count(self, dummy_count):
        self.dummy_count = dummy_count
        self.needsredraw = True

    def set_overflow(self, overflow):
        """
        How should excessive numbers of users be dealt with?
        """
        self.overflow = overflow
        self.needsredraw = True

    def set_bg(self, background_colour):
        """
        Set the background colour
        """
        self.norm_col = background_colour
        self.needsredraw = True

    def set_fg(self, foreground_colour):
        """
        Set the text colour
        """
        self.text_col = foreground_colour
        self.needsredraw = True

    def set_tk(self, talking_colour):
        """
        Set the border colour for users who are talking
        """
        self.talk_col = talking_colour
        self.needsredraw = True

    def set_mt(self, mute_colour):
        """
        Set the colour of mute and deafen logos
        """
        self.mute_col = mute_colour
        self.needsredraw = True

    def set_hi(self, highlight_colour):
        """
        Set the colour of background for speaking users
        """
        self.hili_col = highlight_colour
        self.needsredraw = True

    def set_fg_hi(self, highlight_colour):
        """
        Set the colour of background for speaking users
        """
        self.text_hili_col = highlight_colour
        self.needsredraw = True

    def set_bo(self, border_colour):
        """
        Set the colour for idle border
        """
        self.border_col = border_colour
        self.needsredraw = True

    def set_avatar_size(self, size):
        """
        Set the size of the avatar icons
        """
        self.avatar_size = size
        self.needsredraw = True

    def set_icon_spacing(self, i):
        """
        Set the spacing between avatar icons
        """
        self.icon_spacing = i
        self.needsredraw = True

    def set_text_padding(self, i):
        """
        Set padding between text and border
        """
        self.text_pad = i
        self.needsredraw = True

    def set_text_baseline_adj(self, i):
        """
        Set padding between text and border
        """
        self.text_baseline_adj = i
        self.needsredraw = True

    def set_vert_edge_padding(self, i):
        """
        Set padding between top/bottom of screen and overlay contents
        """
        self.vert_edge_padding = i
        self.needsredraw = True

    def set_horz_edge_padding(self, i):
        """
        Set padding between left/right of screen and overlay contents
        """
        self.horz_edge_padding = i
        self.needsredraw = True

    def set_square_avatar(self, i):
        """
        Set if the overlay should crop avatars to a circle or show full square image
        """
        self.round_avatar = not i
        self.needsredraw = True

    def set_only_speaking(self, only_speaking):
        """
        Set if overlay should only show people who are talking
        """
        self.only_speaking = only_speaking

    def set_highlight_self(self, highlight_self):
        """
        Set if the overlay should highlight the user
        """
        self.highlight_self = highlight_self

    def set_order(self, i):
        """
        Set the method used to order avatar icons & names
        """
        self.order = i
        self.sort_list(self.userlist)
        self.needsredraw= True

    def set_icon_only(self, i):
        """
        Set if the overlay should draw only the icon
        """
        self.icon_only = i
        self.needsredraw = True

    def set_horizontal(self, horizontal=False):
        self.horizontal = horizontal
        self.needsredraw = True

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
        self.col(self.wind_col)

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

    def set_mute_col(self, alpha=1.0):
        """
        Use mute colour to draw
        """
        self.col(self.mute_col, alpha)

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
        screen = self.get_screen()
        # Check if composite state has changed
        if not self.compositing == screen.is_composited():
            alt = True
            self.compositing = screen.is_composited()
        if alt:
            self.needsredraw = True

    def set_connection(self, connection):
        """
        Set if discord has a clean connection to server
        """
        is_connected = connection == "VOICE_CONNECTED"
        if self.connected != is_connected:
            self.connected = is_connected
            self.needsredraw = True

    def sort_list(self, in_list):
        if self.order == 1:  # ID Sort
            in_list.sort(key=lambda x: x["id"])
        elif self.order == 2:  # Spoken sort
            in_list.sort(key=lambda x: x["lastspoken"], reverse=True)
            in_list.sort(key=lambda x: x["speaking"], reverse=True)
        else:  # Name sort
            in_list.sort(key=lambda x: x["friendlyname"])
        return in_list

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
        if self.is_wayland or self.piggyback_parent or self.discover.steamos:
            # Special case!
            # The window is full-screen regardless of what the user has selected.
            # We need to set a clip and a transform to imitate original behaviour
            # Used in wlroots & gamescope
            width = self.width
            height = self.height
            if self.floating:
                context.translate(self.pos_x, self.pos_y)
                context.rectangle(0, 0, width, height)
                context.clip()

        context.set_operator(cairo.OPERATOR_OVER)
        if not self.connected and not self.use_dummy:
            return

        connection = self.discover.connection
        self_user = connection.user

        # Gather which users to draw
        users_to_draw = self.userlist[:]
        userlist = self.userlist
        if self.use_dummy: # Sorting every frame is an awful idea. Maybe put this off elsewhere?
            users_to_draw = self.sort_list(self.dummy_data[0:self.dummy_count])
            userlist = self.dummy_data
        for user in userlist:
            # Bad object equality here, so we need to reassign
            if user["id"] == self_user["id"]:
                self_user = user

            # Update friendly name with nick if possible
            if "nick" in user:
                user["friendlyname"] = user["nick"]
            else:
                user["friendlyname"] = user["username"]

            # Remove users that arent speaking
            if self.only_speaking:
                speaking = "speaking" in user and user["speaking"]
                if not speaking:
                    if user in users_to_draw: 
                        users_to_draw.remove(user)

        if self.highlight_self:
            if self_user in users_to_draw:
                users_to_draw.remove(self_user)
            users_to_draw.insert(0, self_user)

        avatar_size = self.avatar_size
        avatars_per_row = sys.maxsize

        if self.horizontal:
            needed_width = (len(users_to_draw) * self.avatar_size) + \
                (len(users_to_draw) + 1) * self.icon_spacing

            if needed_width > width:
                if self.overflow == 1: # Wrap
                    avatars_per_row = int(width / (avatar_size+self.icon_spacing))
                elif self.overflow == 2: # Shrink
                    available_size = width / len(users_to_draw)
                    avatar_size = available_size - self.icon_spacing
                    if avatar_size<8:
                        avatar_size = 8

            current_y = 0 + self.vert_edge_padding
            offset_y = avatar_size + self.icon_spacing
            if self.align_right: # A lie. Align bottom
                current_y = self.height - avatar_size - self.vert_edge_padding
                offset_y = -(avatar_size + self.icon_spacing)
            rows_to_draw = []
            while len(users_to_draw) > 0:
                row = []
                for i in range(0, min(avatars_per_row, len(users_to_draw))):
                    row.append(users_to_draw.pop(0))
                rows_to_draw.append(row)
            for row in rows_to_draw:
                needed_width = (len(row) * (avatar_size + self.icon_spacing))
                current_x = 0 + self.horz_edge_padding
                if self.align_vert == 1:
                    current_x = (width / 2) - (needed_width) / 2
                elif self.align_vert == 2:
                    current_x = width - needed_width - self.horz_edge_padding

                for user in row:
                    self.draw_avatar(context, user, current_x, current_y, avatar_size)
                    current_x += avatar_size + self.icon_spacing
                current_y+=offset_y
        else:
            # Calculate height needed to show overlay
            needed_height = (len(users_to_draw) * self.avatar_size) + \
                (len(users_to_draw) + 1) * self.icon_spacing

            if needed_height > height:
                if self.overflow == 1: # Wrap
                    avatars_per_row = int(height / (avatar_size + self.icon_spacing))
                elif self.overflow == 2: # Shrink
                    available_size = height / len(users_to_draw)
                    avatar_size = available_size - self.icon_spacing
                    if avatar_size<8:
                        avatar_size = 8

            current_x = 0
            offset_x_mult=1
            offset_x = avatar_size + self.horz_edge_padding
            if self.align_right:
                offset_x_mult =-1
                current_x = self.width - avatar_size - self.horz_edge_padding

            # Choose where to start drawing
            current_y = 0 + self.vert_edge_padding
            if self.align_vert == 1:
                current_y = (height / 2) - (needed_height / 2)
            elif self.align_vert == 2:
                current_y = height - needed_height - self.vert_edge_padding

            cols_to_draw = []
            while len(users_to_draw) > 0:
                col = []
                for i in range(0,min(avatars_per_row, len(users_to_draw))):
                    col.append(users_to_draw.pop(0))
                cols_to_draw.append(col)
            for col in cols_to_draw:
                needed_height = (len(col) * (avatar_size + self.icon_spacing))
                current_y = 0 + self.vert_edge_padding
                if self.align_vert == 1:
                    current_y = (height/2) - (needed_height /2)
                elif self.align_vert == 2:
                    current_y = height - needed_height - self.vert_edge_padding
                largest_text_width = 0
                for user in col:
                    text_width = self.draw_avatar(context, user, current_x, current_y, avatar_size)
                    largest_text_width = max(text_width, largest_text_width)
                    current_y += avatar_size + self.icon_spacing
                if largest_text_width > 0:
                    largest_text_width += self.text_pad
                else:
                    largest_text_width = self.icon_spacing
                current_x += offset_x_mult* (offset_x + largest_text_width)

        context.restore()
        self.context = None

    def recv_avatar(self, identifier, pix):
        """
        Called when image_getter has downloaded an image
        """
        if identifier == 'def':
            self.def_avatar = pix
        else:
            self.avatars[identifier] = pix
        self.needsredraw = True

    def delete_avatar(self, identifier):
        """
        Remove avatar image
        """
        if identifier in self.avatars:
            del self.avatars[identifier]

    def draw_avatar(self, context, user, pos_x, pos_y, avatar_size):
        """
        Draw avatar at given Y position. Includes both text and image based on settings
        """
        # Ensure pixbuf for avatar
        if user["id"] not in self.avatars and user["avatar"]:
            url = "https://cdn.discordapp.com/avatars/%s/%s.png" % (
                user['id'], user['avatar'])
            get_surface(self.recv_avatar, url, user["id"],
                        self.avatar_size)

            # Set the key with no value to avoid spamming requests
            self.avatars[user["id"]] = None

        colour = self.border_col
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
        if user["id"] in self.avatars:
            pix = self.avatars[user["id"]]
        if not self.horizontal:
            if not self.icon_only:
                tw = self.draw_text(
                    context, user["friendlyname"],
                    pos_x,
                    pos_y,
                    fg_col,
                    bg_col,
                    avatar_size
                )
        self.draw_avatar_pix(context, pix,pos_x,pos_y,colour, avatar_size)
        if deaf:
            self.draw_deaf(context, pos_x, pos_y, avatar_size)
        elif mute:
            self.draw_mute(context, pos_x, pos_y, avatar_size)
        return tw

    def draw_text(self, context, string, pos_x, pos_y, tx_col, bg_col, avatar_size):
        """
        Draw username & background at given position
        """
        layout = self.create_pango_layout(string)
        layout.set_auto_dir(True)
        layout.set_markup(string, -1)

        layout.set_width(Pango.SCALE * self.width)
        layout.set_spacing(Pango.SCALE * 3)
        font = None
        if self.text_font:
            font = Pango.FontDescription(self.text_font)
            layout.set_font_description(font)
        (_ink_rect, logical_rect) = layout.get_pixel_extents()
        text_height = logical_rect.height
        text_width = logical_rect.width

        self.col(tx_col)
        height_offset = (avatar_size / 2) - (text_height / 2)
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
                pos_x + self.text_pad+ avatar_size,
                pos_y + text_y_offset
            )
            PangoCairo.show_layout(self.context, layout)

        return text_width

    def draw_avatar_pix(self, context, pixbuf, pos_x, pos_y, border_colour, avatar_size):
        """
        Draw avatar image at given position
        """
        if not pixbuf:
            pixbuf = self.def_avatar
            if not pixbuf:
                return
        context.move_to(pos_x, pos_y)
        context.save()
        if self.round_avatar:
            context.arc(pos_x + (self.avatar_size / 2), pos_y +
                        (self.avatar_size / 2), self.avatar_size / 2, 0, 2 * math.pi)
            context.clip()

        self.set_norm_col()
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.rectangle(pos_x, pos_y, avatar_size, avatar_size)
        context.fill()
        draw_img_to_rect(pixbuf, context, pos_x, pos_y,
                         avatar_size, avatar_size)
        context.restore()
        if border_colour:
            if self.round_avatar:
                context.arc(
                    pos_x + (avatar_size / 2),
                    pos_y + (avatar_size / 2),
                    avatar_size / 2,
                    0, 2 * math.pi
                )
                self.col(border_colour)
                context.stroke()
            else:
                context.rectangle(
                    pos_x, pos_y,
                    avatar_size, avatar_size
                )
                self.col(border_colour)
                context.stroke()

    def draw_mute(self, context, pos_x, pos_y, avatar_size):
        """
        Draw Mute logo
        """
        context.save()
        context.translate(pos_x, pos_y)
        context.scale(avatar_size, avatar_size)
        self.set_mute_col()
        context.save()

        # Clip Strike-through
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

        context.restore()

    def draw_deaf(self, context, pos_x, pos_y, avatar_size):
        """
        Draw deaf logo
        """
        context.save()
        context.translate(pos_x, pos_y)
        context.scale(avatar_size, avatar_size)
        self.set_mute_col()
        context.save()

        # Clip Strike-through
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

        context.restore()
