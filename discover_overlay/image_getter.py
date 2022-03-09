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
import PIL
import PIL.Image as Image
import os
gi.require_version('GdkPixbuf', '2.0')
# pylint: disable=wrong-import-position
from gi.repository import Gio, GdkPixbuf


class ImageGetter():
    """Older attempt. Not advised as it can't manage anything but PNG. Loads to GDK Pixmap"""

    def __init__(self, func, url, identifier, size):
        self.func = func
        self.identifier = identifier
        self.url = url
        self.size = size

    def get_url(self):
        """
        Download and decode
        """
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

            self.func(self.identifier, pixbuf)
        except urllib.error.URLError as exception:
            logging.error(
                "Could not access : %s", self.url)
            logging.error(exception)


class SurfaceGetter():
    """Download and decode image using PIL and store as a cairo surface"""

    def __init__(self, func, url, identifier, size):
        self.func = func
        self.identifier = identifier
        self.url = url
        self.size = size

    def get_url(self):
        """Downloads and decodes"""
        try:
            resp = requests.get(
                self.url, stream=True, headers={
                    'Referer': 'https://streamkit.discord.com/overlay/voice',
                    'User-Agent': 'Mozilla/5.0'
                }
            )
            raw = resp.raw
            image = Image.open(raw)
            surface = self.from_pil(image)

            self.func(self.identifier, surface)
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
        except PIL.UnidentifiedImageError:
            logging.error("Unknown image type")

    def get_file(self):
        locations = [os.path.expanduser('~/.local/'), '/usr/']
        for prefix in locations:
            try:
                image = Image.open(os.path.join(prefix,self.url))
                surface = self.from_pil(image)
                self.func(self.identifier, surface)
                return
            except ValueError:
                logging.error("Unable to read %s", self.url)
            except TypeError:
                logging.error("Unable to read %s", self.url)
            except PIL.UnidentifiedImageError:
                logging.error("Unknown image type")
            except FileNotFoundError:
                logging.error("Unable to load file %s", self.url)

    def from_pil(self, image, alpha=1.0):
        """
        :param im: Pillow Image
        :param alpha: 0..1 alpha to add to non-alpha images
        :param format: Pixel format for output surface
        """
        if 'A' not in image.getbands():
            image.putalpha(int(alpha * 256.))
        arr = bytearray(image.tobytes('raw', 'BGRa'))
        surface = cairo.ImageSurface.create_for_data(
            arr, cairo.FORMAT_ARGB32, image.width, image.height)
        return surface


def get_image(func, identifier, ava, size):
    """Download to GDK Pixmap"""
    image_getter = ImageGetter(func, identifier, ava, size)
    thread = threading.Thread(target=image_getter.get_url, args=())
    thread.start()


def get_surface(func, identifier, ava, size):
    """Download to cairo surface"""
    image_getter = SurfaceGetter(func, identifier, ava, size)
    if identifier.startswith('http'):
        thread = threading.Thread(target=image_getter.get_url, args=())
        thread.start()
    else:
        thread = threading.Thread(target=image_getter.get_file, args=())
        thread.start()


def get_aspected_size(img, width, height, anchor=0, hanchor=0):
    """Get dimensions of image keeping current aspect ratio"""
    pic_width = img.get_width()
    pic_height = img.get_height()
    if pic_height < 1 or height < 1:
        return (0, 0, 0, 0)
    img_aspect = pic_width / pic_height
    rect_aspect = width / height

    offset_y = 0
    offset_x = 0
    if img_aspect > rect_aspect:
        old_height = height
        height = width / img_aspect
        if anchor == 0:
            offset_y = offset_y + (old_height - height)
        if anchor == 1:
            offset_y = offset_y + ((old_height - height) / 2)
    elif img_aspect < rect_aspect:
        old_width = width
        width = height * img_aspect
        if hanchor == 2:
            offset_x = offset_x + (old_width - width)
        if hanchor == 1:
            offset_x = offset_x + ((old_width - width) / 2)
    return (offset_x, offset_y, width, height)


def draw_img_to_rect(img, ctx,
                     pos_x, pos_y,
                     width, height,
                     path=False, aspect=False,
                     anchor=0, hanchor=0):
    """Draw cairo surface onto context

    Path - only add the path do not fill : True/False
    Aspect - keep aspect ratio : True/False
    Anchor - with aspect : 0=left 1=middle 2=right
    HAnchor - with apect : 0=bottom 1=middle 2=top
    """

    ctx.save()
    offset_x = 0
    offset_y = 0
    if aspect:
        (offset_x, offset_y, width, height) = get_aspected_size(
            img, width, height, anchor=anchor, hanchor=hanchor)

    ctx.translate(pos_x + offset_x, pos_y + offset_y)
    ctx.scale(width, height)
    ctx.scale(1 / img.get_width(), 1 / img.get_height())
    ctx.set_source_surface(img, 0, 0)

    ctx.rectangle(0, 0, img.get_width(), img.get_height())
    if not path:
        ctx.fill()
    ctx.restore()
    return (width, height)
