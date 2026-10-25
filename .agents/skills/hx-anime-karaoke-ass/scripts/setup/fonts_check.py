# -*- coding: utf-8 -*-
"""字体是否需要补齐 (与 fetch_fonts.py 的下载目标同一份名单)."""
import os

from setup.env import FONTS


def check_fonts() -> list[str]:
    want = ["ShipporiMinchoB1-Bold.ttf", "ShipporiMincho-Bold.ttf", "MochiyPopOne-Regular.ttf",
            "ZCOOLKuaiLe-Regular.ttf", "CormorantGaramond-Italic[wght].ttf",
            "CormorantGaramond-Light.ttf", "LXGWWenKai-Medium.ttf"]
    return [f for f in want if not os.path.exists(os.path.join(FONTS, f))]
