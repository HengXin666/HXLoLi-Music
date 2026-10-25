import json, colorsys
# 修正色相映射: 问题是"中间值全落在黄绿(50-130)", 观感浑浊
# 正确做法: 用"色相分区"而不是线性插值, 让每段有明确色彩身份
#   v < -0.5        深蓝紫   (250-270)  最负
#   -0.5 <= v < -0.2 青蓝    (200-230)
#   -0.2 <= v < 0.2  中性    (30-45) 或 (330-350) 暖中性
#   0.2 <= v < 0.6   暖橙金  (25-40)
#   v >= 0.6        翠绿/金 (140-160 或 45)
#
# 关键: 跳开 60-130 这段"橄榄/芥末"区, 它在暗明度下观感很差
ZONES=[
    (-1.01,-0.50, 255, "深蓝紫"),
    (-0.50,-0.20, 210, "青蓝"),
    (-0.20, 0.20,  35, "暖中性"),
    ( 0.20, 0.60,  28, "琥珀"),
    ( 0.60, 1.01, 150, "翠绿"),
]
# Agent Notes: KFX 质量红线（静态拦截）
# 
def hue_of(v):
    """Agent Notes
    .agents/notes/implemented/process/2026-09-28-kfx-quality-redline.md
    """
    for lo,hi,h,nm in ZONES:
        if lo <= v < hi: return h, nm
    return 35, "暖中性"

def lum(c):
    def f(x):
        x=x/255.0
        return x/12.92 if x<=0.03928 else ((x+0.055)/1.055)**2.4
    return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2])
def ratio(a,b):
    l1,l2=lum(a),lum(b); hi,lo=max(l1,l2),min(l1,l2)
    return (hi+0.05)/(lo+0.05)

V=[0.10,-0.55,0.65,-0.20,-0.75,0.15,0.35,-0.40,0.20,0.50,0.40,0.05,0.55,0.10,0.30,-0.60,-0.70,-0.45,0.10,-0.25,-0.50,0.45,-0.30,-0.35,0.25,0.45,0.50,0.70,0.65,0.40,0.55,0.20,0.60,0.55,0.60,0.50,0.65,0.75]
A=[0.30,0.75,0.80,0.35,0.60,0.55,0.85,0.65,0.90,0.75,0.50,0.25,0.40,0.35,0.30,0.45,0.40,0.30,0.55,0.30,0.35,0.65,0.60,0.35,0.55,0.15,0.30,0.35,0.40,0.50,0.30,0.40,0.45,0.30,0.45,0.15,0.35,0.40]
BG=(0x0B,0x10,0x16)
res=[]
print(" #  V     A    区      色相  描边RGB           白/描边 时长  缓动")
for i,(v,a) in enumerate(zip(V,A),1):
    h,nm=hue_of(v)
    # 色相做轻微抖动, 避免同区完全一样的色
    h = (h + (a-0.5)*12) % 360
    s = 0.42 + a*0.38          # 0.42~0.80  高唤醒更艳
    l = 0.15 + a*0.03          # 0.15~0.18  守着亮度上限
    r,g,b=colorsys.hls_to_rgb(h/360.0, l, s)
    rgb=(int(r*255),int(g*255),int(b*255))
    R=ratio((255,255,255),rgb)
    dur=int(520-a*380)
    ease="ease-out" if v>=0 else "ease-in"
    ghost=int(108+a*20)
    rg=ratio((ghost,ghost,ghost),BG)
    ok = R>=4.5 and rg>=3.0
    res.append({"i":i,"v":v,"a":a,"hue":round(h,0),"zone":nm,"rgb":rgb,
                "contrast":round(R,2),"ghost":ghost,"ghost_contrast":round(rg,2),
                "dur":dur,"ease":ease})
    print("%2d %+.2f %.2f %-6s %4.0f° RGB%-16s %5.2f  %4d  %-8s %s"
          % (i,v,a,nm,h,str(rgb),R,dur,ease,"" if R>=4.5 else "FAIL"))
json.dump(res, open("/home/hx/kfx-work/params2.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
bad=[x for x in res if x["contrast"]<4.5]
print()
print("不合格:", len(bad), "/", len(res))

