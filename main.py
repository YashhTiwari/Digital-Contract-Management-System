"""Command-line entry point for the contract request workflow engine."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dcms.analytics import summarize
from dcms.engine import WorkflowEngine
from dcms.intake import load_requests
from dcms.policies import POLICIES
from dcms.report import render_request_table, render_summary, render_timeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run contract requests through the workflow engine.")
    parser.add_argument("--data", default="data/sample_requests.csv",
                        help="CSV file with contract requests")
    parser.add_argument("--policy", choices=sorted(POLICIES),
                        default="arrival-order", help="dispatch policy")
    parser.add_argument("--show-audit", action="store_true",
                        help="print the status-change audit trail")
    parser.add_argument("--save-audit", metavar="FILE",
                        help="write the audit trail to FILE")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        requests = load_requests(args.data)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    policy = POLICIES[args.policy]()
    result = WorkflowEngine(requests, policy).run()

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
