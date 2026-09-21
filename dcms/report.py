"""Plain-text rendering of results."""

from __future__ import annotations

from typing import List

from .analytics import PerformanceSummary
from .engine import RunResult, TimelineSegment


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
        f"Average queue wait      : {s.avg_queue_wait:.2f} min\n"
        f"Average handling time   : {s.avg_handling_time:.2f} min\n"
        f"Average first response  : {s.avg_first_response:.2f} min\n"
        f"SLA breaches            : {s.sla_breaches} / {s.total_requests}\n"
        f"Reviewer utilization    : {s.utilization:.1f}%\n"
        f"Total duration          : {s.total_time} min"
    )
