# Digital Contract Management System

A workflow engine for handling contract requests on a shared server. Requests
such as retrieval, approval, deadline alerts, signature verification, archival,
and compliance audits enter a queue, move through a validated lifecycle, and
are dispatched according to a configurable policy. Every status change is
recorded in an audit trail.

**Aligned with:** SDG 8 - Decent Work & Economic Growth

## Problem

On a shared contract server, urgent requests close to their due date can be
delayed behind long-running routine ones, leading to missed obligations. This
project measures how different dispatch policies affect queue wait, handling
time, and SLA breaches.

## Current Features

- Contract request model with derived timing measures
- Request lifecycle (Submitted, Queued, In Progress, Awaiting Approval,
  Completed) with enforced status rules
- Audit trail recording every status change
- CSV intake with input validation
- Workflow engine with pluggable dispatch policies
- Arrival-order policy as the baseline
- Performance summary: queue wait, handling time, first-response delay,
  SLA breaches, reviewer utilization
- Execution timeline and per-request report
- Automated test suite

## Project Structure

```
Digital-Contract-Management-System/
├── dcms/
│   ├── models.py          Contract request and status definitions
│   ├── lifecycle.py       Status rules and audit trail
│   ├── intake.py          CSV loading and validation
│   ├── engine.py          Workflow engine
│   ├── analytics.py       Performance summary
│   ├── report.py          Tables and timeline rendering
│   └── policies/          Dispatch policies
├── data/sample_requests.csv
├── docs/architecture.md
├── tests/
└── main.py                Command-line interface
```

## Getting Started

Requires Python 3.10 or newer.

```bash
git clone https://github.com/YashhTiwari/Digital-Contract-Management-System.git
cd Digital-Contract-Management-System
pip install -r requirements.txt

python main.py                                # run with the sample requests
python main.py --show-audit                   # include the audit trail
python main.py --save-audit output/audit.log  # save the audit trail
python -m pytest                              # run the tests
```

## Request File Format

`data/sample_requests.csv` (all times in minutes)

| Column | Description |
|---|---|
| request_id | Unique request identifier |
| contract_id | Contract the request operates on |
| request_type | Retrieval, Approval Workflow, Deadline Alert, etc. |
| submitted_at | Time the request enters the system |
| effort | Estimated handling time |
| due_at | Time by which the request must be finished |
| priority | 1 (critical) to 4 (routine) |

## Baseline Result (Arrival Order, sample requests)

| Measure | Value |
|---|---|
| Average queue wait | 12.00 min |
| Average handling time | 16.50 min |
| SLA breaches | 6 of 8 |

Short, urgent requests wait behind long routine ones, which motivates
urgency-aware dispatch.

## Roadmap

- [x] Request model, lifecycle rules, and audit trail
- [x] Workflow engine with arrival-order baseline
- [ ] Shortest-effort-first policy with effort estimation from request history
- [ ] Urgency-driven policy that pauses long-running work for near-due requests
- [ ] Policy comparison reports and charts
- [ ] Automation scripts for due-date reminders and archival
- [ ] Integrated demo and final report
