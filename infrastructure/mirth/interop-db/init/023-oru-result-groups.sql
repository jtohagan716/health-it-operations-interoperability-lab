BEGIN;

/*
 * Introduce the report-group level represented by OBR and make
 * observation cardinality and ordering explicit. Existing rows are
 * backfilled deterministically without inventing an original OBX-1.
 */
CREATE TABLE audit.oru_result_groups (
    oru_result_group_id BIGSERIAL PRIMARY KEY,

    oru_message_id BIGINT NOT NULL
        REFERENCES audit.oru_messages(oru_message_id),

    result_group_sequence INTEGER NOT NULL,
    obr_set_id VARCHAR(20),

    placer_order_number VARCHAR(100),
    filler_order_number VARCHAR(100),

    service_code VARCHAR(100),
    service_text VARCHAR(255),
    service_coding_system VARCHAR(50),

    observation_at TIMESTAMPTZ,
    result_status VARCHAR(20),

    recorded_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_oru_result_groups_sequence
        CHECK (result_group_sequence >= 1),

    CONSTRAINT uq_oru_result_groups_message_sequence
        UNIQUE (oru_message_id, result_group_sequence),

    CONSTRAINT uq_oru_result_groups_identity
        UNIQUE (oru_result_group_id, oru_message_id)
);


INSERT INTO audit.oru_result_groups (
    oru_message_id,
    result_group_sequence,
    obr_set_id,
    placer_order_number,
    filler_order_number,
    service_code,
    service_text,
    service_coding_system,
    observation_at,
    result_status,
    recorded_at
)
SELECT
    m.oru_message_id,
    1,
    NULL,
    m.placer_order_number,
    m.filler_order_number,
    m.service_code,
    m.service_text,
    m.service_coding_system,
    m.observation_at,
    m.obr_result_status,
    m.received_at
FROM audit.oru_messages AS m
ORDER BY m.oru_message_id;


ALTER TABLE audit.oru_observations
    ADD COLUMN oru_result_group_id BIGINT,
    ADD COLUMN observation_sequence INTEGER,
    ADD COLUMN obx_set_id VARCHAR(20);


WITH ranked_observations AS (
    SELECT
        o.oru_observation_id,
        g.oru_result_group_id,
        row_number() OVER (
            PARTITION BY o.oru_message_id
            ORDER BY o.oru_observation_id
        )::INTEGER AS observation_sequence
    FROM audit.oru_observations AS o
    JOIN audit.oru_result_groups AS g
      ON g.oru_message_id = o.oru_message_id
     AND g.result_group_sequence = 1
)
UPDATE audit.oru_observations AS o
SET
    oru_result_group_id = ranked.oru_result_group_id,
    observation_sequence = ranked.observation_sequence
FROM ranked_observations AS ranked
WHERE ranked.oru_observation_id = o.oru_observation_id;


ALTER TABLE audit.oru_observations
    ALTER COLUMN oru_result_group_id SET NOT NULL,
    ALTER COLUMN observation_sequence SET NOT NULL;


ALTER TABLE audit.oru_observations
    ADD CONSTRAINT ck_oru_observations_sequence
        CHECK (observation_sequence >= 1),

    ADD CONSTRAINT fk_oru_observations_result_group
        FOREIGN KEY (
            oru_result_group_id,
            oru_message_id
        )
        REFERENCES audit.oru_result_groups (
            oru_result_group_id,
            oru_message_id
        ),

    ADD CONSTRAINT uq_oru_observations_group_sequence
        UNIQUE (
            oru_result_group_id,
            observation_sequence
        );


CREATE INDEX idx_oru_result_groups_message
    ON audit.oru_result_groups(oru_message_id);


COMMENT ON TABLE audit.oru_result_groups IS
    'Ordered semantic result-report groups represented by OBR segments.';

COMMENT ON COLUMN audit.oru_result_groups.result_group_sequence IS
    'Canonical one-based report-group sequence within an ORU message.';

COMMENT ON COLUMN audit.oru_observations.observation_sequence IS
    'Canonical one-based observation sequence within a result group.';

COMMENT ON COLUMN audit.oru_observations.obx_set_id IS
    'Original OBX-1 value when supplied; historical values are not inferred.';


COMMIT;
