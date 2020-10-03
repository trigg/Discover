import gi

gi.require_version("Gtk", "3.0")
import math
from .overlay import OverlayWindow
from .image_getter import get_image
from gi.repository import Gtk, Gdk
import cairo
import logging


class VoiceOverlayWindow(OverlayWindow):

    def __init__(self, discover):
        OverlayWindow.__init__(self)

        self.discover = discover
        self.avatars = {}

        self.avatar_size = 48
        self.text_pad = 6
        self.text_font = None
        self.text_size = 13
        self.icon_spacing = 8
        self.vert_edge_padding = 0
        self.horz_edge_padding = 0

        self.round_avatar = True
        self.talk_col = [0.0, 0.6, 0.0, 0.1]
        self.text_col = [1.0, 1.0, 1.0, 1.0]
        self.norm_col = [0.0, 0.0, 0.0, 0.5]
        self.wind_col = [0.0, 0.0, 0.0, 0.0]
        self.mute_col = [0.7, 0.0, 0.0, 1.0]
        self.userlist = []
        self.users_to_draw = []
        self.connected = False
        self.force_location()
        self.def_avatar = get_image(self.recv_avatar,
                                    "https://cdn.discordapp.com/embed/avatars/3.png",
                                    'def', self.avatar_size)

        self.first_draw = True

    def set_bg(self, bg):
        self.norm_col = bg
        self.redraw()

    def set_fg(self, fg):
        self.text_col = fg
        self.redraw()

    def set_tk(self, tk):
        self.talk_col = tk
        self.redraw()

    def set_mt(self, mt):
        self.mute_col = mt
        self.redraw()

    def set_avatar_size(self, size):
        self.avatar_size = size
        self.reset_avatar()
        self.redraw()

    def set_icon_spacing(self, i):
        self.icon_spacing = i
        self.redraw()

    def set_text_padding(self, i):
        self.text_pad = i
        self.redraw()

    def set_vert_edge_padding(self, i):
        self.vert_edge_padding = i
        self.redraw()

    def set_horz_edge_padding(self, i):
        self.horz_edge_padding = i
        self.redraw()

    def set_square_avatar(self, i):
        self.round_avatar = not i
        self.redraw()

    def set_only_speaking(self, only_speaking):
        self.only_speaking = only_speaking

    def set_highlight_self(self, highlight_self):
        self.highlight_self = highlight_self

    def set_wind_col(self):
        self.col(self.wind_col)

    def set_text_col(self):
        self.col(self.text_col)

    def set_norm_col(self):
        self.col(self.norm_col)

    def set_talk_col(self, a=1.0):
        self.col(self.talk_col, a)

    def set_mute_col(self, a=1.0):
        self.col(self.mute_col, a)

    def reset_avatar(self):
        self.avatars = {}
        get_image(self.recv_avatar,
                  "https://cdn.discordapp.com/embed/avatars/3.png",
                  'def', self.avatar_size)

    def set_user_list(self, userlist, alt):
        self.userlist = userlist
        self.userlist.sort(key=lambda x: x["username"])
        screen = self.get_screen()
        c = screen.is_composited()
        if not self.compositing == c:
            alt = True
            self.compositing = c
        if alt:
            self.redraw()

    def set_connection(self, connection):
        is_connected = connection == "VOICE_CONNECTED"
        if self.connected != is_connected:
            self.connected = is_connected
            self.redraw()

    def draw(self, widget, context):
        # Draw
        self.do_draw(context)

    def do_draw(self, context):
        self.context = context
        context.set_antialias(cairo.ANTIALIAS_GOOD)

        # Make background transparent
        self.set_wind_col()
        # Don't layer drawing over each other, always replace
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        context.set_operator(cairo.OPERATOR_OVER)
        if not self.connected:
            return

        connection = self.discover.connection
        self_user = connection.user

        # Gather which users to draw
        self.users_to_draw = self.userlist[:]
        for user in self.userlist:
            # Bad object equality here, so we need to reassign
            if user["id"] == self_user["id"]:
                self_user = user

            # Remove users that arent speaking
            if self.only_speaking:
                speaking = "speaking" in user and user["speaking"]
                if not speaking:
                    self.users_to_draw.remove(user)

        if self.highlight_self:
            try:
                self.users_to_draw.remove(self_user)
            except ValueError:
                pass  # Not in list
            self.users_to_draw.insert(0, self_user)

        # Get size of window
        (w, h) = self.get_size()
        # Calculate height needed to show overlay
        height = (len(self.users_to_draw) * self.avatar_size) + \
            (len(self.users_to_draw) + 1) * self.icon_spacing

        # Choose where to start drawing
        rh = 0 + self.vert_edge_padding
        if self.align_vert == 1:
            # Ignore padding?
            rh = (h / 2) - (height / 2)
        elif self.align_vert == 2:
            rh = h - height - self.vert_edge_padding

        for user in self.users_to_draw:
            self.draw_avatar(context, user, rh)
            # Shift the relative position down to next location
            rh += self.avatar_size + self.icon_spacing

        # Don't hold a ref
        self.context = None

    def recv_avatar(self, id, pix):
        if(id == 'def'):
            self.def_avatar = pix
        else:
            self.avatars[id] = pix

    def delete_avatar(self, id):
        if id in self.avatars:
            del self.avatars[id]

    def draw_avatar(self, context, user, y):
        # Ensure pixbuf for avatar
        if user["id"] not in self.avatars and user["avatar"]:
            url = "https://cdn.discordapp.com/avatars/%s/%s.jpg" % (
                user['id'], user['avatar'])
            get_image(self.recv_avatar, url, user["id"],
                      self.avatar_size)

            # Set the key with no value to avoid spamming requests
            self.avatars[user["id"]] = None

        (w, h) = self.get_size()
        c = None
        mute = False
        deaf = False
        alpha = 1.0
        if "speaking" in user and user["speaking"]:
            c = self.talk_col
        if "mute" in user and user["mute"]:
            mute = True
        if "deaf" in user and user["deaf"]:
            deaf = True
            alpha = 0.5
        pix = None
        if user["id"] in self.avatars:
            pix = self.avatars[user["id"]]
        if self.align_right:
            self.draw_text(
                context, user["username"], w - self.avatar_size - self.horz_edge_padding, y)
            self.draw_avatar_pix(
                context, pix, w - self.avatar_size - self.horz_edge_padding, y, c, alpha)
            if deaf:
                self.draw_deaf(context, w - self.avatar_size -
                               self.horz_edge_padding, y, 1.0)
            elif mute:
                self.draw_mute(context, w - self.avatar_size -
                               self.horz_edge_padding, y, alpha)
        else:
            self.draw_text(
                context, user["username"], self.avatar_size + self.horz_edge_padding, y)
            self.draw_avatar_pix(
                context, pix, self.horz_edge_padding, y, c, alpha)
            if deaf:
                self.draw_deaf(context, self.horz_edge_padding, y, 1.0)
            elif mute:
                self.draw_mute(context, self.horz_edge_padding, y, alpha)

    def draw_text(self, context, string, x, y):
        if self.text_font:
            context.set_font_face(cairo.ToyFontFace(
                self.text_font, cairo.FontSlant.NORMAL, cairo.FontWeight.NORMAL))
        context.set_font_size(self.text_size)
        xb, yb, w, h, dx, dy = context.text_extents(string)
        ho = (self.avatar_size / 2) - (h / 2)
        if self.align_right:
            context.move_to(0, 0)
            self.set_norm_col()
            context.rectangle(x - w - (self.text_pad * 2), y + ho - self.text_pad,
                              w + (self.text_pad * 4), h + (self.text_pad * 2))
            context.fill()

            self.set_text_col()
            context.move_to(x - w - self.text_pad, y + ho + h)
            context.show_text(string)
        else:
            context.move_to(0, 0)
            self.set_norm_col()
            context.rectangle(x - (self.text_pad * 2), y + ho - self.text_pad,
                              w + (self.text_pad * 4), h + (self.text_pad * 2))
            context.fill()

            self.set_text_col()
            context.move_to(x + self.text_pad, y + ho + h)
            context.show_text(string)

    def draw_avatar_pix(self, context, pixbuf, x, y, c, alpha):
        if not pixbuf:
            pixbuf = self.def_avatar

        if not pixbuf:
            return
        context.move_to(x, y)
        context.save()
        #context.set_source_pixbuf(pixbuf, 0.0, 0.0)
        if self.round_avatar:
            context.arc(x + (self.avatar_size / 2), y +
                        (self.avatar_size / 2), self.avatar_size / 2, 0, 2 * math.pi)
            context.clip()

        self.set_wind_col()
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.rectangle(x, y, self.avatar_size, self.avatar_size)
        context.fill()
        context.set_operator(cairo.OPERATOR_OVER)
        Gdk.cairo_set_source_pixbuf(context, pixbuf, x, y)
        context.paint_with_alpha(alpha)
        context.restore()
        if c:
            if self.round_avatar:
                context.arc(x + (self.avatar_size / 2), y +
                            (self.avatar_size / 2), self.avatar_size / 2, 0, 2 * math.pi)
                self.col(c)
                context.stroke()
            else:
                context.rectangle(x, y, self.avatar_size, self.avatar_size)
                self.col(c)
                context.stroke()

    def draw_mute(self, context, x, y, a):
        context.save()
        context.translate(x, y)
        context.scale(self.avatar_size, self.avatar_size)
        self.set_mute_col(a)
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

    def draw_deaf(self, context, x, y, a):
        context.save()
        context.translate(x, y)
        context.scale(self.avatar_size, self.avatar_size)
        self.set_mute_col(a)
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
