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

        try:
            resp = requests.get(self.url, stream=True, headers={
                'Referer': 'https://streamkit.discord.com/overlay/voice', 'User-Agent': 'Mozilla/5.0'})
            raw = resp.raw
            im = Image.open(raw)
            surf = self.from_pil(im)

            self.func(self.id, surf)
        except:
            logging.error("Unable to open %s" % (self.url))

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


def get_aspected_size(img, w, h, anchor=0, hanchor=0):
    px = img.get_width()
    py = img.get_height()
    if py < 1 or h < 1:
        return (0, 0)
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
    # Path - only add the path do not fill : True/False
    # Aspect - keep aspect ratio : True/False
    # Anchor - with aspect : 0=left 1=middle 2=right
    # HAnchor - with apect : 0=bottom 1=middle 2=top
    ctx.save()
    px = img.get_width()
    py = img.get_height()
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
