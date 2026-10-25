#!/usr/bin/env bash
# 烧录：libass 把 ASS 烙进画面 → x264 编码。用于不支持外挂字幕的场景
# （上传视频网站、发给只看 mp4 的人）。要外挂字幕用 render.sh（更快、无损）。
#
# 用法: render_burn.sh <video> <ass> <fontsdir> <out.mp4> [crf=16] [ffmpeg_sub=ffmpeg] [ffmpeg_enc=ffmpeg]
# 若同一个 ffmpeg 同时有 libass 和 libx264，两个参数填同一个即可；
# 否则“带 libass 的 ffmpeg 输出 rawvideo 管道 → 带 libx264 的 ffmpeg 编码”
# （常见于系统 ffmpeg 缺 x264 的环境）。
set -euo pipefail
V="$1"; A="$2"; F="$3"; O="$4"; CRF="${5:-16}"; FS="${6:-ffmpeg}"; FE="${7:-ffmpeg}"
"$FS" -v error -i "$V" -vf "subtitles=${A}:fontsdir=${F}" -pix_fmt yuv420p -f nut -c:v rawvideo -an - \
 | "$FE" -v error -y -f nut -i - -i "$V" -map 0:v -map 1:a -c:v libx264 -preset slow -crf "$CRF" -tune animation \
     -pix_fmt yuv420p -c:a aac -b:a 256k -movflags +faststart "$O"
echo "rendered $O"
