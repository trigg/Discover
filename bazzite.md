# Congratulations

Bazzite has discover overlay installed by default

## Current state

For all variants of Bazzite there is some degree of support



| image | Support |  
| :------ | --------- |
| kde | Installed by default, Needs enabling |
| gnome | Installed by default, Needs enabling|       
| deck  | Installed & enabled by default        |        

## Enabling

### GUI

Launch `Discover Overlay Configure`

Choose `Core` tab

Tick `Run Overlay on Startup`

It will now start whenever you log in

### Terminal

edit `/etc/default/discover-overlay` as root

set the environment variables as needed
```
AUTO_LAUNCH_DISCOVER_OVERLAY=1
LAUNCH_DISCOVER_ON_GNOME_WAYLAND=0
```

The second environment option will try to force support for Gnome wayland. This may not work for everyone.