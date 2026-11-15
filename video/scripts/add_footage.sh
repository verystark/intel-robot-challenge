#!/usr/bin/env bash
# Add a clip as a shot of the video: converts it to constant 30 fps H.264 (phones record a variable
# frame rate) and rebuilds the video's data.
#   video/scripts/add_footage.sh a1 ~/video-raw/round3/IMG_1234.MOV
# Shot IDs: a1 (the run, wide), a2 (close on inspection and plates), a3 (screen recording),
# a4 (a round being set up), b1-b3 (B-roll). See VIDEO_PLAN.md section 6.
set -euo pipefail
id="${1:?shot id, e.g. a1}"
src="${2:?input clip}"
here="$(cd "$(dirname "$0")/.." && pwd)"
dest="$here/public/footage/$id.mp4"
nice -n 10 ffmpeg -hide_banner -loglevel error -y -i "$src" \
  -vf "fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart "$dest"
echo "wrote $dest ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$dest" | cut -d. -f1) s)"
python3 "$here/scripts/build_data.py" | tail -2
