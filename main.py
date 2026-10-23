"""Command-line entry point for the contract request workflow engine.

Examples:
    python main.py                              # arrival order (FCFS)
    python main.py --policy srtf                # any policy, by name or alias
    python main.py --policy rr --quantum 3
    python main.py --compare                    # every policy side by side
    python main.py --compare --html output/report.html
    python main.py --policy sjf --estimate      # SJF using predicted effort
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dcms.analytics import compare_policies, quantum_sweep, summarize
from dcms.engine import WorkflowEngine
from dcms.estimation import apply_estimates, estimate_by_type, load_history
from dcms.html_report import write_html_report
from dcms.intake import load_requests
from dcms.policies import ALIASES, POLICIES, make_policy
from dcms.report import (render_comparison, render_estimates, render_pcb_table,
                         render_quantum_sweep, render_request_table, render_summary,
                         render_timeline)


def quanta_list(text: str):
    try:
        values = [int(v) for v in text.split(",") if v.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError("expected comma-separated integers, e.g. 1,2,4,8")
    if not values or min(values) < 1:
        raise argparse.ArgumentTypeError("quantum values must be positive")
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run contract requests through the workflow engine.")
    parser.add_argument("--data", default="data/sample_requests.csv",
                        help="CSV file with contract requests")
    parser.add_argument("--policy", choices=sorted(POLICIES) + sorted(ALIASES),
                        default="arrival-order", metavar="POLICY",
                        help="dispatch policy: " + ", ".join(
                            f"{k} ({a})" for a, k in sorted(ALIASES.items(),
                                                            key=lambda kv: kv[1])))
    parser.add_argument("--quantum", type=int, default=4,
                        help="Round Robin time quantum in minutes (default 4)")
    parser.add_argument("--admission-limit", type=int, metavar="N",
                        help="long-term scheduler: at most N requests admitted at once")
    parser.add_argument("--estimate", action="store_true",
                        help="rank by effort predicted from history instead of declared effort")
    parser.add_argument("--history", default="data/request_history.csv",
                        help="request history used by --estimate")
    parser.add_argument("--alpha", type=float, default=0.5,
                        help="exponential averaging weight for --estimate (default 0.5)")
    parser.add_argument("--compare", action="store_true",
                        help="run every policy and print a comparison table")
    parser.add_argument("--quantum-sweep", type=quanta_list, metavar="Q1,Q2,...",
                        help="compare Round Robin with several quantum values")
    parser.add_argument("--html", metavar="FILE",
                        help="write an HTML report with Gantt charts (implies --compare)")
    parser.add_argument("--show-pcb", action="store_true",
                        help="print each request as a Process Control Block")
    parser.add_argument("--show-audit", action="store_true",
                        help="print the status-change audit trail")
    parser.add_argument("--save-audit", metavar="FILE",
                        help="write the audit trail to FILE")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        requests = load_requests(args.data)
        if args.estimate:
            estimates = estimate_by_type(load_history(args.history), args.alpha)
            apply_estimates(requests, estimates)
            print(render_estimates(estimates, args.alpha))
        policy = make_policy(args.policy, args.quantum)
        engine = WorkflowEngine(requests, policy, args.admission_limit)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.show_pcb:
        print("\nProcess Control Blocks (before scheduling):\n" + render_pcb_table(requests))

    if args.compare or args.html:
        results = compare_policies(requests, args.quantum,
                                   admission_limit=args.admission_limit)
        print("\n=== Policy Comparison ===\n")
        print(render_comparison([summarize(r) for r in results]))
        sweep = quantum_sweep(requests, args.quantum_sweep or (1, 2, 3, 4, 6, 8))
        if args.quantum_sweep:
            print("\n=== Round Robin Quantum Sweep ===\n" + render_quantum_sweep(sweep))
        if args.html:
            path = write_html_report(args.html, results, sweep)
            print(f"\nHTML report written to {path}")
        return 0

    if args.quantum_sweep:
        print("\n=== Round Robin Quantum Sweep ===\n")
        print(render_quantum_sweep(quantum_sweep(requests, args.quantum_sweep)))
        return 0

    result = engine.run()
    print(f"\n=== Contract Workflow Run: {policy.name} ===\n")
    print(render_request_table(result))
    print("\nExecution timeline (minutes):\n" + render_timeline(result.timeline))
    print("\n" + render_summary(summarize(result)))

    if args.show_audit:
        print("\nAudit trail:\n" + result.audit.format())
    if args.save_audit:
        Path(args.save_audit).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save_audit).write_text(result.audit.format() + "\n", encoding="utf-8")
        print(f"\nAudit trail saved to {args.save_audit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
