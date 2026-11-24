# direction.kfx.json

放在工程目录, 与 lyrics.txt / timing.json 同级. 生成器只执行它, 校验失败退出码 2.

```jsonc
{
  "song": {"title": "...", "artist": "...", "anime": "...", "why": "这首歌在番里是什么"},
  "seed": "任意字符串, 决定粒子的随机, 同 seed 逐字节可复现",
  "fonts": {               // file 相对方向文件, 必须是播放器实际加载的同一字体
    "jp":   {"name": "Shippori Mincho B1", "file": "../../../static/music/无职转生/fonts/ShipporiMinchoB1-Bold.ttf", "bold": true},
    "ruby": {...}, "zh": {...}, "lat": {...}   // lat: 英文词 (If you do) 用的字体, 斜体
  },
  "geometry": {"jp_y": 838, "jp_fs": 76, "ruby_fs": 30, "zh_fs": 44, "lat_fs": 68, "ruby_gap": 54, "zh_gap": 72},
  "final_hold": 220.5,     // 最后一句停到几秒
  "title_card": {"t0": 1.0, "t1": 10.6, "jp": "オンリー", "latin": "Only", "credit": "...", "zh": "唯一", "why": "...", "palette": {...}},
  "sections": [{
    "id": "B1-crimson", "lines": [5, 6],          // 闭区间, 句号从 0 起; 每句必须且只能属于一段
    "scene": "这一段 MV 画面里是什么",
    "why": "为什么这么设计",
    "palette": {"base": "#FF9797", "sung": "#FFFFFF", "outline": "#3A0A10", "glow": "#FF4B4B",
                "halo": "#1E0508", "zh": "#FFBBBB", "zh_sung": "#FFFFFF"},
    "enter": "flash",      // ink | drift | drop | wind | flash
    "exit": "shatter",     // rise | dissolve | shatter | wind | erase | white | veil
    "scale": 1.0,          // 短句名场面可放大, 例如 1.32
    "particles": {"motif": "ember", "flow": "burst", "per_unit": 1.1, "ambient": 0.6,
                  "size": [8, 13], "colors": ["#FF5A3C", "#FFB070", "#FFFFFF"]}
  }],
  "moments": [{"line": 5, "kind": "cracks", "units": [0, 4], "color": "#FF5D7A", "why": "..."}],
  "words": [{"jp": "貴方", "zh": "你", "color": "#FF8A98", "why": "..."}]
}
```

- motif: mote sparkle snow leaf petal droplet ember shard; flow: fall rise wind burst
- per_unit: 每个音拍平均几片, 按音长自动补偿 (0.3s 为基准, 0.5x 到 2.2x); ambient: 每秒背景几片 (低透明度, 慢)
- moment kind: cracks magic_circle red_thread rays flip tear veil whiteout tilt; units 是该句的单元序号 (lyrics 里一个 [漢字|かな] 或一个假名算一个单元)

## 校验 (退出码 2)

- 所有颜色 #RRGGBB; section / moment / word 缺 why
- 某句没有段落, 或一句属于两段
- 未唱色 base 亮度 < 0.40 (未唱的字是观众提前读词的地方), base 与 outline 对比 < 7
- enter / exit / motif / flow / kind 不在可选值里
- 字体文件不存在
