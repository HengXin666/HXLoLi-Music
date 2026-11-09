"""Stable, position-independent RNG for assfx (replaces Random(seed+i) and the shared beat rng)."""
import hashlib
import random
import re
import unicodedata


def _derive(*parts):
    h = hashlib.blake2b(digest_size=8)
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x1f")
    return int.from_bytes(h.digest(), "big")


def _norm(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def line_keys(lines):
    seen = {}
    keys = []
    for ln in lines:
        if isinstance(ln, dict) and ln.get("id"):
            keys.append(str(ln["id"]))
            continue
        text = ln["text"] if isinstance(ln, dict) else str(ln)
        base = hashlib.blake2b(_norm(text).encode("utf-8"), digest_size=4).hexdigest()
        n = seen.get(base, 0)
        seen[base] = n + 1
        keys.append("%s.%d" % (base, n))
    return keys


def line_rng(seed, key, layer, salt=0):
    return random.Random(_derive(seed, "line", key, layer, salt))


def beat_rng(seed, beat_ms, salt=0):
    return random.Random(_derive(seed, "beat", int(beat_ms), salt))


if __name__ == "__main__":
    a = [{"text": t} for t in ["そらに", "はなを", "そらに", "うたう"]]
    b = a[:2] + [{"text": "新しい行"}] + a[2:]
    ka, kb = line_keys(a), line_keys(b)
    draw = lambda k: line_rng(7, k, "fx").random()
    va = {k: draw(k) for k in ka}
    vb = {k: draw(k) for k in kb}
    assert all(va[k] == vb[k] for k in ka), "untouched lines changed"
    assert ka[0] != ka[2], "repeated lines must get distinct keys"
    assert line_rng(7, ka[0], "fx", 1).random() != va[ka[0]], "salt must reroll"
    assert beat_rng(7, 61200).random() == beat_rng(7, 61200).random()
    print("seeding selftest ok")
