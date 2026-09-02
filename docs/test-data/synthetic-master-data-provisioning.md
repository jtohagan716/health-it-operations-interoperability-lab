# Synthetic Master-Data Provisioning

Issue: #31

## Purpose

Provision three deterministic synthetic facilities and 25 non-login synthetic providers as the organizational foundation for the 100-patient longitudinal test population.

## OpenEMR 8.2.0 implementation finding

OpenEMR advertises create/update support for FHIR Organization and Practitioner. Its FHIR-facing database validators, however, require NPI-shaped values for both facility and practitioner inserts. The existing locally created provider demonstrates that OpenEMR itself permits provider records without an NPI.

The synthetic population must not invent real-looking NPIs simply to satisfy an API validator. Therefore this fixture uses:

- `FacilityService::validate()` and `FacilityService::insertFacility()` for facility records;
- a narrowly scoped transaction for non-login provider fixture rows;
- OpenEMR `UuidRegistry` for application-compatible UUIDs;
- deterministic usernames and `example.invalid` email addresses;
- specialty-aligned NUCC taxonomy classification codes;
- `users.facility_id` and `users_facility` for facility relationships;
- database and later FHIR read verification after persistence.

The adapter is restricted to `local-lab`, the `SYNFAC`/`SYNPROV` namespaces, and source `SYNTHETIC_POPULATION_V1`. It never writes `users_secure`, creates no password, and does not create login-capable credentials.

OpenEMR defaults an omitted provider taxonomy to Family Medicine (`207Q00000X`). The adapter therefore supplies an explicit taxonomy for every provider group. For synthetic records created by an earlier dry-run package, it permits one narrowly guarded normalization only when the record carries the exact synthetic source marker and still contains that untouched OpenEMR default. Any other taxonomy mismatch fails closed.

## Commands

Dry-run is the default:

```powershell
python -m scripts.synthetic.master_data
```

One facility/provider probe:

```powershell
python -m scripts.synthetic.master_data `
    --probe `
    --commit `
    --environment local-lab `
    --confirm-provider-count 1 `
    --confirm-facility-count 1
```

Verify the probe:

```powershell
python -m scripts.synthetic.master_data --probe --verify
```

Full commit after the probe is accepted:

```powershell
python -m scripts.synthetic.master_data `
    --commit `
    --environment local-lab `
    --confirm-provider-count 25 `
    --confirm-facility-count 3
```

Full verification:

```powershell
python -m scripts.synthetic.master_data --verify
```

## Idempotency policy

Facilities are located by deterministic `facility_code`; providers are located by deterministic `username`. An exact match is classified `EXISTING`. A mismatch fails closed rather than silently overwriting local state. Repeating the same committed operation must therefore produce the same three logical facilities and 25 logical providers.

## Department scope

The eight departments are deterministic logical service locations used for provider assignment and later encounter/HL7 location generation. OpenEMR does not expose a general writable department/location resource through the currently advertised API. This pull request does not claim eight separately persisted OpenEMR Location records.

## Required validation

- offline tests pass;
- PHP syntax check runs as a non-root command against the OpenEMR image;
- dry-run produces three facilities, eight departments, and 25 providers;
- guarded one-record probe succeeds;
- probe verification resolves one facility, one provider, and the provider/facility link;
- full commit resolves exact target counts;
- second full commit reports all records as existing;
- FHIR reads expose the created facility and provider records;
- no synthetic facility or provider contains an NPI;
- no `users_secure` rows are created for synthetic providers.
