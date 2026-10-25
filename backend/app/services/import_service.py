"""Master Logsheet import service.
Maps uploaded Excel/CSV columns to canonical fields, routes each row to the
correct destination table(s) based on sheet name / classification checkboxes,
and stages rows for preview/approval before promotion.
"""
import pandas as pd
import uuid
from typing import Optional

MASTER_LOGSHEET_CANONICAL = {
    "sequence_number": ["S.N", "SN", "Serial", "#", "SN."],
    "reported_date": ["Reported Date", "Reported Date to CSD (dd/mm/yy)", "Date Reported"],
    "occurrence_date": ["Occurrence Date", "Occurance Date of report (dd/mm/yy)", "Date of Occurrence"],
    "source": ["Sources of Information", "Source", "Report Source", "Sources of information"],
    "description": ["Report Description", "Description", "Narrative", "Unsafe Event", "Report Description"],
    "classification_occurrence": ["Occurrence"],
    "classification_hazard": ["Hazard"],
    "classification_deficiency": ["Safety deficiency", "Safety Deficiency"],
    "classification_diversion": ["Diversion"],
    "status": ["Status"],
    "concerned_department": ["Concerned department/Personnel", "Concerned Department"],
    "remarks": ["Remarks", "CSD Remarks"],
    "hazard_id": ["Hazard code/ID", "Hazard Code/ID", "Hazard ID"],
    "taxonomy": ["Taxonomy", "Hazard Taxonomy", "Taxonomy- Type of Area/ Operation/ Equipment"],
    "threat": ["Threat", "Threat of Hazard"],
    "consequence": ["Potential Consequence", "Consequence", "Ultimate Consequence"],
    "top_event": ["Top Event", "Unsafe Event"],
    "flight_sector": ["Flight Sector (From-To)", "Flight Sector"],
    "flight_number": ["Flight Number"],
    "diverted_to": ["Diverted to"],
    "aircraft_registration": ["Aircraft Registration"],
    "reason": ["Reason of diversion", "Reason"],
    "taxonomy_specific": ["Specific components", "Specific Components"],
    "priority": ["Report priority Level", "Report priority", "Report Priority"],
    "recommended_action": ["Recommended Action"],
    "corrective_action": ["Corrective Action"],
    "assigned_to": ["Responsible for mitigating Action", "Responsible"],
    "follow_up_date": ["Follow-up Date", "Follow-up"],
}


def _norm(s):
    if s is None:
        return ""
    return " ".join(str(s).strip().split()).lower()


def read_file(file_obj, filename: str) -> dict:
    if filename.lower().endswith(".xlsx"):
        xls = pd.ExcelFile(file_obj)
        out = {}
        for sheet in xls.sheet_names:
            out[sheet] = xls.parse(sheet, header=None)
        return out
    if filename.lower().endswith(".csv"):
        return {"Master": pd.read_csv(file_obj, header=None)}
    raise ValueError("Only .xlsx and .csv are supported")


def _find_header_row(df):
    aliases_norm = {_norm(a) for aliases in MASTER_LOGSHEET_CANONICAL.values() for a in aliases}
    aliases_norm.update({_norm("S.N"), _norm("SN"), _norm("Hazard ID"), _norm("Hazard code/ID")})
    for i in range(min(6, len(df))):
        row = df.iloc[i]
        vals = {_norm(v) for v in row.tolist()}
        if vals & aliases_norm:
            return i
    return 0


def _is_multi_header(df, header_idx):
    if header_idx + 1 >= len(df):
        return False
    next_row = df.iloc[header_idx + 1]
    sub_markers = {_norm("severity"), _norm("probability"), _norm("risk index"), _norm("risk tolerability"), _norm("tolerability")}
    vals = {_norm(v) for v in next_row.tolist()}
    return bool(vals & sub_markers)


def _flatten_columns(df, header_idx, multi):
    header_row = df.iloc[header_idx]
    if multi:
        next_row = df.iloc[header_idx + 1]
        cols = []
        for c in df.columns:
            top = _norm(header_row[c])
            sub = _norm(next_row[c])
            if top and sub and top != sub:
                cols.append(f"{header_row[c]} {next_row[c]}".strip())
            else:
                cols.append(str(header_row[c]).strip() if pd.notna(header_row[c]) else (str(next_row[c]).strip() if pd.notna(next_row[c]) else f"col_{c}"))
        return cols, header_idx + 2
    cols = [str(v).strip() if pd.notna(v) else f"col_{c}" for c, v in header_row.items()]
    return cols, header_idx + 1


def auto_map_columns(headers):
    norm_headers = {_norm(h): h for h in headers}
    mapping = {}
    for canonical, aliases in MASTER_LOGSHEET_CANONICAL.items():
        for alias in aliases:
            if _norm(alias) in norm_headers:
                mapping[norm_headers[_norm(alias)]] = canonical
                break
    return mapping


def row_has_classification(mapped: dict) -> bool:
    return any(mapped.get(k) for k in (
        "classification_occurrence",
        "classification_hazard",
        "classification_deficiency",
        "classification_diversion",
    ))


def route_row(mapped: dict, sheet_name: str) -> list[str]:
    low = sheet_name.lower()
    if "occurrence" in low:
        return ["occurrences"]
    if "safety deficienc" in low:
        return ["safety_deficiencies"]
    if "hazard" in low:
        return ["hazards"]
    if "diversion" in low:
        return ["flight_diversions"]
    # fallback to checkbox routing for single master sheet
    tables = []
    if mapped.get("classification_occurrence"):
        tables.append("occurrences")
    if mapped.get("classification_hazard"):
        tables.append("hazards")
    if mapped.get("classification_deficiency"):
        tables.append("safety_deficiencies")
    if mapped.get("classification_diversion"):
        tables.append("flight_diversions")
    return tables


def parse_batch(file_obj, filename: str):
    sheets = read_file(file_obj, filename)
    all_mapping = {}
    unmapped_set = set()
    staged = []
    for sheet_name, raw in sheets.items():
        if raw.empty:
            continue
        header_idx = _find_header_row(raw)
        multi = _is_multi_header(raw, header_idx)
        cols, data_start = _flatten_columns(raw, header_idx, multi)
        df = raw.iloc[data_start:].copy()
        df.columns = cols
        df = df.dropna(how="all")
        mapping = auto_map_columns(list(df.columns))
        if not all_mapping:
            all_mapping = mapping
        for c in df.columns:
            if c not in mapping:
                unmapped_set.add(c)
        for idx, row in df.iterrows():
            mapped = {mapping[k]: v for k, v in row.items() if k in mapping and pd.notna(v)}
            # For multi-tab sheets, stage all rows that route somewhere
            dest = route_row(mapped, sheet_name)
            if not dest:
                # single master sheet: require classification
                if not row_has_classification(mapped):
                    continue
                dest = route_row(mapped, sheet_name)
                if not dest:
                    continue
            staged.append({
                "row_number": int(idx) + data_start + 1,
                "raw_data": {k: (None if pd.isna(v) else str(v)) for k, v in row.items()},
                "mapped_data": {k: (None if pd.isna(v) else str(v)) for k, v in mapped.items()},
                "destination_tables": dest,
            })
    return all_mapping, sorted(unmapped_set), staged