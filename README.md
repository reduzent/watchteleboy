watchteleboy
============

is a script to watch and record IPTV streams from http://www.teleboy.ch
while leaving out unskippable ads and other browser annoyances. It uses
the highly configurable mpv media player for playback. By using a custom
MPEG-DASH implementation, it allows access to the cached media segments
and thus plays up to 3 hours old content (depending on how long
segments are cached on cdn servers).

This is a complete rewrite in Python of the original script written in Bash.
The new Python version is not yet that mature, but already usable. Teleboy's
switch from Apple HLS to MPEG-DASH triggered the rewrite.

The script comes with an intuitive terminal user interface that gives
access to different video qualities and audio languages.

The code is hosted at:
http://github.com/reduzent/watchteleboy


Copyright: Roman Haefeli, 2011 - 2020
License:   GPL-2


Requirements
------------

This script requires a Python 3 flavour and the following modules:

* **python-crontab**
* **python-requests**
* **python-urwid**

For playback, you also require:

* **mpv**

For merging a recording's audio and video files into a single mkv file,
you need also:

* **ffmpeg**


Usage
-----

Do `watchteleboy --help` in order to get a quick summary of the available
options.


Bugs
----

Please report bugs and feature requests to GitHub by opening
an issue on https://www.github.com/reduzent/watchteleboy .

#### HAVE FUN!

