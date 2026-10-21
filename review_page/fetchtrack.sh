#!/bin/bash
# usage: fetchtrack.sh YYYY-MM-DD "NAME1|NAME2" ; keeps all rows whose VesselName matches
d=$1; pat=$2; y=${d:0:4}; f=AIS_${d//-/_}.zip
curl -s --retry 3 -m 900 -o demo/$f https://coast.noaa.gov/htdata/CMSP/AISDataHandler/$y/$f || exit 1
unzip -p demo/$f | head -1 > demo/$d.tracks.csv
unzip -p demo/$f | grep -E ",($pat)," >> demo/$d.tracks.csv
rm -f demo/$f
