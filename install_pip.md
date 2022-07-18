# Installing Discover Overlay via Python PIP

- If you don't have it, [get PIP](https://pip.pypa.io/en/stable/installation/)
- run the command `python -m pip install discover-overlay`

## `command not found` and does not launch from icon

Most likely your `$HOME/.local/bin` is not included in your path.

Your options are to instead run it as `~/.local/bin/discover-overlay` or to add `$HOME/.local/bin` [to your PATH](https://www.howtogeek.com/658904/how-to-add-a-directory-to-your-path-in-linux/)

## Other notes

There is only access to stable releases via PIP, if you require latest versions for new features or bug testing see [our Github project](https://github.com/trigg/Discover)

This method does not come with Discord at all and that will need to be installed separately.
