#!/bin/bash
################################################
# Bash script for watching/recording online TV streams from teleboy.ch without
# browser and =no f*** flash=.
#
# License:  GNU GPL v2
# Author:   Alexander Tuchacek
# written:  2011-05-21
# modified by: Roman Haefeli
# modified on: 2011-06-08
# program version  1.1~unreleased
################################################

# Set some default variables
USER="xxx"
PASS="xxx"
TMPPATH=/tmp/watchteleboy
UAGENT='Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1'

# Read config
CONFIG=~/.watchteleboyrc
if [ -f $CONFIG ]
then
  . $CONFIG
fi

# Create TMPDIR if required
if  [ ! -d $TMPPATH ]
then
  mkdir -p $TMPPATH
fi

# Channel list
PROG="ard 111.stream
zdf 101.stream
arte 1611.stream
3sat 141.stream
sf1 11.stream
sf2 81.stream
sfinfo 241.stream
orf1 91.stream
orf2 291.stream
zdfneo 121.stream
atv 211.stream
ntv 401.stream
euronews 2161.stream
phoenix 531.stream
sport1 331.stream
eurosport 391.stream
swr 541.stream
mdr 511.stream
ndr 521.stream
wdr 301.stream
rtl 51.stream
rtl2 321.stream
superrtl 351.stream
vox 131.stream
pro7 61.stream
sat1 71.stream
kabel1 311.stream
dasvierte 1721.stream
dmax 151.stream
3plus 1701.stream
telezueri 1971.stream
nickelodeon 221.stream
deluxe 1921.stream
viva 171.stream
joiz 5011.stream
"

p="3sat" # default chan

function login {
  # usage: getcookies USER PASS
  SEND="login=$1&password=$2&x=13&y=17&followup=%2Ftv%2Fplayer%2Fplayer.php"
  URL="http://www.teleboy.ch/layer/rectv/free_live_tv.inc.php"
  wget -U "$UAGENT" \
    --quiet \
    --no-check-certificate \
    --save-cookies $TMPPATH/cookiejar --keep-session-cookies \
    --post-data $SEND \
    -O $TMPPATH/step1.html \
    $URL
  cat $TMPPATH/step1.html | grep "Falsche Eingaben">/dev/null
  if [ $? -eq 0 ]
  then
    echo "login failed!!!!"
    exit 0
  else
    echo "login ok..." 
  fi
}

function session {
  URL='http://www.teleboy.ch/tv/player/player.php'
  wget -U "$UAGENT" \
    --quiet \
    --referer http://www.teleboy.ch/layer/rectv/free_live_tv.inc.php \
    --load-cookies $TMPPATH/cookiejar \
    --save-cookies $TMPPATTH/cookiejar2 -\
    --keep-session-cookies \
    -O $TMPPATH/step2.html \
    $URL
}

echo "Login..."
login $USER $PASS
echo "Establish Session..."
session


# loooooooooooooooooooooop
while true;do

echo "step 3 get rtmp session ids"
URL='http://www.teleboy.ch//tv/player/includes/ajax.php?'

SEND="cmd=getLiveChannelParams&cid=1&cid2=159" # sf1
SEND="cmd=getLiveChannelParams&cid=11&cid2=0" # ard
SEND="cmd=getLiveChannelParams&cid=10&cid2=0" # zdf
SEND="cmd=getLiveChannelParams&cid=8&cid2=108" # sf2
SEND="cmd=getLiveChannelParams&cid=14&cid2=0" # 3sat

wget -U "$UAGENT" \
--quiet \
--referer http://www.teleboy.ch/tv/player/player.php \
--load-cookies $TMPPATTH/cookiejar \
--save-cookies $TMPPATTH/cookiejar2 --keep-session-cookies \
--post-data $SEND \
-O $TMPPATH/step3.html \
$URL

ch=$(cat /tmp/step3.html | cut -d "|" -f1)
app=$(cat /tmp/step3.html | cut -d "|" -f2)
c1=$(cat /tmp/step3.html | cut -d "|" -f3)
c2=$(cat /tmp/step3.html | cut -d "|" -f4)
c3=$(cat /tmp/step3.html | cut -d "|" -f5)
c4=$(cat /tmp/step3.html | cut -d "|" -f6)
c5=$(cat /tmp/step3.html | cut -d "|" -f7)
c6=$(cat /tmp/step3.html | cut -d "|" -f8)

echo "*************** $p *************************"
#ch=$(echo "$ch"|sed -e "s/ /_/")

echo "channels............"
echo "$PROG"|cut -d " " -f 1|tr "\n" " "
echo ""

read -p "TV Channel (default is $p): " -e t1
if [ -n "$t1" ]
then
  p="$t1"
fi

playpath=$(echo "$PROG" | grep "^$p" | head -n1|cut -d " " -f 2)
#echo $playpath

DOIT="rtmpdump -r rtmp://62.65.136.20/nellotv -a $app -f LNX 10,3,181,14 -W http://www.teleboy.ch/tv/player/includes/flash/flashplayer_cinergy_v1_1_6.swf -p http://www.teleboy.ch/tv/player/player.php -C S:$c1 -C S:$c2 -C S:$c3 -C S:$c4 -C S:$c5 -C S:$c6 -y $playpath -o /tmp/$p.flv"

echo "$DOIT"
#$DOIT

# run player in seperate process 
TERM=xterm
P=$(dirname $0)
script=$P/teleboy-ply.sh
#$TERM  -T "$p" -geometry 60x4 -e  $script "$DOIT" &

done

exit  1

