-- HRC reference registry (versioned, corrected)
CREATE TABLE IF NOT EXISTS hrc_reference_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text NOT NULL,
  classification text NOT NULL CHECK (classification IN ('GLOBAL_HRC','GLOBAL_OTHER_RISK','NATIONAL_HRC')),
  title text NOT NULL,
  source_document_id text NOT NULL,
  source_document_title text,
  source_edition text,
  source_section text,
  source_sha256 text NOT NULL,
  jurisdiction text,
  version int NOT NULL DEFAULT 1 CHECK (version > 0),
  approval_status text NOT NULL DEFAULT 'published' CHECK (approval_status IN ('draft','published','deprecated')),
  approved_by text,
  approved_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT hrc_class_jurisdiction_check CHECK (
    (classification IN ('GLOBAL_HRC','GLOBAL_OTHER_RISK') AND jurisdiction IS NULL) OR
    (classification = 'NATIONAL_HRC' AND jurisdiction IS NOT NULL)
  )
);

-- NULLS NOT DISTINCT uniqueness (Postgres 15+)
CREATE UNIQUE INDEX IF NOT EXISTS ux_hrc_ref_version
  ON hrc_reference_versions (code, classification, jurisdiction, version) NULLS NOT DISTINCT;

-- Immutability: prevent update/delete of published rows
CREATE OR REPLACE FUNCTION prevent_published_hrc_mutation() RETURNS trigger AS $$
BEGIN
  IF OLD.approval_status = 'published' THEN
    RAISE EXCEPTION 'Published HRC reference version is immutable';
  END IF;
  RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_published_hrc_update ON hrc_reference_versions;
CREATE TRIGGER trg_prevent_published_hrc_update
  BEFORE UPDATE OR DELETE ON hrc_reference_versions
  FOR EACH ROW EXECUTE FUNCTION prevent_published_hrc_mutation();

-- RLS: no direct client access; backend service role bypasses RLS
ALTER TABLE hrc_reference_versions ENABLE ROW LEVEL SECURITY;
