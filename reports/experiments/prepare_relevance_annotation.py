#!/usr/bin/env python3
"""Prepare a private, blind relevance-annotation page from benchmark pools."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QRELS = ROOT / "reports" / "experiments" / "graph-enrichment-benchmark.qrels.jsonl"
DEFAULT_RESULTS = ROOT / "reports" / "experiments" / "graph-enrichment-benchmark.results.jsonl"
DEFAULT_EVENTS = ROOT / "reports" / "events.zip"
DEFAULT_OUTPUT = ROOT / ".exp-annotation" / "relevance-annotation.html"
STAGES = ("L1", "G0", "G1", "H0", "H1")
SEED = "mneme-relevance-v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def stable_key(value: str) -> str:
    return hashlib.sha256(f"{SEED}:{value}".encode()).hexdigest()


def canonical_path(path: str) -> str:
    return re.sub(r"--2(?=\.md$)", "", path)


def title_from_markdown(text: str, fallback: str) -> str:
    match = re.search(r"(?m)^title:\s*[\"']?(.+?)[\"']?\s*$", text[:4000])
    if match:
        return match.group(1).strip()
    match = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    return match.group(1).strip() if match else fallback


def resolve_document(path: str, bundle: Path, events_zip: Path) -> str:
    if path.startswith("events/"):
        with zipfile.ZipFile(events_zip) as archive:
            return archive.read(path).decode("utf-8", errors="replace")

    direct = bundle / path
    if direct.is_file():
        return direct.read_text(encoding="utf-8", errors="replace")
    duplicate = direct.with_name(f"{direct.stem}--2{direct.suffix}")
    if duplicate.is_file():
        return duplicate.read_text(encoding="utf-8", errors="replace")
    return "# Document unavailable\n\nThe source page could not be resolved in the local bundle."


def pool_candidates(
    qrel: dict[str, Any],
    rows: list[dict[str, Any]],
    limit: int = 5,
) -> list[str]:
    """Pool paths across systems while withholding system and target identity."""
    ranks: dict[str, float] = defaultdict(float)
    frequency: Counter[str] = Counter()
    for row in rows:
        for rank, path in enumerate(row.get("candidate_paths", []), 1):
            path = canonical_path(path)
            ranks[path] += 1.0 / rank
            frequency[path] += 1

    targets = [canonical_path(path) for path in qrel.get("relevant_paths", [])]
    candidates = set(ranks) | set(targets)
    ordered = sorted(
        candidates,
        key=lambda path: (
            0 if path in targets else 1,
            -frequency[path],
            -ranks[path],
            stable_key(f"{qrel['id']}:{path}"),
        ),
    )[:limit]
    return sorted(ordered, key=lambda path: stable_key(f"blind:{qrel['id']}:{path}"))


def select_questions(
    qrels: list[dict[str, Any]],
    results: list[dict[str, Any]],
    count: int = 10,
) -> list[tuple[dict[str, Any], list[dict[str, Any]], list[str]]]:
    expanded: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        if row.get("corpus") == "expanded":
            expanded[row["id"]].append(row)

    ranked = []
    for qrel in qrels:
        if qrel.get("category") == "no_answer":
            continue
        rows = sorted(expanded.get(qrel["id"], []), key=lambda row: STAGES.index(row["stage"]))
        if not rows:
            continue
        candidates = pool_candidates(qrel, rows)
        if len(candidates) < 2:
            continue
        hits = [int(row.get("hit", 0)) for row in rows]
        h1_hit = next((int(row.get("hit", 0)) for row in rows if row["stage"] == "H1"), 0)
        score = (
            1 - h1_hit,
            max(hits) - min(hits),
            len(candidates),
            stable_key(qrel["id"]),
        )
        ranked.append((score, qrel, rows, candidates))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [(qrel, rows, candidates) for _, qrel, rows, candidates in ranked[:count]]


def build_payload(
    qrels: list[dict[str, Any]],
    results: list[dict[str, Any]],
    bundle: Path,
    events_zip: Path,
    count: int = 10,
) -> dict[str, Any]:
    questions = []
    for qrel, _rows, paths in select_questions(qrels, results, count):
        candidates = []
        for index, path in enumerate(paths, 1):
            source = resolve_document(path, bundle, events_zip)
            candidates.append({
                "candidate_id": f"{qrel['id']}-{index}",
                "title": title_from_markdown(source, f"Candidate {index}"),
                "source": source[:120_000],
                "truncated": len(source) > 120_000,
                "path": path,
            })
        questions.append({
            "id": qrel["id"],
            "query": qrel["query"],
            "family": qrel["category"],
            "candidates": candidates,
        })
    return {
        "schema": "mneme-relevance-annotation-v1",
        "instructions": "Direct support is the only positive label used by the primary retrieval metric.",
        "questions": questions,
    }


def render_html(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mneme relevance annotation</title>
<style>
:root{{--bg:#f7f8fa;--panel:#fff;--ink:#17202a;--muted:#67727e;--line:#d8dde3;--accent:#176b5b;--accent-soft:#e3f2ee;--warn:#9c4f1b;--code:#f1f3f5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;font-size:15px;line-height:1.55;letter-spacing:0}}
button{{font:inherit}}button:focus-visible{{outline:3px solid #73a9d8;outline-offset:2px}}
.shell{{max-width:1440px;margin:0 auto;padding:22px 24px 40px}}.mast{{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;padding-bottom:14px;border-bottom:1px solid var(--line)}}
h1{{font-size:22px;font-weight:600;margin:0}}.meta{{color:var(--muted);font-size:13px}}.progress{{font-variant-numeric:tabular-nums;white-space:nowrap}}
.workspace{{display:grid;grid-template-columns:minmax(340px,42%) minmax(0,58%);gap:0;background:var(--panel);border:1px solid var(--line);border-radius:6px;margin-top:18px;min-height:680px}}
.judge{{padding:22px;border-right:1px solid var(--line)}}.reader{{padding:22px 28px;min-width:0}}.eyebrow{{color:var(--muted);font-size:13px;margin-bottom:6px}}
h2{{font-size:19px;font-weight:600;margin:0 0 18px}}h3{{font-size:15px;font-weight:600;margin:22px 0 8px}}.query-check,.labels{{display:grid;gap:8px}}
.query-check{{grid-template-columns:repeat(3,1fr)}}.choice{{text-align:left;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:4px;padding:9px 10px;cursor:pointer}}
.choice:hover{{background:var(--code)}}.choice[aria-pressed="true"]{{border-color:var(--accent);background:var(--accent-soft);color:#104c41}}
.candidate-tabs{{display:flex;flex-wrap:wrap;gap:7px;margin:8px 0 14px}}.candidate-tabs button{{border:1px solid var(--line);background:var(--panel);border-radius:4px;padding:6px 10px;cursor:pointer}}
.candidate-tabs button[aria-selected="true"]{{background:var(--ink);border-color:var(--ink);color:#fff}}.candidate-tabs .done::after{{content:" ·";color:#2ea47f}}
.labels{{grid-template-columns:1fr 1fr}}.labels .choice{{min-height:58px}}.labels small{{display:block;color:var(--muted)}}
.nav{{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:26px;padding-top:18px;border-top:1px solid var(--line)}}.nav button,.export{{border:1px solid var(--line);background:var(--panel);border-radius:4px;padding:8px 12px;cursor:pointer}}
.nav .primary,.export{{background:var(--accent);border-color:var(--accent);color:#fff}}.nav button:disabled{{opacity:.4;cursor:default}}
.reader-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;border-bottom:1px solid var(--line);padding-bottom:12px}}.reader h2{{margin:0;font-size:18px}}
.source{{margin:18px 0 0;white-space:pre-wrap;overflow-wrap:anywhere;font-family:"SFMono-Regular",Consolas,monospace;font-size:13px;line-height:1.65;background:transparent;border:0;padding:0;color:var(--ink)}}
.notice{{color:var(--warn);font-size:13px}}.saved{{color:var(--muted);font-size:13px;min-height:20px}}
@media(max-width:840px){{.shell{{padding:14px}}.mast{{align-items:flex-start;flex-direction:column}}.workspace{{grid-template-columns:1fr}}.judge{{border-right:0;border-bottom:1px solid var(--line)}}.query-check{{grid-template-columns:1fr}}.reader{{padding:20px}}}}
</style></head><body>
<main class="shell"><header class="mast"><div><h1>相关性盲评</h1><div class="meta">先判断题目是否成立，再阅读候选文档并逐一标注</div></div><div><div id="progress" class="progress"></div><button id="export" class="export" type="button">导出标注 JSON</button></div></header>
<section class="workspace"><div class="judge"><div id="question-number" class="eyebrow"></div><h2 id="query"></h2>
<h3>题目是否合理</h3><div id="query-check" class="query-check"></div>
<h3>候选文档</h3><div id="candidate-tabs" class="candidate-tabs" role="tablist"></div>
<h3>这篇文档与题目的关系</h3><div id="labels" class="labels"></div><p id="saved" class="saved" aria-live="polite"></p>
<div class="nav"><button id="prev" type="button">上一题</button><span id="position" class="meta"></span><button id="next" class="primary" type="button">下一题</button></div></div>
<article class="reader"><header class="reader-head"><div><div id="candidate-number" class="eyebrow"></div><h2 id="document-title"></h2></div><span id="truncated" class="notice"></span></header><pre id="source" class="source"></pre></article></section></main>
<script>
const DATA={data};
const STORE='mneme-relevance-annotation-v1';
const labels=[['direct','直接支持','可直接用于回答题目'],['context','相关背景','有关联，但不能直接回答'],['irrelevant','不相关','不能帮助回答'],['cannot_judge','无法判断','证据不足或内容无法理解']];
const queryLabels=[['valid','合理'],['ambiguous','含糊/不合理'],['cannot_judge','无法判断']];
let state={{question:0,candidate:0,answers:{{}},queryJudgements:{{}}}};
try{{state={{...state,...JSON.parse(localStorage.getItem(STORE)||'{{}}')}}}}catch(_e){{}}
const byId=id=>document.getElementById(id);
function save(){{localStorage.setItem(STORE,JSON.stringify(state));byId('saved').textContent='已自动保存';setTimeout(()=>byId('saved').textContent='',900)}}
function key(q,c){{return q.id+'::'+c.candidate_id}}
function render(){{
 const q=DATA.questions[state.question]; if(!q)return;
 state.candidate=Math.min(state.candidate,q.candidates.length-1); const c=q.candidates[state.candidate];
 byId('question-number').textContent=`问题 ${{state.question+1}} · ${{q.family}}`;
 byId('query').textContent=q.query; byId('position').textContent=`${{state.question+1}} / ${{DATA.questions.length}}`;
 byId('prev').disabled=state.question===0; byId('next').textContent=state.question===DATA.questions.length-1?'完成':'下一题';
 byId('query-check').innerHTML=queryLabels.map(([v,t])=>`<button type="button" class="choice" data-qvalue="${{v}}" aria-pressed="${{state.queryJudgements[q.id]===v}}">${{t}}</button>`).join('');
 byId('candidate-tabs').innerHTML=q.candidates.map((item,i)=>`<button type="button" role="tab" data-index="${{i}}" aria-selected="${{i===state.candidate}}" class="${{state.answers[key(q,item)]?'done':''}}">候选 ${{i+1}}</button>`).join('');
 const answer=state.answers[key(q,c)];
 byId('labels').innerHTML=labels.map(([v,t,d])=>`<button type="button" class="choice" data-value="${{v}}" aria-pressed="${{answer===v}}"><strong>${{t}}</strong><small>${{d}}</small></button>`).join('');
 byId('candidate-number').textContent=`候选 ${{state.candidate+1}} / ${{q.candidates.length}}`;
 byId('document-title').textContent=c.title; byId('source').textContent=c.source; byId('truncated').textContent=c.truncated?'正文过长，已截断':'';
 const total=DATA.questions.reduce((n,item)=>n+item.candidates.length,0); const done=Object.keys(state.answers).length;
 byId('progress').textContent=`已标注 ${{done}} / ${{total}} 篇 · 题目判断 ${{Object.keys(state.queryJudgements).length}} / ${{DATA.questions.length}}`;
 document.querySelectorAll('[data-qvalue]').forEach(b=>b.onclick=()=>{{state.queryJudgements[q.id]=b.dataset.qvalue;save();render()}});
 document.querySelectorAll('[data-index]').forEach(b=>b.onclick=()=>{{state.candidate=Number(b.dataset.index);render()}});
 document.querySelectorAll('[data-value]').forEach(b=>b.onclick=()=>{{state.answers[key(q,c)]=b.dataset.value;save();render()}});
}}
byId('prev').onclick=()=>{{if(state.question>0){{state.question--;state.candidate=0;save();render()}}}};
byId('next').onclick=()=>{{if(state.question<DATA.questions.length-1){{state.question++;state.candidate=0;save();render()}}else{{exportLabels()}}}};
function exportLabels(){{
 const records=[]; DATA.questions.forEach(q=>q.candidates.forEach(c=>records.push({{question_id:q.id,query:q.query,query_judgement:state.queryJudgements[q.id]||null,candidate_id:c.candidate_id,path:c.path,label:state.answers[key(q,c)]||null}})));
 const output={{schema:DATA.schema,exported_at:new Date().toISOString(),records}};
 const blob=new Blob([JSON.stringify(output,null,2)],{{type:'application/json'}}); const a=document.createElement('a'); a.href=URL.createObjectURL(blob);a.download='mneme-relevance-labels.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}}
byId('export').onclick=exportLabels; render();
</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=ROOT / ".exp-full" / "wiki")
    parser.add_argument("--qrels", type=Path, default=DEFAULT_QRELS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    payload = build_payload(read_jsonl(args.qrels), read_jsonl(args.results), args.bundle, args.events, args.count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(payload), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
