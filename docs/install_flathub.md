# Installing from FlatHub

## GUI

### Discover (KDE Package Manager)

Choose `Search` and type `Discover Overlay`. If you don't currently have Discord get that here too

### Gnome Software

Choose `Search` and type `Discover Overlay`. If you don't currently have Discord get that here too

## Terminal

### Enable Flathub

If your flatpak doesn't currently have flathub repository added, that's the first step

```
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
```

### Install Discover Overlay

```
flatpak install io.github.trigg.discover_overlay
```

if you don't currently have Discord you can get that with

```
flatpak install com.discordapp.Discord
```
