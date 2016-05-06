#/bin/bash
master_playlist_url="$1"

function mpl_extract_variants {
# creates an array of 'bitrate url' values
# ARG1: url of master playlist
  unset variants
  eval $(\
    wget --quiet --output-document - "$1" | \
   sed -n '/#EXTM3U/d;/^#EXT-X-STREAM-INF/{s/.*,BANDWIDTH=//};N;s/\n/ /;P' | \
   sort -n | \
   sed '=' | \
   sed -n 'N;s/\n/ /;s/^/variants[/;s/ /]="/;s/$/"/;P'\
   )
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
