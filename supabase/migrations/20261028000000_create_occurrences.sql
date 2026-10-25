CREATE TABLE IF NOT EXISTS public.occurrences (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL,
    occurrence_id text,
    date timestamptz,
    source text,
    description text,
    aircraft_registration text,
    status text DEFAULT 'Open',
    department text,
    remarks text,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_occurrences_tenant ON public.occurrences (tenant_id);
