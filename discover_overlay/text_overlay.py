import gi
gi.require_version("Gtk", "3.0")
gi.require_version('PangoCairo', '1.0')
import math
from .overlay import OverlayWindow
from gi.repository import Gtk, Gdk, Pango, PangoCairo
import cairo
import logging
import time
import re
from .image_getter import get_surface


class TextOverlayWindow(OverlayWindow):
    def __init__(self, discover):
        OverlayWindow.__init__(self)
        self.discover = discover
        self.text_spacing = 4
        self.content = []
        self.text_font = None
        self.text_size = 13
        # 0, 0, self.text_size, self.text_size)
        self.pango_rect = Pango.Rectangle()
        self.pango_rect.width = self.text_size * Pango.SCALE
        self.pango_rect.height = self.text_size * Pango.SCALE

        self.connected = True
        self.bg_col = [0.0, 0.6, 0.0, 0.1]
        self.fg_col = [1.0, 1.0, 1.0, 1.0]
        self.attachment = {}

        self.imgList = []
        self.imgFinder = re.compile(r"`")

    def set_text_time(self, t):
        self.text_time = t

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

    def set_show_attach(self, att):
        self.show_attach = att
        self.redraw()

    def set_popup_style(self, b):
        self.popup_style = b

    def set_font(self, name, size):
        self.text_font = name
        self.text_size = size
        self.pango_rect = Pango.Rectangle()
        self.pango_rect.width = self.text_size * Pango.SCALE
        self.pango_rect.height = self.text_size * Pango.SCALE
        self.redraw()

    def make_line(self, msg):
        ret = ""
        if isinstance(msg, list):
            for a in msg:
                ret = "%s%s" % (ret, self.make_line(a))
        elif isinstance(msg, str):
            ret = msg
        elif msg['type'] == 'strong':
            ret = "<b>%s</b>" % (self.make_line(msg['content']))
        elif msg['type'] == 'text':
            ret = self.santize_string(msg['content'])
        elif msg['type'] == 'link':
            ret = "<u>%s</u>" % (self.make_line(msg['content']))
        elif msg['type'] == 'emoji':
            if 'surrogate' in msg:
                # ['src'] is SVG URL
                #ret = msg
                ret = msg['surrogate']
            else:
                ### Add Image ###
                url = ("https://cdn.discordapp.com/emojis/%s.png?v=1" %
                       (msg['emojiId']))
                img = {"url": url}
                self.imgList.append(img)
                ret = "`"
        elif msg['type'] == 'inlineCode' or msg['type'] == 'codeBlock' or msg['type'] == 'blockQuote':
            ret = "<span font_family=\"monospace\" background=\"#0004\">%s</span>" % (
                msg['content'])
        elif msg['type'] == 'u':
            ret = "<u>%s</u>" % (self.make_line(msg['content']))
        elif msg['type'] == 'em':
            ret = "<i>%s</i>" % (self.make_line(msg['content']))
        elif msg['type'] == 's':
            ret = "<s>%s</s>" % (self.make_line(msg['content']))
        elif msg['type'] == 'channel':
            ret = self.make_line(msg['content'])
        elif msg['type'] == 'mention':
            ret = self.make_line(msg['content'])
        elif msg['type'] == 'br':
            ret = '\n'
        else:
            logging.warning("Unknown text type : %s" % (msg["type"]))
        return ret

    def recv_attach(self, id, pix):
        self.attachment[id] = pix
        self.redraw()

    def do_draw(self, context):
        self.context = context
        context.set_antialias(cairo.ANTIALIAS_GOOD)
        (w, h) = self.get_size()

        # Make background transparent
        context.set_source_rgba(0.0, 0.0, 0.0, 0.0)
        context.paint()

        cy = h
        tnow = time.time()
        for line in reversed(self.content):
            if self.popup_style and tnow - line['time'] > self.text_time:
                break
            out_line = ""
            self.imgList = []

            col = "#fff"
            if 'nick_col' in line and line['nick_col']:
                col = line['nick_col']
            for in_line in line['content']:
                out_line = "%s%s" % (out_line, self.make_line(in_line))
            if line['attach'] and self.show_attach:
                at = line['attach'][0]
                url = at['url']
                if url in self.attachment:
                    cy = self.draw_attach(cy, url)
                else:
                    get_surface(self.recv_attach,
                                url,
                                url, None)
                # cy = self.draw_text(cy, "%s" % (line['attach']))
            cy = self.draw_text(cy, "<span foreground='%s'>%s</span>: %s" % (self.santize_string(col),
                                                                             self.santize_string(line["nick"]), out_line))
            if cy <= 0:
                # We've done enough
                break

    def draw_attach(self, y, url):
        (w, h) = self.get_size()
        if self.attachment[url]:
            pix = self.attachment[url]
            h = pix.get_height()
            self.col(self.bg_col)
            self.context.rectangle(0, y - h, w, h)
            self.context.fill()
            self.context.set_operator(cairo.OPERATOR_OVER)
            self.col([1, 1, 1, 1])
            self.context.set_source_surface(pix, 0, y - h)
            self.context.rectangle(0, y - h, w, h)
            self.context.fill()
            return y - h
        return y

    def draw_text(self, y, text):
        (w, h) = self.get_size()

        layout = self.create_pango_layout(text)
        layout.set_markup(text, -1)
        attr = layout.get_attributes()

        layout.set_width(Pango.SCALE * w)
        layout.set_spacing(Pango.SCALE * 3)
        if(self.text_font):
            font = Pango.FontDescription(
                "%s %s" % (self.text_font, self.text_size))
            layout.set_font_description(font)
        tw, th = layout.get_pixel_size()
        self.col(self.bg_col)
        self.context.rectangle(0, y - th, w, th)
        self.context.fill()
        self.context.set_operator(cairo.OPERATOR_OVER)
        self.col(self.fg_col)

        self.context.move_to(0, y - th)
        PangoCairo.context_set_shape_renderer(
            self.get_pango_context(), self.render_custom, None)

        text = layout.get_text()
        count = 0

        for loc in self.imgFinder.finditer(text):
            idx = loc.start()

            if len(self.imgList) <= count:
                break  # We fucked up. Who types ` anyway
            url = self.imgList[count]

            at = Pango.attr_shape_new_with_data(
                self.pango_rect, self.pango_rect, count, None)
            at.start_index = idx
            at.end_index = idx + 1
            attr.insert(at)
            count += 1
        layout.set_attributes(attr)

        PangoCairo.show_layout(self.context, layout)
        return y - th

    def render_custom(self, ctx, shape, path, data):
        key = self.imgList[shape.data]['url']
        if key not in self.attachment:
            get_surface(self.recv_attach,
                        key,
                        key, None)
            return
        pix = self.attachment[key]
        (x, y) = ctx.get_current_point()
        px = pix.get_width()
        py = pix.get_height()
        ctx.save()
        ctx.translate(x, y - self.text_size)
        ctx.scale(self.text_size, self.text_size)
        ctx.scale(1 / px, 1 / py)
        ctx.set_source_surface(pix, 0, 0)

        ctx.rectangle(0, 0, px, py)
        if not path:
            ctx.fill()
        ctx.restore()

        ctx.move_to(x + self.text_size, y)

        return True

    def santize_string(self, string):
        # I hate that Pango has nothing for this.
        return string.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&#39;").replace("\"", "&#34;")
