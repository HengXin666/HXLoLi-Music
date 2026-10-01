# 15 渲染出片

## 只做这一件事

把视频原样封装 + 字幕做成外挂轨 + 字体做成附件, 出一条 MKV.

## 命令

```bash
bash $S/render.sh proj/base.mp4 proj/out.ass fonts out.mkv ffmpeg
```

`render.sh` 走 MKV 外挂: 视频/音频 `-c copy` 原样封装、ASS 单独一轨、字体做附件、
字幕轨设 default. 实测 4.5 分钟的片封装 **0.3 秒**(烧录要编码几分钟), 且**视频零重编码损失**.
改字幕只换轨, 不必重做视频.

字体附件必须带 `mimetype`, 否则 matroska 拒绝写头(`render.sh` 已处理).

## 需要烧录版时才用

上传视频网站、对方只看 mp4 这类场景:

```bash
bash $S/render_burn.sh proj/base.mp4 proj/out.ass fonts out.mp4 16 ffmpeg ffmpeg
```

系统 ffmpeg 无 libx264(openh264 报错)时只影响烧录, 不影响 MKV 外挂.

## 交付物清单

- 成片 **mkv**(视频原样封装 + ASS 外挂轨 + 字体附件)
- `out.ass`
- 工程(`lyrics.txt` + `lyrics.source.json` + `anime.background.json` / `anime.notes.md` / `anime.elements.md`
  + timing / fixes / calib / `make_ass.py` / `review/design-table.md`)
- `check_gates.py` 与 `validate_ass.py` 的报告、`check_fx_visible.py` 结果、目检拼图

## 过关条件

- 第 13 步全部 PASS 之后才渲染;
- 交付说明里如实写: 未验证的设备等价性、未核实的读音、未查到出处的情绪曲线, 都列出来, **不许用推测填空**.

## 这一步要用的脚本

- `<skill>/scripts/render.sh` - 封装成 MKV: 视频/音频 `-c copy` 原样封装 + ASS 外挂轨 + 字体附件 (默认走这条)
- `<skill>/scripts/render_burn.sh` - 把字幕烙进画面的 mp4; 只在目标场景不支持外挂字幕时用
