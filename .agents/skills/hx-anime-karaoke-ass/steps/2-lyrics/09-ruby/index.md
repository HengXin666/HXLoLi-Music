# 09 排版校准(注音高度必须实测)

## 只做这一件事

量出**注音 / 汉字 / 中文**三者的实际墨迹位置, 算出 y 偏移, 产出 `calib.json`

## 为什么必须实测

`\an5` 的中心是**字体行框中心**而不是**墨迹中心**. Shippori Mincho 这类 win 度量大的字体, fs66 时实际墨迹只有 ~42px  按行框摆注音会离汉字很远

## 命令

```bash
hx-karaoke calibrate_ruby.py --fontsdir fonts --jp "Shippori Mincho B1" --jp-fs 84 --rb-fs 34 \
   --cn "LXGW WenKai Medium" --cn-fs 50 --jp-y 915 --ruby-gap 5 --cn-gap 20 --out proj/calib.json
```

字号建议(1080p): 日文墨迹高 ~55px(Shippori fs84)、注音 ~19px(fs34)、中文 ~34px(文楷 fs50); 歌词块放在 y≈866~1000, 下边距 ≥80px

## 判据

**注音墨迹底到汉字墨迹顶 4~6px**; 中文与日文的墨迹间距 ~20px. `calib.json` 里的 `jp-y` 必须与生成器里的 `JP_Y` **一致**, 否则前面量的一切都白量

## 产物与过关条件

`proj/calib.json` 存在, 且生成器读的是同一个文件(不是硬编码的近似值). `check_gates.py --stage render` 会查这个文件存在性
