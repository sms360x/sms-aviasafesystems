-- Tenant HRC registry + mappings (versioned, corrected)
CREATE TABLE IF NOT EXISTS tenant_hrc_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  code text NOT NULL,
  title text NOT NULL,
  description text,
  version int NOT NULL DEFAULT 1 CHECK (version > 0),
  approval_status text NOT NULL DEFAULT 'draft' CHECK (approval_status IN ('draft','published','deprecated')),
  approved_by text,
  approved_at timestamptz,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  effective_from timestamptz,
  retired_at timestamptz,
  UNIQUE (tenant_id, code, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_tenant_hrc_published
  ON tenant_hrc_versions (tenant_id, code) WHERE approval_status='published' AND retired_at IS NULL;

CREATE OR REPLACE FUNCTION prevent_published_tenant_hrc_mutation() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.approval_status IN ('published','deprecated') THEN
      RAISE EXCEPTION 'Published/deprecated tenant HRC version is immutable';
    END IF;
    RETURN OLD;
  END IF;
  IF OLD.approval_status = 'deprecated' THEN
    RAISE EXCEPTION 'Deprecated tenant HRC version is immutable';
  END IF;
  IF OLD.approval_status = 'published' THEN
    IF OLD.retired_at IS NULL AND NEW.retired_at IS NOT NULL
       AND NEW.approval_status = 'deprecated'
       AND NEW.id = OLD.id
       AND NEW.tenant_id = OLD.tenant_id
       AND NEW.code = OLD.code
       AND NEW.title = OLD.title
       AND NEW.description IS NOT DISTINCT FROM OLD.description
       AND NEW.version = OLD.version
       AND NEW.created_by IS NOT DISTINCT FROM OLD.created_by
       AND NEW.created_at = OLD.created_at
       AND NEW.approved_by IS NOT DISTINCT FROM OLD.approved_by
       AND NEW.approved_at IS NOT DISTINCT FROM OLD.approved_at
       AND NEW.effective_from IS NOT DISTINCT FROM OLD.effective_from
    THEN
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Published tenant HRC version is immutable';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_published_tenant_hrc_update ON tenant_hrc_versions;
CREATE TRIGGER trg_prevent_published_tenant_hrc_update
  BEFORE UPDATE OR DELETE ON tenant_hrc_versions
  FOR EACH ROW EXECUTE FUNCTION prevent_published_tenant_hrc_mutation();

CREATE TABLE IF NOT EXISTS hrc_category_mappings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_table text NOT NULL CHECK (source_table IN ('hrc_reference_versions','tenant_hrc_versions')),
  source_id uuid NOT NULL,
  target_table text NOT NULL CHECK (target_table IN ('hrc_reference_versions','tenant_hrc_versions')),
  target_id uuid NOT NULL,
  mapping_type text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_table, source_id, target_table, target_id)
);

-- Prevent cross-tenant mappings and validate referenced records exist
CREATE OR REPLACE FUNCTION validate_hrc_mapping_tenants() RETURNS trigger AS $$
DECLARE
  src_tenant text;
  tgt_tenant text;
  src_exists boolean;
  tgt_exists boolean;
BEGIN
  IF NEW.source_table = 'hrc_reference_versions' THEN
    SELECT EXISTS(SELECT 1 FROM hrc_reference_versions WHERE id = NEW.source_id) INTO src_exists;
    IF NOT src_exists THEN RAISE EXCEPTION 'Source reference record does not exist'; END IF;
  ELSIF NEW.source_table = 'tenant_hrc_versions' THEN
    SELECT EXISTS(SELECT 1 FROM tenant_hrc_versions WHERE id = NEW.source_id) INTO src_exists;
    IF NOT src_exists THEN RAISE EXCEPTION 'Source tenant HRC record does not exist'; END IF;
    SELECT tenant_id INTO src_tenant FROM tenant_hrc_versions WHERE id = NEW.source_id;
  END IF;

  IF NEW.target_table = 'hrc_reference_versions' THEN
    SELECT EXISTS(SELECT 1 FROM hrc_reference_versions WHERE id = NEW.target_id) INTO tgt_exists;
    IF NOT tgt_exists THEN RAISE EXCEPTION 'Target reference record does not exist'; END IF;
  ELSIF NEW.target_table = 'tenant_hrc_versions' THEN
    SELECT EXISTS(SELECT 1 FROM tenant_hrc_versions WHERE id = NEW.target_id) INTO tgt_exists;
    IF NOT tgt_exists THEN RAISE EXCEPTION 'Target tenant HRC record does not exist'; END IF;
    SELECT tenant_id INTO tgt_tenant FROM tenant_hrc_versions WHERE id = NEW.target_id;
  END IF;

  IF src_tenant IS NOT NULL AND tgt_tenant IS NOT NULL AND src_tenant <> tgt_tenant THEN
    RAISE EXCEPTION 'Cross-tenant HRC mapping not allowed';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_hrc_mapping_tenants ON hrc_category_mappings;
CREATE TRIGGER trg_validate_hrc_mapping_tenants
  BEFORE INSERT OR UPDATE ON hrc_category_mappings
  FOR EACH ROW EXECUTE FUNCTION validate_hrc_mapping_tenants();

ALTER TABLE tenant_hrc_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE hrc_category_mappings ENABLE ROW LEVEL SECURITY;