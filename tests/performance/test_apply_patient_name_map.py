import csv
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "performance" / "apply_patient_name_map.py"


def load_module():
    spec = importlib.util.spec_from_file_location("apply_names", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sql_escapes_apostrophes_and_contains_transactional_guards():
    module = load_module()
    rows = [(pid, "Avery", "O'Hagan") for pid in range(1, 55001)]
    sql = module.build_apply_sql(rows)
    assert "O''Hagan" in sql
    assert "START TRANSACTION;" in sql
    assert "CHECK (value = 0)" in sql
    assert "UPDATE patient_data AS target" in sql
    assert "UPDATE patient_data_write_indexed AS target" in sql
    assert "UPDATE patient_data_write_unindexed AS target" in sql
    assert sql.endswith("COMMIT;\n")


def test_map_contract_rejects_incomplete_mapping(tmp_path):
    module = load_module()
    path = tmp_path / "map.csv"
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(("pid", "fname", "lname"))
        writer.writerow((1, "Avery", "Smith"))
    try:
        module.load_map(path)
    except ValueError as error:
        assert "55000" in str(error)
    else:
        raise AssertionError("Incomplete mapping was accepted.")
