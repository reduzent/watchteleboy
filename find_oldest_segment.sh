#/bin/bash

# curl -I -X HEAD http://62.65.140.218/session/90b5988a-17bf-11e6-9eb8-005056bc1a52/nvnv5a/1/1118/2290000/1439261476.ts

url="$1"
current=$(curl -s $url | \
  sed '/#EXT-X-MEDIA-SEQUENCE/!d;/#EXT-X-MEDIA-SEQUENCE/s/#EXT-X-MEDIA-SEQUENCE://')
oldest=$current
baseurl="http://62.65.140.218/session/90b5988a-17bf-11e6-9eb8-005056bc1a52/nvnv5a/1/1118/2290000"
ext="ts"
stepsize=1024

while true
do
  oldest=$(( oldest - stepsize))
  curl -s -I -X HEAD "${baseurl}/${oldest}.${ext}" | \
    head -n1 | grep "HTTP/1.1 200 OK" > /dev/null || break
done

while [ "$stepsize" -gt "1" ]
do
  stepsize=$(( stepsize / 2 ))
  curl -s -I -X HEAD "${baseurl}/${oldest}.${ext}" | \
    head -n1 | grep "HTTP/1.1 200 OK" > /dev/null && \
    oldest=$(( oldest - stepsize )) || \
    oldest=$(( oldest + stepsize ))
  echo "try next: $oldest"
done


echo "oldest $oldest"
echo "current: $current"
echo "deltaseconds: $(( (current - oldest) * 4 ))"
