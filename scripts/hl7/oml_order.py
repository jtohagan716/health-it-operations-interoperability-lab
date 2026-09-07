import json
import subprocess
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LaboratoryOrder:
    placer_order_number: str
    patient_identifier: str
    patient_family_name: str
    patient_given_name: str
    patient_date_of_birth: str
    patient_sex: str
    visit_number: str
    service_code: str
    service_text: str
    ordered_at: str
    order_id: int
    patient_id: int
    encounter_id: int
    lab_id: int


def hl7_timestamp(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%Y%m%d%H%M%S")


def build_oml_segments(order: LaboratoryOrder, *, control_id: str) -> list[str]:
    if not control_id.strip():
        raise ValueError("Message control ID must not be blank.")
    timestamp = hl7_timestamp(order.ordered_at)
    return [
        "|".join([
            "MSH", "^~\\&", "OPENEMR", "INTEROPLAB", "SYNLIS", "LAB",
            timestamp, "", "OML^O21^OML_O21", control_id, "P", "2.5.1",
        ]),
        "|".join([
            "PID", "1", "",
            f"{order.patient_identifier}^^^INTEROPLAB^MR", "",
            f"{order.patient_family_name}^{order.patient_given_name}^^^^^L", "",
            order.patient_date_of_birth, order.patient_sex,
        ]),
        f"PV1|1|O|||||||||||||||||{order.visit_number}",
        f"ORC|NW|{order.placer_order_number}|||||||{timestamp}",
        (
            f"OBR|1|{order.placer_order_number}||"
            f"{order.service_code}^{order.service_text}^LN|||{timestamp}"
        ),
    ]


def parse_verified_order(payload: dict, external_id: str) -> LaboratoryOrder:
    row = payload["records"][external_id]
    required = (
        "order_id", "mrn", "encounter_number", "lab_id", "test_code",
        "test_name", "ordered_at",
    )
    missing = [key for key in required if row.get(key) in (None, "")]
    if missing:
        raise ValueError(f"Verified order is missing: {', '.join(missing)}")
    patient = row.get("patient") or {}
    return LaboratoryOrder(
        placer_order_number=external_id,
        patient_identifier=row["mrn"],
        patient_family_name=patient.get("family_name", "Synthetic"),
        patient_given_name=patient.get("given_name", "Patient"),
        patient_date_of_birth=patient.get("date_of_birth", "19700101"),
        patient_sex=patient.get("administrative_sex", "U"),
        visit_number=str(row["encounter_number"]),
        service_code=row["test_code"],
        service_text=row["test_name"],
        ordered_at=row["ordered_at"],
        order_id=int(row["order_id"]),
        patient_id=int(row.get("patient_id", 0)),
        encounter_id=int(row.get("encounter_id", 0)),
        lab_id=int(row["lab_id"]),
    )


def load_verified_order(external_id: str) -> LaboratoryOrder:
    result = subprocess.run(
        ["python", "-m", "scripts.synthetic.laboratory_orders", "--verify"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    order = parse_verified_order(json.loads(result.stdout), external_id)
    sql = f"""
    USE openemr;
    SELECT JSON_OBJECT(
      'patient_id', po.patient_id,
      'encounter_id', po.encounter_id,
      'family_name', p.lname,
      'given_name', p.fname,
      'date_of_birth', DATE_FORMAT(p.DOB, '%Y%m%d'),
      'administrative_sex', CASE p.sex
        WHEN 'Male' THEN 'M' WHEN 'Female' THEN 'F' ELSE 'U' END
    )
    FROM procedure_order po
    JOIN patient_data p ON p.pid = po.patient_id
    WHERE po.external_id = '{external_id.replace("'", "''")}';
    """
    db = subprocess.run(
        ["docker", "exec", "-i", "health-it-openemr-lab-mysql-1",
         "sh", "-lc", 'exec mariadb --batch --skip-column-names '
         '-uroot --password="$MYSQL_ROOT_PASSWORD"'],
        input=sql, capture_output=True, text=True, check=False,
    )
    if db.returncode != 0 or not db.stdout.strip():
        raise RuntimeError("Could not resolve OpenEMR patient/order context.\n" + db.stderr)
    context = json.loads(db.stdout.strip().splitlines()[-1])
    return LaboratoryOrder(
        placer_order_number=order.placer_order_number,
        patient_identifier=order.patient_identifier,
        patient_family_name=context["family_name"],
        patient_given_name=context["given_name"],
        patient_date_of_birth=context["date_of_birth"],
        patient_sex=context["administrative_sex"],
        visit_number=order.visit_number,
        service_code=order.service_code,
        service_text=order.service_text,
        ordered_at=order.ordered_at,
        order_id=order.order_id,
        patient_id=int(context["patient_id"]),
        encounter_id=int(context["encounter_id"]),
        lab_id=order.lab_id,
    )
