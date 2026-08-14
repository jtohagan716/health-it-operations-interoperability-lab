# OpenEMR Foundation Validation

## Purpose

Validate that the Healthcare IT Operations & Interoperability Lab provides a reproducible OpenEMR environment with persistent clinical state across host restarts and complete container recreation.

This lab uses synthetic data only. No PHI is used.

## Environment

- Windows host
- Docker Desktop
- Docker Compose
- OpenEMR
- MariaDB
- Private Docker network
- Named persistent Docker volumes

### Services

- `mysql`
- `openemr`

### Persistent Volumes

- `health-it-openemr-lab_openemr-db-data`
- `health-it-openemr-lab_openemr-site-data`
- `health-it-openemr-lab_openemr-logs`

## Synthetic Clinical Fixture

### Facility

- Name: Interoperability Lab Clinic
- Organization Type: Healthcare Provider
- Place of Service: 11 - Office
- Service Location: Yes
- Billing Location: Yes
- Primary Business Entity: Yes

### Provider

- Username: `provider01`
- Name: Alice Morgan
- Provider: Yes
- Calendar enabled: Yes
- Default Facility: Interoperability Lab Clinic
- Access Control: Physicians
- Taxonomy: `207Q00000X`

No real NPI, DEA number, license number, Tax ID, or other external professional credentials were assigned.

### Patient

- External ID: `LAB000001`
- Name: Avery Testpatient
- DOB: 1980-01-15
- Synthetic data only

### Encounter

- Encounter ID: 4
- Visit Category: Office Visit
- Class: Outpatient
- Provider: Alice Morgan
- Facility: Interoperability Lab Clinic
- Place of Service: 11
- Reason for Visit: `Routine office visit - synthetic interoperability lab encounter`

## Clinical Data Validation

The following synthetic vital signs were entered and persisted:

| Observation | Value |
|---|---|
| Weight | 180 lb / 81.65 kg |
| Height | 70 in / 177.80 cm |
| Blood Pressure | 120/80 mmHg |
| Pulse | 72/min |
| Respiration | 16/min |
| Temperature | 98.6 F / 37.0 C |
| BMI | 25.82 kg/m^2 |

OpenEMR successfully performed unit conversion and derived BMI from the stored height and weight.

The vitals screen associated clinical observations with LOINC terminology.

## Tobacco Assessment

Synthetic tobacco history was recorded as:

- Tobacco status: Never smoker
- SNOMED CT: `266919005`
- Status: Never
- Cigarette Pack Years: 0

The Clinical Decision Rule reminder for tobacco assessment cleared after the structured smoking history was recorded.

## Clinical Reminder Validation

Initial clinical reminders included:

- Measurement: Weight - Past Due
- Assessment: Tobacco - Past Due

After the appropriate clinical data was recorded:

- Weight reminder cleared
- Tobacco assessment reminder cleared

The weight reminder did not disappear immediately after data entry but cleared after subsequent application/session reevaluation. No duplicate clinical data was entered as a workaround.

## Host Reboot Persistence Test

### Procedure

1. Confirmed OpenEMR and MariaDB were healthy.
2. Rebooted the Windows host.
3. Restarted Docker Desktop.
4. Confirmed both containers automatically returned to healthy status.
5. Retrieved patient `LAB000001`.
6. Verified encounter and clinical data.

### Result

**PASS**

Clinical state remained intact after a host reboot.

## Container Recreation Persistence Test

### Original Runtime

Original container IDs before recreation:

- OpenEMR: `2851561c1592`
- MariaDB: `fd4316094a64`

Both containers were healthy before the test.

### Procedure

Executed:

`docker compose down`

This removed:

- OpenEMR container
- MariaDB container
- Compose network

The three named volumes remained present.

The environment was recreated using:

`docker compose up -d`

Docker created replacement containers and recreated the internal network.

Replacement container IDs:

- OpenEMR: `645840cbc9a3`
- MariaDB: `3b7fabccb9d0`

Both MariaDB and OpenEMR returned to healthy status.

### Application Reconciliation

After container recreation, the following data was independently verified in OpenEMR:

- Avery Testpatient exists
- External ID `LAB000001` exists
- Encounter 4 exists
- Alice Morgan remains associated with the encounter
- Interoperability Lab Clinic remains associated with the encounter
- Reason for Visit remains intact
- Vital signs remain intact
- BMI remains available
- Never-smoker history remains intact
- SNOMED CT smoking-status code remains intact

### Result

**PASS**

The runtime containers were removed and recreated while clinical state survived through persistent storage.

## Key Finding

The lab demonstrates a separation between replaceable runtime infrastructure and persistent application state.

Conceptually:

```text
OpenEMR container
        |
        v
OpenEMR persistent site data

MariaDB container
        |
        v
Persistent database data