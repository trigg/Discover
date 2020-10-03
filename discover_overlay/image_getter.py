import gi
gi.require_version("Gtk", "3.0")
gi.require_version('GdkPixbuf', '2.0')
import urllib
import requests
import threading
from gi.repository.GdkPixbuf import Pixbuf
from gi.repository import Gtk, Gio, GdkPixbuf, Gdk
import cairo
import logging
import PIL.Image as Image
from io import BytesIO


class Image_Getter():
    def __init__(self, func, url, id, size):
        self.func = func
        self.id = id
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
            pixbuf = Pixbuf.new_from_stream(input_stream, None)
            if self.size:
                pixbuf = pixbuf.scale_simple(self.size, self.size,
                                             GdkPixbuf.InterpType.BILINEAR)
            # elif self.limit_x or self.limit_y:
            #    px = pixbuf.width()
            #    py = pixbuf.height()
            #    aspect = px / py
            #    scale = 1.0
            #    if self.limit_x and self.limit_y:
            #        scale = min(self.limit_x / px, self.limit_y / py, 1.0)
            #    elif self.limit_x:
            #        scale = min(self.limit_x / px, 1.0)
            #    elif self.limit_y:
            #        scale = min(self.limit_y / py, 1.0)##
#
#                pixbuf = pixbuf.scale_simple(int(px * scale), int(py * scale),
#                                             GdkPixbuf.InterpType.BILINEAR)

            self.func(self.id, pixbuf)
        except Exception as e:
            logging.error(
                "Could not access : %s" % (self.url))
            logging.error(e)


class Surface_Getter():
    def __init__(self, func, url, id, size):
        self.func = func
        self.id = id
        self.url = url
        self.size = size

    def get_url(self):

        im = Image.open(requests.get(self.url, stream=True, headers={
                        'Referer': 'https://streamkit.discord.com/overlay/voice', 'User-Agent': 'Mozilla/5.0'}).raw)
        surf = self.from_pil(im)

        self.func(self.id, surf)

    def from_pil(self, im, alpha=1.0, format=cairo.FORMAT_ARGB32):
        """
        :param im: Pillow Image
        :param alpha: 0..1 alpha to add to non-alpha images
        :param format: Pixel format for output surface
        """
        assert format in (
            cairo.FORMAT_RGB24, cairo.FORMAT_ARGB32), "Unsupported pixel format: %s" % format
        if 'A' not in im.getbands():
            im.putalpha(int(alpha * 256.))
        arr = bytearray(im.tobytes('raw', 'BGRa'))
        surface = cairo.ImageSurface.create_for_data(
            arr, format, im.width, im.height)
        return surface


def get_image(func, id, ava, size):
    image_getter = Image_Getter(func, id, ava, size)
    t = threading.Thread(target=image_getter.get_url, args=())
    t.start()


def get_surface(func, id, ava, size):
    image_getter = Surface_Getter(func, id, ava, size)
    t = threading.Thread(target=image_getter.get_url, args=())
    t.start()
