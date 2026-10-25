# Agent Note: 番剧设定考据成为特效设计的前置步骤

Status: implemented

Decision-ID: karaoke-anime-background-required


## Code

- `.agents/skills/hx-anime-karaoke-ass/scripts/source/fetch_anime_bg.py`

## Problem

第 11 步的设计文档原本就写了「三层理解：番剧背景 → 歌曲意图 → MV 镜头」，但它只是**正文里的一段话**，
没有任何产物、也没有任何检查点。实际做起来，最省力的路径是「搜一下番名 + 看 MV」就下结论，
于是 30 句歌词的特效退化成通用心形/星星/光点，靠换配色撑完整首歌  技术上全部合法，
validate_ass.py 照样通过，只有成片「缺内涵」，而这是没有机器判据能抓的失败。

仓库里已经有两个正例可以作为对照：無職転生 ED1 的工程里写了洛琪希=魔女帽/水魔法、艾莉丝=红发/剑、
塞妮丝=治愈魔法；ヨスガノソラ OP 的工程里写了比翼鸟一目一翼。这些符号不是从 MV 画面里看出来的，
是从设定里读出来的  但它们只存在于 `make_ass.py` 的注释里，下一个 agent 看不到它们从哪来。

## Decision

把第 8 步拆成 8a「番剧设定考据」与 8b「逐句设计」，并给 8a 定死产物：

- `anime.background.json`：`fetch_anime_bg.py` 抓 bgm.tv 条目 summary + 全部角色简介（实测匿名请求即可）。
- `anime.notes.md`：人读的结论，含「角色 → 视觉母题 → 图形库对应」表与画面时间线；
  逐句设计表的「母题」列必须能指回它，指不回的句子必须显式标为氛围句。

萌娘百科的 `api.php` 实测返回 `action-notallowed`，所以正文走页面抓取（argo_fetch），
这条已写进 `steps/10-anime-bg/impl/background-research.md`，避免后续在 API 上浪费重试。

`steps/11-design/impl/motif-catalog.md` 第 1 节的第 1 条改为指向该文件，第 2、3 条不动。

## Alternatives considered

- **什么都不做（继续只写正文）**: 最强理由是「本来就在设计文档里，agent 读设计文档时自然会看到」。
  否决：它已经被看到了很多次，但没有任何一次留下过产物；没有产物的步骤等于可以宣称做过。
- **只要求查，不规定来源**: 最强理由是「不同作品资料分布不同，写死 bgm.tv 会限制」。
  否决：不指定来源时实际落地是「泛搜一段百科」，正是缺内涵的来源；bgm.tv 的条目+角色结构
  恰好给出「角色 → 设定细节 → 可画符号」这条策划需要的映射，且是机器可取的。
- **把角色简介直接喂给设计步骤，不要求人写 notes**: 否决。简介是原料不是结论，
  「春日野穹病弱深居简出」到「白羽单翼」之间的那一步是设计判断，必须被写出来才能被下一个人复用或反驳。
- **要求所有角色都做母题**: 否决。OP 里只出现两位主角，为配角强行造符号会让画面出现无关元素；
  阈值因此定成「关键句至少能指到一个母题」，而不是「每个角色一个」。

## Consequences

- 三个 example 工程已按新规补齐 `anime.background.json` 与 `anime.notes.md`；
  無職転生 抓到的是 2021 年第一季条目（41 位角色，与 ED1 同季），而不是同名后续季度。
- `anime.notes.md` 直接解释了此前的设计选择为何成立（比翼=成对、ED 反向的偶像风），
  这些理由此前只存在于 `make_ass.py` 的注释里。
- 抓取失败时 `fetch_anime_bg.py` 要求 `--register --why`，把「为什么没查成」写下来，而不是静默跳过。