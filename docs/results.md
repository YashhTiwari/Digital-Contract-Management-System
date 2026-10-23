# Results and Analysis

All scheduling figures come from `data/sample_requests.csv` and are checked by
`tests/test_policies.py`. Regenerate them with:

```bash
python main.py --compare --quantum-sweep 1,2,3,4,6,8 --html output/report.html
```

## Input

| Request | Type | Arrival | Burst | Due | Priority |
|---|---|---|---|---|---|
| REQ-101 | Contract Retrieval | 0 | 8 | 20 | 3 |
| REQ-102 | Approval Workflow | 1 | 4 | 9 | 2 |
| REQ-103 | Deadline Alert | 2 | 2 | 6 | 1 |
| REQ-104 | Archive Request | 3 | 6 | 30 | 4 |
| REQ-105 | Contract Retrieval | 5 | 3 | 14 | 3 |
| REQ-106 | Deadline Alert | 6 | 1 | 8 | 1 |
| REQ-107 | Signature Verification | 8 | 5 | 22 | 2 |
| REQ-108 | Compliance Audit | 9 | 7 | 35 | 4 |

## Policy comparison

| Policy | Avg wait | Avg turnaround | Avg response | Urgent wait | SLA breaches | Context switches |
|---|---|---|---|---|---|---|
| FCFS | 12.00 | 16.50 | 12.00 | 13.50 | 6 / 8 | 8 |
| SJF | 9.75 | 14.25 | 9.75 | 4.50 | 5 / 8 | 8 |
| SRTF | 7.88 | 12.38 | 5.00 | 0.50 | 2 / 8 | 10 |
| Round Robin (q=4) | 13.75 | 18.25 | 9.38 | 10.50 | 6 / 8 | 12 |
| Multilevel Queue | 10.12 | 14.62 | 7.12 | 0.00 | 4 / 8 | 12 |
| Multilevel Feedback Queue | 14.62 | 19.12 | 2.50 | 3.00 | 6 / 8 | 18 |
| EDF | 8.25 | 12.75 | 6.62 | 0.00 | 2 / 8 | 11 |

"Urgent wait" is the average waiting time of the two priority-1 deadline alerts.

## SRTF trace (checked by hand)

| Time | Event | Runs next | Why |
|---|---|---|---|
| 0 | REQ-101 arrives (8) | REQ-101 | only request |
| 1 | REQ-102 arrives (4) | REQ-102 | 4 < 101's remaining 7 -> pre-empt |
| 2 | REQ-103 arrives (2) | REQ-103 | 2 < 102's remaining 3 -> pre-empt |
| 4 | REQ-103 done | REQ-102 | remaining 3 is the shortest |
| 6 | REQ-106 arrives (1) | REQ-102 | tie at 1: the running request keeps the CPU |
| 7 | REQ-102 done | REQ-106 | 1 |
| 8 | REQ-106 done | REQ-105 | 3 |
| 11 | REQ-105 done | REQ-107 | 5 |
| 16 | REQ-107 done | REQ-104 | 6 < 101's 7 < 108's 7 (101 wins the 7-7 tie by arrival) |
| 22 | REQ-104 done | REQ-101 | 7 |
| 29 | REQ-101 done | REQ-108 | 7 |
| 36 | all done | | |

Waiting times: 21, 2, 0, 13, 3, 1, 3, 20 -> total 63 -> average **7.875**.

## Observations

1. **SRTF is the best general policy for this workload**, confirming the
   Review 1 choice: lowest average wait and turnaround, and SLA breaches fall
   from 6 to 2. Its two pre-emptions are cheap compared with the gain.
2. **SJF without pre-emption is not enough.** REQ-101 (8 min) starts at time 0
   and blocks both deadline alerts that arrive while it runs.
3. **EDF and MLQ protect urgent work.** Both serve the deadline alerts with
   zero waiting. EDF also matches SRTF's 2 SLA breaches because it orders by
   due time directly.
4. **MLFQ gives the fastest first response (2.5 min)** because every request
   starts in the 2-minute urgent queue. The price is 18 context switches and a
   higher average turnaround: on a short, fully known workload, a policy that
   knows burst times (SRTF) wins; MLFQ is the right choice when burst times are
   unknown.
5. **Aging works.** In `tests/test_policies.py::test_mlfq_aging_prevents_starvation`
   a long background request finishes earlier when aging is enabled than when
   a stream of short requests can keep it waiting.
6. **Burst estimation matters.** With efforts predicted from history
   (`--estimate`) instead of declared, SJF's average wait rises from 9.75 to
   10.62 because a few predictions are wrong. Exponential averaging still
   ranks deadline alerts first.

## Round Robin quantum sweep

| Quantum | Avg wait | Avg turnaround | Avg response | Context switches |
|---|---|---|---|---|
| 1 | 15.00 | 19.50 | 2.50 | 34 |
| 2 | 14.50 | 19.00 | 5.00 | 19 |
| 3 | 14.75 | 19.25 | 6.88 | 14 |
| 4 | 13.75 | 18.25 | 9.38 | 12 |
| 6 | 12.75 | 17.25 | 10.75 | 9 |
| 8 | 12.00 | 16.50 | 12.00 | 8 |

A small quantum responds fastest but switches up to four times as often. Once
the quantum reaches the longest burst (8), Round Robin is identical to FCFS. A
quantum of **4** is a reasonable middle ground for routine requests and is the
default; urgent requests are better served by MLQ/MLFQ or SRTF than by tuning
the quantum.

## Concurrency results (`python demo.py all`)

Exact counts vary from run to run because thread interleaving is not fixed;
typical results:

| Experiment | Result |
|---|---|
| 8 signers x 50 signatures, no lock | ~70-300 of 400 signatures survive (lost updates) |
| Same with readers-writers lock | 400 / 400 |
| Lock variable | overlapping critical sections, lost updates |
| Strict alternation, Peterson, Bakery (2 and 4 threads), Test-and-Set | 0 overlaps, 0 lost updates |
| Bounded queue (capacity 3) | queue never exceeds 3; producer blocks while full |
| Server: 40 requests, 4 workers, 3 sessions | 40/40 processed, work spread across all workers, at most 3 sessions, 0 readers-writers violations, contract versions match expected writes |
| Dining philosophers, naive | deadlock (circular wait detected by timeout) |
| Dining philosophers, ordered locks | 15/15 approvals, no deadlock |

## Deadlock results

**Banker's Algorithm** (`data/bankers_state.json`, resources: contract
records, signature slots, reviewer sessions; available 3 3 2):

- Initial state is **safe**, sequence <REQ-102, REQ-104, REQ-105, REQ-101, REQ-103>.
- REQ-102 requests (1, 0, 2): **granted**, state stays safe.
- REQ-105 then requests (3, 3, 0): **must wait**, not enough available.
- REQ-101 then requests (0, 2, 0): **must wait**, granting it would be unsafe.

**Detection and recovery:** the wait-for graph REQ-101 -> REQ-102 -> REQ-103 ->
REQ-101 contains a cycle (REQ-104 waits but is not part of it). REQ-103 has
the lowest priority in the cycle, so it is aborted; the graph is then acyclic.
