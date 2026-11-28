#!/bin/bash
# HXLoLi-Music CDN 大文件切片脚本
#
# 将超过 19MB (jsDelivr 限制 20MB, 留余量) 的文件切片
# 生成 info.yaml + 分片文件到 cdn-split/ 目录
# 配合 HX-CDN-Forge 的 reqByCDN() 透明加载
#
# 用法:
#   cd HXLoLi-Music
#   bash scripts/cdn-split.sh
#
# 依赖: npx hx-cdn-split (来自 hx-cdn-forge 包)

set -e

THRESHOLD=$((19 * 1024 * 1024))  # 19MB
SPLIT_DIR="static/cdn/all"
STATIC_DIR="static"

echo "=== HXLoLi-Music CDN 大文件切片 ==="
echo ""

# 查找所有超过阈值的文件 (排除 cdn 产物目录)
# 文本文件 (.ass 等) 不切片: cdn-compress.sh 会给它们做 .gz (原大小的 1/10 到 1/5).
# hx-cdn-forge 的 reqByCDNAuto 先查切片再查预压缩, 有切片就下原文件, 28MB 的 kfx 歌词会比 .gz 慢好几倍.
TEXT_RE='\.(ass|ssa|srt|lrc|json|xml|txt|csv|html|css|js|svg)$'
find "$STATIC_DIR" -path "$STATIC_DIR/cdn" -prune -o -type f -size +${THRESHOLD}c -print | grep -v -i -E "$TEXT_RE" | while read -r file; do
    SIZE=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null)
    SIZE_MB=$(echo "scale=2; $SIZE / 1024 / 1024" | bc)
    echo "📦 发现大文件: $file (${SIZE_MB}MB)"
    echo "   正在切片到 $SPLIT_DIR/ ..."
    
    hx-cdn-split \
        --source "$file" \
        --output "$SPLIT_DIR" \
        --prefix "$STATIC_DIR" \
        --chunk-size 19MB
    
    echo ""
done

echo "✅ 切片完成!"
echo ""
echo "前端配置:"
echo "  splitStoragePath: 'static/cdn'"
echo "  mappingPrefix: '$STATIC_DIR'"
