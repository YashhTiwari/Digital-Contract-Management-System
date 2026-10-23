# OS Concepts and Where They Are Used

## Unit 1 - OS overview, architecture, shell scripting

| Concept | Where in the project |
|---|---|
| Types of OS (batch, multiprogramming, real-time) | The contract server is a multiprogramming system: many requests share one reviewer/CPU (`engine.py`). The deadline-alert module follows the real-time idea (EDF, `policies/earliest_due.py`). |
| OS architecture, system calls, kernel | `scripts/system_info.sh` reads kernel, CPU, load, process and disk information through utilities that make system calls. Worker threads are kernel threads (`sync/server.py` reports their native thread ids). |
| Shell scripting: variables, control structures, functions | `scripts/common.sh` (functions, date arithmetic), `scripts/due_reminder.sh` (getopts, while/read loop, if/elif, arithmetic, exit codes), `scripts/archive_contracts.sh` (case, dry run, tar), `scripts/admin_menu.sh` (menu loop). |

## Unit 2 - Processes, scheduling, threads

| Concept | Where in the project |
|---|---|
| Process and PCB | `ContractRequest` holds PID, state, priority, arrival, burst, remaining time, progress and resource (`models.py`, `pcb()`; `python main.py --show-pcb`). |
| Process state transition diagram | `lifecycle.py` - SUBMITTED (new) -> QUEUED (ready) -> IN_PROGRESS (running) -> COMPLETED (terminated); IN_PROGRESS -> QUEUED on pre-emption; AWAITING_APPROVAL as the waiting state. Illegal transitions raise an error. |
| Long-term scheduler | `WorkflowEngine(admission_limit=N)` keeps submitted requests in a job pool until there is room (degree of multiprogramming). |
| Short-term scheduler and dispatcher | Each policy's `pick_next()` chooses; the engine performs the switch and counts pre-emptions and context switches. |
| Mid-term scheduler | Represented in the state rules by AWAITING_APPROVAL (a request suspended out of the ready queue, then resumed). The simulator itself does not suspend requests. |
| FCFS | `policies/arrival_order.py` |
| SJF | `policies/shortest_effort.py` - `ShortestEffortPolicy` |
| SRTF | `policies/shortest_effort.py` - `ShortestRemainingPolicy` |
| Burst-time prediction | `estimation.py` - exponential averaging, `python main.py --estimate` |
| Round Robin | `policies/round_robin.py`, quantum sweep in `analytics.quantum_sweep` |
| Multilevel Queue | `policies/multilevel.py` - Urgent (RR q=2), Standard (RR q=4), Background (FCFS) |
| Multilevel Feedback Queue | `policies/multilevel.py` - demotion on full quantum, aging promotion |
| RTOS scheduling (case study) | `policies/earliest_due.py` - Earliest Due First |
| Processes vs threads, multithreading models | `sync/server.py` - one server process, many worker threads; Python threads are one-to-one kernel threads. |
| Hyper-threading | `demo.py server` and `scripts/system_info.sh` report logical CPUs. |

## Unit 3 - Synchronization and deadlock

| Concept | Where in the project |
|---|---|
| Race condition, critical section | `sync/store.py` `update_unsafe` / `lost_update_demo`, `python demo.py race` |
| Lock variable | `sync/mutex.py` `LockVariable` (shown to fail) |
| Strict alternation | `sync/mutex.py` `StrictAlternation` |
| Peterson's solution | `sync/mutex.py` `Peterson` |
| Bakery algorithm | `sync/mutex.py` `Bakery` (n threads) |
| Test-and-Set | `sync/mutex.py` `TestAndSetLock` |
| Semaphores (counting, binary) | `sync/primitives.py` - FIFO "strong" semaphore built on a condition variable |
| Monitor | `Semaphore` is itself a monitor (one lock + condition queue) |
| IPC, producer-consumer, bounded buffer | `sync/buffer.py`; intake threads produce, workers consume |
| Readers-Writers | `sync/store.py` `ReadersWriterLock`, one per contract |
| Sleeping Barber | Workers sleep on the empty queue (`consumer_sleeps`); `try_put` turns customers away when all chairs are full |
| Dining Philosophers | `sync/dining.py` - approvers need a contract record and a signature slot |
| Deadlock prevention | Fixed lock order: `deadlock.OrderedLocks`, ordered strategy in `dining.py` |
| Deadlock avoidance | `deadlock.BankersState` - safety and resource-request algorithms |
| Deadlock detection | `deadlock.WaitForGraph.find_cycle` |
| Deadlock recovery | `deadlock.recover` - abort the lowest-priority request in the cycle |
| DB case study (Oracle/MySQL) | Lock ordering and lock-wait timeouts (`OrderedLocks.acquire(timeout=...)`), the same approach InnoDB uses with `innodb_lock_wait_timeout` |
