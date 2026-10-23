# Digital Contract Management System

An Operating Systems project that models a shared contract-management server.
Contract requests (retrieval, approval, deadline alerts, signature
verification, archival, compliance audits) are treated as **processes and
threads**: they are scheduled by CPU-scheduling policies, handled by worker
threads that synchronize on shared contract records, and protected against
deadlock. Routine admin work (due-date reminders, archival) is automated with
shell scripts.

**Course:** Operating Systems (CCSE0303A) · **Group 98** · **Aligned with:** SDG 8 - Decent Work & Economic Growth

## Problem

On a shared contract server, urgent requests close to their due date can be
delayed behind long-running routine ones, and two users editing or signing the
same contract at once can corrupt it. This project measures how scheduling
policies affect waiting time, turnaround time and SLA breaches, and shows how
synchronization and deadlock handling keep concurrent access correct.

## Features

| Area | What is implemented |
|---|---|
| Process model | Request as a PCB (`--show-pcb`), validated state transitions, audit trail |
| Schedulers | Long-term (admission limit), short-term (dispatch policy), dispatcher (engine) |
| CPU scheduling | FCFS, SJF, SRTF, Round Robin, Multilevel Queue, Multilevel Feedback Queue (demotion + aging), EDF |
| Burst estimation | Exponential averaging of past request efforts per request type |
| Evaluation | Waiting, turnaround, response time, SLA breaches, pre-emptions, context switches, RR quantum sweep, HTML report with Gantt charts |
| Threads | Multithreaded server, one kernel thread per worker (one-to-one model) |
| Synchronization | Race-condition demo, Lock variable, Strict alternation, Peterson, Bakery, Test-and-Set, counting/binary semaphores built as monitors |
| Classic problems | Bounded buffer (producer-consumer), Readers-Writers, Sleeping Barber, Dining Philosophers |
| Deadlock | Banker's Algorithm, wait-for-graph detection, victim-based recovery, lock ordering + lock-wait timeouts |
| Shell scripting | Due-date reminders, archival, system info, menu-driven admin console |

See [docs/os-concepts.md](docs/os-concepts.md) for where each syllabus concept lives in the code.

## Project Structure

```
Digital-Contract-Management-System/
├── dcms/
│   ├── models.py          Contract request (PCB) and status definitions
│   ├── lifecycle.py       State-transition rules and audit trail
│   ├── intake.py          CSV loading and validation
│   ├── engine.py          Scheduler simulation (long-term + short-term + dispatcher)
│   ├── policies/          FCFS, SJF, SRTF, RR, MLQ, MLFQ, EDF
│   ├── estimation.py      Exponential-average effort prediction
│   ├── analytics.py       Metrics, policy comparison, quantum sweep
│   ├── report.py          Text tables and timelines
│   ├── html_report.py     HTML report with Gantt charts
│   ├── deadlock.py        Banker's Algorithm, wait-for graph, recovery, lock ordering
│   └── sync/
│       ├── primitives.py  Counting and binary semaphores (monitor-based, FIFO)
│       ├── mutex.py       Mutual-exclusion algorithms and trial runner
│       ├── store.py       Contract store with readers-writers locking
│       ├── buffer.py      Bounded request queue (producer-consumer)
│       ├── server.py      Multithreaded contract server
│       └── dining.py      Approval desks as Dining Philosophers
├── scripts/               Bash admin automation
├── data/                  Sample requests, request history, contracts, Banker's state
├── docs/                  Architecture, concept mapping, results
├── tests/                 102 automated tests
├── main.py                Scheduling CLI
└── demo.py                Concurrency and deadlock CLI
```

## Getting Started

Requires Python 3.10 or newer; the code itself uses only the standard library.
The shell scripts need Bash (Linux, macOS with GNU date, WSL or Git Bash).

```bash
git clone https://github.com/YashhTiwari/Digital-Contract-Management-System.git
cd Digital-Contract-Management-System
pip install -r requirements.txt     # pytest, for the tests
```

### Scheduling (Unit 2)

```bash
python main.py                                   # FCFS baseline
python main.py --policy srtf                     # fcfs, sjf, srtf, rr, mlq, mlfq, edf
python main.py --policy rr --quantum 3
python main.py --policy sjf --estimate           # rank by effort predicted from history
python main.py --show-pcb --show-audit           # PCBs and every state change
python main.py --admission-limit 3               # long-term scheduler limit
python main.py --compare --quantum-sweep 1,2,4,8
python main.py --compare --html output/report.html
```

### Threads, synchronization and deadlock (Unit 3)

```bash
python demo.py race        # lost update, then fixed
python demo.py mutex       # lock variable vs Peterson, Bakery, Test-and-Set ...
python demo.py buffer      # producer-consumer on a bounded queue
python demo.py server      # full multithreaded server (add --verbose for the log)
python demo.py dining      # naive vs ordered locking
python demo.py bankers     # Banker's safety check and requests
python demo.py detect      # wait-for graph detection, recovery, prevention
python demo.py all
```

### Admin automation (Unit 1, shell scripting)

```bash
bash scripts/admin_menu.sh                       # menu for everything below
bash scripts/due_reminder.sh -d 7                # contracts expiring within 7 days
bash scripts/archive_contracts.sh -i -n          # create demo documents, dry run
bash scripts/archive_contracts.sh                # archive + compress
bash scripts/system_info.sh                      # OS, CPUs, load, processes, disk
```

`due_reminder.sh` exits with status 2 when a contract is overdue, so it can be
scheduled with cron and alert on failure.

### Tests

```bash
python -m pytest
```

## Input Formats

`data/sample_requests.csv` (all times in minutes)

| Column | OS meaning | Description |
|---|---|---|
| request_id | PID | Unique request identifier |
| contract_id | resource | Contract the request operates on |
| request_type | | Retrieval, Approval Workflow, Deadline Alert, ... |
| submitted_at | arrival time | Time the request enters the system |
| effort | burst time | Handling time |
| due_at | deadline | Time by which the request must be finished |
| priority | priority | 1 (critical) to 4 (routine) |

Other data files: `request_history.csv` (past efforts, for estimation),
`contracts.csv` (contract register, for the shell scripts) and
`bankers_state.json` (resource state for the Banker's Algorithm).

## Results (sample requests)

| Policy | Avg wait | Avg turnaround | Avg response | Urgent wait | SLA breaches |
|---|---|---|---|---|---|
| FCFS | 12.00 | 16.50 | 12.00 | 13.50 | 6 / 8 |
| SJF | 9.75 | 14.25 | 9.75 | 4.50 | 5 / 8 |
| **SRTF** | **7.88** | **12.38** | 5.00 | 0.50 | **2 / 8** |
| Round Robin (q=4) | 13.75 | 18.25 | 9.38 | 10.50 | 6 / 8 |
| Multilevel Queue | 10.12 | 14.62 | 7.12 | 0.00 | 4 / 8 |
| Multilevel Feedback Queue | 14.62 | 19.12 | 2.50 | 3.00 | 6 / 8 |
| EDF | 8.25 | 12.75 | 6.62 | 0.00 | 2 / 8 |

SRTF, the policy selected in Review 1, cuts average waiting time by 34% and
SLA breaches from 6 to 2 compared with FCFS. EDF and MLQ serve urgent requests
immediately. MLFQ gives the fastest first response at the cost of more context
switches. Full analysis, including the Round Robin quantum sweep and the
concurrency results, is in [docs/results.md](docs/results.md).

## Roadmap

- [x] Request model, lifecycle rules, and audit trail
- [x] Workflow engine with arrival-order baseline
- [x] Shortest-effort-first policy with effort estimation from request history
- [x] Urgency-driven policy that pauses long-running work for near-due requests (SRTF, EDF)
- [x] Round Robin, Multilevel Queue and Multilevel Feedback Queue with aging
- [x] Policy comparison reports and charts
- [x] Thread-based request handling with semaphores and readers-writers locking
- [x] Banker's Algorithm, deadlock detection and recovery
- [x] Automation scripts for due-date reminders and archival
- [x] Integrated demo and final report
