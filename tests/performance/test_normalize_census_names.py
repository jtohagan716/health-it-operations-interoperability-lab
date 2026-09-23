import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "performance" / "normalize_census_names.py"


def test_normalizer_compiles():
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_normalized_csv_contract(tmp_path):
    path = tmp_path / "pool.csv"
    module_namespace = {}
    exec(compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec"), module_namespace)
    module_namespace["write_pool"](path, [("O'Hagan", 1, 100), ("Smith-Jones", 2, 50)])
    with path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    assert rows == [
        {"name": "O'Hagan", "rank": "1", "frequency": "100"},
        {"name": "Smith-Jones", "rank": "2", "frequency": "50"},
    ]
