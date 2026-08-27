ALTER TABLE audit.radiology_workflows
    ADD COLUMN IF NOT EXISTS
        pacs_reconciliation_detail TEXT;