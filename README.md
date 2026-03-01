# HXLoLi-Music

HXLoLi 音乐资源仓库，存放音频、歌词、封面、字体等音乐相关资源。

通过 jsDelivr CDN 为 [HXLoLi](https://github.com/HXLoLi/HXLoLi) 主站提供音乐数据。

## 目录结构

```
HXLoLi-Music/
├── static/music/          # 音乐资源文件
│   ├── fonts/             # 字体文件 (CJK fallback 等)
│   ├── *.mp3              # 音频文件
│   ├── *.ass              # ASS 歌词文件
│   └── *.jpg              # 封面图片
├── py/                    # Python 工具
│   └── music/             # 播放列表生成脚本
├── playlist.json          # 自动生成的播放列表 (勿手动编辑)
└── .gitignore
```

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

当 `static/music/**` 或 `py/music/**` 下的文件变更并 push 到 main 分支时，GitHub Actions 会自动：

1. 运行 `gen_music_playlist.py` 重新生成 `playlist.json`
2. 如果有变动则由 LoLi-Bot 自动提交

也可以在 GitHub Actions 页面手动触发 (`workflow_dispatch`)。

### 更新主仓库版本号

在 HXLoLi 主仓库的 `data/musicVersion.ts` 中更新 `MUSIC_COMMIT_ID` 为最新 commit hash。
