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
"""Notification window for text"""
import logging
import time
import re
import cairo
import math
import gi
from .image_getter import get_surface, draw_img_to_rect, get_aspected_size
from .overlay import OverlayWindow
gi.require_version("Gtk", "3.0")
gi.require_version('PangoCairo', '1.0')
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Gtk, Pango, PangoCairo  # nopep8

log = logging.getLogger(__name__)


class NotificationOverlayWindow(OverlayWindow):
    """Overlay window for notifications"""

    def __init__(self, discover, piggyback=None):
        OverlayWindow.__init__(self, discover, piggyback)
        self.text_spacing = 4
        self.content = []
        self.test_content = [{"icon": "https://cdn.discordapp.com/icons/951077080769114172/991abffc0d2a5c040444be4d1a4085f4.webp?size=96", "title": "Title1"},
                             {"title": "Title2", "body": "Body", "icon": None},
                             {"icon": "https://cdn.discordapp.com/icons/951077080769114172/991abffc0d2a5c040444be4d1a4085f4.webp?size=96", "title": "Title 3",
                                 "body": "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."},
                             {"icon": None, "title": "Title 3", "body": "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."},
                             {"icon": "https://cdn.discordapp.com/avatars/147077941317206016/6a6935192076489fa6dc1eb5dafbf6e7.webp?size=128", "title": "PM", "body": "Birdy test"}]
        self.text_font = None
        self.text_size = 13
        self.text_time = None
        self.show_icon = None
        self.pango_rect = Pango.Rectangle()
        self.pango_rect.width = self.text_size * Pango.SCALE
        self.pango_rect.height = self.text_size * Pango.SCALE

        self.connected = True
        self.bg_col = [0.0, 0.6, 0.0, 0.1]
        self.fg_col = [1.0, 1.0, 1.0, 1.0]
        self.icons = []
        self.reverse_order = False
        self.padding = 10
        self.border_radius = 5
        self.limit_width = 100
        self.testing = False
        self.icon_size = 64
        self.icon_pad = 16
        self.icon_left = True

        self.image_list = {}
        self.warned_filetypes = []
        self.set_title("Discover Notifications")
        self.redraw()

    def set_blank(self):
        self.content = []
        self.set_needs_redraw()

    def tick(self):
        # This doesn't really belong in overlay or settings
        now = time.time()
        newlist = []
        oldsize = len(self.content)
        # Iterate over and remove messages older than 30s
        for message in self.content:
            if message['time'] + self.text_time > now:
                newlist.append(message)
        self.content = newlist
        # If the list is different than before
        if oldsize != len(newlist):
            self.set_needs_redraw()

    def add_notification_message(self, data):
        noti = None
        data = data['data']
        message_id = data['message']['id']
        for message in self.content:
            if message['id'] == message_id:
                return
        if 'body' in data and 'title' in data:
            if 'icon_url' in data:
                noti = {"icon": data['icon_url'],
                        "title": data['title'],
                        "body": data['body'], "time": time.time(),
                        "id": message_id}
            else:
                noti = {"title": data['title'],
                        "body": data['body'], "time": time.time(),
                        "id": message_id}

        if noti:
            self.content.append(noti)
            self.set_needs_redraw()
            self.get_all_images()

    def set_padding(self, padding):
        """
        Set the padding between notifications
        """
        if self.padding != padding:
            self.padding = padding
            self.set_needs_redraw()

    def set_border_radius(self, radius):
        """
        Set the radius of the border
        """
        if self.border_radius != radius:
            self.border_radius = radius
            self.set_needs_redraw()

    def set_icon_size(self, size):
        """
        Set Icon size
        """
        if self.icon_size != size:
            self.icon_size = size
            self.image_list = {}
            self.get_all_images()

    def set_icon_pad(self, pad):
        """
        Set padding between icon and message
        """
        if self.icon_pad != pad:
            self.icon_pad = pad
            self.set_needs_redraw()

    def set_icon_left(self, left):
        if self.icon_left != left:
            self.icon_left = left
            self.set_needs_redraw()

    def set_text_time(self, timer):
        """
        Set the duration that a message will be visible for.
        """
        self.text_time = timer
        self.timer_after_draw = timer

    def set_limit_width(self, limit):
        """
        Set the word wrap limit in pixels
        """
        if self.limit_width != limit:
            self.limit_width = limit
            self.set_needs_redraw()

    def get_all_images(self):
        the_list = self.content
        if self.testing:
            the_list = self.test_content
        for line in the_list:
            icon = line["icon"]

            if icon and icon not in self.image_list:
                get_surface(self.recv_icon, icon, icon,
                            self.icon_size)

    def recv_icon(self, identifier, pix, mask):
        """
        Called when image_getter has downloaded an image
        """
        self.image_list[identifier] = pix
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

    def set_show_icon(self, icon):
        """
        Set if icons should be shown inline
        """
        if self.show_icon != icon:
            self.show_icon = icon
            self.set_needs_redraw()
            self.get_all_images()

    def set_reverse_order(self, rev):
        if self.reverse_order != rev:
            self.reverse_order = rev
            self.set_needs_redraw()

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

    def recv_attach(self, identifier, pix):
        """
        Called when an image has been downloaded by image_getter
        """
        self.icons[identifier] = pix
        self.set_needs_redraw()

    def calc_all_height(self):
        h = 0
        my_list = self.content
        if self.testing:
            my_list = self.test_content
        for line in my_list:
            h += self.calc_height(line)
        if h > 0:
            h -= self.padding  # Remove one unneeded padding
        return h

    def calc_height(self, line):
        icon_width = 0
        icon_pad = 0
        icon = line['icon']
        if self.show_icon and icon and icon in self.image_list and self.image_list[icon]:
            icon_width = self.icon_size
            icon_pad = self.icon_pad
        message = ""
        if 'body' in line and len(line['body']) > 0:
            m_no_body = "<span>%s</span>\n%s"
            message = m_no_body % (self.sanitize_string(line["title"]),
                                   self.sanitize_string(line['body']))
        else:
            m_with_body = "<span>%s</span>"
            message = m_with_body % (self.sanitize_string(line["title"]))
        layout = self.create_pango_layout(message)
        layout.set_auto_dir(True)
        layout.set_markup(message, -1)
        attr = layout.get_attributes()
        (floating_x, floating_y, floating_width,
         floating_height) = self.get_floating_coords()
        width = self.limit_width if floating_width > self.limit_width else floating_width
        layout.set_width((Pango.SCALE * (width -
                         (self.border_radius * 4 + icon_width + icon_pad))))
        layout.set_spacing(Pango.SCALE * 3)
        if self.text_font:
            font = Pango.FontDescription(self.text_font)
            layout.set_font_description(font)
        text_width, text_height = layout.get_pixel_size()
        if text_height < icon_width:
            text_height = icon_width
        return text_height + (self.border_radius*4) + self.padding

    def has_content(self):
        if not self.enabled:
            return False
        if self.hidden:
            return False
        if self.testing:
            return self.test_content
        return self.content

    def overlay_draw(self, _w, context, data=None):
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

            # Make background transparent
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

        current_y = height
        if self.align_vert == 0:
            current_y = 0
        if self.align_vert == 1:  # Center. Oh god why
            current_y = (height/2.0) - (self.calc_all_height() / 2.0)
        tnow = time.time()
        if self.testing:
            the_list = self.test_content
        else:
            the_list = self.content
        if self.reverse_order:
            the_list = reversed(the_list)
        for line in the_list:
            col = "#fff"
            if 'body' in line and len(line['body']) > 0:
                m_no_body = "<span foreground='%s'>%s</span>\n%s"
                message = m_no_body % (self.sanitize_string(col),
                                       self.sanitize_string(line["title"]),
                                       self.sanitize_string(line['body']))
            else:
                m_with_body = "<span foreground='%s'>%s</span>"
                message = m_with_body % (self.sanitize_string(col),
                                         self.sanitize_string(line["title"]))

            icon = None
            # If we've got an embedded image
            if "icon_surface" in line and line["icon_surface"]:
                icon = line["icon_surface"]
            # If we're given an icon name, it's in the list of icons, and it's not none
            elif line["icon"] and line["icon"] in self.image_list and self.image_list[line["icon"]]:
                icon = self.image_list[line["icon"]]

            current_y = self.draw_text(current_y, message, icon)
            if current_y <= 0:
                # We've done enough
                break
        context.restore()
        self.context = None

    def draw_text(self, pos_y, text, icon):
        """
        Draw a text message, returning the Y position of the next message
        """

        icon_width = self.icon_size
        icon_pad = self.icon_pad
        if not self.show_icon:
            icon = None
        if not icon:
            icon_pad = 0
            icon_width = 0

        layout = self.create_pango_layout(text)
        layout.set_auto_dir(True)
        layout.set_markup(text, -1)
        attr = layout.get_attributes()

        (floating_x, floating_y, floating_width,
         floating_height) = self.get_floating_coords()
        width = self.limit_width if floating_width > self.limit_width else floating_width
        layout.set_width((Pango.SCALE * (width -
                         (self.border_radius * 4 + icon_width + icon_pad))))
        layout.set_spacing(Pango.SCALE * 3)
        if self.text_font:
            font = Pango.FontDescription(self.text_font)
            layout.set_font_description(font)
        text_width, text_height = layout.get_pixel_size()
        self.col(self.bg_col)
        top = 0
        if self.align_vert == 2:  # Bottom align
            top = pos_y - (text_height + self.border_radius * 4)
        else:  # Top align
            top = pos_y
        if text_height < icon_width:
            text_height = icon_width
        shape_height = text_height + self.border_radius * 4
        shape_width = text_width + self.border_radius*4 + icon_width + icon_pad

        left = 0
        if self.align_right:
            left = floating_width - shape_width

        self.context.save()
        # Draw Background
        self.context.translate(left, top)
        # self.context.rectangle(self.border_radius, 0,
        #                       shape_width - (self.border_radius*2), shape_height)
        # self.context.fill()
        # self.context.rectangle(0, self.border_radius,
        #                       shape_width, shape_height - (self.border_radius * 2))

        # self.context.arc(0.7, 0.3, 0.035, 1.25 * math.pi, 2.25 * math.pi)
        # self.context.arc(0.3, 0.7, 0.035, .25 * math.pi, 1.25 * math.pi)
        if self.border_radius == 0:

            self.context.move_to(0.0, 0.0)
            self.context.line_to(shape_width, 0.0)
            self.context.line_to(shape_width, shape_height)
            self.context.line_to(0.0, shape_height)
            self.context.close_path()
            self.context.fill()
        else:
            # Edge top
            self.context.move_to(self.border_radius, 0.0)
            self.context.line_to(shape_width - self.border_radius, 0.0)

            # Arc topright
            self.context.arc(shape_width - self.border_radius, self.border_radius,
                             self.border_radius, 1.5 * math.pi, 2 * math.pi)

            # Edge right
            self.context.line_to(
                shape_width, shape_height - self.border_radius)

            # Arc bottomright
            self.context.arc(shape_width - self.border_radius, shape_height - self.border_radius,
                             self.border_radius, 0.0, 0.5 * math.pi)

            # Edge bottom
            self.context.line_to(self.border_radius, shape_height)

            # Arch bottomleft
            self.context.arc(self.border_radius, shape_height -
                             self.border_radius, self.border_radius, 0.5 * math.pi, math.pi)

            # Edge left
            self.context.line_to(0.0, self.border_radius)

            # Arc topleft
            self.context.arc(self.border_radius, self.border_radius,
                             self.border_radius, math.pi, 1.5 * math.pi)

            # End
            self.context.close_path()
            self.context.fill()

        self.context.set_operator(cairo.OPERATOR_OVER)
        # Draw Image
        if icon:
            self.context.save()
            if self.icon_left:
                self.context.translate(
                    self.border_radius*2, self.border_radius*2)
                draw_img_to_rect(icon, self.context, 0, 0,
                                 icon_width, icon_width)
            else:
                self.context.translate(
                    self.border_radius*2 + text_width + icon_pad, self.border_radius*2)
                draw_img_to_rect(icon, self.context, 0, 0,
                                 icon_width, icon_width)
            self.context.restore()

        self.col(self.fg_col)

        if self.icon_left:
            self.context.translate(
                self.border_radius*2 + icon_width + icon_pad, self.border_radius*2)
            PangoCairo.context_set_shape_renderer(
                self.get_pango_context(), self.render_custom, None)

            text = layout.get_text()
            count = 0

            layout.set_attributes(attr)

            PangoCairo.show_layout(self.context, layout)
        else:
            self.context.translate(self.border_radius*2, self.border_radius*2)
            PangoCairo.context_set_shape_renderer(
                self.get_pango_context(), self.render_custom, None)

            text = layout.get_text()
            count = 0

            layout.set_attributes(attr)

            PangoCairo.show_layout(self.context, layout)

        self.context.restore()
        next_y = 0
        if self.align_vert == 2:
            next_y = pos_y - (shape_height + self.padding)
        else:
            next_y = pos_y + shape_height + self.padding
        return next_y

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

    def set_testing(self, testing):
        self.testing = testing
        self.set_needs_redraw()
        self.get_all_images()
