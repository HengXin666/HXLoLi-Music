# 判断档与剧本的产物格式

六份产物都放在 `proj/judge/`. 判据脚本是 `hx-karaoke judge/check_judge.py --project proj [--stage X]`. 退出码 0 才能往下走

做的顺序: `shots` -> `visual` -> `bar` -> `style` -> `arc` -> `concepts`. 下游只能引用上游产物里已有的东西

判据只查能机械证伪的项: 覆盖, 引用能指到上游, 有对比, 有留白, 手法不重复. 写得好不好由自审盲审判 (意图还原, 专属性测试)

## 共同约定

- 句子用 `line` (与 `timing.json` 的 line 相同) + `text` (日文原文, 去掉注音) 定位
- `text` 不要手抄. 先跑 `check_judge.py --project proj --skeleton`, 复制它打印的 line 与 text
- `text` 与歌词不符时判 FAIL. 歌词改过, 这一句的分析要重做
- 时间用秒 (数字), 或 `"m:ss"` / `"m:ss.s"`
- 音乐事件类型: `onset` `sub` `section` `beat` (来自 `review/music-events.json`), `mora` (人声音拍, 来自 `timing.json`), `silence` (>=1s 的句间静默). 容差 0.08s
- 事件表: 新工程必须有 `review/music-events.json` (分轨后跑 40 步的 `music_events.py --verify`, 三条判据都过). 只有 grid 的老工程在 bar.json 写 `"events": "missing"`, 这时只许绑 `section` (取 grid.json 段落起点) / `mora` / `silence`, 绑 onset / sub / beat 判 FAIL. 有事件表却写 missing 也判 FAIL

## shots.json: 视频元素

```json
{"version": 1, "shots": [
  {"id": "s01", "t0": 0.0, "t1": 6.4, "color": "蓝灰, 低饱和", "subject": "主角背影",
   "motion": "镜头推近", "symbols": ["剑", "雨"]}]}
```

- 镜头按时间排, 相邻镜头空隙 <= 0.5s, 不许重叠
- 要覆盖全部歌词的时间区间
- `color` `subject` `motion` 不能为空. `symbols` 是列表, 可以为空
- 有 `review/scene-timeline.json` 时, 镜头起点离切点 > 0.3s 给 WARN
- 没有视频: `{"version": 1, "source": "none", "reason": "..."}`. 只给 WARN. 下游不能用镜头锚点, 风格表要从原作取证
- 视频只覆盖一部分 (例: 官方只有 TV size 无字幕 ED): 没画面的时段写一条 `{"id": "n1", "t0": .., "t1": .., "source": "none", "reason": ".."}`. 它算覆盖与连续, 给 WARN, 不能当镜头锚点
- 视频与歌曲音频有偏移时写 `"video_offset"` (秒, 歌曲时间 = 视频时间 + offset). 镜头一律写歌曲时间. scene-timeline 的切点按它换算

## lines.visual.json: 歌词视觉化

```json
{"version": 1, "lines": [
  {"line": 0, "text": "愛のイロハを学んでも", "image": ["学ぶ", "イロハ"], "mood": "自嘲, 克制",
   "voice": {"who": "主角", "to": "对方"}, "weight": ["愛"],
   "link": {"prev": "开场", "next": "下一句给出结论: 还是得不到"}}]}
```

- 每句都要有, 一句一条
- `image`: 具体名词或动词, 非空列表. 下游 arc 的 image 锚点只能取这里的词
- `weight`: 1-2 个承重的字或词, 必须在本句原文里
- `voice`: 谁对谁唱. `link`: 与前后句的关系. 没有关系写 "断开" 并说明

## bar.json: 定标

```json
{"version": 1,
 "events": "present",
 "searched": [{"where": "bilibili", "query": "オンリー 特效字幕", "found": 0}],
 "refs": [{"id": "r1", "tier": "B", "title": "...", "url": "...", "why": "同番 OP, 同一画师",
           "moments": [{"t": "1:23", "what": "副歌第一字碎成羽毛", "technique": "字形粒子化"}]}],
 "highlights": [{"id": "h1", "lines": [12, 13], "music_event": {"kind": "section", "t": 83.2},
                 "reaction": "副歌进来时屏息", "unique": "只有这部番有的羽毛与剑",
                 "anchor": {"motif": "羽毛"}, "refs": ["r1"]}]}
```

参照分三层. 上一层不够 3 个, 才从下一层补:

| 层 | 参照 |
|---|---|
| A | 本曲的卡拉OK, 本曲官方 MV |
| B | 同番其他 OP/ED/PV/预告, 同一歌手的 MV, 番剧本身的名场面 |
| C | 同类歌曲的顶级作品, 按 BPM 区间 + 情绪 + 声部结构挑 |

- `refs` 至少 3 个. 每个至少一个带时间戳的 moment, 写清手法
- `searched` 记每次检索. 没有 A 层参照时至少 2 条. "没找到" 只能让层级下降, 不能降低要求
- `highlights` 3-6 个. 层级下降时数量不许减少. 不同高光不许共用句子
- 每个高光必须有:
  1. `music_event`: 绑定的音乐事件, 时间在这几句附近 (±2s), 并且对得上事件表
  2. `reaction`: 观众该有的反应
  3. `unique`: 只有这首歌能做的元素
  4. `anchor`: `motif` (必须在 `anime.elements.md`) 或 `shot` (必须在 shots.json). 没有锚点的高光换到别的歌也成立
- "手法在全曲只用一次" 在 arc.json 查. "盲审能还原锚点" 与专属性测试在自审查

## style.json: 风格表

```json
{"version": 1,
 "evidence": [{"id": "e1", "what": "片尾水彩背景", "where": "shot:s04"}],
 "palette": [{"name": "暮色", "hex": "#C8A27A", "from": "e1"}],
 "line": "铅笔感细线, 线端不收尖", "texture": "纸纹 + 水彩晕染",
 "motion": [{"word": "飘落", "from": "e2"}],
 "banned": [{"what": "霓虹发光", "why": "原作没有高饱和光源"}]}
```

- `evidence` 至少 3 条, 每条写 where: `shot:<id>`, 集数 + 时间, 或 url
- `palette` 至少 3 色, `motion` 至少 2 条. 每条 `from` 指向一条证据
- `banned` 至少 1 条. 这是 "不出戏" 的依据
- 可选 `role_color` 与 `line_glow`: 角色标识色和每句光晕色是两个字段, 作用在不同层, 不要混成一个色变量
  - `role_color`: `[{"role", "hex", "from", "lines": [句号], "why"}]`. 只管字身 (L2 base 的 `\1c`), 表示"这个字属于谁" (如艾莉丝红, 洛琪希蓝), 是叙事信息, 不随背景变. 不在 `lines` 里的句字身用默认色
  - `line_glow`: `{"from": "hue.json", "rule", "scope"}`. 只管光晕与描边 (高亮层 `\3c`, L1/L2 暗晕, 贴字光晕/粒子), 按逐句对比原则从 `hue.json` 取 (冷背景配暖光晕). 角色句的光晕也照此走, 不被角色色覆盖
  - 两条同时成立: 角色句 = 角色色字身 + 逐句对比光晕

## arc.json: 全曲剧本

```json
{"version": 1,
 "sections": [{"id": "V1", "lines": [0, 1, 2, 3], "budget": 0.3, "why": "自嘲的铺垫, 压住"}],
 "lines": [{"line": 0, "text": "愛のイロハを学んでも", "role": "carrier",
            "idea": "字像被橡皮擦过, 学了又忘", "technique": "erase-trail",
            "anchors": [{"kind": "image", "ref": "学ぶ"}, {"kind": "event", "ref": {"kind": "onset", "t": 26.6}}],
            "highlight": null, "thread": {"mode": "carry", "state": "擦痕颜色传给下一句"}}]}
```

- `sections` 按顺序连续地切分全部句子. `budget` 是强度预算 0..1, 写 `why`
- 强度要有对比: 段落预算的极差 >= 0.4
- 要有留白: 至少一句 `role=rest`, 或至少一段预算 <= 0.3
- 每句: `role` (highlight / carrier / rest), `idea` (观众看到什么, 为什么), `technique` (手法标签), `anchors` (至少一个)
- 锚点类型:
  - `motif`: 在 `anime.elements.md`
  - `image`: 在 lines.visual.json 这一句的 image 里
  - `shot`: 在 shots.json, 时间与本句重叠 (±1s)
  - `event`: `{"kind", "t"}`, 时间在本句附近 (±1s), 并且对得上事件表
- 高光: bar.json 的高光句必须写 `role=highlight` 与对应 `highlight` id. 不在 bar 里的句子不许标高光
- 不同高光的手法标签不许相同
- 第 2 句起都要有 `thread`: `carry` 写传什么, `break` 写为什么断

## concepts.json: 高光句发散

```json
{"version": 1, "highlights": [{"id": "h1", "concepts": [
  {"id": "c1", "idea": "...", "technique": "feather-burst", "vs_bar": "接近 r1 的 1:23",
   "frames": ["judge/frames/h1_c1_83.2.png"], "chosen": true},
  {"id": "c2", "idea": "...", "technique": "blade-cut", "vs_bar": "...",
   "frames": ["judge/frames/h1_c2_83.2.png"], "chosen": false, "reject_reason": "与第二段高光太近"}]}]}
```

- bar.json 的每个高光都要有发散稿, 每个 2-3 个构想
- 各构想手法标签不同. 只换参数不算另一个构想
- 正好选定 1 个. 落选的写 `reject_reason`
- `frames` 用真渲染器抽帧, 路径相对工程目录, 文件要存在
- 选定构想的手法要与 arc.json 这个高光的手法一致
