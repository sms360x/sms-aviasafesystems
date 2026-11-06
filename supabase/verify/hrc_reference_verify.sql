SELECT classification, count(*) FROM hrc_reference_versions GROUP BY classification;
SELECT count(*) AS total FROM hrc_reference_versions;
SELECT code, classification, jurisdiction FROM hrc_reference_versions ORDER BY classification, code;
