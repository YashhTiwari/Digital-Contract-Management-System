"""Plain-text rendering of results."""

from __future__ import annotations

from typing import Dict, List, Sequence

from .analytics import PerformanceSummary
from .engine import RunResult, TimelineSegment
from .models import ContractRequest


def render_timeline(timeline: List[TimelineSegment]) -> str:
    bar, axis = "|", ""
    for label, start, end in timeline:
        width = max(len(label) + 2, end - start)
        bar += label.center(width) + "|"
        axis += str(start).ljust(width + 1)
    axis += str(timeline[-1][2])
    return f"{bar}\n{axis}"


def render_request_table(result: RunResult) -> str:
    header = (f"{'Request':<9}{'Contract':<14}{'Type':<24}{'Submit':>7}{'Effort':>7}"
              f"{'Start':>6}{'Done':>5}{'Wait':>5}{'Total':>6}{'Due':>5}  SLA")
    lines = [header, "-" * len(header)]
    for r in result.requests:
        sla = "Breached" if r.sla_breached else "Met"
        lines.append(
            f"{r.request_id:<9}{r.contract_id:<14}{r.request_type:<24}"
            f"{r.submitted_at:>7}{r.effort:>7}{r.started_at:>6}{r.completed_at:>5}"
            f"{r.queue_wait:>5}{r.total_handling_time:>6}{r.due_at:>5}  {sla}"
        )
    return "\n".join(lines)


def render_summary(s: PerformanceSummary) -> str:
    return (
        f"Dispatch policy         : {s.policy}\n"
        f"Average queue wait      : {s.avg_queue_wait:.2f} min   (waiting time)\n"
        f"Average handling time   : {s.avg_handling_time:.2f} min   (turnaround time)\n"
        f"Average first response  : {s.avg_first_response:.2f} min   (response time)\n"
        f"Urgent request wait     : {s.urgent_avg_wait:.2f} min   (priority 1 only)\n"
        f"SLA breaches            : {s.sla_breaches} / {s.total_requests}\n"
        f"Pre-emptions            : {s.preemptions}\n"
        f"Context switches        : {s.context_switches}\n"
        f"Reviewer utilization    : {s.utilization:.1f}%\n"
        f"Throughput              : {s.throughput:.2f} requests / 10 min\n"
        f"Total duration          : {s.total_time} min"
    )


def render_comparison(summaries: Sequence[PerformanceSummary]) -> str:
    header = (f"{'Policy':<34}{'Wait':>7}{'Turnaround':>12}{'Response':>10}"
              f"{'Urgent':>8}{'SLA miss':>10}{'Switches':>10}")
    lines = [header, "-" * len(header)]
    best_wait = min(s.avg_queue_wait for s in summaries)
    for s in summaries:
        mark = "  <- lowest wait" if s.avg_queue_wait == best_wait else ""
        lines.append(
            f"{s.policy:<34}{s.avg_queue_wait:>7.2f}{s.avg_handling_time:>12.2f}"
            f"{s.avg_first_response:>10.2f}{s.urgent_avg_wait:>8.2f}"
            f"{s.sla_breaches:>6} / {s.total_requests}{s.context_switches:>10}{mark}"
        )
    return "\n".join(lines)


def render_quantum_sweep(summaries: Sequence[PerformanceSummary]) -> str:
    header = f"{'Quantum':<22}{'Wait':>7}{'Turnaround':>12}{'Response':>10}{'Switches':>10}"
    lines = [header, "-" * len(header)]
    for s in summaries:
        lines.append(f"{s.policy:<22}{s.avg_queue_wait:>7.2f}{s.avg_handling_time:>12.2f}"
                     f"{s.avg_first_response:>10.2f}{s.context_switches:>10}")
    return "\n".join(lines)


def render_pcb_table(requests: Sequence[ContractRequest]) -> str:
    rows: List[Dict[str, object]] = [r.pcb() for r in requests]
    cols = list(rows[0])
    widths = {c: max(len(c), *(len(str(row[c])) for row in rows)) + 2 for c in cols}
    lines = ["".join(c.ljust(widths[c]) for c in cols)]
    lines.append("-" * len(lines[0]))
    for row in rows:
        lines.append("".join(str(row[c]).ljust(widths[c]) for c in cols))
    return "\n".join(lines)


def render_estimates(estimates: Dict[str, float], alpha: float) -> str:
    lines = [f"Effort estimates from history (exponential average, alpha={alpha}):"]
    for request_type, tau in sorted(estimates.items()):
        lines.append(f"  {request_type:<24} {tau:>6.2f} min")
    return "\n".join(lines)
