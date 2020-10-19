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
"""Overlay window for text"""
import logging
import time
import re
import cairo
import gi
from .image_getter import get_surface, draw_img_to_rect, get_aspected_size
from .overlay import OverlayWindow
gi.require_version("Gtk", "3.0")
gi.require_version('PangoCairo', '1.0')
# pylint: disable=wrong-import-position
from gi.repository import Pango, PangoCairo


class TextOverlayWindow(OverlayWindow):
    """Overlay window for voice"""

    def __init__(self, discover):
        OverlayWindow.__init__(self)
        self.discover = discover
        self.text_spacing = 4
        self.content = []
        self.text_font = None
        self.text_size = 13
        self.text_time = None
        self.show_attach = None
        self.popup_style = None
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
        self.set_title("Discover Text")

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
                self.make_line(msg['content']))
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
            logging.error("Unknown text type : %s", msg["type"])
        return ret

    def recv_attach(self, identifier, pix):
        self.attachment[identifier] = pix
        self.redraw()

    def overlay_draw(self, _w, context, data=None):
        self.context = context
        context.set_antialias(cairo.ANTIALIAS_GOOD)
        (w, h) = self.get_size()
        # Make background transparent
        context.set_source_rgba(0.0, 0.0, 0.0, 0.0)
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        context.save()
        if self.is_wayland:
            # Special case!
            # The window is full-screen regardless of what the user has selected. Because Wayland
            # We need to set a clip and a transform to imitate original behaviour

            w = self.w
            h = self.h
            context.translate(self.x, self.y)
            context.rectangle(0, 0, w, h)
            context.clip()

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
        if self.is_wayland:
            context.restore()

    def draw_attach(self, y, url):
        if url in self.attachment and self.attachment[url]:
            pix = self.attachment[url]
            iw = pix.get_width()
            ih = pix.get_height()
            iw = min(iw, self.w)
            ih = min(ih, (self.h * .7))
            (_ax, _ay, _aw, ah) = get_aspected_size(pix, iw, ih)
            self.col(self.bg_col)
            self.context.rectangle(0, y - ah, self.w, ah)

            self.context.fill()
            self.context.set_operator(cairo.OPERATOR_OVER)
            _new_w, new_h = draw_img_to_rect(
                pix, self.context, 0, y - ih, iw, ih, aspect=True)
            return y - new_h
        return y

    def draw_text(self, y, text):

        layout = self.create_pango_layout(text)
        layout.set_markup(text, -1)
        attr = layout.get_attributes()

        layout.set_width(Pango.SCALE * self.w)
        layout.set_spacing(Pango.SCALE * 3)
        if(self.text_font):
            font = Pango.FontDescription(
                "%s %s" % (self.text_font, self.text_size))
            layout.set_font_description(font)
        _tw, th = layout.get_pixel_size()
        self.col(self.bg_col)
        self.context.rectangle(0, y - th, self.w, th)
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
            #url = self.imgList[count]

            at = Pango.attr_shape_new_with_data(
                self.pango_rect, self.pango_rect, count, None)
            at.start_index = idx
            at.end_index = idx + 1
            attr.insert(at)
            count += 1
        layout.set_attributes(attr)

        PangoCairo.show_layout(self.context, layout)
        return y - th

    def render_custom(self, ctx, shape, path, _data):
        key = self.imgList[shape.data]['url']
        if key not in self.attachment:
            get_surface(self.recv_attach,
                        key,
                        key, None)
            return
        pix = self.attachment[key]
        (x, y) = ctx.get_current_point()
        draw_img_to_rect(pix, ctx, x, y - self.text_size, self.text_size,
                         self.text_size, path=path)
        return True

    def santize_string(self, string):
        # I hate that Pango has nothing for this.
        return string.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&#39;").replace("\"", "&#34;")
