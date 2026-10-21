#!/bin/bash
# usage: fetchday.sh YYYY-MM-DD outdir ; writes per-vessel summary for that day
d=$1; o=$2; y=${d:0:4}; f=AIS_${d//-/_}.zip
[ -s $o/$d.csv ] && exit 0
curl -s --retry 3 -m 900 -o $o/$f https://coast.noaa.gov/htdata/CMSP/AISDataHandler/$y/$f || exit 1
# columns: MMSI,BaseDateTime,LAT,LON,SOG,COG,Heading,VesselName,IMO,CallSign,VesselType,Status,Length,...
unzip -p $o/$f | awk -F, 'NR>1{k=$1; n[k]++; if(!(k in nm)){nm[k]=$8; ty[k]=$11; ln[k]=$13; la[k]=$3; lo[k]=$4}} END{for(k in n) print k","nm[k]","ty[k]","ln[k]","la[k]","lo[k]","n[k]}' > $o/$d.tmp && mv $o/$d.tmp $o/$d.csv
rm -f $o/$f
