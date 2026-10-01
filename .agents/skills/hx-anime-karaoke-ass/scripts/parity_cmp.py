# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
# 副歌/重复段对比：同一句词在两次出现中的相对节奏（差 >0.12s 标 <<）
# 用法: uv run parity_cmp.py timing.json 15:48,16:49
import json,sys
T=json.load(open(sys.argv[1]))
def L(li): return [m for m in T if m["line"]==li]
for pair in sys.argv[2].split(","):
    a,b=map(int,pair.split(":")); A,B=L(a),L(b)
    off=B[0]["s"]-A[0]["s"]
    print(f"{a}:{b} off {off:.2f}")
    for x,y in zip(A,B):
        d=y["s"]-x["s"]-off
        print(f'  {x["unit"]},{x["mora"]}{x["text"]}{x["s"]:.2f} | {y["unit"]},{y["mora"]}{y["text"]}{y["s"]:.2f}  {d:+.2f}{" <<" if abs(d)>0.12 else ""}')
