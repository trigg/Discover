import gi
gi.require_version("Gtk", "3.0")
gi.require_version('PangoCairo', '1.0')
gi.require_version('GdkPixbuf', '2.0')
import urllib
import threading
from gi.repository.GdkPixbuf import Pixbuf
from gi.repository import Gtk, GLib, Gio, GdkPixbuf, Gdk, Pango, PangoCairo
import logging


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
            pixbuf = pixbuf.scale_simple(self.size, self.size,
                                         GdkPixbuf.InterpType.BILINEAR)
            self.func(self.id, pixbuf)
        except Exception as e:
            logging.error(
                "Could not access : %s" % (url))
            logging.error(e)


def get_image(func, id, ava, size):
    image_getter = Image_Getter(func, id, ava, size)
    t = threading.Thread(target=image_getter.get_url, args=())
    t.start()
