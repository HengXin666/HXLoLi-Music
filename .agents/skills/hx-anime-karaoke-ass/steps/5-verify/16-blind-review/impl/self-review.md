# 自审: 用户看到之前

## 做什么

成品给用户之前, agent 自己审全曲. 不过的句自动重写. 重写有预算, 用完就停, 剩下的交给验收台.

前提: `judge/arc.json` 与 `judge/bar.json` 已过 `check_judge.py`. 没有剧本就没有 "这句指向什么" 的答案, 自审无从判.

## 为什么用两个盲审

作者会替自己的设计找理由. 所以判 "读不读得出" 的必须是没看过剧本的子代理.

- **意图盲审**: 只拿截图与歌词. 说出每句特效指向什么. 说不出 = 没意义.
- **专属性盲审**: 只拿高光句截图与 5 张作品卡 (本作 + 4 个其他工程的元素表, 乱序). 选出这是哪部作品. 选错 = 特效换到别的歌也成立, 判套用, 重写.

两个盲审分开开, 都是新鲜子代理. 不许 fork, 不许给剧本, 不许给答案.

## 命令

```bash
hx-karaoke selfreview/selfreview.py round PROJ [--renderer octopus|ffmpeg] [--decoy-root DIR]
# 开两个子代理, 结论写回 rN/intent/verdict.json 与 rN/unique/verdict.json
hx-karaoke selfreview/selfreview.py score PROJ     # 每句下一步: pass / fix / reanchor / human / upstream
# 按下一步改产物或代码 (改代码走 accept.py begin / predict / verify), 再跑 round
hx-karaoke selfreview/selfreview.py gate PROJ --handoff
```

- 渲染器默认 `octopus` (观众看到的). 确认 ass 没有 VSFilterMod 扩展标签时可用 `ffmpeg`, 快得多.
- 增量: 只审没过的句, 以及事件指纹变了的已过句. 第 1 轮全曲: 每句 1 帧, 高光句 3 帧.
- 干扰项默认取工程上两级目录下其他带 `anime.elements.md` 的工程. 不够 4 个时用 `--decoy-root` 加目录.
- 产物都在 `proj/judge/review/`: `state.json` 与每轮的 `rN/`. `rN/key.json` 是答案, 不给盲审.

## 五项判据

| 判据 | 谁判 | 不过的条件 |
|---|---|---|
| intent | 脚本对照剧本 | 盲审说不出; 或它说的词对不上这句的锚点 (motif, image, 镜头主体与符号, 事件类型的说法) |
| intent (留白句) | 脚本对照剧本 | `arc.json` 里 role=rest 的句: 盲审读出了特效 (说得出指向). 读成空白才算过. 2026-11-08 加: mushoku r1 的 8 句留白全按 "说不出" 判不过, 与剧本相反 |
| readable | 意图盲审 | 字看不清 |
| style | 意图盲审 | 不像同一部作品 |
| vs_bar | 意图盲审, 只审高光句 | 没到参照时刻的水平 (包里给参照时刻, 不给剧本) |
| unique | 脚本对照答案, 只审高光句 | 专属性盲审选的不是本作 |

## 预算 (起始值, 做完两首按实测调整, 写回这里)

- 单句: 第 1 次不过, 原构想内修. 第 2 次不过, 换锚点重写 (`arc.json` 里这句的锚点必须变, 否则 `round` 拒绝). 第 3 次不过, 需人判, 不再碰.
- 全局: 合计最多 4 轮.
- 归并: 同一判据一轮里 3 句以上不过, 是上游问题. 按 `score` 指的产物改一次, 这些句不占单句次数.
- 停下转人 (任一): 高光句两轮不过; 4 轮用完; 第 2 轮后不过的句超过 20%. 最后一条**待校准**, 不进 hard-rules.
- 停下不是让用户描述需求. `gate --handoff` 把需人判写进验收台 issues (status `need-human`, 附盲审意见), 台子打开时排最前, 每条配 2 个候选.

## 意图盲审 prompt (照抄, 不加自己的话)

```
你是独立评审. 你没有参与这份特效字幕的设计.
读 <rN>/intent/packet.json. 每句有歌词原文 (text) 与截图 (frames, 同目录). 高光句另有参照时刻 (bar).
逐句看截图, 写 <rN>/intent/verdict.json:
{"lines": [{"line": 句号, "says": "这句特效在表现什么, 一句话", "points_to": ["它指向的词: 歌词里的词, 画面里的东西, 音乐上的点"],
            "readable": true/false, "style": true/false, "vs_bar": "reach"/"below" (只有高光句写), "note": "不过时写原因"}]}
- 说不出这句特效指向什么, says 写 "", points_to 写 []. 不许猜一个凑数.
- style: 和其他句比, 是否像同一部作品的同一套画风.
- 每句都要写. 不许读这个目录以外的任何文件.
```

## 专属性盲审 prompt (照抄, 不加自己的话)

```
你是独立评审. 读 <rN>/unique/packet.json. 每道题有几张特效截图 (frames, 同目录) 与 5 张作品卡 (A-E, 每张是一部作品的元素名).
判断截图里的特效属于哪部作品, 写 <rN>/unique/verdict.json:
{"answers": [{"q": "Q1", "pick": "A-E 之一", "why": "截图里哪个东西让你这么选"}]}
- 只凭截图里画出来的东西判. 截图里的歌词文字不算依据.
- 看不出时也要选一个, why 写 "看不出".
- 不许读这个目录以外的任何文件.
```

## 已知限制

- 截图里有歌词. 专属性盲审若认得歌词, 会绕过特效直接认出作品. prompt 要求不以歌词为依据, 但脚本查不了. 待实测后决定是否出帧时隐藏主歌词层.
- intent 的匹配是词面匹配. 盲审换了同义说法会误判不过. 误判按 "需人判" 进台子, 不会静默放过.
- 真渲染器 (octopus) 依赖 chromium. 跑不了时用 `--renderer ffmpeg`, 但只在 ass 没有扩展标签时可信.
