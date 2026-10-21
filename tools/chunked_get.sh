#!/bin/bash
# Download a large file in 2 MB ranges with retries (the NRC server drops long transfers).
# usage: chunked_get.sh URL OUTFILE
url=$1; out=$2; tmp=$out.parts; mkdir -p $tmp
size=$(curl -s -m 60 -r 0-0 -D - -o /dev/null "$url" | grep -i "^content-range" | sed "s|.*/||" | tr -dc 0-9)
[ -z "$size" ] && { echo "no size for $url"; exit 1; }
cs=2000000; n=$(( (size + cs - 1) / cs ))
for ((i=0;i<n;i++)); do
  s=$((i*cs)); e=$((s+cs-1)); [ $e -ge $size ] && e=$((size-1))
  want=$((e-s+1)); f=$tmp/$(printf %04d $i)
  for a in 1 2 3 4 5 6; do
    [ -f $f ] && [ $(stat -c %s $f) -eq $want ] && break
    curl -s -m 120 -r $s-$e -o $f "$url"; sleep 1
  done
  [ $(stat -c %s $f 2>/dev/null || echo 0) -eq $want ] || { echo "chunk $i failed"; exit 1; }
done
cat $tmp/* > $out && rm -rf $tmp && echo "ok $out $size"
