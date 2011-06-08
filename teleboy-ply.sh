#!/bin/bash
# in $1 den rtmp link

CMD="$1"
NAME=$(echo "$CMD"|sed -e "s/.*\///g")

$CMD &

sleep 5
mplayer /tmp/$NAME
read x
