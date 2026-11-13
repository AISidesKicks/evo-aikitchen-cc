#!/usr/bin/env bash
# Compress the hero image for the web, once.
#
# The original poster was 2752x1536 and 2.4 MB, which is twenty times larger than
# the page needs. 1600px wide keeps the smallest label legible at normal zoom.
# Re-running is a no-op once the image is already small, because re-encoding a
# JPEG loses quality for nothing.

set -eu

image="docs/EVO.jpeg"
target_width=1600
quality=4

width=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$image")

if [ "$width" -le "$target_width" ]; then
    echo "$image is already ${width}px wide"
    exit 0
fi

before=$(du -h "$image" | cut -f1)
ffmpeg -y -v error -i "$image" -vf "scale=${target_width}:-2:flags=lanczos" -q:v "$quality" "$image.tmp"
mv "$image.tmp" "$image"
after=$(du -h "$image" | cut -f1)
echo "compressed $image from $before to $after at ${target_width}px"
