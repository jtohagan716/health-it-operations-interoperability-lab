CREATE TABLE IF NOT EXISTS audit.oru_messages (
    oru_message_id BIGSERIAL PRIMARY KEY,

    message_control_id VARCHAR(100) NOT NULL,

    patient_identifier VARCHAR(100),
    assigning_authority VARCHAR(100),
    identifier_type VARCHAR(20),

    placer_order_number VARCHAR(100),
    filler_order_number VARCHAR(100),

    sending_application VARCHAR(100),
    sending_facility VARCHAR(100),

    message_type VARCHAR(20) NOT NULL,
    trigger_event VARCHAR(20) NOT NULL,

    service_code VARCHAR(100),
    service_text VARCHAR(255),
    service_coding_system VARCHAR(50),

    obr_result_status VARCHAR(20),

    processing_status VARCHAR(30) NOT NULL,

    received_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS audit.oru_observations (
    oru_observation_id BIGSERIAL PRIMARY KEY,

    oru_message_id BIGINT NOT NULL
        REFERENCES audit.oru_messages(oru_message_id),

    observation_code VARCHAR(100) NOT NULL,
    observation_text VARCHAR(255),
    observation_coding_system VARCHAR(50),

    value_type VARCHAR(20),

    observation_value TEXT,

    units VARCHAR(100),

    reference_range VARCHAR(100),

    abnormal_flag VARCHAR(20),

    result_status VARCHAR(20),

    recorded_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


CREATE INDEX IF NOT EXISTS idx_oru_messages_control_id
    ON audit.oru_messages(message_control_id);

CREATE INDEX IF NOT EXISTS idx_oru_messages_patient
    ON audit.oru_messages(patient_identifier);

CREATE INDEX IF NOT EXISTS idx_oru_messages_placer_order
    ON audit.oru_messages(placer_order_number);

CREATE INDEX IF NOT EXISTS idx_oru_messages_filler_order
    ON audit.oru_messages(filler_order_number);

CREATE INDEX IF NOT EXISTS idx_oru_messages_received_at
    ON audit.oru_messages(received_at);

CREATE INDEX IF NOT EXISTS idx_oru_observations_message
    ON audit.oru_observations(oru_message_id);

CREATE INDEX IF NOT EXISTS idx_oru_observations_code
    ON audit.oru_observations(observation_code);