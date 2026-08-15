# Mirth Connect Foundation Validation

## Status

PASS

A reproducible Mirth Connect 4.5.2 environment backed by PostgreSQL was deployed, functionally validated, and tested for persistence across complete container recreation.

## Environment

- Mirth Connect: 4.5.2
- Mirth image digest: `sha256:4afa295cfe7c5ffd596efee69594157fea87202e33d66bb4a98a52db4598f836`
- PostgreSQL image: 16
- PostgreSQL runtime version: 16.15
- PostgreSQL image digest: `sha256:11a9d238fbb48bab14599c57e41123254452b1a2d93c6c8595bce96f346bd082`
- Deployment: Docker Compose
- Data: synthetic laboratory environment only

## Runtime Validation

Mirth startup logging confirmed:

```text
Mirth Connect 4.5.2
server successfully started
database backend: postgres
```

The PostgreSQL backend was therefore validated from the running application rather than inferred from configuration alone.

## Application Readiness

| Validation | Result |
|---|---|
| PostgreSQL readiness | PASS - accepting connections |
| Mirth HTTP 8080 | PASS - HTTP 200 |
| Mirth HTTPS 8443 | PASS - HTTP 200 |
| Administrator launch | PASS |
| Administrator login | PASS |

## PostgreSQL Validation

Mirth initialized its application schema in PostgreSQL.

- Public PostgreSQL tables: 14
- Representative tables: `channel`, `configuration`, `person`, `person_password`, `event`, `script`, `schema_info`

This confirmed application persistence in PostgreSQL rather than use of the embedded Derby database.

## Persistent Storage

Named Docker volumes:

- `health-it-mirth-lab_mirth-db-data`
- `health-it-mirth-lab_mirth-appdata`

PostgreSQL is not mapped to a host port. It is reachable only through the internal Compose network.

## Container Recreation Test

Original Mirth container:

`b2c34c8cebd469b7266c2b3e93756372b301e773f773e9021b50edb4bfcb7de8`

Replacement Mirth container:

`70327d31fa2e71d1b5d4f16181eebef7c33c5565a3d2b3c0861b9bafe9514351`

Original PostgreSQL container:

`9f4dd7760518fb52f5f03d14419f313db97185ca445350a7f96cde37462d1729`

Replacement PostgreSQL container:

`3ca5e0ba29120816d1aeedeece4eee512d9d5ea39abb3c201e72bcfd52e9d541`

Both original containers were removed using `docker compose down` without `-v`.

The named volumes remained present.

New containers were then created using the same Compose definition.

Both replacement container IDs differed from the originals, proving that new containers were created rather than merely restarted.

## Persistence Validation

After container recreation:

- PostgreSQL returned to healthy status.
- Mirth 4.5.2 started successfully.
- Mirth again identified its database backend as PostgreSQL.
- The Mirth PostgreSQL schema remained present.
- The administrator credential established during first login remained valid.
- Administrator dashboard access succeeded.

This functionally demonstrates persistence of Mirth application state across complete container recreation.

## Security and Credential Handling

- The real `.env` file is excluded from Git.
- `.env.example` contains placeholders only.
- No administrator password is stored in repository evidence.
- No database password is stored in tracked configuration.
- No PHI or production credentials are used.

## Engineering Result

The Mirth foundation satisfies the distinction:

```text
container running
    !=
application ready
    !=
database initialized
    !=
state proven persistent
```

Each layer was independently validated.
