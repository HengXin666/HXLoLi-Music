# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载本 skill 需要的字体到 <skill>/fonts/。

字体不进 git（体积大且都是 OFL），用这个脚本重建。已存在的文件会跳过。
用法:
  hx-karaoke fetch_fonts.py                 # 装到 <skill>/fonts/
  hx-karaoke fetch_fonts.py --out /tmp/f    # 装到别处
  hx-karaoke fetch_fonts.py --only LXGWWenKai-Medium.ttf ShipporiMinchoB1-Bold.ttf
"""
import argparse, os, sys, urllib.request

UA = "curl/8"  # Google Fonts 对现代 UA 返回 woff2 分片; 这个 UA 让它返回完整 .ttf 直链

# 日文正文 / 注音 用 Shippori Mincho B1（B1 是屏幕显示优化版，注音小字更清晰）
# 中文翻译用霞鹜文楷；圆体/元气的歌换 Mochiy Pop One + 站酷快乐体；拉丁用 Cormorant Garamond Italic
SOURCES = {
    "ShipporiMinchoB1-Bold.ttf": "https://fonts.gstatic.com/s/shipporiminchob1/v24/wXK1E2wCr44tulPdnn-xbIpJ9RgT9-nKMo9P3g.ttf",
    "ShipporiMincho-Bold.ttf": "https://fonts.gstatic.com/s/shipporimincho/v17/VdGDAZweH5EbgHY6YExcZfDoj0B4Z9Cm5A.ttf",
    "MochiyPopOne-Regular.ttf": "https://fonts.gstatic.com/s/mochiypopone/v12/QdVPSTA9Jh-gg-5XZP2UmU4O9kww.ttf",
    "ZCOOLKuaiLe-Regular.ttf": "https://fonts.gstatic.com/s/zcoolkuaile/v22/tssqApdaRQokwFjFJjvM6h2Wpg.ttf",
    "CormorantGaramond-Italic[wght].ttf": "https://fonts.gstatic.com/s/cormorantgaramond/v21/co3smX5slCNuHLi8bLeY9MK7whWMhyjYrGFEsdtdc62E6zd58jDOjw.ttf",
    "CormorantGaramond-Light.ttf": "https://fonts.gstatic.com/s/cormorantgaramond/v21/co3umX5slCNuHLi8bLeY9MK7whWMhyjypVO7abI26QOD_qE6GnM.ttf",
    "LXGWWenKai-Medium.ttf": "https://github.com/lxgw/LxgwWenKai/releases/download/v1.520/LXGWWenKai-Medium.ttf",
}

MIN_BYTES = 100_000  # 断点/错误页通常远小于此


def fetch(url: str, dest: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
        f.write(r.read())


def main() -> int:
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(here, "fonts"))
    ap.add_argument("--only", nargs="*", help="只装这几个文件名")
    ap.add_argument("--force", action="store_true", help="已存在也重新下载")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    want = a.only or list(SOURCES)
    bad = [n for n in want if n not in SOURCES]
    if bad:
        sys.exit("未知字体名: " + ", ".join(bad) + "\n可选: " + ", ".join(SOURCES))

    for name in want:
        dest = os.path.join(a.out, name)
        if os.path.exists(dest) and os.path.getsize(dest) >= MIN_BYTES and not a.force:
            print(f"skip  {name} ({os.path.getsize(dest)/1048576:.1f}MB)")
            continue
        try:
            fetch(SOURCES[name], dest)
        except Exception as exc:
            print(f"FAIL  {name}: {exc}", file=sys.stderr)
            if os.path.exists(dest):
                os.remove(dest)
            continue
        sz = os.path.getsize(dest)
        print(f"{'ok' if sz >= MIN_BYTES else 'SUSPECT':8s} {name} ({sz/1048576:.1f}MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
