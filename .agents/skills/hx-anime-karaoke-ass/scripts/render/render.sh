#!/usr/bin/env bash
# 渲染：把视频流、音频流、ASS 字幕轨、字体封装进一个 MKV（字幕外挂，不烧录）。
#
# 为什么是 MKV 外挂而不是 MP4 烧录：视频流 -c:v copy 原样封装，几分钟的 MV 从「编码几分钟」
# 变成「封装几秒」且画质零损失；字幕是可开关的字幕轨，改字幕只换轨；MKV 原生是字幕容器。
#
# 用法: render.sh <video> <ass> <fontsdir> <out.mkv> [ffmpeg=ffmpeg]
# 例:   bash render.sh proj/base.mp4 proj/out.ass fonts out.mkv
set -euo pipefail
V="$1"; A="$2"; F="$3"; O="$4"; FF="${5:-ffmpeg}"

case "$O" in
  *.mkv) ;;
  *) echo "[warn] 外挂字幕用 .mkv 更稳，当前输出名: $O" >&2 ;;
esac

# 字体作为附件：换机器播放时字幕不依赖系统装了什么字体。
# 每个附件必须带 mimetype，否则 matroska 拒绝写头（实测 "has no mimetype tag"）。
ATT=()
IDX=0
while IFS= read -r f; do
  case "${f,,}" in
    *.ttf) mt="font/ttf" ;;
    *.otf) mt="font/otf" ;;
    *.ttc) mt="font/collection" ;;
    *)     mt="application/octet-stream" ;;
  esac
  ATT+=(-attach "$f" -metadata:s:t:"$IDX" "mimetype=$mt" -metadata:s:t:"$IDX" "filename=$(basename "$f")")
  IDX=$((IDX + 1))
done < <(find "$F" -maxdepth 1 -type f \( -iname "*.ttf" -o -iname "*.otf" -o -iname "*.ttc" \) | sort)

if [ "$IDX" -eq 0 ]; then
  echo "[warn] $F 里没找到字体，不附字体  换机器可能缺字形" >&2
fi

# 全程 -c copy：视频/音频原样封装，字幕单独一轨，字体做附件
"$FF" -v error -y -i "$V" -i "$A" "${ATT[@]}" \
  -map 0:v:0 -map 0:a:0? -map 1:0 \
  -c:v copy -c:a copy -c:s copy \
  -metadata:s:s:0 language=jpn \
  -metadata:s:s:0 title="Karaoke (ASS)" \
  -disposition:s:0 default \
  "$O"

echo "rendered $O"
ffprobe -v error -show_entries stream=index,codec_type,codec_name -of csv=p=0 "$O" 2>/dev/null || true
