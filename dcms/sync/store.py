"""Shared contract store protected by the Readers-Writers rule.

Many users may view a contract at the same time, but an edit or signature
must have the record to itself. Without that rule two simultaneous signers
both read the same version and one signature is lost (a lost update).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional

from .primitives import BinarySemaphore


@dataclass
class ContractRecord:
    contract_id: str
    version: int = 0
    signatures: int = 0
    status: str = "Active"
    history: List[str] = field(default_factory=list)


class ReadersWriterLock:
    """First readers-writers solution with two semaphores and a reader count.

    The first reader in locks writers out; the last reader out lets them in.
    Readers have preference, so a steady stream of readers can starve a
    writer - acceptable here because edits are rare compared to views.
    """

    def __init__(self) -> None:
        self._mutex = BinarySemaphore()   # protects read_count
        self._write = BinarySemaphore()   # held by a writer, or by the reader group
        self.read_count = 0

    def acquire_read(self) -> None:
        with self._mutex:
            self.read_count += 1
            if self.read_count == 1:
                self._write.wait()

    def release_read(self) -> None:
        with self._mutex:
            self.read_count -= 1
            if self.read_count == 0:
                self._write.signal()

    def acquire_write(self) -> None:
        self._write.wait()

    def release_write(self) -> None:
        self._write.signal()


class ContractStore:
    """Contract records, one readers-writers lock per contract, plus the
    instrumentation used to prove the rule holds."""

    def __init__(self, contract_ids: Iterable[str]) -> None:
        self.records: Dict[str, ContractRecord] = {c: ContractRecord(c) for c in contract_ids}
        self.locks: Dict[str, ReadersWriterLock] = {c: ReadersWriterLock() for c in self.records}
        self._probe = threading.Lock()   # measurement only
        self.readers_inside: Dict[str, int] = {c: 0 for c in self.records}
        self.writers_inside: Dict[str, int] = {c: 0 for c in self.records}
        self.max_readers = 0
        self.violations = 0              # a writer was not alone on its contract

    def read(self, contract_id: str, work: float = 0.0) -> ContractRecord:
        rw = self.locks[contract_id]
        rw.acquire_read()
        try:
            self._enter(contract_id, writer=False)
            time.sleep(work)
            record = self.records[contract_id]
            snapshot = ContractRecord(record.contract_id, record.version,
                                      record.signatures, record.status)
            self._leave(contract_id, writer=False)
            return snapshot
        finally:
            rw.release_read()

    def update(self, contract_id: str, change: Callable[[ContractRecord], None],
               note: str = "", work: float = 0.0) -> None:
        rw = self.locks[contract_id]
        rw.acquire_write()
        try:
            self._enter(contract_id, writer=True)
            record = self.records[contract_id]
            current = record.version
            time.sleep(work)
            change(record)
            record.version = current + 1
            record.history.append(note)
            self._leave(contract_id, writer=True)
        finally:
            rw.release_write()

    def update_unsafe(self, contract_id: str, pause: Optional[Callable[[], None]] = None) -> None:
        """Add a signature with no locking at all (used to show the race)."""
        record = self.records[contract_id]
        seen = record.signatures
        (pause or (lambda: time.sleep(0)))()
        record.signatures = seen + 1

    def _enter(self, c: str, writer: bool) -> None:
        with self._probe:
            if writer:
                self.writers_inside[c] += 1
                if self.writers_inside[c] > 1 or self.readers_inside[c] > 0:
                    self.violations += 1
            else:
                self.readers_inside[c] += 1
                if self.writers_inside[c] > 0:
                    self.violations += 1
                self.max_readers = max(self.max_readers, self.readers_inside[c])

    def _leave(self, c: str, writer: bool) -> None:
        with self._probe:
            if writer:
                self.writers_inside[c] -= 1
            else:
                self.readers_inside[c] -= 1


def add_signature(record: ContractRecord) -> None:
    record.signatures += 1


def lost_update_demo(signers: int = 8, signatures_each: int = 50,
                     safe: bool = False) -> Dict[str, int]:
    """Several threads sign one contract. Returns expected vs actual signatures."""
    store = ContractStore(["CON-2026-001"])

    def signer() -> None:
        for _ in range(signatures_each):
            if safe:
                store.update("CON-2026-001", add_signature, "signed")
            else:
                store.update_unsafe("CON-2026-001")

    threads = [threading.Thread(target=signer, name=f"signer-{i}") for i in range(signers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    expected = signers * signatures_each
    actual = store.records["CON-2026-001"].signatures
    return {"expected": expected, "actual": actual, "lost": expected - actual}
