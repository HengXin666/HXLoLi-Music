# HXLoLi-Music

HXLoLi 音乐资源仓库, 存放音频、歌词、封面、字体等音乐相关资源。

通过 jsDelivr CDN 为 [HXLoLi](https://github.com/HengXin666/HXLoLi) 主站提供音乐数据。

ASS 歌词由 [SubtitlesOctopus (HXLoLi 定制版)](https://github.com/HengXin666/JavascriptSubtitlesOctopus) 渲染引擎驱动，
原生支持 VSFilterMod 扩展标签（`\1img` 图片纹理、`\fsvp` 垂直偏移、`\moves3`/`\moves4` 贝塞尔曲线移动等）。

## 目录结构

```
HXLoLi-Music/
├── static/music/          # 音乐资源文件
│   ├── fonts/             # 字体文件 (CJK fallback 等)
│   ├── *.mp3              # 音频文件
│   ├── *.ass              # ASS 歌词文件
│   └── *.jpg              # 封面图片
├── static/info/           # 歌曲详细配置 (按需加载, 自动生成)
│   └── {id}.json          # 单首歌曲的字体/图片/边界框等重数据
├── py/                    # Python 工具
│   └── music/             # 播放列表生成脚本
├── playlist.json          # 自动生成的播放列表 (勿手动编辑)
└── .gitignore
```

## 按需加载架构

`playlist.json` 仅存放歌曲列表的元信息 (id、标题、艺术家、音频/歌词/封面路径等), 体积很小, 页面加载时一次性获取。

每首歌曲的重数据 (字体映射 `assFontMap`、图片 base64 `assImageData`、边界框时间轴 `assBoundsTimeline` 等) 被拆分到 `static/info/{id}.json` 中, 仅在用户点击播放该歌曲时才按需加载。

这样可以避免首屏加载数百 KB 的 JSON, 显著提升列表加载速度。

## 使用方法

### 添加新歌曲

1. 将音频文件放入 `static/music/` 目录
2. (可选) 将同名 `.ass` 歌词文件放在同目录
3. (可选) 将同名封面图片放在同目录
4. 运行播放列表生成脚本

### 生成播放列表

```bash
cd py
uv sync          # 首次运行或依赖变更时
uv run python music/gen_music_playlist.py
```

### CI/CD 自动化

当 `static/music/**` 或 `py/music/**` 下的文件变更并 push 到 main 分支时, GitHub Actions 会自动:

1. 运行 `gen_music_playlist.py` 重新生成 `playlist.json`
2. 如果有变动则由 LoLi-Bot 自动提交

也可以在 GitHub Actions 页面手动触发 (`workflow_dispatch`)。

### 更新主仓库版本号

在 HXLoLi 主仓库的 `data/musicVersion.ts` 中更新 `MUSIC_COMMIT_ID` 为最新 commit hash。

## 许可证 / ライセンス

本仓库采用分离许可证, 详见 [LICENSE](LICENSE)。

- **代码**(Python 脚本、CI/CD 配置等): MIT License
- **音乐资源**(音频、歌词、封面等): 版权归原始权利人所有, 未经授权不得再分发

## ⚠️ 免责声明 / 免責事項

> [!TIP]
> Ass 字幕 详细来源见 [Ass 版权所属 说明](./doc/AssCopyright.md)

### 中文

本仓库中的音乐资源(包括音频文件、歌词文件、封面图片)的著作权归原作者及相关权利人所有。这些资源仅供个人学习、研究和欣赏目的使用, **不得用于任何商业用途**。

本仓库不提供任何形式的音乐下载服务, 也不鼓励任何侵犯版权的行为。如果您是相关权利人并认为本仓库侵犯了您的合法权益, 请通过 Issue 或邮件联系我, 我将在收到通知后**立即删除**相关内容。

### 日本語

本リポジトリに含まれる音楽リソース(音声ファイル、歌詞ファイル、カバー画像)の著作権は、原作者および関連する権利者に帰属します。これらのリソースは個人的な学習・研究・鑑賞目的のみに使用され、**商用利用は一切禁止**されています。

本リポジトリは音楽のダウンロードサービスを提供するものではなく、著作権を侵害する行為を推奨するものでもありません。関連する権利者の方で、本リポジトリが正当な権利を侵害していると判断された場合は、Issue またはメールにてご連絡ください。通知を受け次第、該当コンテンツを**直ちに削除**いたします。

## 歌词约定

### 多份歌词

- `<音频同名>.ass` 是默认歌词, `<音频同名>.<标签>.ass` 是另一份 (标签只能用 `[A-Za-z0-9_-]`)
- 在 ASS 的 `[Script Info]` 里写两行注释, 给每一份起名字和说明, 博客的歌词按钮会显示:

```
; lyric-label: 青晶·虚空
; lyric-desc: 一句话说明这份歌词的风格
```

### 裁剪范围 (博客悬浮窗)

生成器 `py/music/lyric_box.py` 按下面的顺序决定怎么裁:

1. 有 `; lyric-box: x0 y0 x1 y1` (按 PlayRes 坐标): 整首用这个常量矩形, 不预扫描
2. 有 `; assfx-band: <名字> x0 y0 x1 y1 t0 t1`: 按每句的声明排成阶梯时间轴, 不预扫描
3. kfx 成品 (事件 Name 是 `ly:*` / `fx:*`): 预扫描一次, 取全局并集当常量矩形 (结果有缓存)
4. 其余老歌词: 预扫描的动态时间轴

新版歌词按 skill 的硬规则, 内容都在歌词块外扩 5% 的固定矩形里, 所以 1 到 3 都是直接裁剪, 字号不会跟着抖

### CDN

- 超过 19MB 的音频, 字体等由 `scripts/cdn-split.sh` 切片到 `static/cdn/all/`
- `.ass` 等文本不切片, 由 `scripts/cdn-compress.sh` 压成 `static/cdn/gzip/` 下的 `.gz` (约原大小的 1/10 到 1/5)。主站要开 `enablePreCompression`
- 字体按每首歌实际用到的字裁成子集, 放在 `static/cdn/subset/` (`py/music/font_subset.py`)
- CF Worker 部署会跳过超过 25MB 的文件 (Cloudflare 的单文件上限), 这些文件由切片或 `.gz` 提供
- 进了 `static/music/` 的歌都算在验收台发布过, 扫描时的 kfx 红线只提示, 不拦截
