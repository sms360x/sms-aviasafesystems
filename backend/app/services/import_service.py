"""Master Logsheet import service (CSV-only)."""
import pandas as pd

MASTER_LOGSHEET_CANONICAL = {
    "sequence_number": ["S.N", "SN", "Serial", "#"],
    "reported_date": ["Reported Date", "Date Reported"],
    "occurrence_date": ["Occurrence Date", "Date of Occurrence"],
    "source": ["Sources of Information", "Source", "Report Source"],
    "description": ["Report Description", "Description", "Narrative"],
    "classification_occurrence": ["Occurrence"],
    "classification_hazard": ["Hazard"],
    "classification_deficiency": ["Safety deficiency", "Safety Deficiency"],
    "classification_diversion": ["Diversion"],
    "status": ["Status"],
    "concerned_department": ["Concerned department/Personnel", "Concerned Department"],
    "remarks": ["Remarks"],
    "hazard_id": ["Hazard ID", "Hazard Code"],
    "taxonomy": ["Taxonomy", "Hazard Taxonomy"],
    "threat": ["Threat of Hazard", "Threats"],
    "top_event": ["Unsafe Event", "Top Event"],
    "consequence": ["Consequence", "Potential Consequence"],
    "priority": ["Report priority Level", "Priority"],
    "flight_number": ["Flight Number"],
    "flight_sector": ["Flight Sector"],
    "diverted_to": ["Diverted to"],
    "aircraft_registration": ["Aircraft Registration"],
    "reason": ["Reason of diversion"],
}


def read_file(file_obj, filename: str) -> pd.DataFrame:
    if filename.lower().endswith(".csv"):
        return pd.read_csv(file_obj)
    raise ValueError("Only .csv files are supported. Please convert your Excel file to CSV.")


def auto_map_columns(headers):
    mapping = {}
    for canonical, aliases in MASTER_LOGSHEET_CANONICAL.items():
        for alias in aliases:
            if alias in headers:
                mapping[alias] = canonical
                break
    return mapping


def parse_batch(file_obj, filename: str):
    df = read_file(file_obj, filename)
    df.columns = [str(c).strip() for c in df.columns]
    mapping = auto_map_columns(list(df.columns))
    unmapped = [c for c in df.columns if c not in mapping]

    staged = []
    for idx, row in df.iterrows():
        if pd.isna(row).all():
            continue

        mapped = {mapping[k]: v for k, v in row.items() if k in mapping and pd.notna(v)}

        dest = []
        if mapped.get("flight_sector"):
            dest.append("flight_diversions")
        elif mapped.get("hazard_id") or mapped.get("taxonomy"):
            dest.append("hazards")
        elif mapped.get("description"):
            dest.append("occurrences")

        if not dest:
            continue

        staged.append({
            "row_number": int(idx) + 2,
            "raw_data": {str(k): (None if pd.isna(v) else str(v)) for k, v in row.items()},
            "mapped_data": {k: (None if pd.isna(v) else str(v)) for k, v in mapped.items()},
            "destination_tables": dest,
        })

    return mapping, list(set(unmapped)), staged
