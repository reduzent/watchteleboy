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
  # ARG1: url of stream variant
  # ARG2: time (as understood by 'date')
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

function hls_select_variant_url {
  # print url of selected variant
  # ARG1: index of variant
  local index="$1"
  local count=${#HLS_VARIANTS[@]}

  # do we have variants?
  [ "$count" -gt "0" ]
  test_success "no variants found"

  # validate given index
  [ "$index" -le "$count" ] && [ "$1" -ge "1" ]
  test_success "selected variant not in range 1 to $count"

  # return result
  echo "${HLS_VARIANTS[$index]}" | cut -d" " -f2
  return 0
}

function hls_select_variant_bitrate {
  # print bitrate of selected variant
  # ARG1: index of variant
  local index="$1"
  local count=${#HLS_VARIANTS[@]}

  # do we have variants?
  [ "$count" -gt "0" ]
  test_success "no variants found"

  # validate given index
  [ "$index" -le "$count" ] && [ "$1" -ge "1" ]
  test_success "selected variant not in range 1 to $count"

  # return result
  echo "${HLS_VARIANTS[$index]}" | cut -d" " -f1
  return 0
}

function hls_download_variant {
  # download given stream variant to file, starting from given time
  # ARG1: url of stream variant
  # ARG2: file to write stream into
  # ARG3: start time (as understood by 'date') [optional]
  # ARG4: end time [optional]
  local url="$1"
  local url_base="$(dirname "$url")"
  local file="$2"
  [ -z "$3" ] && local time_start="now" || local time_start="$3"
  # if no time_stop is given, default it to 6 hours after time_start
  local time_stop_default="@$(( $(date +%s -d"$time_start") + 21600))"
  [ -z "$4" ] && local time_stop="$time_stop_default" || local time_stop="$4"
  local ext="ts"

  # check if time_stop is after time_start
  [ "$(date +%s -d"$time_stop")" -gt "$(date +%s -d"$time_start")" ]
  test_success "given stop time is before start time"

  # get start and stop segment
  local segment=$(hls_get_segment_of_time "$url" "$time_start")
  test_success "could not extract start segment"
  local segment_stop=$(hls_get_segment_of_time "$url" "$time_stop")
  test_success "could not extract stop segment"

  # get ref time and ref segment
  # to make sure not to download from the future
  local segment_current=$(hls_get_current_segment "$url")
  local segment_ref=$((segment_current + 3))
  local time_ref=$(date +%s)

  # now do it
  local sleep=0
  > "$file" 2> /dev/null
  test_success "cannot create file: $file"
  while sleep $sleep
  do
    curl -fs "${url_base}/${segment}.${ext}" >> "$file" || \
      echo "segment $segment not available" 1>&2
    [ "$segment" -lt "$segment_stop" ] || break
    local time_current=$(date +%s)
    local time_delta=$((time_current - time_ref))
    local segment_delta=$((segment - segment_ref))
    [ "$segment_delta" -gt "0" ] || segment_delta=0
    sleep=$(( 4 + (4 * segment_delta) - time_delta))
    [ "$sleep" -gt "0" ] || sleep=0
    ((segment+=1))
  done
}
