import os
from pathlib import Path
from typing import Optional

import psycopg
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MIRTH_ENV_FILE = (
    PROJECT_ROOT
    / "infrastructure"
    / "mirth"
    / ".env"
)

load_dotenv(MIRTH_ENV_FILE)


INTEROP_DB_HOST = os.getenv(
    "INTEROP_DB_HOST",
    "localhost",
)

INTEROP_DB_PORT = int(
    os.getenv(
        "INTEROP_DB_PORT",
        "55432",
    )
)

INTEROP_DB_NAME = os.getenv(
    "INTEROP_DB_NAME",
    "interop",
)

INTEROP_DB_USER = os.getenv(
    "INTEROP_DB_USER",
    "interop_app",
)

INTEROP_DB_PASSWORD = os.getenv(
    "INTEROP_DB_PASSWORD"
)


def get_connection():
    if not INTEROP_DB_PASSWORD:
        raise RuntimeError(
            "INTEROP_DB_PASSWORD is not set."
        )

    return psycopg.connect(
        host=INTEROP_DB_HOST,
        port=INTEROP_DB_PORT,
        dbname=INTEROP_DB_NAME,
        user=INTEROP_DB_USER,
        password=INTEROP_DB_PASSWORD,
    )


def find_transaction_id(
    message_control_id: str,
) -> int:
    sql = """
        SELECT transaction_id
        FROM audit.interface_transactions
        WHERE message_control_id = %s
        ORDER BY transaction_id DESC
        LIMIT 1
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (message_control_id,),
            )

            row = cur.fetchone()

    if row is None:
        raise RuntimeError(
            "No logical transaction found for "
            f"message_control_id={message_control_id}"
        )

    return row[0]


def record_fhir_lineage(
    transaction_id: int,
    resource_type: str,
    resource_id: str,
    fhir_version: Optional[str] = None,
    profile_url: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> int:
    sql = """
        INSERT INTO audit.fhir_resource_lineage (
            transaction_id,
            resource_type,
            resource_id,
            fhir_version,
            profile_url,
            endpoint
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (
            transaction_id,
            resource_type,
            resource_id
        )
        DO UPDATE SET
            fhir_version = EXCLUDED.fhir_version,
            profile_url = EXCLUDED.profile_url,
            endpoint = EXCLUDED.endpoint
        RETURNING fhir_lineage_id
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    transaction_id,
                    resource_type,
                    resource_id,
                    fhir_version,
                    profile_url,
                    endpoint,
                ),
            )

            lineage_id = cur.fetchone()[0]

        conn.commit()

    return lineage_id


def record_validation_result(
    fhir_lineage_id: int,
    validation_category: str,
    validation_rule: str,
    validation_status: str,
    source_element: Optional[str] = None,
    target_element: Optional[str] = None,
    expected_value: Optional[str] = None,
    actual_value: Optional[str] = None,
    failure_domain: Optional[str] = None,
    diagnostic_message: Optional[str] = None,
    duration_ms: Optional[float] = None,
    validation_run_id: Optional[int] = None,
) -> int:
    sql = """
        INSERT INTO audit.validation_results (
            fhir_lineage_id,
            validation_category,
            validation_rule,
            source_element,
            target_element,
            expected_value,
            actual_value,
            validation_status,
            failure_domain,
            diagnostic_message,
            duration_ms,
            validation_run_id
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING validation_result_id
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    fhir_lineage_id,
                    validation_category,
                    validation_rule,
                    source_element,
                    target_element,
                    expected_value,
                    actual_value,
                    validation_status,
                    failure_domain,
                    diagnostic_message,
                    duration_ms,
                    validation_run_id,
                ),
            )

            result_id = cur.fetchone()[0]

        conn.commit()

    return result_id

def create_validation_run(
    fhir_lineage_id: int,
    run_type: str,
    scenario_name: str,
    synthetic: bool = False,
) -> int:
    sql = """
        INSERT INTO audit.validation_runs (
            fhir_lineage_id,
            run_type,
            scenario_name,
            synthetic
        )
        VALUES (%s, %s, %s, %s)
        RETURNING validation_run_id
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    fhir_lineage_id,
                    run_type,
                    scenario_name,
                    synthetic,
                ),
            )

            validation_run_id = cur.fetchone()[0]

        conn.commit()

    return validation_run_id

def complete_validation_run(
    validation_run_id: int,
    overall_status: str,
) -> None:
    sql = """
        UPDATE audit.validation_runs
        SET
            overall_status = %s,
            completed_at = CURRENT_TIMESTAMP
        WHERE validation_run_id = %s
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    overall_status,
                    validation_run_id,
                ),
            )

        conn.commit()