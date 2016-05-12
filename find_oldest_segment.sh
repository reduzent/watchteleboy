#/bin/bash

url="$1"

function test_success {
  # Continue execution only if last command succeeded
  # ARG1: exit message
  # ARG2: optional exit code
  if [ "$?" -ne "0" ]
  then
    [ -z "$2" ] && local exitcode=1 || local exitcode=$2
    echo "$1" >&2
    exit $exitcode
  fi
  return 0
}

function fetch_url {
  # download url and print it to stdout, exit on failure
  # ARG1: URL
  local url="$1"
  local errormsg="could not download: $url"
  curl -fs "$url"
  local exitcode=$?
  test_success "$errormsg" $exitcode
  return 0
}

function hls_get_current_segment {
  # retrieve current segment of given stream variant.
  # the provided URL is expexted to be a valid index file
  # of a stream variant. the index number is printed
  # to stdout
  # ARG1: URL of stream variant index

  # get data
  local indexurl="$1"
  local raw="$(fetch_url "$indexurl")"
  test_success "could not download: $url" "$?"

  # validate data
  # check EXTM3U tag
  echo "$raw" | head -n1 | grep '^#EXTM3U$' > /dev/null
  test_success "not a valid playlist file"
  # extract current segment
  local current_segment="$(echo "$raw" | \
    sed '/#EXT-X-MEDIA-SEQUENCE/!d;
         /#EXT-X-MEDIA-SEQUENCE/s/#EXT-X-MEDIA-SEQUENCE://')"
  # validate segment
  [[ $current_segment =~ ^-?[0-9]+$ ]]
  test_success "could not extract current segment number"

  # return result
  echo "$current_segment"
  return 0
}

function hls_get_oldest_segment {
  # retrieve the oldest available segment of given stream variant
  # ARG1: URL of stream variant index
  
  # some vars
  local indexurl="$1"
  local baseurl="$(dirname "$url")"
  local ext="ts"
  local stepsize=1024
  
  # get current segment
  local current="$(hls_get_current_segment "$indexurl")"
  test_success "could not extract current segment"

  # go back in huge steps
  local oldest=$current
  while true
  do
    oldest=$((oldest - stepsize))
    curl -s -I -X HEAD "${baseurl}/${oldest}.${ext}" | \
      head -n1 | grep "HTTP/1.1 200 OK" > /dev/null || break
  done

  # narrow it down by halving stepsize on each iteration
  while [ "$stepsize" -gt "1" ]
  do
    stepsize=$(( stepsize / 2 ))
    curl -s -I -X HEAD "${baseurl}/${oldest}.${ext}" | \
      head -n1 | grep "HTTP/1.1 200 OK" > /dev/null && \
      oldest=$(( oldest - stepsize )) || \
      oldest=$(( oldest + stepsize ))
  done

  # return result
  echo "$oldest"
  return 0
}

current=$(hls_get_current_segment "$url")
oldest=$(hls_get_oldest_segment "$url")

echo "oldest $oldest"
echo "current: $current"
echo "deltaseconds: $(( (current - oldest) * 4 ))"
