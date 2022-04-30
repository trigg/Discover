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
import io
gi.require_version('GdkPixbuf', '2.0')
# pylint: disable=wrong-import-position
from gi.repository import Gio, GdkPixbuf  # nopep8

log = logging.getLogger(__name__)

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
            surface = from_pil(image)

            self.func(self.identifier, surface)
        except requests.HTTPError:
            log.error("Unable to open %s", self.url)
        except requests.TooManyRedirects:
            log.error("Unable to open %s - Too many redirects", self.url)
        except requests.Timeout:
            log.error("Unable to open %s - Timeout", self.url)
        except requests.ConnectionError:
            log.error("Unable to open %s - Connection error", self.url)
        except ValueError:
            log.error("Unable to read %s", self.url)
        except TypeError:
            log.error("Unable to read %s", self.url)
        except PIL.UnidentifiedImageError:
            log.error("Unknown image type")

    def get_file(self):
        locations = [os.path.expanduser('~/.local/'), '/usr/', '/app']
        for prefix in locations:
            mixpath = os.path.join(prefix, self.url)
            image = None
            try:
                image = Image.open(mixpath)
            except ValueError:
                log.error("Value Erorr - Unable to read %s", mixpath)
            except TypeError:
                log.error("Type Error - Unable to read %s", mixpath)
            except PIL.UnidentifiedImageError:
                log.error("Unknown image type: %s", mixpath)
            except FileNotFoundError:
                log.error("File not found: %s", mixpath)
            if image:
                surface = from_pil(image)
                if surface:
                    self.func(self.identifier, surface)
                    return


def from_pil(image, alpha=1.0):
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

def get_surface(func, identifier, ava, size):
    """Download to cairo surface"""
    image_getter = SurfaceGetter(func, identifier, ava, size)
    if identifier.startswith('http'):
        thread = threading.Thread(target=image_getter.get_url, args=())
        thread.start()
    else:
        thread = threading.Thread(target=image_getter.get_file, args=())
        thread.start()


def make_surface_from_raw(raw, size):
    """Create surface from raw notification data"""
    width = raw[0]
    height = raw[1]
    rowstride = raw[2]
    hasalpha = raw[3]
    bitspersample = raw[4]
    channels = raw[5]
    image_raw_dbus = raw[6]
    image_raw = bytes(image_raw_dbus)
    image = None
    if hasalpha:
        image = Image.frombytes('RGBA', [width, height], image_raw, 'raw')
    else:
        image = Image.frombytes('RGB', [width, height], image_raw, 'raw')
    surface = from_pil(image)
    return surface


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
