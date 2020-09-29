import gi
gi.require_version("Gtk", "3.0")
gi.require_version('PangoCairo', '1.0')
gi.require_version('GdkPixbuf', '2.0')
import math
from .overlay import OverlayWindow
from gi.repository.GdkPixbuf import Pixbuf
from gi.repository import Gtk, GLib, Gio, GdkPixbuf, Gdk, Pango, PangoCairo
import cairo
import urllib


class VoiceOverlayWindow(OverlayWindow):
    def __init__(self):
        OverlayWindow.__init__(self)

        self.avatars = {}

        self.avatar_size = 48
        self.text_pad = 6
        self.text_font = None
        self.text_size = 13
        self.icon_spacing = 8
        self.edge_padding = 0

        self.round_avatar = True
        self.talk_col = [0.0, 0.6, 0.0, 0.1]
        self.text_col = [1.0, 1.0, 1.0, 1.0]
        self.norm_col = [0.0, 0.0, 0.0, 0.5]
        self.wind_col = [0.0, 0.0, 0.0, 0.0]
        self.mute_col = [0.7, 0.0, 0.0, 1.0]
        self.userlist = []
        self.connected = False
        self.force_location()
        self.def_avatar = self.get_img(
            "https://cdn.discordapp.com/embed/avatars/3.png")

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

    def set_edge_padding(self, i):
        self.edge_padding = i
        self.redraw()

    def set_square_avatar(self, i):
        self.round_avatar = not i
        self.redraw()

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
        self.def_avatar = self.get_img(
            "https://cdn.discordapp.com/embed/avatars/3.png")

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

        # Get size of window
        (w, h) = self.get_size()
        # Calculate height needed to show overlay
        height = (len(self.userlist) * self.avatar_size) + \
            (len(self.userlist) + 1) * self.icon_spacing

        # Choose where to start drawing
        rh = 0 + self.edge_padding
        if self.align_vert == 1:
            # Ignore padding?
            rh = (h / 2) - (height / 2)
        elif self.align_vert == 2:
            rh = h - height - self.edge_padding
        # Iterate users in room.
        for user in self.userlist:
            self.draw_avatar(context, user, rh)
            # Shift the relative position down to next location
            rh += self.avatar_size + self.icon_spacing

        # Don't hold a ref
        self.context = None

    def get_img(self, url):
        req = urllib.request.Request(url)
        req.add_header(
            'Referer', 'https://streamkit.discord.com/overlay/voice')
        req.add_header('User-Agent', 'Mozilla/5.0')
        try:
            response = urllib.request.urlopen(req)
            input_stream = Gio.MemoryInputStream.new_from_data(
                response.read(), None)
            pixbuf = Pixbuf.new_from_stream(input_stream, None)
            pixbuf = pixbuf.scale_simple(self.avatar_size, self.avatar_size,
                                         GdkPixbuf.InterpType.BILINEAR)
            return pixbuf
        except:
            print("Could not access : %s" % (url))
        return none

    def draw_avatar(self, context, user, y):
        # Ensure pixbuf for avatar
        if user["id"] not in self.avatars and user["avatar"]:
            url = "https://cdn.discordapp.com/avatars/%s/%s.jpg" % (
                user["id"], user["avatar"])
            p = self.get_img(url)
            if p:
                self.avatars[user["id"]] = p

        (w, h) = self.get_size()
        c = None
        mute = False
        alpha = 1.0
        if "speaking" in user and user["speaking"]:
            c = self.talk_col
        if "mute" in user and user["mute"]:
            mute = True
        if "deaf" in user and user["deaf"]:
            alpha = 0.5
        pix = None
        if user["id"] in self.avatars:
            pix = self.avatars[user["id"]]
        if self.align_right:
            self.draw_text(context, user["username"], w - self.avatar_size, y)
            self.draw_avatar_pix(
                context, pix, w - self.avatar_size, y, c, alpha)
            if mute:
                self.draw_mute(context, w - self.avatar_size, y, alpha)
        else:
            self.draw_text(context, user["username"], self.avatar_size, y)
            self.draw_avatar_pix(context, pix, 0, y, c, alpha)
            if mute:
                self.draw_mute(context, 0, y, alpha)

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
        context.move_to(x, y)
        context.save()
        #context.set_source_pixbuf(pixbuf, 0.0, 0.0)
        if self.round_avatar:
            context.arc(x + (self.avatar_size / 2), y +
                        (self.avatar_size / 2), self.avatar_size / 2, 0, 2 * math.pi)
            context.clip()
        if not pixbuf:
            pixbuf = self.def_avatar
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
