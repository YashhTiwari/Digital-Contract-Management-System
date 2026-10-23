"""Self-contained HTML report: policy comparison, Gantt charts, quantum sweep.

Uses only the standard library, so the report can be produced anywhere the
simulator runs. Open the generated file in any browser.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Dict, List, Sequence

from .analytics import PerformanceSummary, summarize
from .engine import IDLE, RunResult

# Categorical slots (light, dark), assigned to requests in a fixed order.
SERIES = [
    ("#2a78d6", "#3987e5"), ("#eb6834", "#d95926"), ("#1baf7a", "#199e70"),
    ("#eda100", "#c98500"), ("#e87ba4", "#d55181"), ("#008300", "#008300"),
    ("#6250d6", "#9085e9"), ("#e34948", "#e66767"),
]

CSS = """
:root{--surface:#fcfcfb;--page:#f9f9f7;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;
--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);--bar:#2a78d6;--idle:#e1e0d9;%LIGHT%}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){--surface:#1a1a19;
--page:#0d0d0d;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;
--ring:rgba(255,255,255,.10);--bar:#3987e5;--idle:#2c2c2a;%DARK%}}
:root[data-theme="dark"]{--surface:#1a1a19;--page:#0d0d0d;--ink:#f0efec;--ink2:#c3c2b7;
--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--bar:#3987e5;--idle:#2c2c2a;%DARK%}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1000px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:40px 0 4px}
p.sub{color:var(--ink2);margin:0 0 8px}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:10px;
padding:16px;margin-top:12px;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}
th,td{padding:6px 7px;text-align:right;border-bottom:1px solid var(--grid);white-space:nowrap}
th:first-child,td:first-child{text-align:left}th{color:var(--ink2);font-weight:600}
tr.best td{font-weight:700}
svg text{fill:var(--ink2);font:12px system-ui,-apple-system,"Segoe UI",sans-serif}
svg .lbl{fill:var(--ink)}svg .grid{stroke:var(--grid)}svg .axis{stroke:var(--axis)}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;margin:4px 0 8px;color:var(--ink2);font-size:13px}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.gantt h3{font-size:15px;margin:18px 0 2px}.gantt .m{color:var(--muted);font-size:13px}
#tip{position:fixed;pointer-events:none;background:var(--surface);color:var(--ink);
border:1px solid var(--ring);border-radius:6px;padding:6px 9px;font-size:13px;
box-shadow:0 2px 8px rgba(0,0,0,.15);display:none;white-space:pre}
"""

SCRIPT = """
const tip=document.getElementById('tip');
document.querySelectorAll('[data-tip]').forEach(el=>{
 el.addEventListener('mousemove',e=>{tip.textContent=el.dataset.tip;tip.style.display='block';
  tip.style.left=Math.min(e.clientX+12,innerWidth-tip.offsetWidth-8)+'px';tip.style.top=(e.clientY+12)+'px';});
 el.addEventListener('mouseleave',()=>{tip.style.display='none';});
});
"""


def _colour_vars(ids: Sequence[str]) -> Dict[str, str]:
    light = "".join(f"--s{i}:{SERIES[i % len(SERIES)][0]};" for i in range(len(ids)))
    dark = "".join(f"--s{i}:{SERIES[i % len(SERIES)][1]};" for i in range(len(ids)))
    return {"%LIGHT%": light, "%DARK%": dark}


def _gantt(result: RunResult, index: Dict[str, int], scale_end: int) -> str:
    left, width, height = 8, 900, 58
    px = (width - 2 * left) / scale_end
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" '
             f'aria-label="Gantt chart for {escape(result.policy_name)}">']
    step = 2 if scale_end <= 40 else 5
    for t in range(0, scale_end + 1, step):
        x = left + t * px
        parts.append(f'<line class="grid" x1="{x:.1f}" y1="6" x2="{x:.1f}" y2="36"/>'
                     f'<text x="{x:.1f}" y="52" text-anchor="middle">{t}</text>')
    for label, start, end in result.timeline:
        x, w = left + start * px + 1, (end - start) * px - 2   # 2px surface gap
        fill = "var(--idle)" if label == IDLE else f"var(--s{index[label]})"
        tip = f"{label}\nminutes {start}-{end} ({end - start} min)"
        parts.append(f'<rect x="{x:.1f}" y="12" width="{max(w, 1):.1f}" height="22" rx="4" '
                     f'fill="{fill}" data-tip="{escape(tip)}"/>')
        if w > 40:
            parts.append(f'<text class="lbl" x="{x + w / 2:.1f}" y="9" '
                         f'text-anchor="middle">{escape(label)}</text>')
    parts.append(f'<line class="axis" x1="{left}" y1="36" x2="{width - left}" y2="36"/></svg>')
    return "".join(parts)


def _bar_chart(summaries: Sequence[PerformanceSummary]) -> str:
    label_w, width, row = 240, 900, 30
    top, height = 8, 8 + row * len(summaries) + 26
    hi = max(s.avg_queue_wait for s in summaries)
    hi = (int(hi / 4) + 1) * 4
    px = (width - label_w - 60) / hi
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" '
             f'aria-label="Average waiting time per policy">']
    for t in range(0, hi + 1, 4):
        x = label_w + t * px
        parts.append(f'<line class="grid" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" '
                     f'y2="{height - 22}"/><text x="{x:.1f}" y="{height - 6}" '
                     f'text-anchor="middle">{t} min</text>')
    for i, s in enumerate(summaries):
        y = top + i * row
        w = s.avg_queue_wait * px
        tip = (f"{s.policy}\nwaiting {s.avg_queue_wait:.2f} min\nturnaround "
               f"{s.avg_handling_time:.2f} min\nSLA breaches {s.sla_breaches}/{s.total_requests}")
        parts.append(f'<text class="lbl" x="{label_w - 10}" y="{y + 18}" '
                     f'text-anchor="end">{escape(s.policy)}</text>'
                     f'<rect x="{label_w}" y="{y + 5}" width="{max(w, 1):.1f}" height="18" '
                     f'rx="4" fill="var(--bar)" data-tip="{escape(tip)}"/>'
                     f'<text x="{label_w + w + 6:.1f}" y="{y + 18}">{s.avg_queue_wait:.2f}</text>')
    parts.append(f'<line class="axis" x1="{label_w}" y1="{top}" x2="{label_w}" '
                 f'y2="{height - 22}"/></svg>')
    return "".join(parts)


def _table(summaries: Sequence[PerformanceSummary], first_col: str) -> str:
    best = min(s.avg_queue_wait for s in summaries)
    rows = [f"<tr><th>{first_col}</th><th>Avg wait</th><th>Avg turnaround</th>"
            "<th>Avg response</th><th>Urgent wait</th><th>SLA breaches</th>"
            "<th>Pre-emptions</th><th>Switches</th></tr>"]
    for s in summaries:
        cls = ' class="best"' if s.avg_queue_wait == best else ""
        rows.append(f"<tr{cls}><td>{escape(s.policy)}</td><td>{s.avg_queue_wait:.2f}</td>"
                    f"<td>{s.avg_handling_time:.2f}</td><td>{s.avg_first_response:.2f}</td>"
                    f"<td>{s.urgent_avg_wait:.2f}</td><td>{s.sla_breaches} / {s.total_requests}</td>"
                    f"<td>{s.preemptions}</td><td>{s.context_switches}</td></tr>")
    return "<table>" + "".join(rows) + "</table>"


def build_html_report(results: List[RunResult], sweep: Sequence[PerformanceSummary],
                      title: str = "Contract Request Scheduling Report") -> str:
    ids = sorted({r.request_id for r in results[0].requests})
    index = {rid: i for i, rid in enumerate(ids)}
    summaries = [summarize(r) for r in results]
    scale_end = max(r.total_time for r in results)

    css = CSS
    for key, value in _colour_vars(ids).items():
        css = css.replace(key, value)

    legend = "".join(f'<span><i style="background:var(--s{index[rid]})"></i>{escape(rid)}</span>'
                     for rid in ids)
    legend += '<span><i style="background:var(--idle)"></i>Idle</span>'
    gantts = "".join(
        f'<h3>{escape(r.policy_name)}</h3><div class="m">avg wait {s.avg_queue_wait:.2f} min · '
        f'turnaround {s.avg_handling_time:.2f} min · {s.sla_breaches} SLA breaches · '
        f'{s.preemptions} pre-emptions</div>{_gantt(r, index, scale_end)}'
        for r, s in zip(results, summaries))

    req_rows = "".join(
        f"<tr><td>{escape(r.request_id)}</td><td>{escape(r.contract_id)}</td>"
        f"<td>{escape(r.request_type)}</td><td>{r.submitted_at}</td><td>{r.effort}</td>"
        f"<td>{r.due_at}</td><td>{r.priority}</td></tr>" for r in results[0].requests)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scheduling Report</title><style>{css}</style></head>
<body><main>
<h1>{escape(title)}</h1>
<p class="sub">Digital Contract Management System · same request set run under every
dispatch policy. All times in minutes.</p>

<h2>Average waiting time by policy</h2>
<p class="sub">Lower is better. Hover a bar for turnaround and SLA figures.</p>
<div class="card">{_bar_chart(summaries)}</div>

<h2>Comparison table</h2>
<div class="card">{_table(summaries, "Policy")}</div>

<h2>Gantt charts</h2>
<p class="sub">Which request the reviewer handled in each minute. Hover a block for its interval.</p>
<div class="card gantt"><div class="legend">{legend}</div>{gantts}</div>

<h2>Round Robin: choosing the time quantum</h2>
<p class="sub">Small quanta respond quickly but switch often; large quanta approach FCFS.</p>
<div class="card">{_table(sweep, "Quantum")}</div>

<h2>Input requests</h2>
<div class="card"><table><tr><th>Request</th><th>Contract</th><th>Type</th><th>Arrival</th>
<th>Burst</th><th>Due</th><th>Priority</th></tr>{req_rows}</table></div>
</main><div id="tip"></div><script>{SCRIPT}</script></body></html>
"""


def write_html_report(path: str | Path, results: List[RunResult],
                      sweep: Sequence[PerformanceSummary]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_html_report(results, sweep), encoding="utf-8")
    return path
