#!/bin/sh
# Sets the RX 7900 XTX (PCI 1002:744c) power cap at boot. Only writes within the driver's min..max range.
CAP_W=272
for dev in /sys/class/drm/card*/device; do
  [ "$(cat "$dev/vendor" 2>/dev/null)" = "0x1002" ] || continue
  [ "$(cat "$dev/device" 2>/dev/null)" = "0x744c" ] || continue
  for cap in "$dev"/hwmon/hwmon*/power1_cap; do
    [ -w "$cap" ] || continue
    dir=$(dirname "$cap"); want=$((CAP_W * 1000000))
    min=$(cat "$dir/power1_cap_min"); max=$(cat "$dir/power1_cap_max")
    if [ "$want" -ge "$min" ] && [ "$want" -le "$max" ]; then
      echo "$want" > "$cap" && echo "gpu-power-cap: $cap = $want"
    else
      echo "gpu-power-cap: $want outside [$min, $max], not applied" >&2
    fi
  done
done
