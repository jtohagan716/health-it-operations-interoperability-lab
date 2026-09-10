# Managed DICOM Storage SCP Validation

## Objective

Remove the PACS workflow's hidden dependency on a manually
started downstream DICOM receiver and establish a reproducible,
health-checked destination managed by Docker Compose.

## Initial observed state

Orthanc was operational as application entity `ORTHANC` on port
`4242`. Its `interoplab` remote modality was configured as
`INTEROPLAB` at `host.docker.internal:11112`.

No process was listening on host port `11112`. Orthanc's REST
C-ECHO request returned HTTP 500, and its logs reported a DICOM
association TCP initialization failure.

The focused PACS regression suite produced seven failures:

- destination health was false;
- manual routing returned HTTP 500;
- metadata-selected autorouting did not reach the destination;
- three C-MOVE success and identity assertions failed; and
- aggregate destination health reported zero healthy targets.

The autorouting log contained `AUTO-ROUTE MATCH`, establishing
that inbound storage, metadata evaluation, and route selection
had succeeded before the outbound association failed.

## Root cause

The downstream Storage SCP was implemented as a Python process
that had to be started manually in a separate terminal. Docker
Compose managed Orthanc but did not manage the receiver's
lifecycle. When that terminal process was absent, the configured
destination had no listener.

The seven failing tests were downstream effects of this single
unavailable DICOM association boundary.

## Remediation

The receiver was converted into the `dicom-storage-scp` Compose
service with:

- AE title `INTEROPLAB`;
- DICOM port `11112`;
- restart policy `unless-stopped`;
- pinned `pydicom` and `pynetdicom` dependencies;
- a DICOM C-ECHO health probe;
- Orthanc startup dependency on receiver health;
- Docker service-name discovery; and
- a host bind mount for received DICOM objects.

Orthanc now resolves the destination as
`dicom-storage-scp:11112` instead of routing through
`host.docker.internal` to a manually operated process.

The receiver was also updated to provide real command-line help,
environment-driven configuration, immediate operational logging,
missing-SOP-UID rejection, and explicit persistence-failure
handling.

## Why the health check is meaningful

The container health check does not merely test whether TCP port
`11112` is open. It negotiates a DICOM association using the
Verification SOP Class and requires a successful C-ECHO status of
`0x0000` from the called AE title `INTEROPLAB`.

Docker therefore reports the receiver healthy only when it can
perform a real DICOM protocol operation.

## Persistence boundary

The receiver writes to `/data/received` inside its container.
Compose maps that location to the host repository path:

```text
artifacts/dicom/received
```

This makes routed and retrieved objects visible to the existing
host-side tests and preserves them across receiver recreation.

## Validation commands

```powershell
docker compose `
    -f .\infrastructure\orthanc\compose.yaml `
    ps

python -m scripts.dicom.storage_scp_health `
    --host localhost `
    --port 11112 `
    --called-ae INTEROPLAB

Invoke-RestMethod `
    -Method Post `
    -Uri http://localhost:8042/modalities/interoplab/echo
```

The live Orthanc modality configuration must report:

```text
AET  : INTEROPLAB
Host : dicom-storage-scp
Port : 11112
```

## Regression result

After the managed receiver was introduced:

```text
25 passed in 12.37s
```

The passing suite covered destination health, manual routing,
metadata-driven autorouting, C-FIND, C-MOVE, retrieved-object
identity, DICOM hierarchy preservation, PACS reconciliation,
radiology lineage, failure-state handling, and persistence.

Two later setup errors were traced to inaccessible Windows ACLs
on the disposable `.pytest_runtime` directory. No DICOM assertion
failed. After the directory permissions were repaired, the two
previously blocked tests passed:

```text
2 passed in 20.69s
```

## Result

The workflow no longer depends on an operator remembering to
launch and preserve a separate terminal process. Destination
availability is now represented as versioned infrastructure with
an explicit network identity, restart policy, dependency set,
health contract, persistent output boundary, and regression
coverage.
