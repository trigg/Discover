# Using Discover Overlay

After installing with [Flathub](install_flathub), [Python PIP](install_pip) or from [another source](https://github.com/trigg/Discover) you should have two launcher icons in 'Utilities' for `Discover Overlay` and `Discover Overlay Configuration`.

Development is focused on X11 and wlroots-based environments, Plasma on wayland works but Gnome on wayland does not.

## Configuration

Choose `Discover Overlay Configuration` from your application menu. Changes made here or directly to the config file take effect on any running overlays

## Autostart

The Configuration 'Start on boot' option is grayed out in the flatpak version. This can be achieved by adding `Discover Overlay` to your desktop autostart list

## Nothing shows up?

By default the overlay itself with show nothing if there's nothing to display.

Make sure you're running Discord, and enter a voice chat room. The list of users in the voice chat room should be overlayed on your primary display.
