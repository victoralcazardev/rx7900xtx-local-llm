#!/usr/bin/env bash
# interleave two binaries: alt.sh <binA> <tagA> <binB> <tagB> <rounds>
for i in $(seq 1 $5); do ./loop.sh $1 1 $2 >/dev/null 2>&1; ./loop.sh $3 1 $4 >/dev/null 2>&1; done
for t in $2 $4; do echo "$t: $(grep -c ': ok' $t/summary.txt) ok, $(grep -c ': died' $t/summary.txt) died"; done
