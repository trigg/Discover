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
from .about_settings import AboutSettingsWindow
gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position,wrong-import-order
from gi.repository import Gtk


class MainSettingsWindow(Gtk.Window):
    """Settings window holding all settings tab"""

    def __init__(self, discover):
        Gtk.Window.__init__(self)

        self.connect("destroy", self.close_window)
        self.connect("delete-event", self.close_window)

        self.discover = discover
        self.text_overlay = discover.text_overlay
        self.voice_overlay = discover.voice_overlay
        self.set_title("Discover Overlay Configuration")
        self.set_icon_name("discover-overlay")
        self.set_default_size(280, 180)

        # Create
        notebook = Gtk.Notebook()

        if discover.steamos:
            notebook.set_tab_pos(Gtk.PositionType.LEFT)

            self.set_default_size(1280, 800)

        self.about_settings = AboutSettingsWindow(self.discover)
        about_label = Gtk.Label.new("Overview")
        notebook.append_page(self.about_settings)
        notebook.set_tab_label(self.about_settings, about_label)

        self.voice_settings = VoiceSettingsWindow(self.voice_overlay)
        voice_label = Gtk.Label.new("Voice")
        notebook.append_page(self.voice_settings)
        notebook.set_tab_label(self.voice_settings, voice_label)

        self.text_settings = TextSettingsWindow(self.text_overlay)
        text_label = Gtk.Label.new("Text")
        
        notebook.append_page(self.text_settings)
        notebook.set_tab_label(self.text_settings, text_label)

        self.core_settings = GeneralSettingsWindow(self.discover)
        core_label = Gtk.Label.new("Core")
        notebook.append_page(self.core_settings)
        notebook.set_tab_label(self.core_settings, core_label)
        self.add(notebook)
        self.notebook = notebook

    def close_window(self, widget=None, event=None):
        """
        Hide the settings window for use at a later date
        """
        self.text_settings.close_window(widget, event)
        self.voice_settings.close_window(widget, event)
        self.core_settings.close_window(widget, event)
        self.hide()
        return True

    def present_settings(self):
        """
        Show the settings window
        """
        self.about_settings.present_settings()
        self.voice_settings.present_settings()
        self.text_settings.present_settings()
        self.core_settings.present_settings()
        self.notebook.show()
        self.show()
