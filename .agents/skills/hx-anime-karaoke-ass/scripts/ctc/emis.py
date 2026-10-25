# -*- coding: utf-8 -*-
"""CTC 后验的读取与「听到的音拍 vs 歌词音拍」相似度.

为什么单独一个模块: grid_align 的主流程是动态规划(排布), 而这里是**模型侧**的两件事
 跑/读 wav2vec2 的对数后验, 以及把假名对的相似度定义成可比较的罚分. 两者互不依赖,
拆开后 grid_align 只剩"证据 + 槽位 + DP".

similarity 的罚分口径(一致 0 / 同字差浊点 -0.4 / 同元音 -0.8 / 同辅音 -1.2 / 其他 -2.2)
是实测标定的: 齐唱时辅音常被听错(ば↔だ、み↔に), 元音稳定得多, 所以同元音的尖峰算"弱证据".
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ctc.align_ctc import MID, read_wav   # noqa: E402

SMALL = set("ゃゅょぁぃぅぇぉゎ")
# 元音分组：齐唱时辅音常被听错（ば↔だ、み↔に），元音稳定得多 → 同元音的尖峰算“弱证据”
_ROWS = ["あかさたなはまやらわがざだばぱぁゃゎ", "いきしちにひみりぎじぢびぴぃ", "うくすつぬふむゆるぐずづぶぷぅゅ",
         "えけせてねへめれげぜでべぺぇ", "おこそとのほもよろをごぞどぼぽぉょ"]
VOWEL = {c: i for i, r in enumerate(_ROWS) for c in r}


_COLS = ["あいうえお", "かきくけこ", "がぎぐげご", "さしすせそ", "ざじずぜぞ", "たちつてと", "だぢづでど", "なにぬねの",
         "はひふへほ", "ばびぶべぼ", "ぱぴぷぺぽ", "まみむめも", "やゆよ", "らりるれろ", "わを"]
CONS = {c: i for i, r in enumerate(_COLS) for c in r}


def similarity(lyr, heard):
    """
    .agents/notes/implemented/process/2026-10-05-karaoke-scripts-grouping.md
歌词音拍 vs 听到的音拍（均为假名串，如 しゃ / じゃ）"""
    import unicodedata
    # Agent Notes: hx-anime-karaoke-ass 的 scripts/ 按职责分组，并把 5 个超 300 行的模块拆开
    # 
    base = lambda c: unicodedata.normalize("NFD", c)[0]
    if lyr == heard:
        return 0.0
    if lyr[0] in "んー" and heard[0] in "んー":
        return -0.5
    if base(lyr[0]) == base(heard[0]):       # 同字 / 只差浊点（し↔じ、は↔ば↔ぱ）
        return -0.4
    v1, v2 = mora_vowel(lyr), mora_vowel(heard)
    c1, c2 = CONS.get(lyr[0]), CONS.get(heard[0])
    if v1 is not None and v1 == v2:
        return -0.8
    if c1 is not None and c1 == c2:
        return -1.2
    return -2.2


def mora_vowel(tx):
    for c in reversed(tx):
        if c in VOWEL:
            return VOWEL[c]
    return None


# Agent Notes: 卡拉OK skill 通用化  去掉单次制作的事实与清单式铺陈
# 
def emissions(wav, cache=None, threads=48, prefer=""):
    """
    .agents/notes/implemented/process/2026-10-04-karaoke-skill-genericize.md
整首 CTC 对数后验（20ms/帧），可缓存到 npz"""
    if cache and os.path.exists(cache):
        z = np.load(cache, allow_pickle=True)
        return z["lp"], float(z["fd"]), list(z["vocab"])
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    torch.set_num_threads(threads)
    from setup.device import pick_device, log_device, warmup
    DEV = pick_device(prefer)
    log_device(DEV, "grid_align wav2vec2")
    warmup(DEV)
    proc = Wav2Vec2Processor.from_pretrained(MID); model = Wav2Vec2ForCTC.from_pretrained(MID).eval().to(DEV)
    A = read_wav(wav); sr = 16000; CH, OV = 16.0, 1.0; fd = 0.02
    n = int(len(A) / sr / fd) + 1; V = model.config.vocab_size
    lp = np.full((n, V), -30.0, np.float32); t = 0.0
    while t < len(A) / sr:
        seg = A[int(t * sr):int((t + CH) * sr)]
        with torch.no_grad():
            lg = model(proc(seg, sampling_rate=sr, return_tensors="pt").input_values.to(DEV)).logits[0]
        l = torch.log_softmax(lg, -1).detach().cpu().numpy(); f = (len(seg) / sr) / l.shape[0]
        for i in range(l.shape[0]):
            tt = t + i * f
            if t > 0 and tt < t + OV / 2:
                continue
            k = int(round(tt / fd))
            if k < n:
                lp[k] = l[i]
        t += CH - OV
    inv = {v: k for k, v in proc.tokenizer.get_vocab().items()}
    vocab = [inv.get(i, "?") for i in range(V)]
    if cache:
        np.savez(cache, lp=lp, fd=fd, vocab=np.array(vocab, dtype=object))
    return lp, fd, vocab
