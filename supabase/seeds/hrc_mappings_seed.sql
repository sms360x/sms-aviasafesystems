-- Idempotent mapping seed (six correspondences)
-- Resolves reference IDs by classification/jurisdiction/edition
INSERT INTO hrc_category_mappings (source_table, source_id, target_table, target_id, mapping_type)
SELECT 'hrc_reference_versions', s.id, 'hrc_reference_versions', t.id, 'DIRECT'
FROM hrc_reference_versions s
JOIN hrc_reference_versions t ON t.code=s.code
WHERE s.classification IN ('GLOBAL_HRC') AND s.jurisdiction IS NULL AND s.source_edition='2026-2028'
  AND t.classification='NATIONAL_HRC' AND t.jurisdiction='NP' AND t.source_edition='2023-2025'
  AND s.code IN ('CFIT','LOC-I','MAC','RE','RI')
ON CONFLICT DO NOTHING;

INSERT INTO hrc_category_mappings (source_table, source_id, target_table, target_id, mapping_type)
SELECT 'hrc_reference_versions', s.id, 'hrc_reference_versions', t.id, 'CROSS'
FROM hrc_reference_versions s
JOIN hrc_reference_versions t ON t.code=s.code
WHERE s.classification='GLOBAL_OTHER_RISK' AND s.code='ARC' AND s.jurisdiction IS NULL AND s.source_edition='2026-2028'
  AND t.classification='NATIONAL_HRC' AND t.code='ARC' AND t.jurisdiction='NP' AND t.source_edition='2023-2025'
ON CONFLICT DO NOTHING;
