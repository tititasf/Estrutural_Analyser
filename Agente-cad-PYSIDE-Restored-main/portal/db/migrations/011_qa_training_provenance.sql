-- Proveniencia suficiente para auditoria e curadoria futura de dataset/RAG.
-- Toda amostra nasce inelegivel; promocao exige gate/decisao humana posterior.

ALTER TABLE portal_qa_items ADD COLUMN prompt_text TEXT;
ALTER TABLE portal_qa_items ADD COLUMN prompt_sha256 TEXT;
ALTER TABLE portal_qa_items ADD COLUMN evidence_json TEXT;
ALTER TABLE portal_qa_items ADD COLUMN adapter_version TEXT;
ALTER TABLE portal_qa_items ADD COLUMN decision_authority TEXT NOT NULL DEFAULT 'PENDENTE';
ALTER TABLE portal_qa_items ADD COLUMN training_eligible INTEGER NOT NULL DEFAULT 0;

ALTER TABLE portal_qa_attempts ADD COLUMN provider_version TEXT;
ALTER TABLE portal_qa_attempts ADD COLUMN raw_response_text TEXT;
ALTER TABLE portal_qa_attempts ADD COLUMN raw_response_sha256 TEXT;
