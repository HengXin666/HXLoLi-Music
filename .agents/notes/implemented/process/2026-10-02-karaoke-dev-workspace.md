# Agent Note: 卡拉OK 制作工作区统一为 dev/<番名>/<歌曲名>/，整棵屏蔽 git

Status: implemented

- 影响: `.gitignore`（新增 `/dev/` 与旧位置兜底）、`steps/00-setup/index.md`（新增「工作区」
  与「发布」两节）；把 7 个工程从仓库根/`demo/` 迁进 `dev/<番名>/<歌曲名>/`；
  修好 5 个 `make_ass.py` 的 skill 路径解析与 1 个字体软链
- 决策依据: 用户原话「给当前skill界定一个工作区吧, HXLoLi-Musilc/dev/歌曲名, 然后把这个工作室的
  内容全部屏蔽git. 然后等做好了之后，再把它移动到 static/ 对应的位置里面，并且配上音乐文件，
  然后走一波 make.sh 生成，确保可用」；形态与迁移范围经确认选
  「`dev/<番名>/<歌曲名>/`」+「现有 5 个根级工程全部搬进来」

## Problem

制作现场一直散在仓库根: `demo/`（4 个子目录）、`漆黑子弹/`、`proj-touhou/`、`lolicon-proj/`、
`guilty-crown-op2-pv/`，共 **7.6GB**。它们全都**未被 git 忽略**（`git status` 里是 `??`），
只靠"记得别 `git add .`"来避免误提交 —— 一次手滑就会把 5.8GB 的 `proj-touhou/`
（含一个 5.5GB 的旧 `.venv-karaoke`）推进仓库。

同时命名无章法: `proj-tokohana`、`guilty-crown-op2-pv`、`tsunagukizuna` 三种风格并存，
看不出属于哪部番，也看不出搬去 `static/music/<番名>/` 时该放哪。

发布链路（`make.sh` → `playlist.json` → 前端）本身是能用的，但没有写下来的约定:
ass 与音频**必须同名同目录**（`find_matching_ass` 按 `audio_path.stem + .ass` 找），
`title` 取 mp3 的 `TIT2`、`artist` 取 `TPE1` —— 这些只能靠读 `py/music/` 的源码才知道。

## Decision

**工作区 = `dev/<番名>/<歌曲名>/`，与发布目录 `static/music/<番名>/` 一一对应。**

- `.gitignore` 加一条 `/dev/` 覆盖整棵树。为什么不逐条列子目录: 工程里会不断长出
  `stems/`、`review/`、`assets/`、`frames/` 等新目录，逐条列必然漏；而且搬迁后目录名变了，
  老规则会静默失效。**一棵树一条规则**，没有漏网的空间。
- 旧位置（`/demo/`、`/漆黑子弹/` 等）也加兜底，防止有人把工程挪回根目录。
- **7 个工程全部迁进 `dev/`**（用户选定）：`ヨスガノソラ/{ツナグキズナ,比翼の羽根,ピンキージョーンズ}`、
  `漆黑子弹/トコハナ`、`东方/果てなき風の軌跡さえ`、`ちぃむdmp☆/ろりこんでよかった~`、
  `罪恶王冠/The Everlasting Guilty Crown`；`demo/mv/raw.mp4` 是其素材，归入
  `dev/ヨスガノソラ/ツナグキズナ/.mv-raw/`。
- **skill 路径解析统一走 `ASSFX`**，不再写相对层数。5 个 `make_ass.py` 原先有三种写法
  （`../../`、`../../../../../../`、写死的 `/home/hx/.../HXLoLis/.agents/skills/anime-karaoke-ass`），
  搬进 `dev/` 后**全部失效**，其中 touhou 那个原本就指向一个不存在的路径。
- 发布流程写进 `steps/00-setup/index.md`：门禁过 → 抽 mp3（与 ass 同名）→ 搬 ass →
  放目录级 `fonts/` → `bash make.sh` → 核对 `playlist.json` / 两个 URL / `static/info/<id>.json`。

## Alternatives considered

- **什么都不做，只手工小心别提交**：最强理由是「现状跑了这么久也没出事，加规则是多余的」。
  否决：7.6GB 未跟踪内容 + 一次 `git add -A` 就是事故；而且"该放哪部番"这个问题
  在每次搬家时都要重新判断一次，这正是要消掉的成本。
- **逐个目录加忽略规则**（`/demo/tsunagukizuna/`、`/proj-touhou/` …）：最强理由是
  「精确，不会误伤将来可能想入库的东西」。否决：工程内部会持续长出新的子目录，
  逐条列必然漏；而且一旦搬迁（本次就搬了），老规则静默失效且不报错。
- **把工作区放仓库外**（如 `~/karaoke-dev/`）：最强理由是「最彻底，绝无可能误提交」。
  否决：工程要引用 skill 的 `scripts/` 与 `fonts/`，放仓库外就必然要写绝对路径或另设
  环境变量；而 ass 的发布目标 `static/` 在仓库内，放外面会让"做完就搬过去"变成跨仓库操作。
- **只搬还没做完的工程，已完成的不动**：最强理由是「已发布的产物留在原地最省事」。
  否决：那会同时存在两套目录约定，下一个人仍然要判断"这个工程算做完了吗" ——
  而判断标准本身就是本次要消掉的东西。一起搬之后，位置本身就说明了归属。
- **给工作区加一个 `README.md` 说明**：最强理由是「不写进 skill 的话，下次还得问」。
  否决：真正会被读到的地方是 `steps/00-setup/index.md`（走流程时必读），
  在工作区里放一份说明反而与 skill 的渐进披露原则冲突（那份说明在别处读不到）。

## Consequences

- 仓库根从「7 个散落的工程 + 一个 `demo/`」变成 `dev/` 一个入口。7.6GB 内容全部移出 git 视野。
- 代价：搬进 `dev/` 让工程与仓库根之间多了三层，任何**写死相对层数**的脚本都会断。
  本次修了 5 个 `make_ass.py` + 1 个字体软链；`ASSFX` 的约定已写进 skill，避免复发。
  踩到并已修的一个具体坑：把生成器里的 `SKILL` 改名成 `_SKILL_SCRIPTS` 时忘了
  `FONTS = os.environ.get("ASSFX_FONTS", os.path.join(SKILL, "fonts"))` 还在用 `SKILL`，
  三个工程立刻 `NameError` —— 所以新写法**同时定义** `_SKILL_SCRIPTS` 与 `SKILL`。
- 无损性已实测：5 个生成器在 `dev/` 下全部能跑；`トコハナ` 重生成的 ass 与迁移前
  **md5 完全相同**（`8a66e35cff41b17396e7e04277553c9b`）。
- 收益：发布的三个隐性约定（ass 与音频同名、`TIT2`/`TPE1`、目录级 `fonts/`）第一次写下来，
  下次不用再读 `py/music/` 的源码去发现它们。
- **遗留（未处理，需人工决定）**：`dev/` 7.6GB 里有 **5.5GB** 是
  `dev/东方/果てなき風の軌跡さえ/.venv-karaoke/` —— 工程自建的 venv，正是
  `hx-karaoke` 共享环境要取代的东西。它现在只被同目录的 `NOTES.md` 当历史命令引用
  （那些命令已过时，应改用 `hx-karaoke <脚本>`）。因为删除 5.5GB 属破坏性且不在本次指令范围内，
  **没有动它**；确认无用后删掉即可把 `dev/` 从 7.6GB 降到约 2.1GB。

## Testing

- `git status --short dev/` → **0 条**（整棵屏蔽生效）；`static/music/漆黑子弹/` 是 `??`（发布产物入库）。
- 5 个生成器逐个真跑：`cd dev/<番>/<曲> && hx-karaoke make_ass.py /tmp/x.ass` 全部 OK。
- 发布链路端到端：`dev/漆黑子弹/トコハナ` → `static/music/漆黑子弹/やなぎなぎ - トコハナ (常花).{ass,mp3}`
  + 目录级 `fonts/` → `bash make.sh` → `playlist.json` 13 首含新曲、
  `title=トコハナ (常花)` / `artist=やなぎなぎ`；起服务实测
  `audioUrl` 200/5259618B、`assUrl` 200/3323020B、`static/info/216f6d500c45.json` 200。
- `node .agents/skills/hx-agent-notes/scripts/verify-all.ts` 全绿。
