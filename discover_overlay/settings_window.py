from .voice_settings import VoiceSettingsWindow
from .text_settings import TextSettingsWindow
from .general_settings import GeneralSettingsWindow

import gi
gi.require_version("Gtk", "3.0")
import sys
import os
from gi.repository import Gtk, Gdk
import logging


class MainSettingsWindow(Gtk.Window):
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
        #nb.set_tab_pos(Gtk.POS_TOP)

        self.voice_settings = VoiceSettingsWindow(self.voice_overlay)
        nb.append_page(self.voice_settings)
        nb.set_tab_label_text(self.voice_settings, "Voice")
        self.text_settings = TextSettingsWindow(self.text_overlay)
        nb.append_page(self.text_settings)
        nb.set_tab_label_text(self.text_settings, "Text")
        self.core_settings = GeneralSettingsWindow(self.text_overlay,self.voice_overlay)
        nb.append_page(self.core_settings)
        nb.set_tab_label_text(self.core_settings, "Core")
        self.add(nb)

    def close_window(self,a=None,b=None):
        self.text_settings.close_window(a,b)
        self.voice_settings.close_window(a,b)
        self.core_settings.close_window(a,b)
        self.hide()
        return True

    def present(self):
        self.voice_settings.present()
        self.text_settings.present()
        self.core_settings.present()
        self.show_all()