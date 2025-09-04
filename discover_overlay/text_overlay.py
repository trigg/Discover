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
import re
import json
import gi
from .overlay import OverlayWindow

gi.require_version("Gtk", "4.0")

from gi.repository import Pango

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
        self.width_limit = 500
        self.height_limit = 300

    def set_blank(self):
        """Set contents blank and redraw"""
        self.content = []

    def tick(self):
        """Check for old images"""
        if len(self.attachment) > self.line_limit:
            # We've probably got old images!
            oldlist = self.attachment
            self.attachment = {}
            log.info("Cleaning old images")
            for message in self.content:
                if "attach" in message and message["attach"]:
                    url = message["attach"][0]["url"]
                    log.info("keeping %s", url)
                    self.attachment[url] = oldlist[url]

    def set_text_time(self, timer):
        """Config option: Time before messages disappear from overlay"""
        if self.text_time != timer or self.timer_after_draw != timer:
            self.text_time = timer
            self.timer_after_draw = timer

    def set_text_list(self, tlist, altered):
        """Change contents of overlay"""
        self.content = tlist[-self.line_limit :]
        if altered:
            pass

    def set_fg(self, fg_col):
        """Config option: Sets the text colour"""
        if self.fg_col != fg_col:
            self.fg_col = fg_col

    def set_bg(self, bg_col):
        """Config option: Set the background colour"""
        if self.bg_col != bg_col:
            self.bg_col = bg_col

    def set_show_attach(self, attachment):
        """Config option: Show image attachments"""
        if self.attachment != attachment:
            self.show_attach = attachment

    def set_popup_style(self, boolean):
        """Config option: Messages should disappear after being shown for some time"""
        if self.popup_style != boolean:
            self.popup_style = boolean

    def set_font(self, font):
        """Config option: Set font used for rendering"""
        if self.text_font != font:
            self.text_font = font

            self.pango_rect = Pango.Rectangle()
            font = Pango.FontDescription(self.text_font)
            self.pango_rect.width = font.get_size() * Pango.SCALE
            self.pango_rect.height = font.get_size() * Pango.SCALE

    def set_line_limit(self, limit):
        """Config option: Limit number of lines rendered"""
        if self.line_limit != limit:
            self.line_limit = limit

    def make_line(self, message):
        """Decode a recursive JSON object into pango markup."""
        ret = ""
        if isinstance(message, list):
            for inner_message in message:
                ret = f"{ret}{self.make_line(inner_message)}"
        elif isinstance(message, str):
            ret = self.sanitize_string(message)
        elif message["type"] == "strong":
            ret = f"<b>{self.make_line(message['content'])}</b>"
        elif message["type"] == "text":
            ret = self.sanitize_string(message["content"])
        elif message["type"] == "link":
            ret = f"<u>{self.make_line(message['content'])}</u>"
        elif message["type"] == "emoji":
            if "surrogate" in message:
                # ['src'] is SVG URL
                # ret = msg
                ret = message["surrogate"]
            else:
                ### Add Image ###
                self.image_list.append(
                    f"https://cdn.discordapp.com/emojis/{message['emojiId']}.png?v=1"
                )
                ret = "`"
        elif (
            message["type"] == "inlineCode"
            or message["type"] == "codeBlock"
            or message["type"] == "blockQuote"
        ):
            ret = f"<span font_family=\"monospace\" background=\"#0004\">{self.make_line(message['content'])}</span>"
        elif message["type"] == "u":
            ret = f"<u>{self.make_line(message['content'])}</u>"
        elif message["type"] == "em":
            ret = f"<i>{self.make_line(message['content'])}</i>"
        elif message["type"] == "s":
            ret = f"<s>{self.make_line(message['content'])}</s>"
        elif message["type"] == "channel":
            ret = self.make_line(message["content"])
        elif message["type"] == "mention":
            ret = self.make_line(message["content"])
        elif message["type"] == "br":
            ret = "\n"
        else:
            if message["type"] not in self.warned_filetypes:
                log.error("Unknown text type : %s", message["type"])
                self.warned_filetypes.append(message["type"])
        return ret

    def recv_attach(self, identifier, pix):
        """Callback from image_getter"""
        self.attachment[identifier] = pix

    def has_content(self):
        """Returns true if overlay has meaningful content to render"""
        if self.piggyback and self.piggyback.has_content():
            return True
        if not self.enabled:
            return False
        if self.hidden:
            return False
        return self.content

    def sanitize_string(self, string):
        """Sanitize a text message so that it doesn't intefere with Pango's XML format"""
        string = string.replace("&", "&amp;")
        string = string.replace("<", "&lt;")
        string = string.replace(">", "&gt;")
        string = string.replace("'", "&#39;")
        string = string.replace('"', "&#34;")
        return string

    def set_config(self, config):
        OverlayWindow.set_config(self, config)
        self.set_enabled(config.getboolean("enabled", fallback=False))

        channel = config.get("channel", fallback="0")
        guild = config.get("guild", fallback="0")
        self.discover.connection.set_text_channel(channel, guild)

        font = config.get("font", fallback=None)
        self.set_bg(json.loads(config.get("bg_col", fallback="[0.0,0.0,0.0,0.5]")))
        self.set_fg(json.loads(config.get("fg_col", fallback="[1.0,1.0,1.0,1.0]")))
        self.set_popup_style(config.getboolean("popup_style", fallback=False))
        self.set_text_time(config.getint("text_time", fallback=30))
        self.set_show_attach(config.getboolean("show_attach", fallback=True))
        self.set_line_limit(config.getint("line_limit", fallback=20))
        self.set_hide_on_mouseover(config.getboolean("autohide", fallback=False))
        self.set_mouseover_timer(config.getint("autohide_timer", fallback=1))

        self.set_monitor(config.get("monitor", fallback="Any"))

        if font:
            self.set_font(font)
