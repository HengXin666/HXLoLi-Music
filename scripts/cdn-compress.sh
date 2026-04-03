#!/bin/bash
# HXLoLi-Music CDN 文本文件预压缩脚本
#
# 对文本类文件 (如 .ass 字幕) 进行 gzip 预压缩
# 生成 .gz 文件 + info-zip.yaml, 配合 HX-CDN-Forge 的 reqByCDNAuto()
# 实现「预压缩 + Range 并行下载 + 客户端 DecompressionStream 解压」
#
# 与 cdn-split.sh 互补:
#   - cdn-split.sh:    处理超过 19MB 的大文件 (切片), 输出到 static/cdn/all
#   - cdn-compress.sh: 处理文本文件 (预压缩), 输出到 static/cdn/gzip
#   - 文本文件无论大小都应该走预压缩 (压缩率远优于切片)
#   - reqByCDNAuto 优先检查 info.yaml (切片), 再检查 info-zip.yaml (压缩)
#     因此如果同一文件同时有切片和压缩, 压缩会被优先使用 — 不对, 切片优先
#     但文本文件压缩后通常远小于切片阈值, 不需要切片
#
# 用法:
#   cd HXLoLi-Music
#   bash scripts/cdn-compress.sh
#
# 依赖: hx-cdn-compress (来自 hx-cdn-forge 包)

set -e

COMPRESS_DIR="static/cdn/gzip"
STATIC_DIR="static"

# 文本文件扩展名 (适合预压缩的类型)
TEXT_EXTENSIONS="ass ssa srt lrc json xml txt csv html css js svg"

# 最小文件大小 (低于此值不值得预压缩, 因为 CDN 自动 gzip 已足够)
# 100KB — 小于 100KB 的文本文件走 direct 模式 CDN gzip 即可
MIN_SIZE=$((100 * 1024))

echo "=== HXLoLi-Music CDN 文本文件预压缩 ==="
echo ""
echo "  输出: ${COMPRESS_DIR}"
echo "  目标: 文件大小 > ${MIN_SIZE} bytes 的文本文件"
echo "  扩展名: ${TEXT_EXTENSIONS}"
echo ""

COMPRESSED_COUNT=0
SKIPPED_COUNT=0

# 构建 find 的 -name 条件
FIND_ARGS=""
for ext in $TEXT_EXTENSIONS; do
    if [ -n "$FIND_ARGS" ]; then
        FIND_ARGS="$FIND_ARGS -o"
    fi
    FIND_ARGS="$FIND_ARGS -name *.${ext}"
done

# 查找符合条件的文本文件
eval "find \"$STATIC_DIR\" -type f \\( $FIND_ARGS \\)" | while read -r file; do
    SIZE=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null)

    # 跳过太小的文件
    if [ "$SIZE" -lt "$MIN_SIZE" ]; then
        continue
    fi

    SIZE_KB=$(echo "scale=1; $SIZE / 1024" | bc)
    echo "🗜️  预压缩: $file (${SIZE_KB}KB)"

    hx-cdn-compress \
        --source "$file" \
        --output "$COMPRESS_DIR" \
        --prefix "$STATIC_DIR" \
        --encoding gzip \
        --level 9

    COMPRESSED_COUNT=$((COMPRESSED_COUNT + 1))
    echo ""
done

echo "✅ 预压缩完成! (共 ${COMPRESSED_COUNT} 个文件)"
echo ""
echo "前端配置:"
echo "  splitStoragePath: 'static/cdn/all'"
echo "  preCompressionStoragePath: 'static/cdn/gzip'"
echo "  mappingPrefix: '$STATIC_DIR'"
echo "  enablePreCompression: true"
