# Agent Note: 卡拉OK skill 的运行期产物一律移出 skill 目录

Status: implemented

- 影响: `.agents/skills/hx-anime-karaoke-ass/scripts/assfx/svg2ass.py`（缓存目录改为 `ASSFX_SVG_CACHE` /
  `~/.cache/hx-anime-karaoke-ass/svg`）、`scripts/assfx/bake_shapes.py`（新增 `--out`/`--video` 必填化与
  skill 写入拒绝）、`scripts/check_lag.py`（`--project` 替代硬编码工程路径）、
  `HXLoLi-Music/.gitignore`（新增 6 行兜底规则）、
  `assets/svg_cache/`（50 份 SVG 从 git 移除）
- 决策依据: 用户原话「禁止任何项目都项目素材被存入 skill，比如 assets/svg_cache 等」
- 相关: [karaoke-steps-restructure](./2026-10-02-karaoke-steps-restructure.md)（同一次重构的另一半）

## Problem

skill 目录里长出了**一次具体制作的产物**，而且不止一处：

| 产物 | 怎么进去的 | 后果 |
|---|---|---|
| `assets/svg_cache/` 50 份 SVG | `svg2ass.fetch()` 的缓存路径写死成 `<skill>/assets/svg_cache` | 做漆黑子弹时下载的图标永久留在 skill 里，换首歌删都分不清哪些该留 |
| `examples/blackbullet_ed/` 共 726MB | 把工程目录直接建在 `examples/` 下 | 含 `base.mp4` 169MB、`stems/` 96MB、成片 356MB；其中 165 个文件已进 git |
| `examples/*/assets/shapes.json` | `bake_shapes.py` 的 `OUT` 是硬编码绝对路径 | 该文件是"某一帧 MV 的抠图 + 某组图标"的产物，只对这一份 MV 成立 |
| `scripts/check_lag.py` 里的工程路径 | 脚本里写死 `P = .../static/music/ヨスガノソラ/demo/tsunagukizuna` | 脚本变成"只能对那一首歌跑"，与同目录其它脚本的 `--project` 约定不一致 |

判据一句话：**skill 是代码与契约，它不该携带任何一次运行的痕迹。**
判据若是"跑完 `git status` 看 skill 目录脏不脏" —— 旧版是脏的（50 个 SVG 未追踪、165 个文件已追踪）。

## Decision

把"产物属于工程"变成**代码侧的强制**，而不只靠文档叮嘱：

1. **缓存目录按环境变量取**：`svg2ass._ensure_cache()` 依次看 `ASSFX_SVG_CACHE`、
   `$XDG_CACHE_HOME/hx-anime-karaoke-ass/svg`、`~/.cache/hx-anime-karaoke-ass/svg`。
   skill 里不再有任何写死到自身的缓存路径。
2. **`bake_shapes.py` 的产物改成必填参数，且拒绝写进 skill**：
   `--out proj/assets/shapes.json` 为必填；`--video` 不给时只烧网络图标（不去猜某份 `base.mp4` 在哪）；
   `--out` 落在 skill 子树内直接 `sys.exit` 并说明理由。MV 抠图的坐标（`MV_CROPS`）随之标注为
   "某个工程某一帧的事实"，换片源即不成立。
3. **`check_lag.py` 改成 `--project`**，与同目录其它脚本一致；判据引用改到
   `steps/08-review-timing/impl/lag-verdict.md`。
4. **工程搬到工程目录**：`examples/blackbullet_ed` → `static/music/漆黑子弹/proj-tokohana`（含其
   `one_line` 子工程），`examples/yosuga_{op,ed}` → `static/music/ヨスガノソラ/demo/`。
   `static/music/` 下已有 `ヨスガノソラ/demo/tsunagukizuna` 这个先例（同样未进 git）。
5. **`.gitignore` 兜底**：对 `assets/`、`**/svg_cache/`、`**/stems/`、`**/review/`、
   `examples/*/out/`、`examples/*/assets/` 各加一条。这是第三道闸 ——
   前两道（缓存路径 + `--out` 拒绝）挡的是当前代码，git 挡的是"有人手改回旧路径"或"旧版本写回来"。

## Alternatives considered

- **什么都不做，只删掉现有的 `assets/svg_cache/`**：最强理由是「清一次就干净了，改代码是过度工程」。
  否决：缓存路径仍写死在 `svg2ass.py` 里，**下一次跑 `props.prefetch()` 就会原样长回来**。
  实测复现：删目录后调用 `svg2ass.from_url(...)` 一次，`assets/svg_cache/` 立即重新出现 1 个文件。
- **把缓存留在 skill 但在 `.gitignore` 里忽略**：最强理由是「反正 git 不追踪，等于没进仓库」。
  否决：用户的原话是"禁止素材被存入 skill"，不是"禁止提交"。缓存留在 skill 里会污染
  skill 的**语义**（换一首歌时，读者无法判断哪些图形是这首歌在用的），
  且 `git clean -xfd` 之外的任何清理动作都可能误删它。
- **把 `assets/` 整个删除，图形改为每次现下**：最强理由是「skill 最干净」。
  否决：断网时无法复现（`props.prefetch()` 的设计就是"首次联网、之后离线"），
  且缓存本来就是为了避免重复下载。移到用户级缓存目录同时满足"不进 skill"与"可离线复现"。
- **工程留在 `examples/` 但加 `.gitignore` 忽略大文件**：最强理由是「示例就该放在 skill 里，
  模型照着做最方便」。否决：726MB 的 `base.mp4`/stems/成片跟示例价值无关，
  而"照着做"需要的是 `make_ass.py` + `lyrics.txt` + `timing.json` ——
  这些保留一份 `examples/mushoku_ed1`（1.7MB，无二进制）就够；其余历史工程归工程区。
  同时这符合本仓既有的 [mv-source-not-in-git](./2026-09-29-mv-source-not-in-git.md) 判据
  （可重取的素材不进仓库）。
- **`bake_shapes.py` 用"检测是否在 skill 内"的软警告代替退出**：否决。
  它已经实测写错过一次（`OUT` 硬编码到 `examples/blackbullet_ed/assets/`）；警告不会拦住下一次。

## Consequences

- skill 体积从 **728MB（examples）→ 1.7MB**；`git ls-files` 从 308 个降到 40 个左右，
  其中不再有任何缓存或大二进制。
- 实跑验证：`uv run --with svgelements -c "...svg2ass.from_url(eye)"` 打印
  `cache dir = /home/hx/.cache/hx-anime-karaoke-ass/svg`，连取两次均 2634 字符（第二次走缓存），
  且 skill 目录内 `find . -name "*.svg"` 为空。
- `bake_shapes.py --out scripts/assfx/tmp/shapes.json` → 打印
  `--out 落在 skill 目录里（…）。skill 是只读的代码与契约，产物属于工程 —— 把它指到 proj/assets/ 下面。` 并退出。
- 已知边界：`static/music/` 里的工程产物**不进 git**（与 `tsunagukizuna` 一致），
  所以换机器后历史工程不会跟着克隆过来 —— 它们本来就是本地制作现场，不是可复现资产。
  保留的 `examples/mushoku_ed1` 才是"给模型看的样子"。
- `.gitignore` 的 6 条规则与被删除的 50 个 SVG 同一次提交：`git status` 在提交后干净。
