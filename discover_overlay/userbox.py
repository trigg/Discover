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
"""A Gtk Box with direction"""
import gettext
import logging
import gi
import importlib_resources
from .image_getter import get_surface
from .layout import UserBoxLayout
from .connection_state import ConnectionState

gi.require_version("Gtk", "4.0")


from gi.repository import Gtk, GLib

log = logging.getLogger(__name__)
with importlib_resources.as_file(
    importlib_resources.files("discover_overlay") / "locales"
) as path:
    t = gettext.translation(
        "default",
        path,
        fallback=True,
    )
    _ = t.gettext


class UserBox(Gtk.Box):
    """A GtkBox with information about the user it is displaying"""

    def __init__(self, overlay, userid):
        super().__init__()
        self.overlay = overlay
        self.userid = userid

        self.add_css_class("user")

        self.is_in_chat = False
        self.talking = False

        self.image = Gtk.Image()
        self.label = Gtk.Label()
        self.mute = Gtk.Image()
        self.deaf = Gtk.Image()

        self.image.set_overflow(Gtk.Overflow.HIDDEN)

        self.image.add_css_class("usericon")
        self.label.add_css_class("userlabel")
        self.mute.add_css_class("usermute")
        self.deaf.add_css_class("userdeaf")

        self.image.set_halign(Gtk.Align.CENTER)
        self.image.set_valign(Gtk.Align.CENTER)
        self.mute.set_halign(Gtk.Align.CENTER)
        self.mute.set_valign(Gtk.Align.CENTER)
        self.deaf.set_halign(Gtk.Align.CENTER)
        self.deaf.set_valign(Gtk.Align.CENTER)

        self.append(self.label)
        self.append(self.image)
        self.append(self.mute)
        self.append(self.deaf)

        self.mute.hide()
        self.deaf.hide()

        self.pixbuf = None
        self.pixbuf_requested = False
        self.previous_avatar_url = None
        self.name = ""

        self.grace_timeout = None

        self.set_layout_manager(UserBoxLayout())
        self.update_image()

    def update_user_data(self, userblob):
        """Set internals based on most recent object from connector. Avoid flickering/reflow where possible"""
        name = userblob["username"]
        if "nick" in userblob:
            name = userblob["nick"]
        if self.name != name:
            self.name = name
            self.update_label()

        # These are set by server, from multiple sources.
        if "mute" in userblob:
            self.set_mute(userblob["mute"])
        if "deaf" in userblob:
            self.set_deaf(userblob["deaf"])

        url = f"https://cdn.discordapp.com/avatars/{userblob['id']}/{userblob['avatar']}.png"

        if not self.pixbuf_requested and url != self.previous_avatar_url:
            get_surface(self.recv_avatar, url, userblob["id"], self.get_display())
            self.pixbuf_requested = True

    def update_label(self):
        """Update the label widget, assuming config has changed"""
        if self.overlay.icon_only:
            self.label.hide()
            return
        self.label.show()

        if len(self.name) < self.overlay.nick_length:
            self.label.set_text(self.name)
        else:
            self.label.set_text(self.name[: (self.overlay.nick_length - 1)] + "\u2026")

    def update_image(self):
        """Update the image widget, assuming config has changed"""
        if self.overlay.deafpix:
            self.deaf.set_from_pixbuf(self.overlay.deafpix)
        if self.overlay.mutepix:
            self.mute.set_from_pixbuf(self.overlay.mutepix)

        if not self.overlay.show_avatar:
            self.image.hide()
            return
        self.image.show()

        if self.pixbuf:
            self.image.set_from_pixbuf(self.pixbuf)
        elif self.overlay.def_avatar:
            self.image.set_from_pixbuf(self.overlay.def_avatar)

    def recv_avatar(self, _identifier, pix):
        """Callback to return an image to main thread"""
        self.pixbuf = pix
        self.pixbuf_requested = False
        self.image.set_from_pixbuf(self.pixbuf)

    def set_mute(self, mute):
        """Set this user to display as muted"""
        if mute:
            self.add_css_class("mute")
            self.mute.show()
        else:
            self.remove_css_class("mute")
            self.mute.hide()

    def set_deaf(self, deaf):
        """Set this user to display as deafened"""
        if deaf:
            self.add_css_class("deaf")
            self.deaf.show()
        else:
            self.remove_css_class("deaf")
            self.deaf.hide()

    def set_talking(self, talking):
        """Called by connector when user starts or stops talking"""
        self.talking = talking
        if self.grace_timeout:
            GLib.source_remove(self.grace_timeout)
            self.grace_timeout = None
        if talking:
            self.add_css_class("talking")
        else:
            self.remove_css_class("talking")
            if self.overlay.only_speaking:
                grace = self.overlay.only_speaking_grace_period
                if grace > 0:
                    self.grace_timeout = GLib.timeout_add_seconds(grace, self.grace_cb)
        self.set_shown()

    def user_left(self):
        """This user has left the room"""
        self.is_in_chat = False
        self.set_shown()

    def user_join(self):
        """This user has joined the room"""
        self.is_in_chat = True
        self.set_shown()

    def set_shown(self):
        """Set widget to shown based on information available"""
        if self.should_show():
            self.show()
            return
        self.hide()

    def should_show(self):
        """Should this widget be shown"""
        return self.is_user_visible()

    def is_user_visible(self):
        """Is this a user and visible."""
        if self.grace_timeout:
            return True  # We're awaiting a timeout, keep showing
        if self.overlay.only_speaking and not self.talking:
            return False
        if self.is_in_chat:
            return True
        return False

    def grace_cb(self):
        """Called X seconds after user stops talking. Remove callback ID and hide self if needed"""
        self.grace_timeout = None
        self.set_shown()
        return False  # Do not repeat


class UserBoxConnection(UserBox):
    """A User-like box to show the connection state before users in voice overlay"""

    def __init__(self, overlay):
        self.show_always = False
        self.show_disconnected = True
        self.last = ConnectionState.NO_DISCORD
        super().__init__(overlay, None)

    def set_show_always(self, show):
        """Config option: Show this widget always. Overrides disconnected config option"""
        self.show_always = show

    def set_show_only_disconnected(self, show):
        """Config option: Show this widget only when connection to local discord is lost, or discord is not connected to a room"""
        self.show_disconnected = show

    def get_image_name(self):
        """Lookup pixbuf for given connection string"""
        level = self.last
        if level == ConnectionState.NO_DISCORD:
            return "network-wired-disconnected"
        if level == ConnectionState.DISCORD_INVALID:
            return "dialog-error"
        elif level == ConnectionState.NO_VOICE_CHAT:
            return "network-cellular-signal-ok"
        elif level == ConnectionState.VOICE_CHAT_NOT_CONNECTED:
            return "network-wired-disconnected"
        elif level == ConnectionState.CONNECTED:
            return "network-cellular-signal-excellent"
        else:
            return ""

    def get_label_text(self):
        """Lookup text string for state. Intentionally verbose to force i18n"""
        level = self.last
        if level == ConnectionState.NO_DISCORD:
            return _("NO DISCORD")
        elif level == ConnectionState.DISCORD_INVALID:
            return _("DISCORD INVALID")
        elif level == ConnectionState.NO_VOICE_CHAT:
            return _("NO VOICE CHAT")
        elif level == ConnectionState.VOICE_CHAT_NOT_CONNECTED:
            return _("VOICE CHAT NOT CONNECTED")
        elif level == ConnectionState.CONNECTED:
            return _("CONNECTED")
        else:
            return _("ERROR")

    def set_connection(self, level):
        """Set connection string. Updates image and label"""
        self.last = level
        self.image.set_from_icon_name(self.get_image_name())
        self.update_label()
        self.update_image()
        self.set_shown()
        self.get_root().set_visibility()

    def should_show(self):
        """Returns True if this should show in overlay, False otherwise"""
        if self.last == ConnectionState.DISCORD_INVALID:
            return True
        if self.show_always:
            return True
        elif self.show_disconnected and (
            self.last == ConnectionState.NO_DISCORD
            or self.last == ConnectionState.VOICE_CHAT_NOT_CONNECTED
        ):
            return True
        return False

    def update_image(self):
        """Updates the image, assuming there is changed config or info"""
        if not self.overlay.show_avatar:
            self.image.hide()
            return
        self.image.show()
        self.image.set_from_icon_name(self.get_image_name())

    def update_label(self):
        """Updates the label, assuming there is changed config or info"""
        self.set_shown()
        if self.overlay.icon_only:
            self.label.hide()
            return
        self.label.show()
        label_text = self.get_label_text()
        if len(label_text) < self.overlay.nick_length:
            self.label.set_text(label_text)
        else:
            self.label.set_text(label_text[: (self.overlay.nick_length - 1)] + "\u2026")

    def is_user_visible(self):
        return False


class UserBoxTitle(UserBox):
    """A Widget to show user icon, name, mute & deaf state"""

    def __init__(self, overlay):
        super().__init__(overlay, None)
        self.show_title = True
        self.last = ""

    def set_show(self, show):
        """Config option: if this should be shown"""
        self.show_title = show

    def set_label(self, label):
        """Sets the channel title"""
        self.last = label
        if self.overlay.icon_only:
            self.label.hide()
        else:
            self.label.show()
        self.update_label()
        self.set_shown()

    def set_image(self, image):
        """Sets the channel image"""
        if self.show_title:
            self.show()
        if self.overlay.show_avatar:
            self.image.show()
        self.pixbuf = image
        self.image.set_from_pixbuf(self.pixbuf)

    def blank(self):
        """Blanks image and hides self"""
        self.pixbuf = None
        self.last = None
        self.set_shown()

    def should_show(self):
        """If this widget should be shown"""
        return self.show_title and self.last

    def update_image(self):
        if not self.overlay.show_avatar:
            self.image.hide()
            return
        self.image.show()
        self.image.set_from_pixbuf(self.pixbuf)

    def update_label(self):
        self.set_shown()
        if self.overlay.icon_only:
            self.label.hide()
            return
        self.label.show()
        if self.last:
            if len(self.last) < self.overlay.nick_length:
                self.label.set_text(self.last)
            else:
                self.label.set_text(
                    self.last[: (self.overlay.nick_length - 1)] + "\u2026"
                )

    def is_user_visible(self):
        return False
