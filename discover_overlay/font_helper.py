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

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango


# https://toshiocp.github.io/Gtk4-tutorial/sec23.html
# TODO Weights, Italics
def desc_to_css_font(desc):
    size = ""
    if desc.get_size_is_absolute():
        size = "%dpx" % (desc.get_size() / Pango.SCALE)
    else:
        size = "%dpt" % (desc.get_size() / Pango.SCALE)
    mods = ""
    family = desc.get_family()
    font = '%s %s "%s"' % (mods, size, family)
    return font


def font_string_to_css_font_string(string_in):
    if string_in[0].isnumeric():  # If it starts with a number it is Probably correct
        return string_in
    # It might be an old-style font string...
    fb = Gtk.FontButton()
    fb.set_font(string_in)
    return desc_to_css_font(fb.get_font_desc())
