# Discover
Yet another Discord overlay for Linux written in Python using GTK3.

Discover-Overlay is a GTK3 overlay written in Python3. It can be configured to show who is currently talking on discord or it can be set to display text and images from a preconfigured channel. It is fully customisable and can be configured to display anywhere on the screen. We fully support X11 and wlroots based environments. We felt the need to make this project due to the shortcomings in support on Linux by the official discord client.

Considerably lighter on system resources and less hack-and-slash included than discord-overlay.

![Screenshot](https://trigg.github.io/Discover/overlay.png)
## Usage

Easy user instructions can be found on our [User website](https://trigg.github.io/Discover/)

Got a question about development, bug reports or a feature request? [Join our Discord!](https://discord.gg/jRKWMuDy5V) or open an [issue on GitHub](https://github.com/trigg/Discover/issues)


### Terminal usage

On top of graphical options there are multiple ways to use this program from the command line

#### Start the overlay

You can start the overlay by running  
`discover-overlay`

This will close out any already running discover overlay for this user

#### Close the overlay
`discover-overlay --close` or `discover-overlay -x`

This closes the process running the overlay, hence any `--rpc` commands sent afterwards will do nothing

#### Open configuration window
`discover-overlay --configure` or `discover-overlay -c`

#### Log debug to file
`discover-overlay --debug` or `discover-overlay -d`

This will redirect all debug to the file `~/.config/discover-overlay/output.txt`

#### Hide the currently shown overlays
`discover-overlay --rpc --hide`

This will not stop the process running the overlay. This means the `--rpc` commands sent afterwards continue working as expected, and the `--show` is much quicker than starting the overlay from the start.

#### Show the overlays 
`discover-overlay --rpc --show`

Note that if the process running the overlay has stopped or crashed then this will do nothing

#### Mute yourself in voice chat
`discover-overlay --rpc --mute`

#### Unmute yourself in voice chat
`discover-overlay --rpc --unmute`

#### Deafen yourself in voice chat
`discover-overlay --rpc --deaf`

#### Undeafen yourself in voice chat
`discover-overlay --rpc --undeaf`

#### Attempt to join voice channel by room ID
`discover-overlay --rpc --moveto=X` 

Using a Room ID from Discord to replace `X`, this will attempt to join the voice channel.

#### Populate the channel RPC file with a list of guilds
`discover-overlay --rpc --refresh-guilds`
Requests a list of guilds. Once collected, it will write them to 
`~/.config/discover-overlay/channels.rpc`
as a JSON object

#### Populate the channel RPC file with a list of channels from a guild
`discover-overlay --rpc --guild-request=X`
Using a Server ID from Discord to replace `X`, this will request a list of channels (text & voice) from the given guild. Once collected, it will write them to
`~/.config/discover-overlay/channels.rpc`
as a JSON object.

#### Force SteamOS compatibility mode
`discover-overlay --steamos`
Forces the overlay to start as if it was started in a Gamescope & SteamOS session. Intended for testing against Gamescope while still nested in a generic desktop environment

Once Gamescope is started, get the DISPLAY variable for it and run as
`env -u WAYLAND_DISPLAY DISPLAY=:X discover-overlay --steamos`
Which will disallow it drawing to the outer desktop and instead connect to Gamescope 

## Installing

### Flatpak via Flathub

Visit our [Flathub page](https://flathub.org/apps/details/io.github.trigg.discover_overlay) or install via commandline

```bash
flatpak install io.github.trigg.discover_overlay
```

### Stable
```bash
python3 -m pipx install discover-overlay
```

### Latest Testing
```bash
git clone https://github.com/trigg/Discover.git
cd Discover
python3 -m pipx install .
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

A compositor is strongly advised but there is compatibility for X11 sessions without a compositor

It is advised to install python-gobject from your system's own package manager.

#### Debian/Ubuntu

`apt install python3-gi python3-gi-cairo libappindicator3-dev`

Libappindicator might conflict with other installed packages, but is optional

with Wayland support

`apt install gtk-layer-shell libgtk-layer-shell-dev`

#### Arch

`pacman -S python-gobject libappindicator-gtk3`

with Wayland support

`pacman -S gtk-layer-shell`

#### Fedora

`dnf install python3-pip python3-gobject gtk3-devel python3-cairo python-devel python-gobject python-gobject-devel`

with Wayland support

`dnf install gtk-layer-shell`

## Usage

Run `discover-overlay` to start the overlay. Note that by default it will show nothing until you join a voice channel.

Comes with sane-enough default but has a configuration screen to tweak to your own use. Configuration can be reached by running `discover-overlay --configure`

Desktop shortcuts for both of these are added at install time.

### Debugging

See [Wiki](https://github.com/trigg/Discover/wiki/Debugging)

### Translations

For [developers](https://github.com/trigg/Discover/wiki/Translations----as-a-developer) and [translators](https://github.com/trigg/Discover/wiki/Translations---as-a-translator-with-git) translation information can be found on our Wiki.

#### Incorrect translations and missing translations

We welcome pull requests and bug reports about missing or wrong translations, but don't have the resources to get it all right. Please be patient with us and alert us if any translations are wildly inaccurate.

## A note on terminology

I often use some terms interchangably:

Guild, Server : the leftmost pane in Discord.

Channel, Room, Chat: The next level in, these are all the same thing internally.

## Why do you keep making Discord Overlays?

I feel like I shouldn't have to at all! Until we get an official one I might just create a new one every few months. Look forward to Rust/Vulkan version coming in a few months. /s

### Are you serious?

Generally, no.

