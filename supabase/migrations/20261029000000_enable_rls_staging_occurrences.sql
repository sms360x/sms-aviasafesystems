-- 1. Enable RLS on the tables
ALTER TABLE public.master_logsheet_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.occurrences ENABLE ROW LEVEL SECURITY;

-- 2. Policy for master_logsheet_staging (Tenant isolation)
CREATE POLICY "Tenant isolation for staging" 
ON public.master_logsheet_staging
FOR ALL
USING (tenant_id = current_setting('app.current_tenant', true));

-- 3. Policy for occurrences (Tenant isolation)
CREATE POLICY "Tenant isolation for occurrences" 
ON public.occurrences
FOR ALL
USING (tenant_id = current_setting('app.current_tenant', true));