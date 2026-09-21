import pytest

from dcms.intake import load_requests


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        load_requests("does_not_exist.csv")


def test_missing_columns(tmp_path):
    f = tmp_path / "bad.csv"
    f.write_text("request_id,contract_id\nA,B\n")
    with pytest.raises(ValueError):
        load_requests(f)


def test_duplicate_request_id(tmp_path):
    f = tmp_path / "dup.csv"
    f.write_text(
        "request_id,contract_id,request_type,submitted_at,effort,due_at,priority\n"
        "A,C1,T,0,2,10,1\nA,C2,T,1,2,10,1\n")
    with pytest.raises(ValueError):
        load_requests(f)
