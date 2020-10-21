# Discover
Yet another Discord overlay for Linux written in Python using GTK3.

Considerably lighter on system resources and less hack-and-slash included than discord-overlay.
![Screenshot](https://user-images.githubusercontent.com/964775/94065879-9c4e4480-fde3-11ea-9b8a-4688fd02ca17.png)

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

## Dependencies

Most requirements should be handled by pip.

A compositor is strongly advised but there is a non-compositor mode optionally

It is advised to install python-gobject from your system's own package manager.

#### Debian/Ubuntu

`apt install python3-gi`

#### Arch

`pacman -S python-gobject`


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

I feel like I shouldn't have to at all! Until we get an official one I might just create a new one every few months. Look forward to Rust/Vulkan version coming in a few months.

### Are you serious?

Generally, no.

