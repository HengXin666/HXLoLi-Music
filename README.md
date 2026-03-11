# HXLoLi-Music

HXLoLi 音乐资源仓库, 存放音频、歌词、封面、字体等音乐相关资源。

通过 jsDelivr CDN 为 [HXLoLi](https://github.com/HXLoLi/HXLoLi) 主站提供音乐数据。

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

每首歌曲的重数据 (字体映射 `assFontMap`、图片 base64 `assImageData`、图片事件 `assImageEvents`、边界框时间轴 `assBoundsTimeline` 等) 被拆分到 `static/info/{id}.json` 中, 仅在用户点击播放该歌曲时才按需加载。

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
