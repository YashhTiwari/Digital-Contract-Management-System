"""End-to-end checks of the command-line tools and admin shell scripts."""

import shutil
import subprocess
from pathlib import Path

import pytest

import demo
import main

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def project_root(monkeypatch):
    monkeypatch.chdir(ROOT)


def test_single_policy_run(capsys):
    assert main.main(["--policy", "srtf"]) == 0
    out = capsys.readouterr().out
    assert "Shortest Remaining First (SRTF)" in out and "7.88" in out


def test_compare_writes_html(tmp_path, capsys):
    html = tmp_path / "report.html"
    assert main.main(["--compare", "--quantum-sweep", "1,4", "--html", str(html)]) == 0
    text = html.read_text(encoding="utf-8")
    assert "<svg" in text and "Multilevel Feedback Queue" in text
    assert "Round Robin (q=1)" in capsys.readouterr().out


def test_estimate_and_pcb(capsys):
    assert main.main(["--policy", "sjf", "--estimate", "--show-pcb"]) == 0
    out = capsys.readouterr().out
    assert "exponential average" in out and "Progress (PC)" in out


def test_bad_data_file(capsys):
    assert main.main(["--data", "missing.csv"]) == 1


@pytest.mark.parametrize("name", ["race", "bankers", "detect", "dining", "buffer"])
def test_demos_run(name, capsys):
    assert demo.main([name, "--iterations", "50"]) == 0
    assert "===" in capsys.readouterr().out


def _working_bash():
    """A bash that can run the scripts (GNU date), or None.

    On Windows `bash` may be the WSL launcher with no Linux installed, so
    each candidate is tried rather than trusted.
    """
    candidates = [shutil.which("bash"), r"C:\Program Files\Git\bin\bash.exe"]
    for bash in filter(None, candidates):
        try:
            probe = subprocess.run([bash, "-c", "date -d 2026-01-02 +%F"],
                                   capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if probe.returncode == 0 and probe.stdout.strip() == "2026-01-02":
            return bash
    return None


BASH = _working_bash()


@pytest.mark.skipif(BASH is None, reason="no working bash with GNU date")
def test_due_reminder_script(tmp_path):
    proc = subprocess.run([BASH, "scripts/due_reminder.sh", "-t", "2026-10-23", "-d", "10"],
                          capture_output=True, text=True, cwd=ROOT,
                          env={"LOG_DIR": str(tmp_path), "PATH": _path()})
    assert proc.returncode == 2, proc.stderr          # one contract is overdue
    assert "CON-2026-050" in proc.stdout and "OVERDUE" in proc.stdout
    assert "CON-2026-031" not in proc.stdout          # due next year


@pytest.mark.skipif(BASH is None, reason="no working bash with GNU date")
def test_archive_script_dry_run(tmp_path):
    proc = subprocess.run([BASH, "scripts/archive_contracts.sh", "-i", "-n",
                           "-s", str(tmp_path / "storage")],
                          capture_output=True, text=True, cwd=ROOT,
                          env={"LOG_DIR": str(tmp_path), "PATH": _path()})
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.count("would archive") == 3
    assert len(list((tmp_path / "storage" / "active").glob("*.txt"))) == 10


def _path():
    import os
    return os.environ.get("PATH", "")
