#!/bin/bash
################################################
# Bash script for watching/recording online TV streams from teleboy.ch without
# browser and =no f*** flash=.
#
# License:  GNU GPL v2
# Author:   Alexander Tuchacek
# written:  2011-05-21
# program version  1.0
################################################

USER="xxx"
PASS="xxx"

PROG="ard 111.stream
zdf 101.stream
3sat 141.stream
sf1 11.stream
sf2 81.stream
orf1 91.stream
orf2 291.stream
zdfneo 121.stream
atv 211.stream
ntv 401.stream
swr 541.stream
mdr 511.stream
ndr 521.stream
wdr 301.stream
rtl 51.stream
vox 131.stream
pro7 61.stream
sat1 71.stream
pro7 61.stream
"
p="3sat" # default chan

BROWSER='Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1'
SEND="login=$USER&password=$PASS&x=13&y=17&followup=%2Ftv%2Fplayer%2Fplayer.php"
URL="http://www.teleboy.ch/layer/rectv/free_live_tv.inc.php"
TMPPATTH="/tmp"

echo "login"
wget -U "$BROWSER" \
--quiet \
--no-check-certificate \
--save-cookies $TMPPATTH/cookiejar --keep-session-cookies \
--post-data $SEND \
-O $TMPPATTH/step1.html \
$URL

cat $TMPPATTH/step1.html | grep "Falsche Eingaben">/dev/null
if [ $? -eq 0 ] ; then
 echo "login faild!!!!"
 exit 0
else
 echo "login ok..." 
fi

echo "step 2: fun"
URL='http://www.teleboy.ch/tv/player/player.php'
wget -U "$BROWSER" \
--quiet \
--referer http://www.teleboy.ch/layer/rectv/free_live_tv.inc.php \
--load-cookies $TMPPATTH/cookiejar \
--save-cookies $TMPPATTH/cookiejar2 --keep-session-cookies \
-O $TMPPATTH/step2.html \
$URL

# loooooooooooooooooooooop
while true;do

echo "step 3 get rtmp session ids"
URL='http://www.teleboy.ch//tv/player/includes/ajax.php?'

SEND="cmd=getLiveChannelParams&cid=1&cid2=159" # sf1
SEND="cmd=getLiveChannelParams&cid=11&cid2=0" # ard
SEND="cmd=getLiveChannelParams&cid=10&cid2=0" # zdf
SEND="cmd=getLiveChannelParams&cid=8&cid2=108" # sf2
SEND="cmd=getLiveChannelParams&cid=14&cid2=0" # 3sat

wget -U "$BROWSER" \
--quiet \
--referer http://www.teleboy.ch/tv/player/player.php \
--load-cookies $TMPPATTH/cookiejar \
--save-cookies $TMPPATTH/cookiejar2 --keep-session-cookies \
--post-data $SEND \
-O $TMPPATTH/step3.html \
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
$TERM  -T "$p" -geometry 60x4 -e  $script "$DOIT" &

done

exit  1

