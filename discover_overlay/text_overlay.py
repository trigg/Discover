import gi
gi.require_version("Gtk", "3.0")
gi.require_version('PangoCairo', '1.0')
gi.require_version('GdkPixbuf', '2.0')
import math
from .overlay import OverlayWindow
from gi.repository.GdkPixbuf import Pixbuf
from gi.repository import Gtk, GLib, Gio, GdkPixbuf, Gdk, Pango, PangoCairo
import cairo
import logging
import time


class TextOverlayWindow(OverlayWindow):
    def __init__(self):
        OverlayWindow.__init__(self)
        self.text_spacing = 4
        self.content = []
        self.text_font = None
        self.text_size = 13
        self.connected = True
        self.bg_col = [0.0, 0.6, 0.0, 0.1]
        self.fg_col = [1.0, 1.0, 1.0, 1.0]

    def set_text_list(self, tlist, alt):
        self.content = tlist
        if alt:
            self.redraw()

    def set_enabled(self, en):
        if en:
            self.show_all()
        else:
            self.hide()

    def set_fg(self, fg_col):
        self.fg_col = fg_col
        self.redraw()

    def set_bg(self, bg_col):
        self.bg_col = bg_col
        self.redraw()

    def set_popup_style(self, b):
        self.popup_style = b

    def do_draw(self, context):
        self.context = context
        context.set_antialias(self.compositing)
        (w, h) = self.get_size()

        # Make background transparent
        context.set_source_rgba(0.0, 0.0, 0.0, 0.0)
        context.paint()
        if not self.connected:
            return

        long_string = ""
        sep = ""
        tnow = time.time()
        for line in self.content:
            if not self.popup_style or tnow - line['time'] < 30:
                col = "#fff"
                if 'nick_col' in line and line['nick_col']:
                    col = line['nick_col']
                long_string = "%s%s<span foreground='%s'>%s</span>: %s" % (
                    long_string,
                    sep,
                    self.santize_string(col),
                    self.santize_string(line["nick"]),
                    self.santize_string(line["content"]))
                sep = '\n'
        if len(long_string) == 0:
            return
        layout = self.create_pango_layout(long_string)
        layout.set_markup(long_string, -1)
        attr = Pango.AttrList()

        layout.set_width(Pango.SCALE * w)
        layout.set_spacing(Pango.SCALE * 3)
        if(self.text_font):
            font = Pango.FontDescription(
                "%s %s" % (self.text_font, self.text_size))
            layout.set_font_description(font)
        tw, th = layout.get_pixel_size()

        # Don't layer drawing over each other, always replace
        self.col(self.bg_col)
        context.rectangle(0, -th + h, w, th)
        context.fill()
        context.set_operator(cairo.OPERATOR_OVER)
        self.col(self.fg_col)

        context.move_to(0, -th + h)
        PangoCairo.show_layout(context, layout)

    def santize_string(self, string):
        # I hate that Pango has nothing for this.
        return string.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&#39;").replace("\"", "&#34;")
