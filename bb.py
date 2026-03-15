import json,re,subprocess,os,sys
from pathlib import Path
from datetime import datetime

def main():
    url=sys.argv[1]
    print("URL: "+url)

    print("1/4 タイトル取得...")
    title="Bloomberg Brief"
    try:
        r=subprocess.run(["yt-dlp","--get-title","--no-playlist",url],capture_output=True,text=True,timeout=30)
        if r.returncode==0 and r.stdout.strip():title=r.stdout.strip()
    except:pass
    print("  "+title)

    print("2/4 音声ダウンロード...")
    Path("/tmp/bb").mkdir(exist_ok=True)
    for f in Path("/tmp/bb").glob("*"):f.unlink()
    subprocess.run(["yt-dlp","-x","--audio-format","wav","--postprocessor-args","-ar 16000 -ac 1","-o","/tmp/bb/a.%(ext)s","--no-playlist",url],capture_output=True)
    ap=None
    for f in Path("/tmp/bb").glob("a.*"):ap=f;break
    if not ap:
        print("音声DL失敗")
        return
    print("  "+str(round(ap.stat().st_size/1024/1024,1))+"MB")

    print("3/4 Whisper文字起こし...")
    import whisper
    m=whisper.load_model("base")
    r=m.transcribe(str(ap),language="en")
    text=r["text"]
    print("  "+str(len(text))+"文字")

    print("4/4 Claude分析...")
    import anthropic
    client=anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    sp="JSONだけ返せ。説明不要。"

    r1=client.messages.create(model="claude-sonnet-4-20250514",max_tokens=3000,system=sp,
        messages=[{"role":"user","content":"Bloomberg Briefトランスクリプトをテーマ3-5個に分割。transcriptは正確な英語、translationは自然な日本語、market_impactは投資への影響。\nJSON:{\"segments\":[{\"theme\":\"英語\",\"theme_ja\":\"日本語\",\"transcript\":\"英語\",\"translation\":\"日本語\",\"market_impact\":\"日本語\"}],\"macro_summary\":{\"key_takeaways\":[\"日本語\"],\"market_sentiment\":\"日本語\",\"sectors_to_watch\":[\"セクター\"]}}\n\nテキスト:\n"+text[:6000]}])
    raw1="".join(b.text for b in r1.content if b.type=="text")
    d1=json.loads(raw1[raw1.find("{"):raw1.rfind("}")+1])

    r2=client.messages.create(model="claude-sonnet-4-20250514",max_tokens=3000,system=sp,
        messages=[{"role":"user","content":"Bloomberg Brief字幕から重要英語表現6-8個抽出。etymology語源詳しく、examples3種。\nJSON:{\"vocabulary\":[{\"expression\":\"英語\",\"reading\":\"カタカナ\",\"meaning\":\"意味\",\"etymology\":\"語源\",\"context\":\"使われ方\",\"collocations\":[\"3つ\"],\"examples\":[{\"type\":\"real-life\",\"en\":\"英文\",\"ja\":\"訳\"},{\"type\":\"macro\",\"en\":\"英文\",\"ja\":\"訳\"},{\"type\":\"business\",\"en\":\"英文\",\"ja\":\"訳\"}]}]}\n\nテキスト:\n"+text[:4000]}])
    raw2="".join(b.text for b in r2.content if b.type=="text")
    d2=json.loads(raw2[raw2.find("{"):raw2.rfind("}")+1])

    a={**d1,**d2,"title":title,"date":datetime.now().strftime("%Y-%m-%d")}
    transcript="\n\n".join(s.get("transcript","") for s in a.get("segments",[]))
    m=a.get("macro_summary",{})

    segs=""
    for i,s in enumerate(a.get("segments",[])):
        segs+=f"<div class=card><h3>{i+1}. {s.get('theme','')} / {s.get('theme_ja','')}</h3><p><b>English:</b> {s.get('transcript','')}</p><p><b>日本語:</b> {s.get('translation','')}</p><p><b>Impact:</b> {s.get('market_impact','')}</p></div>"

    vocs=""
    for v in a.get("vocabulary",[]):
        exs="".join(f"<div class=ex><b>{e.get('type','')}:</b> {e.get('en','')}<br><i>{e.get('ja','')}</i></div>" for e in v.get("examples",[]))
        vocs+=f"<div class=vcard><h3>{v.get('expression','')} ({v.get('reading','')})</h3><p><b>意味:</b> {v.get('meaning','')}</p><p><b>語源:</b> {v.get('etymology','')}</p><p><b>使われ方:</b> {v.get('context','')}</p><p><b>Collocations:</b> {', '.join(v.get('collocations',[]))}</p>{exs}</div>"

    tk="".join(f"<li>{t}</li>" for t in m.get("key_takeaways",[]))
    sc=", ".join(m.get("sectors_to_watch",[]))

    html=f"""<!DOCTYPE html><html><head><meta charset=UTF-8><meta name=viewport content="width=device-width,initial-scale=1">
<style>body{{font-family:sans-serif;background:#0a1628;color:#d4dce6;padding:16px;max-width:800px;margin:0 auto}}
h1{{color:#fff;font-size:20px}}h2{{color:#00c896;margin-top:24px}}h3{{color:#e8ecf2;font-size:15px}}
a{{color:#00a0ff}}.card,.vcard{{background:rgba(255,255,255,.04);border-left:3px solid #00c896;padding:12px;margin:8px 0;border-radius:4px}}
.vcard{{border-left-color:#ffaa32}}.ex{{background:rgba(0,0,0,.2);padding:8px;margin:4px 0;border-radius:4px;font-size:14px}}
li{{line-height:2}}b{{color:#fff}}i{{color:rgba(200,215,230,.6)}}</style></head>
<body><h1>{title}</h1><p>{a['date']}</p><a href="{url}">YouTube</a>
<h2>Key Takeaways</h2><ul>{tk}</ul><p><b>Sentiment:</b> {m.get('market_sentiment','')}</p><p><b>注目:</b> {sc}</p>
<h2>テーマ別</h2>{segs}<h2>重要表現</h2>{vocs}
<h2>Full Transcript</h2><div style="background:rgba(0,0,0,.2);padding:16px;border-radius:6px;line-height:2">{transcript}</div></body></html>"""

    Path("reports").mkdir(exist_ok=True)
    d=a["date"]
    Path(f"reports/{d}.html").write_text(html)
    Path(f"reports/{d}.json").write_text(json.dumps(a,ensure_ascii=False,indent=2))
    print("完了: reports/"+d+".html")

if __name__=="__main__":main()
