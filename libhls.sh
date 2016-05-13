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
  local baseurl="$(dirname "$indexurl")"
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
    curl -fs -I -X HEAD "${baseurl}/${oldest}.${ext}" > /dev/null || break
  done

  # narrow it down by halving stepsize on each iteration
  while [ "$stepsize" -gt "1" ]
  do
    stepsize=$(( stepsize / 2 ))
    curl -fs -I -X HEAD "${baseurl}/${oldest}.${ext}" > /dev/null && \
      oldest=$(( oldest - stepsize )) || \
      oldest=$(( oldest + stepsize ))
  done

  # return result
  echo "$oldest"
  return 0
}

function hls_get_segment_of_time {
  # find segment from given time
  # ARG1: url of stream variant index
  # ARG1: time (as understood by 'date')
  local indexurl="$1"
  local time_given="$2"
  local baseurl="$(dirname "$indexurl")"
  local ext="ts"

  # get current segment
  local segment_now=$(hls_get_current_segment "$1")
  segment_now=$((segment_now + 3))
  test_success "could not extract current segment"

  # set time
  local time_now=$(date +%s)
  local time_then=$(date +%s -d "$time_given")

  # deltas
  local time_delta=$((time_now - time_then))
  local segment_delta=$(((time_delta + 4) / 4))
  local segment_then=$((segment_now - segment_delta))

  # check if segment_then is available
  curl -sf -I -X HEAD "${baseurl}/${segment_then}.${ext}" > /dev/null
  test_success "requested time is too far in the past"

  # return result
  echo "$segment_then"
  return 0
}

function hls_extract_variants {
  # creates an array HLS_VARIANTS with 'bitrate url' values
  # ARG1: url of master playlist
  local master_url="$1"
  unset HLS_VARIANTS
  
  # get data
  local raw="$(curl -fs "$master_url")"
  test_success "could not download: $master_url"

  # verify data
  echo "$raw" | head -n1 | grep '^#EXTM3U$' > /dev/null
  test_success "not a valid playlist file"

  # create array HLS_VARIANTS
  eval $(\
    echo "$raw" | \
    sed -n '/#EXTM3U/d;/^#EXT-X-STREAM-INF/{s/.*,BANDWIDTH=//};N;s/\n/ /;P' | \
    sort -n | \
    sed '=' | \
    sed -n 'N;s/\n/ /;s/^/HLS_VARIANTS[/;s/ /]="/;s/$/"/;P')

  # verify array
  [ "${#HLS_VARIANTS[@]}" -gt "0" ]
  test_success "could not extract variants from master playlist"

  return 0
}

function mpl_select_variant {
# print url of selected variant
# ARG1: index of variant
  if [ "$1" -gt "${#variants[@]}" ] || [ "$1" -lt "1" ]
  then
    echo "No such variant. The range is 1 to ${#variants[@]}"
    return 1
  fi
  echo ${variants[$1]} | cut -d" " -f2
}

function bla {
# create the array of variants
mpl_extract_variants "$master_playlist_url"

# select the one with the highest index (~ highest bitrate)
stream_url=$(mpl_select_variant ${#variants[@]})
stream_url_base="$(dirname $stream_url)"
stream_start_segment=$(wget -O - -q "$stream_url" | \
  grep "#EXT-X-MEDIA-SEQUENCE" | \
  cut -d':' -f2
  )
stream_ref_segment=$((stream_start_segment+3))
stream_current_segment=$stream_start_segment
stream_ref_time=$(date +%s)
while wget "${stream_url_base}/${stream_current_segment}.ts"
do
  time_current=$(date +%s)
  time_delta=$((time_current-stream_ref_time))
  echo "time_delta: $time_delta"
  segment_delta=$((stream_current_segment-stream_ref_segment))
  echo "segment_delta: $segment_delta"
  # set 0 if negative
  [ "$segment_delta" -gt "0" ] || segment_delta=0
  echo "segment_delta: $segment_delta"
  seconds_to_wait=$(( 2 + 4 * segment_delta - time_delta))
  [ "$seconds_to_wait" -gt "0" ] || seconds_to_wait=0 
  stream_current_file=${stream_current_segment}.ts
  cat $stream_current_file >> stream.m2t
  rm $stream_current_file
  echo "==== WAIT $seconds_to_wait SECONDS ======="
  sleep "$seconds_to_wait"
  ((stream_current_segment+=1))
done
}
