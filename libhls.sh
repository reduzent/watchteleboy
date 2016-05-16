function printerr {
  # print error message to stderr
  # ARG1: error message
  echo "$1" >&2
  return 0
}

function fetch_url {
  # download url and print it to stdout, exit on failure
  # ARG1: URL
  local url="$1"
  local errormsg="could not download: $url"
  curl -fs "$url" \
    || { printerr "$errormsg"; return 1; }
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
  local raw="$(fetch_url "$indexurl")" \
    || { printerr "could not download: $url"; return 1; }

  # validate data
  # check EXTM3U tag
  echo "$raw" | head -n1 | grep '^#EXTM3U$' > /dev/null \
    || { printerr "not a valid playlist file"; return 1; }
  # extract current segment
  local current_segment="$(echo "$raw" | \
    sed '/#EXT-X-MEDIA-SEQUENCE/!d;
         /#EXT-X-MEDIA-SEQUENCE/s/#EXT-X-MEDIA-SEQUENCE://')"
  # validate segment
  [[ $current_segment =~ ^-?[0-9]+$ ]] \
    || { printerr "could not extract current segment number"; return 1; }

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
  local current="$(hls_get_current_segment "$indexurl")" \
    || { printerr "could not extract current segment"; return 1; }

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
  segment_now=$((segment_now + 3)) \
    || { printerr "could not extract current segment"; return 1; }

  # set time
  local time_now=$(date +%s)
  local time_then=$(date +%s -d "$time_given")

  # deltas
  local time_delta=$((time_now - time_then))
  local segment_delta=$(((time_delta + 4) / 4))
  local segment_then=$((segment_now - segment_delta))

  # check if segment_then is available (only if it's from the past)
  if [ "$time_then" -lt "$time_now" ]
  then
    curl -sf -I -X HEAD "${baseurl}/${segment_then}.${ext}" > /dev/null \
      || { printerr "requested time is too far in the past: $time_given"; return 1; }
  fi

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
  local raw="$(curl -fs "$master_url")" \
    || { printerr "could not download: $master_url"; return 1; }

  # verify data
  echo "$raw" | head -n1 | grep '^#EXTM3U$' > /dev/null \
    || { printerr "not a valid playlist file"; return 1; }

  # create array HLS_VARIANTS
  eval $(\
    echo "$raw" | \
    sed -n '/#EXTM3U/d;/^#EXT-X-STREAM-INF/{s/.*,BANDWIDTH=//};N;s/\n/ /;P' | \
    sort -n | \
    sed '=' | \
    sed -n 'N;s/\n/ /;s/^/HLS_VARIANTS[/;s/ /]="/;s/$/"/;P')

  # verify array
  if [ "${#HLS_VARIANTS[@]}" -eq "0" ]
  then
    printerr "could not extract variants from master playlist"
    return 1
  fi
  return 0
}

function hls_select_variant_url {
  # print url of selected variant
  # ARG1: index of variant
  local index="$1"
  local count=${#HLS_VARIANTS[@]}

  # do we have variants?
  if [ "$count" -eq "0" ]
  then
    printerr "no variants found"
    return 1
  fi

  # validate given index
  if [ "$index" -gt "$count" ] || [ "$index" -lt "1" ]
  then
    printerr "selected variant not in range 1 to $count"
    return 1
  fi

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
  if [ "$count" -eq "0" ]
  then
    printerr "no variants found"
    return 1
  fi

  # validate given index
  if [ "$index" -gt "$count" ] || [ "$index" -lt "1" ]
  then
    printerr "selected variant not in range 1 to $count"
    return 1
  fi

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
  if [ "$(date +%s -d"$time_stop")" -le "$(date +%s -d"$time_start")" ]
  then
    printerr "given stop time is before start time"
    return 1
  fi

  # get start and stop segment
  local segment=$(hls_get_segment_of_time "$url" "$time_start") \
    || { printerr "could not extract start segment"; return 1; }
  local segment_stop=$(hls_get_segment_of_time "$url" "$time_stop") \
    || { printerr "could not extract stop segment"; return 1; }

  # get ref time and ref segment
  # to make sure not to download from the future
  local segment_current=$(hls_get_current_segment "$url")
  local segment_ref=$((segment_current + 3))
  local time_ref=$(date +%s)

  # now do it
  local sleep=0
  > "$file" 2> /dev/null \
    || { printerr "cannot create file: $file"; return 1; }
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
