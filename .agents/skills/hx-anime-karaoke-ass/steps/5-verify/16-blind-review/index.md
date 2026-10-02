# 16 盲审(出片前的最后一关, 必须开子代理)

## 只做这一件事

**开一个新鲜的子代理**, 它不看设计过程, 只拿 `review/score.md` 与产物本身,
按同一套判据独立打分, 并与主代理打的分**对账**.

## 为什么要开子代理(不是"再检查一遍")

主代理有一个结构性缺陷: **它是设计者, 会替自己的设计找理由**。
实测(2026-10-03, 漆黑子弹 v5)主代理在门禁 6/6 通过、自评"效果更好了"的情况下,
被用户连提三次「特效太多了」「图形很粗糙」「尺寸这么大」。

所以盲审的价值**不在"多一双眼睛"**, 而在**切断"作者为自己辩护"这条路径**:
子代理没有参与设计, 它读到的只有判据与数字。

## 硬性要求

1. **必须新起子代理**(`subagent`, `fresh` context), **不要**用 `subagent_fork`
   —— fork 会继承本轮的思考过程, 那就等于自查。
2. 给子代理的 prompt 里**只放判据与文件路径**, 不放你的设计意图、不放"我觉得"。
3. 子代理必须**自己跑** `score_kfx.py`, 不许采信主代理给的分。
4. 分差 >= 1.5 分, 或任一方判 FAIL 而另一方判 PASS 时, **以子代理为准**,
   并把分差写进 `review/score.md` 的末尾。

## 命令

```bash
# 主代理: 先自评
hx-karaoke score_kfx.py --project proj

# 子代理: 独立复评(它自己跑同一条命令 + 目检)
hx-karaoke score_kfx.py --project proj --out proj/review/score-blind.md
hx-karaoke render_octopus.py proj/out.ass --times <句首,高潮,句尾> --out proj/review/blind/
```

## 给子代理的 prompt 模板(照抄, 不要加自己的结论)

```
你是独立评审. 工程在 <绝对路径>.

任务: 按这套 skill 的判据, 独立给这份特效字幕打分, 并指出不合格项.

步骤:
1. 读 <skill>/steps/4-kfx/index.md 了解五层结构, 再读 42-text-main/impl/density.md 与
   47-color/index.md 了解密度与配色的判据.
2. 自己跑: hx-karaoke score_kfx.py --project <proj> --out <proj>/review/score-blind.md
   不要采信任何已有的分数文件.
3. 再跑: hx-karaoke render_octopus.py <proj>/out.ass --times <3 个时刻> --out <dir>
   用你的眼睛看这三帧, 回答两个问题:
   a) 特效有没有把歌词盖住 / 显得过密?
   b) 图形看起来粗糙还是精细? 尺寸与文字的比例是否合适?
4. 输出一张表: 判据 | 实测 | 阈值 | PASS/FAIL, 外加总分与"最该先修的三条".
   不要复述 skill 的原文; 只给结论与依据.
5. 若你与 <proj>/review/score.md 的分数差 >= 1.5, 说明差在哪一条.

禁止: 修改任何文件(除 score-blind.md 与截图目录); 不要读主代理的思考过程.
```

## 过关条件

- `review/score-blind.md` 存在, 且**子代理的总分 >= `--min-score`(默认 8.0)**
- 若子代理分 < 门槛: **不许出片**, 按它列出的"最该先修的三条"改完再重跑 16
- `review/score.md` 末尾记录了两次打分的差值

## 这一步要用的脚本

- `<skill>/scripts/score_kfx.py` - 六组判据打分, 出 `review/score.md`; 退出码 = 是否达门槛
- `<skill>/scripts/render_octopus.py` - 抽帧目检(必须用真渲染器, 见 `14-inspect`)
