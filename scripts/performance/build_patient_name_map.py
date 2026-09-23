"""Build a deterministic, frequency-weighted synthetic patient name map."""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

DEFAULT_SEED = "openemr-performance-names-20260923-v1"


def read_pool(path: Path) -> list[tuple[str, int]]:
    with path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    pool = [(row["name"], int(row["frequency"])) for row in rows]
    if not pool or any(not name or weight < 1 for name, weight in pool):
        raise ValueError(f"Invalid name pool: {path}")
    if len({name.casefold() for name, _ in pool}) != len(pool):
        raise ValueError(f"Duplicate names in pool: {path}")
    return pool


def digest_number(*parts: object) -> int:
    value = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(value).digest(), "big")


def weighted_choice(
    pool: list[tuple[str, int]], cumulative: list[int], total: int, *key: object
) -> str:
    target = digest_number(*key) % total
    return pool[bisect.bisect_right(cumulative, target)][0]


def assignments(
    pool: list[tuple[str, int]], *, total_rows: int, required_window: int,
    seed: str, label: str
) -> list[str]:
    if len(pool) > required_window or required_window > total_rows:
        raise ValueError("Pool/window/row cardinalities are incompatible.")
    cumulative: list[int] = []
    running = 0
    for _, weight in pool:
        running += weight
        cumulative.append(running)
    first = [name for name, _ in pool]
    first.extend(
        weighted_choice(pool, cumulative, running, seed, label, "base", index)
        for index in range(required_window - len(first))
    )
    first = [
        value
        for _, value in sorted(
            (
                (digest_number(seed, label, "shuffle", index, name), name)
                for index, name in enumerate(first)
            ),
            key=lambda item: item[0],
        )
    ]
    first.extend(
        weighted_choice(pool, cumulative, running, seed, label, "extra", index)
        for index in range(total_rows - required_window)
    )
    return first


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_map(
    given_pool: list[tuple[str, int]], surname_pool: list[tuple[str, int]],
    *, total_rows: int, primary_rows: int, seed: str
) -> list[tuple[int, str, str]]:
    given = assignments(
        given_pool, total_rows=total_rows, required_window=primary_rows,
        seed=seed, label="given"
    )
    surnames = assignments(
        surname_pool, total_rows=total_rows, required_window=primary_rows,
        seed=seed, label="surname"
    )
    return [(pid, given[pid - 1], surnames[pid - 1]) for pid in range(1, total_rows + 1)]


def write_map(path: Path, rows: list[tuple[int, str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("pid", "fname", "lname"))
        writer.writerows(rows)


def summarize(rows: list[tuple[int, str, str]], primary_rows: int) -> dict:
    primary = rows[:primary_rows]
    first_counts = Counter(row[1] for row in primary)
    last_counts = Counter(row[2] for row in primary)
    pair_counts = Counter((row[1], row[2]) for row in primary)
    return {
        "total_rows": len(rows),
        "primary_rows": len(primary),
        "primary_distinct_first_names": len(first_counts),
        "primary_distinct_last_names": len(last_counts),
        "primary_distinct_full_names": len(pair_counts),
        "primary_duplicate_full_name_rows": sum(count - 1 for count in pair_counts.values()),
        "top_first_names": first_counts.most_common(10),
        "top_last_names": last_counts.most_common(10),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--given-names", type=Path, required=True)
    parser.add_argument("--surnames", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--total-rows", type=int, default=55000)
    parser.add_argument("--primary-rows", type=int, default=50000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    given_pool = read_pool(args.given_names)
    surname_pool = read_pool(args.surnames)
    rows = build_map(
        given_pool, surname_pool, total_rows=args.total_rows,
        primary_rows=args.primary_rows, seed=args.seed
    )
    output_path = args.output_directory / "patient_name_map.csv"
    write_map(output_path, rows)
    summary = summarize(rows, args.primary_rows)
    summary.update({"seed": args.seed, "mapping_sha256": sha256(output_path)})
    summary_path = args.output_directory / "patient_name_map_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
