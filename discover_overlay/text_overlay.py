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
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Pango, PangoCairo, GLib  # nopep8

log = logging.getLogger(__name__)


class TextOverlayWindow(OverlayWindow):
    """Overlay window for text"""

    def __init__(self, discover, piggyback=None):
        OverlayWindow.__init__(self, discover, piggyback)
        self.text_spacing = 4
        self.content = []
        self.text_font = None
        self.text_size = 13
        self.text_time = None
        self.show_attach = None
        self.popup_style = None
        self.line_limit = 100
        # 0, 0, self.text_size, self.text_size)
        self.pango_rect = Pango.Rectangle()
        self.pango_rect.width = self.text_size * Pango.SCALE
        self.pango_rect.height = self.text_size * Pango.SCALE

        self.connected = True
        self.bg_col = [0.0, 0.6, 0.0, 0.1]
        self.fg_col = [1.0, 1.0, 1.0, 1.0]
        self.attachment = {}

        self.image_list = []
        self.img_finder = re.compile(r"`")
        self.warned_filetypes = []
        self.set_title("Discover Text")
        self.redraw()

    def set_blank(self):
        self.content = []
        self.set_needs_redraw()

    def tick(self):
        if len(self.attachment) > self.line_limit:
            # We've probably got old images!
            oldlist = self.attachment
            self.attachment = {}
            log.info("Cleaning old images")
            for message in self.content:
                if 'attach' in message and message['attach']:
                    url = message['attach'][0]['url']
                    log.info("keeping %s", url)
                    self.attachment[url] = oldlist[url]

    def set_text_time(self, timer):
        """
        Set the duration that a message will be visible for.
        """
        if self.text_time != timer or self.timer_after_draw != timer:
            self.text_time = timer
            self.timer_after_draw = timer
            self.set_needs_redraw()

    def set_text_list(self, tlist, altered):
        """
        Update the list of text messages to show
        """
        self.content = tlist[-self.line_limit:]
        if altered:
            self.set_needs_redraw()

    def set_fg(self, fg_col):
        """
        Set default text colour
        """
        if self.fg_col != fg_col:
            self.fg_col = fg_col
            self.set_needs_redraw()

    def set_bg(self, bg_col):
        """
        Set background colour
        """
        if self.bg_col != bg_col:
            self.bg_col = bg_col
            self.set_needs_redraw()

    def set_show_attach(self, attachment):
        """
        Set if attachments should be shown inline
        """
        if self.attachment != attachment:
            self.show_attach = attachment
            self.set_needs_redraw()

    def set_popup_style(self, boolean):
        """
        Set if message disappear after a certain duration
        """
        if self.popup_style != boolean:
            self.popup_style = boolean

    def set_font(self, font):
        """
        Set font used to render text
        """
        if self.text_font != font:
            self.text_font = font

            self.pango_rect = Pango.Rectangle()
            font = Pango.FontDescription(self.text_font)
            self.pango_rect.width = font.get_size() * Pango.SCALE
            self.pango_rect.height = font.get_size() * Pango.SCALE
            self.set_needs_redraw()

    def set_line_limit(self, limit):
        """
        Change maximum number of lines in overlay
        """
        if self.line_limit != limit:
            self.line_limit = limit

    def make_line(self, message):
        """
        Decode a recursive JSON object into pango markup.
        """
        ret = ""
        if isinstance(message, list):
            for inner_message in message:
                ret = "%s%s" % (ret, self.make_line(inner_message))
        elif isinstance(message, str):
            ret = self.sanitize_string(message)
        elif message['type'] == 'strong':
            ret = "<b>%s</b>" % (self.make_line(message['content']))
        elif message['type'] == 'text':
            ret = self.sanitize_string(message['content'])
        elif message['type'] == 'link':
            ret = "<u>%s</u>" % (self.make_line(message['content']))
        elif message['type'] == 'emoji':
            if 'surrogate' in message:
                # ['src'] is SVG URL
                # ret = msg
                ret = message['surrogate']
            else:
                ### Add Image ###
                self.image_list.append(
                    f"https://cdn.discordapp.com/emojis/{message['emojiId']}.png?v=1"
                )
                ret = "`"
        elif (message['type'] == 'inlineCode' or
              message['type'] == 'codeBlock' or
              message['type'] == 'blockQuote'):
            ret = "<span font_family=\"monospace\" background=\"#0004\">%s</span>" % (
                self.make_line(message['content']))
        elif message['type'] == 'u':
            ret = "<u>%s</u>" % (self.make_line(message['content']))
        elif message['type'] == 'em':
            ret = "<i>%s</i>" % (self.make_line(message['content']))
        elif message['type'] == 's':
            ret = "<s>%s</s>" % (self.make_line(message['content']))
        elif message['type'] == 'channel':
            ret = self.make_line(message['content'])
        elif message['type'] == 'mention':
            ret = self.make_line(message['content'])
        elif message['type'] == 'br':
            ret = '\n'
        else:
            if message["type"] not in self.warned_filetypes:
                log.error("Unknown text type : %s", message["type"])
                self.warned_filetypes.append(message['type'])
        return ret

    def recv_attach(self, identifier, pix, mask):
        """
        Called when an image has been downloaded by image_getter
        """
        self.attachment[identifier] = pix
        self.set_needs_redraw()

    def has_content(self):
        if self.piggyback and self.piggyback.has_content():
            return True
        if not self.enabled:
            return False
        if self.hidden:
            return False
        return self.content

    def overlay_draw(self, w, context, data=None):
        """
        Draw the overlay
        """
        if self.piggyback:
            self.piggyback.overlay_draw(w, context, data)
        if not self.enabled:
            return
        self.context = context
        (width, height) = self.get_size()
        if not self.piggyback_parent:
            context.set_antialias(cairo.ANTIALIAS_GOOD)
            context.set_source_rgba(0.0, 0.0, 0.0, 0.0)
            context.set_operator(cairo.OPERATOR_SOURCE)
            context.paint()
        self.tick()
        context.save()
        if self.is_wayland or self.piggyback_parent or self.discover.steamos:
            # Special case!
            # The window is full-screen regardless of what the user has selected.
            # We need to set a clip and a transform to imitate original behaviour
            # Used in wlroots & gamescope
            (floating_x, floating_y, floating_width,
             floating_height) = self.get_floating_coords()
            if self.floating:
                context.new_path()
                context.translate(floating_x, floating_y)
                context.rectangle(0, 0, floating_width, floating_height)
                context.clip()
            pass
        (floating_x, floating_y, floating_width,
         floating_height) = self.get_floating_coords()
        current_y = floating_height
        tnow = time.time()
        for line in reversed(self.content):
            if self.popup_style and tnow - line['time'] > self.text_time:
                break
            out_line = ""
            self.image_list = []

            col = "#fff"
            if 'nick_col' in line and line['nick_col']:
                col = line['nick_col']
            for in_line in line['content']:
                out_line = "%s%s" % (out_line, self.make_line(in_line))
            if line['attach'] and self.show_attach:
                attachment = line['attach'][0]
                url = attachment['url']
                extension = attachment['filename']
                extension = extension.rsplit(".", 1)[1]
                extension = extension.lower()
                if extension in ['jpeg', 'jpg', 'png', 'gif']:
                    if url in self.attachment:
                        current_y = self.draw_attach(current_y, url)
                    else:
                        get_surface(self.recv_attach,
                                    url,
                                    url, None)
                        self.attachment[url] = None  # Avoid asking repeatedly
                else:
                    log.warning("Unknown file extension '%s'", extension)
                # cy = self.draw_text(cy, "%s" % (line['attach']))
            message = "<span foreground='%s'>%s</span>: %s" % (self.sanitize_string(col),
                                                               self.sanitize_string(
                                                                   line["nick"]),
                                                               out_line)
            current_y = self.draw_text(current_y, message)
            if current_y <= 0:
                # We've done enough
                break
        context.restore()
        self.context = None

    def draw_attach(self, pos_y, url):
        """
        Draw an attachment
        """
        (floating_x, floating_y, floating_width,
         floating_height) = self.get_floating_coords()
        if url in self.attachment and self.attachment[url]:
            pix = self.attachment[url]
            image_width = min(pix.get_width(), floating_width)
            image_height = min(pix.get_height(), (floating_height * .7))
            (_ax, _ay, _aw, aspect_height) = get_aspected_size(
                pix, image_width, image_height)
            self.col(self.bg_col)
            self.context.rectangle(0, pos_y - aspect_height,
                                   floating_width, aspect_height)

            self.context.fill()
            self.context.set_operator(cairo.OPERATOR_OVER)
            _new_w, new_h = draw_img_to_rect(
                pix, self.context, 0, pos_y - image_height, image_width, image_height, aspect=True)
            return pos_y - new_h
        return pos_y

    def draw_text(self, pos_y, text):
        """
        Draw a text message, returning the Y position of the next message
        """
        layout = self.create_pango_layout(text)
        layout.set_auto_dir(True)
        layout.set_markup(text, -1)
        attr = layout.get_attributes()

        (floating_x, floating_y, floating_width,
         floating_height) = self.get_floating_coords()
        layout.set_width(Pango.SCALE * floating_width)
        layout.set_spacing(Pango.SCALE * 3)
        if self.text_font:
            font = Pango.FontDescription(self.text_font)
            layout.set_font_description(font)
        _tw, text_height = layout.get_pixel_size()
        self.col(self.bg_col)
        self.context.rectangle(0, pos_y - text_height,
                               floating_width, text_height)
        self.context.fill()
        self.context.set_operator(cairo.OPERATOR_OVER)
        self.col(self.fg_col)

        self.context.move_to(0, pos_y - text_height)
        PangoCairo.context_set_shape_renderer(
            self.get_pango_context(), self.render_custom, None)

        text = layout.get_text()
        count = 0

        for loc in self.img_finder.finditer(text):
            idx = loc.start()

            if len(self.image_list) <= count:
                break  # We fucked up. Who types ` anyway
            # url = self.imgList[count]

            attachment = Pango.attr_shape_new_with_data(
                self.pango_rect, self.pango_rect, count, None)
            attachment.start_index = idx
            attachment.end_index = idx + 1
            attr.insert(attachment)
            count += 1
        layout.set_attributes(attr)

        PangoCairo.show_layout(self.context, layout)
        return pos_y - text_height

    def render_custom(self, ctx, shape, path, _data):
        """
        Draw an inline image as a custom emoticon
        """
        if shape.data >= len(self.image_list):
            log.warning(f"{shape.data} >= {len(self.image_list)}")
            return
        # key is the url to the image
        key = self.image_list[shape.data]
        if key not in self.attachment:
            get_surface(self.recv_attach,
                        key,
                        key, None)
            return
        pix = self.attachment[key]
        (pos_x, pos_y) = ctx.get_current_point()
        draw_img_to_rect(pix, ctx, pos_x, pos_y - self.text_size, self.text_size,
                         self.text_size, path=path)
        return True

    def sanitize_string(self, string):
        """
        Sanitize a text message so that it doesn't intefere with Pango's XML format
        """
        string = string.replace("&", "&amp;")
        string = string.replace("<", "&lt;")
        string = string .replace(">", "&gt;")
        string = string.replace("'", "&#39;")
        string = string.replace("\"", "&#34;")
        return string
