watchteleboy
============

is a script to watch and record live TV streams from
http://www.teleboy.ch without browser nor flash.

THIS MOST LIKELY WORKS ONLY FROM SWITZERLAND, SINCE THE IPTV SERVICE
FROM TELEBOY.CH IS ONLY AVAILABLE TO SWISS IP ADDRESSES.

see: http://github.com/reduzent/watchteleboy

Copyright: Roman Haefeli, 2011 - 2017

License:   GPL-2


News
----

Since version 1.21 there is no need to have avconv installed anymore. Instead, the
HLS stream receiver is implemented in bash with curl. By not sticking strictly to
the HLS protocol, `watchteleboy` now is able to watch shows up to 6 hours after their
air time. Just use the option --starttime when you want to watch a missed show.


Requirements
------------

This script is based on the following binary programs (make sure
you have them installed):

* One of the following media players:

  * **mpv** (recommended on most Linux systems)
  * **mplayer** (if mpv is not available)
  * **vlc** (not well tested)

* **crontab**
* **date**
* **jq** - JSON processor for the cmdline
* **curl**
* **whiptail** (optional, used for 'nice' dialogs)


Installation
------------
### Ubuntu
1. Install reduzent's ppa:

   `sudo apt-add-repository ppa:reduzierer/reduzent`

2. `sudo apt update`
3. `sudo apt install watchteleboy`

### Debian
1. Download latest [release](https://github.com/reduzent/watchteleboy/releases/latest) as .deb-file
2. Install it by doing:

   `gdebi watchteleboy_<version>_all.deb`

### macOS
`brew install reduzent/reduzent/watchteleboy`

Usage
-----

Do `watchteleboy --help` in order to get a quick summary of the available
options. When invoked without options it starts in interactive mode.
`man watchteleboy` shows the full documentation of all commandline flags
and configuration file options.


Bugs
----

Please report bugs and feature requests to GitHub by opening
an issue on https://www.github.com/reduzent/watchteleboy .

#### HAVE FUN!

