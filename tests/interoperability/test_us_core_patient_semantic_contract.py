from scripts.fhir.patient_helpers import get_fhir_patient, load_hl7_patient


US_CORE_SEX_URL = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-sex"
)

EXPECTED_MALE_SNOMED_CODE = "248153007"


def _find_extension(resource: dict, url: str) -> dict:
    for extension in resource.get("extension", []):
        if extension.get("url") == url:
            return extension

    raise AssertionError(f"FHIR extension not found: {url}")


def test_us_core_patient_sex_coding_matches_source_semantics():
    hl7_patient = load_hl7_patient()

    assert hl7_patient["gender"] == "male"

    patient = get_fhir_patient(hl7_patient["identifier"])

    sex_extension = _find_extension(patient, US_CORE_SEX_URL)
    coding = sex_extension.get("valueCoding")

    assert coding is not None, "US Core sex extension must contain valueCoding"

    assert coding.get("system") == "http://snomed.info/sct"

    assert coding.get("code") == EXPECTED_MALE_SNOMED_CODE, (
        "Semantic terminology mismatch: source patient is male, "
        f"but OpenEMR emitted SNOMED code {coding.get('code')} "
        f"with display {coding.get('display')!r}. "
        f"Expected male SNOMED code {EXPECTED_MALE_SNOMED_CODE}."
    )