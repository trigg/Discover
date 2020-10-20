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
"""Functions & Classes to assist image loading."""
import urllib
import threading
import logging
import gi
import requests
import cairo
import PIL.Image as Image
gi.require_version('GdkPixbuf', '2.0')
# pylint: disable=wrong-import-position
from gi.repository import Gio, GdkPixbuf


class ImageGetter():
    """Older attempt. Not advised as it can't manage anything but PNG. Loads to GDK Pixmap"""

    def __init__(self, func, url, identifier, size):
        self.func = func
        self.id = identifier
        self.url = url
        self.size = size

    def get_url(self):
        req = urllib.request.Request(self.url)
        req.add_header(
            'Referer', 'https://streamkit.discord.com/overlay/voice')
        req.add_header('User-Agent', 'Mozilla/5.0')
        try:
            response = urllib.request.urlopen(req)
            input_stream = Gio.MemoryInputStream.new_from_data(
                response.read(), None)
            pixbuf = GdkPixbuf.Pixbuf.new_from_stream(input_stream, None)
            if self.size:
                pixbuf = pixbuf.scale_simple(self.size, self.size,
                                             GdkPixbuf.InterpType.BILINEAR)

            self.func(self.id, pixbuf)
        except urllib.error.URLError as exception:
            logging.error(
                "Could not access : %s", self.url)
            logging.error(exception)


class SurfaceGetter():
    """Download and decode image using PIL and store as a cairo surface"""

    def __init__(self, func, url, identifier, size):
        self.func = func
        self.id = identifier
        self.url = url
        self.size = size

    def get_url(self):
        """Downloads and decodes"""
        try:
            resp = requests.get(self.url, stream=True, headers={
                'Referer': 'https://streamkit.discord.com/overlay/voice', 'User-Agent': 'Mozilla/5.0'})
            raw = resp.raw
            im = Image.open(raw)
            surf = self.from_pil(im)

            self.func(self.id, surf)
        except requests.HTTPError:
            logging.error("Unable to open %s", self.url)
        except requests.TooManyRedirects:
            logging.error("Unable to open %s - Too many redirects", self.url)
        except requests.Timeout:
            logging.error("Unable to open %s - Timeout", self.url)
        except requests.ConnectionError:
            logging.error("Unable to open %s - Connection error", self.url)
        except ValueError:
            logging.error("Unable to read %s", self.url)
        except TypeError:
            logging.error("Unable to read %s", self.url)

    def from_pil(self, im, alpha=1.0):
        """
        :param im: Pillow Image
        :param alpha: 0..1 alpha to add to non-alpha images
        :param format: Pixel format for output surface
        """
        if 'A' not in im.getbands():
            im.putalpha(int(alpha * 256.))
        arr = bytearray(im.tobytes('raw', 'BGRa'))
        surface = cairo.ImageSurface.create_for_data(
            arr, cairo.FORMAT_ARGB32, im.width, im.height)
        return surface


def get_image(func, identifier, ava, size):
    """Download to GDK Pixmap"""
    image_getter = ImageGetter(func, identifier, ava, size)
    t = threading.Thread(target=image_getter.get_url, args=())
    t.start()


def get_surface(func, identifier, ava, size):
    """Download to cairo surface"""
    image_getter = SurfaceGetter(func, identifier, ava, size)
    t = threading.Thread(target=image_getter.get_url, args=())
    t.start()


def get_aspected_size(img, w, h, anchor=0, hanchor=0):
    """Get dimensions of image keeping current aspect ratio"""
    px = img.get_width()
    py = img.get_height()
    if py < 1 or h < 1:
        return (0, 0, 0, 0)
    img_aspect = px / py
    rect_aspect = w / h

    y = 0
    x = 0
    if img_aspect > rect_aspect:
        oh = h
        h = w / img_aspect
        if anchor == 0:
            y = y + (oh - h)
        if anchor == 1:
            y = y + ((oh - h) / 2)
    elif img_aspect < rect_aspect:
        ow = w
        w = h * img_aspect
        if hanchor == 2:
            x = x + (ow - w)
        if hanchor == 1:
            x = x + ((ow - w) / 2)
    return (x, y, w, h)


def draw_img_to_rect(img, ctx, x, y, w, h, path=False, aspect=False, anchor=0, hanchor=0):
    """Draw cairo surface onto context"""
    # Path - only add the path do not fill : True/False
    # Aspect - keep aspect ratio : True/False
    # Anchor - with aspect : 0=left 1=middle 2=right
    # HAnchor - with apect : 0=bottom 1=middle 2=top
    ctx.save()
    px = img.get_width()
    py = img.get_height()
    x_off = 0
    y_off = 0
    if aspect:
        (x_off, y_off, w, h) = get_aspected_size(
            img, w, h, anchor=anchor, hanchor=hanchor)

    ctx.translate(x + x_off, y + y_off)
    ctx.scale(w, h)
    ctx.scale(1 / px, 1 / py)
    ctx.set_source_surface(img, 0, 0)

    ctx.rectangle(0, 0, px, py)
    if not path:
        ctx.fill()
    ctx.restore()
    return (w, h)
