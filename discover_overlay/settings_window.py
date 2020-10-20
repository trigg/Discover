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
"""Settings window holding all settings tab"""
import gi
from .voice_settings import VoiceSettingsWindow
from .text_settings import TextSettingsWindow
from .general_settings import GeneralSettingsWindow
gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position
from gi.repository import Gtk


class MainSettingsWindow(Gtk.Window):
    """Settings window holding all settings tab"""

    def __init__(self, text_overlay, voice_overlay):
        Gtk.Window.__init__(self)

        self.connect("destroy", self.close_window)
        self.connect("delete-event", self.close_window)

        self.text_overlay = text_overlay
        self.voice_overlay = voice_overlay
        self.set_title("Discover Overlay Configuration")
        self.set_icon_name("discover-overlay")
        self.set_default_size(280, 180)

        # Create
        nb = Gtk.Notebook()
        # nb.set_tab_pos(Gtk.POS_TOP)

        self.voice_settings = VoiceSettingsWindow(self.voice_overlay)
        nb.append_page(self.voice_settings)
        nb.set_tab_label_text(self.voice_settings, "Voice")
        self.text_settings = TextSettingsWindow(self.text_overlay)
        nb.append_page(self.text_settings)
        nb.set_tab_label_text(self.text_settings, "Text")
        self.core_settings = GeneralSettingsWindow(
            self.text_overlay, self.voice_overlay)
        nb.append_page(self.core_settings)
        nb.set_tab_label_text(self.core_settings, "Core")
        self.add(nb)
        self.nb = nb

    def close_window(self, a=None, b=None):
        self.text_settings.close_window(a, b)
        self.voice_settings.close_window(a, b)
        self.core_settings.close_window(a, b)
        self.hide()
        return True

    def present_settings(self):
        self.voice_settings.present_settings()
        self.text_settings.present_settings()
        self.core_settings.present_settings()
        self.nb.show()
        self.show()
