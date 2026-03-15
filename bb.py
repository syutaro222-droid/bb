import json,re,subprocess,os
from pathlib import Path
from urllib.request import urlopen,Request
from xml.etree import ElementTree
from datetime import datetime

def get_videos():
    url="https://www.youtube.com/feeds/videos.xml?channel_id=UCRzbOEy7m44akpTBhHuClgA"
    r=Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urlopen(r,timeout=30) as f:x=f.read()
    ns={"a":"http://www.w3.org/2005/Atom","y":"http://www.youtube.com/xml/schemas/2015"}
    root=ElementTree.fromstring(x)
    vids=[]
    for e in root.findall("a:entry",ns):
        t=e.find("a:title",ns).text or""
        if any(k in t.lower() for k in["daybreak","surveillance","brief","open interest","the close","balance of power"]):
            vids.append({"id":e.find("y:videoId",ns).text,"title":t,"url":"https://www.youtube.com/watch?v="+e.find("y:videoId",ns).text})
    return vids

def get_subs(url):
    subprocess.run(["yt-dlp","--write-auto-sub","--sub-lang","en","--skip-download","--sub-format","vtt","-o","/tmp/s.%(ext)s","--no-playlist",url],capture_output=True)
    for f in Path("/tmp").glob("*.vtt"):
        prev=""
        lines=[]
        for l in f.read_text(errors="ignore").split("\n"):
            l=l.strip()
            if not l or l.startswith("WEBVTT") or l.startswith("Kind") or l.startswith("Lang") or"-->"in l or re.match(r"^\d+$",l):continue
            c=re.sub(r"<[^>]+>","",l).strip()
            if c and c!=prev:lines.append(c);prev=c
        f.unlink()
        return" ".join(lines)
    return""

def whisper_transcribe(url):
    subprocess.run(["yt-dlp","-x","--audio-format","wav","--postprocessor-args","-ar 16000 -ac 1","-o","/tmp/a.%(ext)s","--no-playlist",url],capture_output=True)
    ap=None
    for f in Path("/tmp").glob("a.*"):ap=f;break
    if not ap:return""
    import whisper
    m=whisper.load_model("base")
    r=m.transcribe(str(ap),language="en")
    ap.unlink()
    return r["text"]

def analyze(client,text,title):
    sp="JSONだけ返せ。説明不要。"
    r1=client.messages.create(model="claude-sonnet-4-20250514",max_tokens=3000,system=sp,
        messages=[{"role":"user","content":"Bloomberg Briefトランスクリプトをテーマ3-5個に分割。transcriptは誤字修正済み英語、translationは自然な日本語、market_impactは投資への影響。\nJSON:{\"segments\":[{\"theme\":\"英語\",\"theme_ja\":\"日本語\",\"transcript\":\"英語\",\"translation\":\"日本語\",\"market_impact\":\"日本語\"}],\"macro_summary\":{\"key_takeaways\":[\"日本語\"],\"market_sentiment\":\"日本語\",\"sectors_to_watch\":[\"セクター\"]}}\n\nテキスト:\n"+text[:6000]}])
    raw1="".join(b.text for b in r1.content if b.type=="text")
    s1=raw1.find("{");e1=raw1.rfind("}")
    d1=json.loads(raw1[s1:e1+1])
    r2=client.messages.create(model="claude-sonnet-4-20250514",max_tokens=3000,system=sp,
        messages=[{"role":"user","content":"Bloomberg Brief字幕から重要英語表現6-8個抽出。etymology語源詳しく、examples3種。\nJSON:{\"vocabulary\":[{\"expression\":\"英語\",\"reading\":\"カタカナ\",\"meaning\":\"意味\",\"etymology\":\"語源\",\"context\":\"使われ方\",\"collocations\":[\"3つ\"],\"examples\":[{\"type\":\"real-life\",\"en\":\"英文\",\"ja\":\"訳\"},{\"type\":\"macro\",\"en\":\"英文\",\"ja\":\"訳\"},{\"type\":\"business\",\"en\":\"英文\",\"ja\":\"訳\"}]}]}\n\nテキスト:\n"+text[:4000]}])
    raw2="".join(b.text for b in r2.content if b.type=="text")
    s2=raw2.find("{");e2=raw2.rfind("}")
    d2=json.loads(raw2[s2:e2+1])
    return{**d1,**d2,"title":title,"date":datetime.now().strftime("%Y-%m-%d")}

def make_html(a,url):
    segs=""
    for i,s in enumerate(a.get("segments",[])):
        segs+=f"<div class=card><h3>{i+1}. {s.get('theme','')} / {s.get('theme_ja','')}</h3>"
        segs+=f"<p><b>English:</b> {s.get('transcript','')}</p>"
        segs+=f"<p><b>日本語:</b> {s.get('translation','')}</p>"
        segs+=f"<p><b>Impact:</b> {s.get('market_impact','')}</p></div>"
    vocs=""
    for i,v in enumerate(a.get("vocabulary",[])):
        exs=""
        for ex in v.get("examples",[]):
            exs+=f"<div class=ex><b>{ex.get('type','')}:</b> {ex.get('en','')}<br><i>{ex.get('ja','')}</i></div>"
        cols=", ".join(v.get("collocations",[]))
        vocs+=f"<div class=vcard><h3>{v.get('expression','')} ({v.get('reading','')})</h3>"
        vocs+=f"<p><b>意味:</b> {v.get('meaning','')}</p>"
        vocs+=f"<p><b>語源:</b> {v.get('etymology','')}</p>"
        vocs+=f"<p><b>使われ方:</b> {v.get('context','')}</p>"
        vocs+=f"<p><b>Collocations:</b> {cols}</p>{exs}</div>"
    m=a.get("macro_summary",{})
    tk="".join(f"<li>{t}</li>" for t in m.get("key_takeaways",[]))
    sc=", ".join(m.get("sectors_to_watch",[]))
    return f"""<!DOCTYPE html><html><head><meta charset=UTF-8><meta name=viewport content="width=device-width,initial-scale=1">
<style>body{{font-family:sans-serif;background:#0a1628;color:#d4dce6;padding:16px;max-width:800px;margin:0 auto}}
h1{{color:#fff;font-size:20px}}h2{{color:#00c896;margin-top:24px}}h3{{color:#e8ecf2;font-size:15px}}
a{{color:#00a0ff}}.card,.vcard{{background:rgba(255,255,255,.04);border-left:3px solid #00c896;padding:12px;margin:8px 0;border-radius:4px}}
.vcard{{border-left-color:#ffaa32}}.ex{{background:rgba(0,0,0,.2);padding:8px;margin:4px 0;border-radius:4px;font-size:14px}}
li{{line-height:2}}b{{color:#fff}}i{{color:rgba(200,215,230,.6)}}</style></head>
<body><h1>{a.get('title','')}</h1><p>{a.get('date','')}</p><a href="{url}">YouTube</a>
<h2>Key Takeaways</h2><ul>{tk}</ul><p><b>Sentiment:</b> {m.get('market_sentiment','')}</p><p><b>注目:</b> {sc}</p>
<h2>テーマ別</h2>{segs}<h2>重要表現</h2>{vocs}</body></html>"""

def main():
    done=[]
    dp=Path("done.json")
    if dp.exists():done=json.loads(dp.read_text())
    vids=get_videos()
    if not vids:print("No videos");return
    import anthropic
    client=anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    for v in vids[:1]:
        if v["id"]in done:print("Skip "+v["id"]);continue
        print("Processing: "+v["title"])
        text=whisper_transcribe(v["url"])
        if not text:
            print("Whisper failed, trying subs...")
            text=get_subs(v["url"])
        if not text:print("No transcript");continue
        a=analyze(client,text,v["title"])
        Path("reports").mkdir(exist_ok=True)
        d=a.get("date",datetime.now().strftime("%Y-%m-%d"))
        Path(f"reports/{d}.html").write_text(make_html(a,v["url"]))
        Path(f"reports/{d}.json").write_text(json.dumps(a,ensure_ascii=False,indent=2))
        done.append(v["id"])
        dp.write_text(json.dumps(done))
        print("Done: "+v["title"])

if __name__=="__main__":main()
