#/bin/bash

# curl -I -X HEAD http://62.65.140.218/session/90b5988a-17bf-11e6-9eb8-005056bc1a52/nvnv5a/1/1118/2290000/1439261476.ts

function test_success {
  # Continue execution only if last command succeeded
  # ARG1: exit message
  # ARG2: optional exit code
  [ -z "$2" ] && local exitcode=1 || local exitcode=$2
  if [ "$?" -ne "0" ]
  then
    echo "$1" >&2
    exit $exitcode
  fi
}

function fetch_url {
  # download url and print it to stdout, but exit when it fails
  # ARG1: URL
  # ARG2: error message printed to stdout (optional)
  local url="$1"
  local errormsg="$2"
  curl -ifs "$url"
  local exitcode=$?
  if [ "$exitcode" -ne "0" ]
  then
    echo "exitcode: $exitcode"
    [ -z "$2" ] || echo "$errormsg" >&2
    exit $exitcode
  fi
}

url="$1"

fetch_url "$url"

exit 0
current=$(fetch_url "$url" | \
  sed '/#EXT-X-MEDIA-SEQUENCE/!d;/#EXT-X-MEDIA-SEQUENCE/s/#EXT-X-MEDIA-SEQUENCE://')

oldest=$current
baseurl="$(dirname "$url")"
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
