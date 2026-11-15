"""Build the blind page for the human second rater: one self-contained HTML file.

usage: python3 -I review_page/build_second_rater.py   (from the repo root)
inputs : stage_a/second_rater_sample.csv (order, incident_id, mmsi),
         review_page/build/index.json and cases_NN.json (from build_review.py),
         review_page/review.html (layout and rules text)
output : review_page/second_rater.html

BLIND: only the case cards built by build_review.py are embedded. Nothing from
data/janice_review.csv, data/claude_review.csv or data/second_look.csv is read, and
the sample file carries no stratum, so neither earlier answer can reach the page.
Answers are kept in the rater's browser (localStorage) and downloaded as a CSV.
"""
import json
import re

import pandas as pd

idx = json.load(open("review_page/build/index.json"))
chunk = idx["chunk"]
pos = {k: i for i, k in enumerate(idx["keys"])}
sample = pd.read_csv("stage_a/second_rater_sample.csv").sort_values("order")
cache, cases = {}, []
for r in sample.itertuples():
    key = f"{r.incident_id}__{r.mmsi}"
    i = pos[key]
    n = i // chunk
    if n not in cache:
        cache[n] = json.load(open(f"review_page/build/cases_{n:02d}.json"))
    c = cache[n][i % chunk]
    assert c["key"] == key
    cases.append(c)
assert len(cases) == 100 and len({c["key"] for c in cases}) == 100

html = open("review_page/review.html").read()
html = re.sub(r"<meta name=\"claude:[^>]*>\n?", "", html)

# header and notices
html = html.replace("<h1>WAKE Match Review</h1>", "<h1>WAKE Match Review: second rater</h1>")
html = re.sub(r'<div class="warn" id="nodb" hidden>.*?</div>',
              '<div class="warn" id="nodb">Answers are saved in this browser on this computer only. '
              'Use the same browser each time, do not clear its history, and when you finish click '
              '<b>Download answers</b> and send the file to Janice.</div>', html, flags=re.S)
html = html.replace(
    '<form class="jump" id="jumpf">',
    '<button type="button" class="small" id="dl">Download answers</button>\n      <form class="jump" id="jumpf">')
html = html.replace(
    " Cases 1–50 are a random sample used for an early check, so please do those first.",
    " Work alone and do not look up the vessels elsewhere; decide from what is on screen. "
    "The full rules are in SECOND_RATER_INSTRUCTIONS.md, which came with this page.")

# data: embedded instead of fetched
script_head = ("const CASES=" + json.dumps(cases, separators=(",", ":")) + ";\n"
               "const KEY='wake_second_rater_v1';\n")
html = html.replace("<script>\n", "<script>\n" + script_head, 1)
html = re.sub(r"async function loadChunk\(n\)\{.*?\n\}\nasync function getCase\(i\)\{.*?\}\n",
              "async function getCase(i){return CASES[i]}\n", html, flags=re.S)

# storage: localStorage instead of the artifact database
WRITE = ("function write(key){\n"
              "  try{const a=answers[key];a.at=new Date().toISOString();localStorage.setItem(KEY,JSON.stringify(answers));\n"
              "      if(INDEX.keys[cur]===key&&$(\"saved\"))$(\"saved\").textContent=\"Saved\";}\n"
              "  catch(e){if($(\"saved\"))$(\"saved\").textContent=\"Not saved: this browser blocks storage\";}\n"
              "}\n"
              "function download(){\n"
              "  const q=s=>'\"'+String(s??'').replace(/\"/g,'\"\"')+'\"';\n"
              "  const rows=[\"order,incident_id,mmsi,decision,note,answered_at\"];\n"
              "  INDEX.keys.forEach((k,i)=>{const a=answers[k]||{};const [inc,m]=k.split('__');\n"
              "    rows.push([i+1,inc,m,a.v||'',q(a.note),a.at||''].join(','))});\n"
              "  const b=new Blob([rows.join('\\n')+'\\n'],{type:'text/csv'});const u=URL.createObjectURL(b);\n"
              "  const l=document.createElement('a');l.href=u;l.download='second_rater_answers.csv';document.body.appendChild(l);l.click();l.remove();\n"
              "  setTimeout(()=>URL.revokeObjectURL(u),1000);\n"
              "}\n")
html = re.sub(r"async function write\(key\)\{.*?\n\}\n", lambda m: WRITE, html, flags=re.S)
html = html.replace('$("saved").textContent=db?"Saving…":"Not saved (no storage here)";',
                    '$("saved").textContent="Saving…";')

# start-up
html = re.sub(r"\(async function start\(\)\{.*?\n\}\)\(\);",
              "(async function start(){\n"
              "  INDEX={keys:CASES.map(c=>c.key),n:CASES.length};\n"
              "  try{answers=JSON.parse(localStorage.getItem(KEY)||'{}')||{}}catch(e){answers={}}\n"
              "  $(\"nextun\").onclick=nextUnanswered; $(\"dl\").onclick=download;\n"
              "  $(\"jumpf\").addEventListener(\"submit\",e=>{e.preventDefault();const n=parseInt($(\"jumpn\").value,10);if(n>=1&&n<=INDEX.n)go(n-1)});\n"
              "  const i=INDEX.keys.findIndex(k=>!(answers[k]&&answers[k].v));\n"
              "  renderStatus(); await go(i>0?i:0);\n"
              "})();", html, flags=re.S)

for bad in ("fetch(", "window.claude", "claude_review", "janice_review"):
    assert bad not in html, bad
open("review_page/second_rater.html", "w").write(html)
print("wrote review_page/second_rater.html,", len(html) // 1024, "KB,", len(cases), "cases")
