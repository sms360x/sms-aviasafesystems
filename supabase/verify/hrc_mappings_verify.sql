SELECT mapping_type, count(*) FROM hrc_category_mappings GROUP BY mapping_type;
SELECT count(*) AS total_mappings FROM hrc_category_mappings;
SELECT count(*) AS duplicates FROM (
  SELECT source_id, target_id, count(*) c FROM hrc_category_mappings GROUP BY source_id,target_id HAVING count(*)>1
) x;
SELECT 'OK' AS status;
