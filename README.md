# Discover
Yet another Discord overlay for Linux written in Python using GTK3.

Discover-Overlay is a GTK3 overlay written in Python3. It can be configured to show who is currently talking on discord or it can be set to display text and images from a preconfigured channel. It is fully customisable and can be configured to display anywhere on the screen. We fully support X11 and wlroots based environments. We felt the need to make this project due to the shortcomings in support on Linux by the official discord client.

Considerably lighter on system resources and less hack-and-slash included than discord-overlay.

![Screenshot](https://user-images.githubusercontent.com/535772/149630830-750f8af6-e935-44a6-ad1c-da1d204ee107.png)

Got a question about development or a feature request? [Join our Discord!](https://discord.gg/jRKWMuDy5V) or open an [issue on GitHub](https://github.com/trigg/Discover/issues)

## Installing

### Stable
```
python3 -m pip install discover-overlay
```

### Latest Testing
```
git clone https://github.com/trigg/Discover.git
cd Discover
python3 -m pip install .
```

### Externally Packaged 

Note that while we list links to other locations to download, the version provided is unknown and often untested by us. Report bugs in these implementations to their respective project, not here.

##### Arch AUR

[Stable](https://aur.archlinux.org/packages/discover-overlay/)
[Latest](https://aur.archlinux.org/packages/discover-overlay-git/)

##### [Fedora](https://copr.fedorainfracloud.org/coprs/mavit/discover-overlay/)

```bash
sudo yum copr enable mavit/discover-overlay
sudo yum install discover-overlay
```

##### [Gentoo](https://gpo.zugaina.org/net-voip/discover-overlay)

```bash
sudo eselect repository enable guru
sudo emaint -r guru sync
sudo emerge net-voip/discover-overlay
```

## Dependencies

Most requirements should be handled by pip.

A compositor is strongly advised but there is a non-compositor mode optionally

It is advised to install python-gobject from your system's own package manager.

#### Debian/Ubuntu

`apt install python3-gi`

#### Arch

`pacman -S python-gobject`

with Wayland support

`pacman -S gtk-layer-shell`


## Usage

Run `discover-overlay` if this fails it is most likely in `~/.local/bin/discover-overlay`

Comes with sane-enough default but has a configuration screen to tweak to your own use. Configuration can be reached either via System tray or by running `discover-overlay --configure`

### Debugging
If you are trying to debug on VS Code you are likely to get the following message:
```
/usr/bin/python3: No module named discover_overlay.__main__; 'discover_overlay' is a package and cannot be directly executed
```

To get around this, copy the main file created by discover-overlay with ``cp $(which discover-overlay) /path/to/Discover/discover_overlay/__main__.py``

## Why do you keep making Discord Overlays?

I feel like I shouldn't have to at all! Until we get an official one I might just create a new one every few months. Look forward to Rust/Vulkan version coming in a few months. /s

### Are you serious?

Generally, no.

