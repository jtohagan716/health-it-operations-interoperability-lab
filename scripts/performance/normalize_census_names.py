"""Normalize aggregate 2020 Census name workbooks into deterministic CSV pools."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

XML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"x": XML_NS}
CELL_REFERENCE = re.compile(r"([A-Z]+)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(node.text or "" for node in item.iter(f"{{{XML_NS}}}t"))
        for item in root.findall("x:si", NS)
    ]


def read_first_sheet(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        strings = _shared_strings(archive)
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        output: list[list[str]] = []
        for row in root.findall(".//x:sheetData/x:row", NS):
            values: dict[int, str] = {}
            for cell in row.findall("x:c", NS):
                reference = cell.get("r", "A1")
                letters = CELL_REFERENCE.match(reference).group(1)
                column = 0
                for letter in letters:
                    column = column * 26 + ord(letter) - 64
                cell_type = cell.get("t")
                value_node = cell.find("x:v", NS)
                if cell_type == "inlineStr":
                    value = "".join(
                        node.text or "" for node in cell.iter(f"{{{XML_NS}}}t")
                    )
                elif value_node is None:
                    value = ""
                elif cell_type == "s":
                    value = strings[int(value_node.text)]
                else:
                    value = value_node.text or ""
                values[column - 1] = value.strip()
            width = max(values, default=-1) + 1
            output.append([values.get(index, "") for index in range(width)])
        return output


def normalize_name(value: str) -> str:
    return value.strip().title()


def extract_pool(path: Path, header: str, limit: int) -> list[tuple[str, int, int]]:
    rows = read_first_sheet(path)
    header_index = next(
        index for index, row in enumerate(rows) if row and row[0] == header
    )
    pool: list[tuple[str, int, int]] = []
    seen: set[str] = set()
    for row in rows[header_index + 1 :]:
        if len(row) < 3 or not row[0] or not row[1] or not row[2]:
            continue
        name = normalize_name(row[0])
        key = name.casefold()
        if key in seen:
            continue
        rank = int(float(row[1]))
        count = int(float(row[2]))
        if rank < 1 or count < 1:
            raise ValueError(f"Invalid rank/count for {name!r}.")
        seen.add(key)
        pool.append((name, rank, count))
        if len(pool) == limit:
            break
    if len(pool) != limit:
        raise ValueError(f"Expected {limit} unique names in {path}; found {len(pool)}.")
    return pool


def write_pool(path: Path, pool: list[tuple[str, int, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("name", "rank", "frequency"))
        writer.writerows(pool)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-names", type=Path, required=True)
    parser.add_argument("--last-names", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    given = extract_pool(args.first_names, "FIRST NAME", 1000)
    surnames = extract_pool(args.last_names, "LAST NAME", 10000)
    given_path = args.output_directory / "given_names.csv"
    surname_path = args.output_directory / "surnames.csv"
    write_pool(given_path, given)
    write_pool(surname_path, surnames)
    manifest = {
        "source": "U.S. Census Bureau 2020 aggregate name-frequency tables",
        "first_names_source_sha256": sha256(args.first_names),
        "last_names_source_sha256": sha256(args.last_names),
        "given_name_count": len(given),
        "surname_count": len(surnames),
        "given_names_sha256": sha256(given_path),
        "surnames_sha256": sha256(surname_path),
    }
    manifest_path = args.output_directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
