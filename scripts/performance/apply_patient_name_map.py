"""Safely apply a deterministic name map to isolated OpenEMR benchmark tables."""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DATABASE = "openemr_performance_lab"
TABLE_ROWS = {
    "patient_data": 50000,
    "patient_data_write_indexed": 55000,
    "patient_data_write_unindexed": 55000,
}
DEFAULT_CONTAINER = "health-it-openemr-lab-mysql-1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_map(path: Path) -> list[tuple[int, str, str]]:
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["pid", "fname", "lname"]:
            raise ValueError("Mapping header must be pid,fname,lname.")
        rows = [(int(row["pid"]), row["fname"], row["lname"]) for row in reader]
    if len(rows) != 55000:
        raise ValueError(f"Mapping must contain 55000 rows; found {len(rows)}.")
    if [row[0] for row in rows] != list(range(1, 55001)):
        raise ValueError("Mapping PIDs must be exactly 1 through 55000 in order.")
    for pid, first, last in rows:
        if not first or not last or len(first) > 255 or len(last) > 255:
            raise ValueError(f"Invalid mapped name at PID {pid}.")
    return rows


def mariadb(sql: str, container: str) -> str:
    command = [
        "docker", "exec", "-i", container, "sh", "-lc",
        'exec mariadb --connect-timeout=5 -u root '
        '--password="$MYSQL_ROOT_PASSWORD" --batch --raw '
        f'--skip-column-names {DATABASE}',
    ]
    result = subprocess.run(
        command, input=sql, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"MariaDB command failed with exit code {result.returncode}.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout


def sql_text(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def inspect_database(container: str) -> dict[str, int]:
    sql = "\n".join(
        ["SELECT DATABASE();"]
        + [f"SELECT '{table}', COUNT(*) FROM {table};" for table in TABLE_ROWS]
    )
    lines = [line for line in mariadb(sql, container).splitlines() if line]
    if not lines or lines[0] != DATABASE:
        raise RuntimeError(f"Database guard failed; expected {DATABASE!r}.")
    counts: dict[str, int] = {}
    for line in lines[1:]:
        table, count = line.split("\t")
        counts[table] = int(count)
    if counts != TABLE_ROWS:
        raise RuntimeError(f"Row-count guard failed: {counts!r}.")
    return counts


def backup_names(directory: Path, container: str) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=False)
    paths: list[Path] = []
    for table in TABLE_ROWS:
        output = mariadb(
            f"SELECT pid, pubpid, fname, lname FROM {table} ORDER BY pid;",
            container,
        )
        path = directory / f"{table}-names-before.tsv"
        path.write_text("pid\tpubpid\tfname\tlname\n" + output, encoding="utf-8")
        paths.append(path)
    return paths


def build_apply_sql(rows: list[tuple[int, str, str]]) -> str:
    parts = [
        "SET autocommit=0;",
        "START TRANSACTION;",
        "CREATE TEMPORARY TABLE patient_name_stage ("
        "pid BIGINT NOT NULL PRIMARY KEY, fname VARCHAR(255) NOT NULL, "
        "lname VARCHAR(255) NOT NULL);",
    ]
    for start in range(0, len(rows), 1000):
        values = ",\n".join(
            f"({pid},{sql_text(first)},{sql_text(last)})"
            for pid, first, last in rows[start : start + 1000]
        )
        parts.append(
            "INSERT INTO patient_name_stage (pid,fname,lname) VALUES\n"
            + values + ";"
        )
    parts.extend(
        [
            "CREATE TEMPORARY TABLE fixture_assertion ("
            "value BIGINT NOT NULL CHECK (value = 0));",
            "INSERT INTO fixture_assertion SELECT COUNT(*) - 55000 "
            "FROM patient_name_stage;",
        ]
    )
    for table, expected in TABLE_ROWS.items():
        parts.extend(
            [
                f"INSERT INTO fixture_assertion SELECT COUNT(*) - {expected} "
                f"FROM {table};",
                f"UPDATE {table} AS target JOIN patient_name_stage AS source "
                "ON source.pid = target.pid SET target.fname = source.fname, "
                "target.lname = source.lname;",
                f"INSERT INTO fixture_assertion SELECT COUNT(*) FROM {table} AS target "
                "LEFT JOIN patient_name_stage AS source ON source.pid = target.pid "
                "WHERE source.pid IS NULL OR target.fname <> source.fname "
                "OR target.lname <> source.lname;",
            ]
        )
    parts.extend(
        [
            "INSERT INTO fixture_assertion SELECT COUNT(*) FROM patient_data AS p "
            "JOIN patient_data_write_indexed AS wi ON wi.pid=p.pid "
            "JOIN patient_data_write_unindexed AS wu ON wu.pid=p.pid "
            "WHERE p.fname<>wi.fname OR p.lname<>wi.lname "
            "OR p.fname<>wu.fname OR p.lname<>wu.lname;",
            "COMMIT;",
        ]
    )
    return "\n".join(parts) + "\n"


def verify_mapping(rows: list[tuple[int, str, str]], container: str) -> None:
    expected = {pid: (first, last) for pid, first, last in rows}
    for table, expected_count in TABLE_ROWS.items():
        output = mariadb(
            f"SELECT pid, fname, lname FROM {table} ORDER BY pid;", container
        )
        actual = {}
        for line in output.splitlines():
            pid, first, last = line.split("\t", 2)
            actual[int(pid)] = (first, last)
        if len(actual) != expected_count:
            raise RuntimeError(f"Post-update count mismatch in {table}.")
        mismatches = [pid for pid, names in actual.items() if expected[pid] != names]
        if mismatches:
            raise RuntimeError(f"Post-update mismatch in {table} at PID {mismatches[0]}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--backup-root", type=Path, default=Path("artifacts/name-backups"))
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--confirm-database")
    parser.add_argument("--confirm-row-count", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = load_map(args.mapping)
    counts = inspect_database(args.container)
    print(f"Mapping SHA256: {sha256(args.mapping)}")
    print(f"Validated database: {DATABASE}")
    print(f"Validated table counts: {counts}")
    if not args.commit:
        print("DRY RUN: no database rows were modified.")
        return 0
    if args.confirm_database != DATABASE or args.confirm_row_count != 55000:
        raise RuntimeError(
            "Commit requires --confirm-database openemr_performance_lab "
            "and --confirm-row-count 55000."
        )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_directory = args.backup_root / stamp
    backups = backup_names(backup_directory, args.container)
    for path in backups:
        print(f"Backup: {path} SHA256={sha256(path)}")
    mariadb(build_apply_sql(rows), args.container)
    verify_mapping(rows, args.container)
    print("COMMIT: names updated and reconciled successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
