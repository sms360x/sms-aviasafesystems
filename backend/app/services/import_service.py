"""Master Logsheet import service.
Maps uploaded Excel/CSV columns to canonical fields, routes each row to the
correct destination table(s) based on classification checkboxes, and stages
rows for preview/approval before promotion.
"""
import pandas as pd
import uuid
from typing import Optional

MASTER_LOGSHEET_CANONICAL = {
    "sequence_number": ["S.N", "SN", "Serial", "#"],
    "reported_date": ["Reported Date", "Reported Date to CSD (dd/mm/yy)", "Date Reported"],
    "occurrence_date": ["Occurrence Date", "Occurance Date of report (dd/mm/yy)", "Date of Occurrence"],
    "source": ["Sources of Information", "Source", "Report Source"],
    "description": ["Report Description", "Description", "Narrative"],
    "classification_occurrence": ["Occurrence"],
    "classification_hazard": ["Hazard"],
    "classification_deficiency": ["Safety deficiency", "Safety Deficiency"],
    "classification_diversion": ["Diversion"],
    "status": ["Status"],
    "concerned_department": ["Concerned department/Personnel", "Concerned Department"],
    "remarks": ["Remarks"],
    "flight_sector": ["Flight Sector (From-To)", "Flight Sector"],
    "flight_number": ["Flight Number"],
    "diverted_to": ["Diverted to"],
    "aircraft_registration": ["Aircraft Registration"],
    "reason": ["Reason of diversion"],
    "taxonomy": ["Taxonomy", "Hazard Taxonomy", "Taxonomy- Type of Area/ Operation/ Equipment"],
}


def read_file(file_obj, filename: str) -> pd.DataFrame:
    if filename.lower().endswith(".xlsx"):
        return pd.read_excel(file_obj)
    if filename.lower().endswith(".csv"):
        return pd.read_csv(file_obj)
    raise ValueError("Only .xlsx and .csv are supported")


def auto_map_columns(headers):
    mapping = {}
    for canonical, aliases in MASTER_LOGSHEET_CANONICAL.items():
        for alias in aliases:
            if alias in headers:
                mapping[alias] = canonical
                break
    return mapping


def row_has_classification(mapped: dict) -> bool:
    return any(mapped.get(k) for k in (
        "classification_occurrence",
        "classification_hazard",
        "classification_deficiency",
        "classification_diversion",
    ))


def route_row(mapped: dict) -> list[str]:
    tables = []
    if mapped.get("classification_occurrence"):
        tables.append("occurrences")
    if mapped.get("classification_hazard"):
        tables.append("hazards")
    if mapped.get("classification_deficiency"):
        tables.append("hazards")
    if mapped.get("classification_diversion"):
        tables.append("flight_diversions")
    return tables


def parse_batch(file_obj, filename: str):
    """Parse file, return (mapping, unmapped_columns, staged_rows)."""
    df = read_file(file_obj, filename)
    mapping = auto_map_columns(list(df.columns))
    unmapped = [c for c in df.columns if c not in mapping]

    staged = []
    for idx, row in df.iterrows():
        mapped = {mapping[k]: v for k, v in row.items() if k in mapping and pd.notna(v)}
        if not row_has_classification(mapped):
            continue
        dest = route_row(mapped)
        if not dest:
            continue
        staged.append({
            "row_number": int(idx) + 2,
            "raw_data": {k: (None if pd.isna(v) else str(v)) for k, v in row.items()},
            "mapped_data": {k: (None if pd.isna(v) else str(v)) for k, v in mapped.items()},
            "destination_tables": dest,
        })
    return mapping, unmapped, staged
