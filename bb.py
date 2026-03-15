import json,re,subprocess,os,sys
from pathlib import Path
from datetime import datetime

def clean_url(url):
    if "youtu.be/" in url:
        vid=url.split("youtu.be/")[1].split("?")[0].split("&")[0]
        return "https://www.youtube.com/watch?v="+vid
    if "watch?v=" in url:
        vid=url.split("watch?v=")[1].split("&")[0]
        return "https://www.youtube.com/watch?v="+vid
    return url

def get_subs(url):
    Path("/tmp/bb").mkdir(exist_ok=True)
    for f in Path("/tmp/bb").glob("*"):f.unlink()
    for method in [["--write-auto-sub"],["--write-sub"]]:
        cmd=["yt-dlp"]+method+["--sub-lang","en","--skip-download","--sub-format","vtt","-o","/tmp/bb/s.%(ext)s","--no-playlist",url]
        subprocess.run(cmd,capture_output=True,text=True,timeout=60)
        for f in Path("/tmp/bb").glob("*.vtt"):
            prev=""
            lines=[]
            for line in f.read_text(errors="ignore").split("\n"):
                line=line.strip()
                if not line or line.startswith("WEBVTT") or line.startswith("Kind") or line.startswith("Lang") or "-->" in line or re.match(r"^\d+$",line):continue
                c=re.sub(r"<[^>]+>","",line).strip()
                if c and c!=prev:lines.append(c);prev=c
            if lines:return " ".join(lines)
    return ""

def main():
    url=clean_url(sys.argv[1])
    print("URL: "+url)

    print("1/3 字幕取得...")
    sub=get_subs(url)
    if not sub:
        print("字幕取得失敗")
        return
    sub=sub[:10000]
    print(f"  {len(sub)}文字取得")

    print("2/3 Claude分析...")
    import anthropic
    client=anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    sp="JSONだけ返せ。説明不要。"

    print("  セグメント分析...")
    r1=client.messages.create(model="claude-sonnet-4-20250514",max_tokens=3000,system=sp,
        messages=[{"role":"user","content":"以下はBloomberg Briefの自動生成YouTube字幕です。誤字・脱字が多いので、あなたの金融知識で正しい英語に修正してください。テーマ3-5個に分割。\nJSON:{\"segments\":[{\"theme\":\"英語\",\"theme_ja\":\"日本語\",\"transcript\":\"修正済み正確な英語\",\"translation\":\"自然な日本語訳\",\"market_impact\":\"投資への影響（日本語）\"}],\"macro_summary\":{\"key_takeaways\":[\"日本語\"],\"market_sentiment\":\"日本語\",\"sectors_to_watch\":[\"セクター\"]}}\n\n字幕:\n"+sub[:6000]}])
    raw1="".join(b.text for b in r1.content if b.type=="text")
    d1=json.loads(raw1[raw1.find("{"):raw1.rfind("}")+1])
    print(f"    {len(d1.get('segments',[]))}セグメント")

    print("  語彙分析...")
    r2=client.messages.create(model="claude-sonnet-4-20250514",max_tokens=3000,system=sp,
        messages=[{"role":"user","content":"以下のBloomberg Brief字幕から重要英語表現6-8個抽出。etymology語源は詳しく。examples3種（real-life日常会話、macroマクロ動向、businessビジネス）。\nJSON:{\"vocabulary\":[{\"expression\":\"英語\",\"reading\":\"カタカナ\",\"meaning\":\"意味\",\"etymology\":\"語源（詳しく）\",\"context\":\"使われ方\",\"collocations\":[\"3つ\"],\"examples\":[{\"type\":\"real-life\",\"en\":\"英文\",\"ja\":\"訳\"},{\"type\":\"macro\",\"en\":\"英文\",\"ja\":\"訳\"},{\"type\":\"business\",\"en\":\"英文\",\"ja\":\"訳\"}]}]}\n\n字幕:\n"+sub[:4000]}])
    raw2="".join(b.text for b in r2.content if b.type=="text")
    d2=json.loads(raw2[raw2.find("{"):raw2.rfind("}")+1])
    print(f"    {len(d2.get('vocabulary',[]))}表現")

    title=d1.get("segments",[{}])[0].get("theme","Bloomberg Brief")
    date=datetime.now().strftime("%Y-%m-%d")
    a={**d1,**d2,"title":"Bloomberg Brief "+date,"date":date}
    transcript="\n\n".join(s.get("transcript","") for s in a.get("segments",[]))
    mc=a.get("macro_summary",{})

    print("3/3 レポート生成...")
    segs=""
    for i,s in enumerate(a.get("segments",[])):
        segs+=f"<div class=card><h3>{i+1}. {s.get('theme','')} / {s.get('theme_ja','')}</h3><p><b>English:</b> {s.get('transcript','')}</p><p><b>日本語:</b> {s.get('translation','')}</p><p><b>Impact:</b> {s.get('market_impact','')}</p></div>"
    vocs=""
    for v in a.get("vocabulary",[]):
        exs="".join(f"<div class=ex><b>{e.get('type','')}:</b> {e.get('en','')}<br><i>{e.get('ja','')}</i></div>" for e in v.get("examples",[]))
        vocs+=f"<div class=vcard><h3>{v.get('expression','')} ({v.get('reading','')})</h3><p><b>意味:</b> {v.get('meaning','')}</p><p><b>語源:</b> {v.get('etymology','')}</p><p><b>使われ方:</b> {v.get('context','')}</p><p><b>Collocations:</b> {', '.join(v.get('collocations',[]))}</p>{exs}</div>"
    tk="".join(f"<li>{t}</li>" for t in mc.get("key_takeaways",[]))
    sc=", ".join(mc.get("sectors_to_watch",[]))

    html=f"""<!DOCTYPE html><html><head><meta charset=UTF-8><meta name=viewport content="width=device-width,initial-scale=1">
<style>body{{font-family:sans-serif;background:#0a1628;color:#d4dce6;padding:16px;max-width:800px;margin:0 auto}}
h1{{color:#fff;font-size:20px}}h2{{color:#00c896;margin-top:24px}}h3{{color:#e8ecf2;font-size:15px}}
a{{color:#00a0ff}}.card,.vcard{{background:rgba(255,255,255,.04);border-left:3px solid #00c896;padding:12px;margin:8px 0;border-radius:4px}}
.vcard{{border-left-color:#ffaa32}}.ex{{background:rgba(0,0,0,.2);padding:8px;margin:4px 0;border-radius:4px;font-size:14px}}
li{{line-height:2}}b{{color:#fff}}i{{color:rgba(200,215,230,.6)}}</style></head>
<body><h1>Bloomberg Brief {date}</h1><p>{date}</p><a href="{url}">YouTube</a>
<h2>Key Takeaways</h2><ul>{tk}</ul><p><b>Sentiment:</b> {mc.get('market_sentiment','')}</p><p><b>注目:</b> {sc}</p>
<h2>テーマ別</h2>{segs}<h2>重要表現</h2>{vocs}
<h2>Full Transcript</h2><div style="background:rgba(0,0,0,.2);padding:16px;border-radius:6px;line-height:2">{transcript}</div></body></html>"""

    Path("reports").mkdir(exist_ok=True)
    Path(f"reports/{date}.html").write_text(html)
    Path(f"reports/{date}.json").write_text(json.dumps(a,ensure_ascii=False,indent=2))
    print(f"完了: reports/{date}.html")

if __name__=="__main__":main()
