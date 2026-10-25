import json, os, sys
INC="/home/hx/.local/opt/aegisub/usr/share/aegisub/automation/include"
AL="/home/hx/.local/opt/aegisub/usr/share/aegisub/automation/autoload"
os.environ["AEGISUB_AUTOMATION_INCLUDE"]=INC
sys.path.insert(0,"/home/hx/.local/opt/aegisub-mcp/src")
import aegisub_mcp.lua.engine as E
from aegisub_mcp.asscore import document as doc
BS=chr(92)
P=json.load(open("/home/hx/kfx-work/params2.json",encoding="utf-8"))
pmap={x["i"]:x for x in P}
src="/home/hx/kfx-work/df_full/7_phonetic.ass"
raw=open(src,encoding="utf_8_sig").read()
events=[]
for l in raw.splitlines():
    if l.startswith("Dialogue:") or (l.startswith("Comment:") and ",karaoke," in l):
        f=l.split(",",9)
        if len(f)>=10: events.append({"start":f[1],"end":f[2],"text":f[9]})
def to_ass(rgb):
    r,g,b=rgb
    return "&H00%02X%02X%02X&" % (b,g,r)
HDR = "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
sty=[]
for i in range(1,len(events)+1):
    c=to_ass(pmap[i]["rgb"])
    sty.append("Style: S%d,Noto Sans CJK JP,86,&H00FFFFFF,&H000000FF,%s,&H96000000,-1,0,0,0,100,100,3,0,1,4,2,5,10,10,0,1" % (i,c))
lines=[HDR+"\n".join(sty)]
lines.append("\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
for i,e in enumerate(events,1):
    lines.append("Dialogue: 0,%s,%s,S%d,,0,0,0,,%s" % (e["start"],e["end"],i,e["text"]))
for i,e in enumerate(events,1):
    p=pmap[i]; dur=int(p["dur"]); g=p["ghost"]; c=to_ass(p["rgb"])
    ghost="&H00%02X%02X%02X&" % (g,g,g)
    t1=int(dur*0.45); t2=dur
    # 用 + 拼接, 不用 % 格式化
    tpl=("{"+BS+"an5"+BS+"pos($scenter,$middle)"+BS+"alpha&H00&"
         +BS+"1c"+ghost+BS+"3c&H00100804&"+BS+"bord2"+BS+"blur2.2"
         +BS+"t(!$sstart!,!$sstart+"+str(t1)+"!,"+BS+"1c&H00FFFFFF&"+BS+"3c"+c+BS+"bord4"+BS+"blur0.4"+BS+"fscx126"+BS+"fscy126)"
         +BS+"t(!$sstart+"+str(t1)+"!,!$sstart+"+str(t2)+"!,"+BS+"fscx100"+BS+"fscy100)}")
    lines.append("Comment: 0,0:00:00.00,0:00:00.00,S"+str(i)+",,0,0,0,template syl,"+tpl)
open("/home/hx/kfx-work/df_full/20_in.ass","w",encoding="utf_8_sig").write("\n".join(lines)+"\n")
d=doc.AssDocument.load("/home/hx/kfx-work/df_full/20_in.ass")
e2=E.LuaEngine(d)
for f in ("karaskel.lua","utils.lua","unicode.lua"):
    pp=os.path.join(INC,f)
    if os.path.exists(pp): e2.load_file(pp)
e2.load_file(os.path.join(AL,"kara-templater.lua"))
r=e2.run_filter("Karaoke template")
print("模板器:", r.ok, (r.error or "")[:120])
print("事件:", len(d.events()))
if r.ok:
    out="/home/hx/kfx-work/df_full/21_model.ass"
    d.save(out)
    print("成品:", os.path.getsize(out), "字节")
    n=0
    for ev in d.events():
        if ev.is_comment: continue
        print("  ", str(ev.raw)[:120] if hasattr(ev,"raw") else str(ev)[:120]); n+=1
        if n>=3: break

