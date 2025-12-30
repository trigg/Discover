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
"""Functions to assist font picking"""
import gi
import json

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango


# https://toshiocp.github.io/Gtk4-tutorial/sec23.html
# TODO Weights, Italics
def desc_to_css_font(desc):
    """Formats a font description into a CSS rule"""
    if desc.get_size_is_absolute():
        size = f"{desc.get_size() / Pango.SCALE}px"
    else:
        size = f"{desc.get_size() / Pango.SCALE}pt"
    mods = ""
    family = desc.get_family()
    font = f'{size} {mods} "{family}"'
    return font


def font_string_to_css_font_string(string_in):
    """Takes a string of uncertain origin and feeds it into a
    Gtk.FontButton in the hopes of turning it into a font
    description, then turning that into a CSS rule"""
    if string_in[0].isnumeric():  # If it starts with a number it is Probably correct
        return string_in
    # It might be an old-style font string...
    fb = Gtk.FontButton()
    fb.set_font(string_in)
    return desc_to_css_font(fb.get_font_desc())


def col_to_css(col):
    """Convert a JSON-encoded string or a tuple into a CSS colour"""
    if isinstance(col, str):
        col = json.loads(col)
    assert len(col) == 4
    red = int(col[0] * 255)
    green = int(col[1] * 255)
    blue = int(col[2] * 255)
    alpha = col[3]
    return f"rgba({red},{green},{blue},{alpha:2.2f})"
