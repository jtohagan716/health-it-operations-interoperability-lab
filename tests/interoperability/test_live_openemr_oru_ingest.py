import os
from pathlib import Path

import pytest

from scripts.hl7.openemr_oru_ingest import (
    OpenEmrTarget,
    execute_openemr_scenario,
)


LIVE_ORDER_ID = os.getenv("OPENEMR_ORU_LIVE_ORDER_ID")


@pytest.mark.skipif(
    LIVE_ORDER_ID is None,
    reason=(
        "Set OPENEMR_ORU_LIVE_ORDER_ID to enable the "
        "non-mutating live OpenEMR dry run."
    ),
)
def test_existing_openemr_order_accepts_oru_dry_run():
    target = OpenEmrTarget(
        order_id=int(LIVE_ORDER_ID),
        patient_id=int(
            os.getenv("OPENEMR_ORU_LIVE_PATIENT_ID", "1")
        ),
        encounter_id=int(
            os.getenv("OPENEMR_ORU_LIVE_ENCOUNTER_ID", "6")
        ),
        lab_id=int(
            os.getenv("OPENEMR_ORU_LIVE_LAB_ID", "2")
        ),
    )

    result = execute_openemr_scenario(
        Path(
            "fixtures/hl7/oru/scenarios/"
            "normal-glucose-final.json"
        ),
        target,
    )

    assert result.dry_run["status"] == "DRY_RUN_PASSED"
    assert result.committed is None

