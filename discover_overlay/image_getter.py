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
import threading
import logging
import os
import gi
import requests
import PIL.Image as Image
import io

gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, GdkPixbuf, GLib

log = logging.getLogger(__name__)


class SurfaceGetter:
    """Download and decode image to Pixbuf"""

    def __init__(self, func, url, identifier, display, recolor):
        self.func = func
        self.identifier = identifier
        self.url = url
        self.display = display
        self.recolor = recolor

    def pil_recolor(self, image):
        """Takes a PIL Image object, rejigs the colours, and outputs a GLib.Bytes containing a PNG formatted version of the image"""
        arr = bytearray(image.tobytes())
        r_p = self.recolor[0] * self.recolor[3]
        g_p = self.recolor[1] * self.recolor[3]
        b_p = self.recolor[2] * self.recolor[3]
        a_p = self.recolor[3]
        if image.has_transparency_data:
            for idx in range(0, len(arr), 4):
                arr[idx] = int(arr[idx] * r_p)
                arr[idx + 1] = int(arr[idx + 1] * g_p)
                arr[idx + 2] = int(arr[idx + 2] * b_p)
                arr[idx + 3] = int(arr[idx + 3] * a_p)
        else:
            for idx in range(0, len(arr), 3):
                arr[idx] = int(arr[idx] * r_p)
                arr[idx + 1] = int(arr[idx + 1] * g_p)
                arr[idx + 2] = int(arr[idx + 2] * b_p)
        pimage = Image.frombytes(
            "RGBA" if image.has_transparency_data else "RGB", image.size, arr
        )
        img_byte_arr = io.BytesIO()
        pimage.save(img_byte_arr, format="PNG")
        return GLib.Bytes(img_byte_arr.getvalue())

    def get_url(self):
        """Downloads and decodes"""
        pixbuf = None
        resp = None
        try:
            resp = requests.get(
                self.url,
                stream=True,
                timeout=10,
                headers={
                    "Referer": "https://streamkit.discord.com/overlay/voice",
                    "User-Agent": "Mozilla/5.0",
                },
            )
        except requests.HTTPError:
            log.error("Unable to open %s", self.url)
            return
        except requests.TooManyRedirects:
            log.error("Unable to open %s - Too many redirects", self.url)
            return
        except requests.Timeout:
            log.error("Unable to open %s - Timeout", self.url)
            return
        except requests.ConnectionError as e:
            log.error("Unable to open %s - Connection error %s", self.url, e)
            return

        content = self.pil_recolor(Image.open(resp.raw))

        loader = GdkPixbuf.PixbufLoader()
        try:
            loader.write_bytes(content)
            loader.close()
        except ValueError as e:
            log.error("Unable to open %s - Value error %s", self.url, e)
            return
        except TypeError as e:
            log.error("Unable to open %s - Type error %s", self.url, e)
            return
        except GLib.GError as e:
            log.error("Unable to open %s - GError %s", self.url, e)
            return
        pixbuf = loader.get_pixbuf()
        self.func(self.identifier, pixbuf)

    def get_file(self):
        """Attempt to load the file"""
        errors = []
        icon = None
        content = None
        log.info("Opening local file : %s", self.url)
        if "/" in self.url or "." in self.url or "~" in self.url:  # URL is a filename
            # It's a filename for sure
            if self.url.startswith("/") or self.url.startswith("~"):
                # Single path
                locations = [""]
            else:
                # Take pot shots
                locations = [
                    "",
                    os.path.join(
                        os.path.expanduser("~/.local/"),
                        "share/icons/hicolor/256x256/apps/",
                    ),
                    os.path.join("/usr/", "share/icons/hicolor/256x256/apps/"),
                    os.path.join("/app", "share/icons/hicolor/256x256/apps/"),
                ]

            # Not found in theme, try some common locations
            for prefix in locations:
                mixpath = os.path.join(
                    prefix,
                    self.url,
                )
                if not os.path.isfile(mixpath):
                    errors.append(f"File not found: {mixpath}")
                    continue
                content = self.pil_recolor(Image.open(mixpath))
        else:  # URL is a GTK icon name
            icon_theme = Gtk.IconTheme.get_for_display(self.display)
            icon = icon_theme.lookup_icon(
                self.url,
                None,
                -1,
                1,
                Gtk.TextDirection.NONE,
                Gtk.IconLookupFlags.FORCE_REGULAR,
            )

            if icon:
                try:
                    image = GdkPixbuf.Pixbuf.new_from_file(icon.get_file().get_path())
                    self.func(self.identifier, image)
                    return
                except ValueError as e:
                    errors.append(f"Value Error - Unable to read {self.url} {e}")
                except FileNotFoundError as e:
                    errors.append(f"File not found: {self.url} {e}")

            errors.append("Not an icon : self.url")
            return

        loader = GdkPixbuf.PixbufLoader()
        try:
            loader.write_bytes(content)
            loader.close()
        except ValueError as e:
            log.error("Unable to open %s - Value error %s", self.url, e)
            return
        except TypeError as e:
            log.error("Unable to open %s - Type error %s", self.url, e)
            return
        except GLib.GError as e:
            log.error("Unable to open %s - GError %s", self.url, e)
            return
        pixbuf = loader.get_pixbuf()
        self.func(self.identifier, pixbuf)
        for error in errors:
            log.error(error)


def get_surface(func, identifier, ava, display, recolor=[1.0, 1.0, 1.0, 1.0]):
    """Download to Pixbuf"""
    image_getter = SurfaceGetter(func, identifier, ava, display, recolor)
    if identifier.startswith("http"):
        thread = threading.Thread(target=image_getter.get_url)
        thread.start()
    else:
        thread = threading.Thread(target=image_getter.get_file)
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
