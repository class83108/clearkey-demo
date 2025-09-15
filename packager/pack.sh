#!/usr/bin/env bash
set -euo pipefail
IN="/work/input/input.mp4"; OUT="/work/out"
KID_HEX="${KID_HEX:?}"; KEY_HEX="${KEY_HEX:?}"
mkdir -p "$OUT"

# 先試視訊+音訊
set +e
packager \
  "input=$IN,stream=video,segment_template=$OUT/video_\$Number\$.m4s,init_segment=$OUT/video_init.mp4,drm_label=SD" \
  "input=$IN,stream=audio,segment_template=$OUT/audio_\$Number\$.m4s,init_segment=$OUT/audio_init.mp4,drm_label=AUDIO" \
  --enable_raw_key_encryption \
  --keys "label=SD:key_id=$KID_HEX:key=$KEY_HEX,label=AUDIO:key_id=$KID_HEX:key=$KEY_HEX" \
  --protection_scheme=cenc \
  --generate_static_live_mpd \
  --mpd_output="$OUT/stream.mpd"
rc=$?
set -e

# 落到只有視訊（來源沒有音軌時）
if [[ $rc -ne 0 ]]; then
  packager \
    "input=$IN,stream=video,segment_template=$OUT/video_\$Number\$.m4s,init_segment=$OUT/video_init.mp4" \
    --enable_raw_key_encryption \
    --keys "label=:key_id=$KID_HEX:key=$KEY_HEX" \
    --protection_scheme=cenc \
    --generate_static_live_mpd \
    --mpd_output="$OUT/stream.mpd"
fi
echo "OK -> $OUT/stream.mpd"