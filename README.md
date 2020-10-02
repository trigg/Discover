# Discover
Yet another discord overlay for linux written in Python using GTK3

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

Requirements should be handled by pip.

Requires PyGTK3 3.22 or newer, websocket_client

A compositor is strongly advised but there is a non-compositor mode optionally


## Usage

run `discover-overlay` if this fails it is most likely in `~/.local/bin/discover-overlay`

Comes with sane-enough defaults but has a system tray icon & settings window if needed.


## Why do you keep making Discord Overlays?

I feel like I shouldn't have to at all! Until we get an official one I might just create a new one every few months. Look forward to Rust/Vulkan version coming in a few months.

### Are you serious?

Generally, no.

