#/bin/bash
stream_url="$1"
stream_url_base="$(echo "$stream_url"  | \
  cut -d'/' -f-9)"
counter=$(wget -O - -q "$stream_url" | \
  grep "#EXT-X-MEDIA-SEQUENCE" | \
  cut -d':' -f2
  )
stream_start_time=$(date +%s)
while wget "${stream_url_base}/${counter}.ts"
do
  cat ${counter}.ts >> stream.m2t
  rm ${counter}.ts
  ((counter+=1))
done
