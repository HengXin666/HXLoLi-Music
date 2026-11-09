# 预设: 有名字, 有理由, 有校验

预设让改动可控: 改色只能在有名字的色组间切, 换动作只能在有理由的组合间选. 不提供"随机预设", 那等于回到抽奖

## skill 自带的起点

| 文件 | format | 每项字段 |
|---|---|---|
| `scripts/assfx/presets/themes.json` | `assfx-themes` | `hi glow dark` (`#RRGGBB`), `why` |
| `scripts/assfx/presets/motions.json` | `assfx-motions` | `ent ext hl`, 可选 `din dout`, `why` 必填 |

`Generator` 启动时自动载入. 工程登记的同名项优先

## 校验 (照 shotcraft 的 parsePalette)

- `format` 与 `version` 不对: 拒收整个文件
- 颜色不是 `#RRGGBB`, 缺 `hi/glow/dark`: 拒收
- 动作的 `ent/ext/hl` 不在库支持的选项里: 拒收
- 动作没写 `why`: 拒收. 说不出组合表达什么, 它就不该是预设

## 工程自己登记

```python
from assfx.layer.manifest import register_theme, register_motion, register_family
TH_RAIN = register_theme("RAIN", TH("#EEF4FF", "#7FA8D8", "#0A1424"), why="雨夜, 冷色街景")
register_motion("回眸", "flip", "fade", "bloom", why="角色回头的镜头")
register_family("ember", ["#FFB040", "#FF6A1F"], why="篝火段卡点")
```

预设名会写进清单与交付说明. 起名用画面或情绪, 不用颜色值
