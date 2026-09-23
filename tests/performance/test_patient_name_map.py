import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "performance" / "build_patient_name_map.py"


def load_module():
    spec = importlib.util.spec_from_file_location("patient_name_map", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mapping_is_deterministic_and_preserves_cardinality():
    module = load_module()
    given = [("James", 100), ("Maria", 50), ("Avery", 10)]
    surnames = [("Smith", 100), ("Garcia", 50), ("O'Hagan", 10), ("Ng", 5)]
    first = module.build_map(
        given, surnames, total_rows=40, primary_rows=30, seed="fixed"
    )
    second = module.build_map(
        given, surnames, total_rows=40, primary_rows=30, seed="fixed"
    )
    assert first == second
    assert [row[0] for row in first] == list(range(1, 41))
    assert len({row[1] for row in first[:30]}) == 3
    assert len({row[2] for row in first[:30]}) == 4


def test_different_seed_changes_mapping():
    module = load_module()
    pool = [("One", 10), ("Two", 5), ("Three", 1)]
    first = module.build_map(pool, pool, total_rows=30, primary_rows=20, seed="a")
    second = module.build_map(pool, pool, total_rows=30, primary_rows=20, seed="b")
    assert first != second
