CREATE TABLE IF NOT EXISTS public.master_logsheet_staging (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id uuid NOT NULL,
    tenant_id text NOT NULL,
    row_number integer NOT NULL,
    raw_data jsonb NOT NULL,
    mapped_data jsonb NOT NULL,
    destination_tables text[] NOT NULL,
    validation_status text NOT NULL DEFAULT 'pending',
    validation_errors jsonb,
    promoted_at timestamptz,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_master_logsheet_staging_batch ON public.master_logsheet_staging (batch_id);
CREATE INDEX IF NOT EXISTS ix_master_logsheet_staging_tenant ON public.master_logsheet_staging (tenant_id);
