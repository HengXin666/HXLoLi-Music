# mushoku_ed1: 無職転生 ED1「オンリー」(大原ゆい子)

skill 内唯一的完整示例工程 (2026-11-12 起为 オンリー 定稿快照). 用法与文件分工见 `steps/4-kfx/49-generate/index.md`.

## assets 有意不入库

`assets/` 被仓库 `.gitignore` (`examples/*/assets/`) 挡住: 里面的 PNG 是从 MV 原片抠出来的, 不进 git. 要跑出完整版, 自备这 4 个文件放到 `assets/`:

| 文件 | 用在 | slot |
|------|------|------|
| `assets/motif.json` | 图片母题配置 (裁切 / 尺寸 / 锚点 / 调色) | 全部 |
| `assets/sword_red_x.png` | 第 30 句交叉剑 | `p30_sword_a`, `p30_sword_b` |
| `assets/hand_palm_01.png` | 第 31 句托掌 | `p31_palm` |
| `assets/hand_reach_01.png` | (配置里登记, 当前版本未上屏) | |

## 缺了会怎样

不报错, 照常生成, 但图片母题回退成矢量, 并且**有声音**: 生成结束时终端打一行 `[motif_img] 注意: 这次不是完整版, N 个 slot 回退成矢量 ...`, `out.ass` 旁边留 `out.motif_fallback.json` 旁证 (完整版不留这个文件).

| 版本 | out.ass sha256 (前 8 位) | Dialogue | validate | 与完整版的差别 |
|------|------|------|------|------|
| 完整版 (自备 assets) | c67225a5 | 10380 | 通过 | 与 dev 定稿逐字节一致 |
| 干净 clone (无 assets) | bc4d35fd | 10378 | 通过 | p30 交叉剑、p31 托掌回退成矢量; 67.0 / 69.0 / 165.5 / 190.6 / 215.5s 关键帧 0 像素差 |

干净 clone 那一行是本示例对外的实际承诺.
