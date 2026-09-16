from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict
from typing import Any

from scripts.radiology.openemr_order import (
    OpenEMRRadiologyOrder,
    build_orm_segments,
    normalize_openemr_order,
)


OPENEMR_DB_CONTAINER = (
    "health-it-openemr-lab-mysql-1"
)


def build_order_query(order_id: int) -> str:
    if order_id <= 0:
        raise ValueError(
            "OpenEMR order ID must be positive."
        )

    return f"""
USE openemr;
SELECT JSON_OBJECT(
    'procedure_order_id',
        po.procedure_order_id,
    'order_uuid_hex',
        HEX(po.uuid),
    'external_id',
        po.external_id,
    'patient_id',
        po.patient_id,
    'patient_identifier',
        p.pubpid,
    'patient_given_name',
        p.fname,
    'patient_family_name',
        p.lname,
    'patient_date_of_birth',
        DATE_FORMAT(p.DOB, '%Y%m%d'),
    'patient_sex',
        CASE p.sex
            WHEN 'Male' THEN 'M'
            WHEN 'Female' THEN 'F'
            ELSE 'U'
        END,
    'encounter_id',
        po.encounter_id,
    'encounter_time',
        DATE_FORMAT(
            fe.date,
            '%Y%m%d%H%i%s'
        ),
    'encounter_reason',
        fe.reason,
    'provider_id',
        po.provider_id,
    'provider_given_name',
        u.fname,
    'provider_family_name',
        u.lname,
    'lab_id',
        po.lab_id,
    'radiology_provider',
        pp.name,
    'date_ordered',
        DATE_FORMAT(
            po.date_ordered,
            '%Y-%m-%d %H:%i:%s'
        ),
    'clinical_hx',
        po.clinical_hx,
    'activity',
        po.activity,
    'procedure_order_type',
        po.procedure_order_type,
    'date_transmitted',
        po.date_transmitted,
    'procedure_order_seq',
        poc.procedure_order_seq,
    'procedure_code',
        poc.procedure_code,
    'procedure_name',
        poc.procedure_name,
    'procedure_type',
        poc.procedure_type
)
FROM procedure_order AS po
JOIN procedure_order_code AS poc
  ON poc.procedure_order_id =
     po.procedure_order_id
JOIN patient_data AS p
  ON p.pid = po.patient_id
JOIN form_encounter AS fe
  ON fe.encounter = po.encounter_id
 AND fe.pid = po.patient_id
LEFT JOIN users AS u
  ON u.id = po.provider_id
JOIN procedure_providers AS pp
  ON pp.ppid = po.lab_id
WHERE po.procedure_order_id = {order_id};
""".strip()


def parse_query_output(
    stdout: str,
    order_id: int,
) -> dict[str, Any]:
    rows = [
        line.strip()
        for line in stdout.splitlines()
        if line.strip()
    ]

    if len(rows) != 1:
        raise RuntimeError(
            "Expected exactly one OpenEMR order line "
            f"for order {order_id}; found {len(rows)}."
        )

    payload = json.loads(rows[0])

    if int(payload["procedure_order_id"]) != order_id:
        raise RuntimeError(
            "OpenEMR returned an unexpected order ID."
        )

    return payload


def load_openemr_radiology_order(
    order_id: int,
) -> OpenEMRRadiologyOrder:
    query = build_order_query(order_id)

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            OPENEMR_DB_CONTAINER,
            "sh",
            "-lc",
            (
                'exec mariadb --batch '
                '--skip-column-names '
                '-uroot '
                '--password="$MYSQL_ROOT_PASSWORD"'
            ),
        ],
        input=query,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "OpenEMR database query failed:\n"
            f"{result.stderr}"
        )

    source = parse_query_output(
        result.stdout,
        order_id,
    )

    return normalize_openemr_order(source)


def preview_order(
    order_id: int,
) -> dict[str, Any]:
    order = load_openemr_radiology_order(
        order_id
    )
    segments = build_orm_segments(order)

    return {
        "status": "PREVIEW",
        "source": "OpenEMR procedure_order",
        "order": asdict(order),
        "orm_message": "\r".join(segments) + "\r",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Preview a guarded OpenEMR-originated "
            "radiology ORM order."
        )
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    preview_parser = subparsers.add_parser(
        "preview",
        help="Read and render without transmitting.",
    )
    preview_parser.add_argument(
        "--order-id",
        type=int,
        required=True,
    )

    args = parser.parse_args()

    if args.command == "preview":
        result = preview_order(args.order_id)
    else:
        parser.error("Unsupported command.")

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
