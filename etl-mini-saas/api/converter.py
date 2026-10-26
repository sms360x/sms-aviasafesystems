"""Standalone workbook extraction and contract validation. No SMS dependencies."""
import csv
import io
import re
import zipfile
from datetime import date, datetime
from pathlib import Path

import pandas as pd

CONTRACTS = {
    'Hazard': ['S.N','Reported Date','Occurrence Date','Sources of Information','Description','Hazard ID','Taxonomy','Threat','Top Event','Consequence','Priority','Status','Concerned Department','Remarks'],
    'Occurrence': ['S.N','Reported Date','Occurrence Date','Sources of Information','Description','Occurrence','Status','Concerned Department','Remarks'],
    'Diversion': ['S.N','Occurrence Date','Flight Number','Flight Sector','Diverted To','Aircraft Registration','Reason of diversion','Description','Status','Remarks'],
}
ALIASES = {
    'S.N': ['sn','s n','sequence number'],
    'Description': ['report description','unsafe event reported projected','unsafe event ue reported projected'],
    'Reported Date': ['reported date to csd dd mm yy','reported date date of occ','reported date occurrence date','reported date date of occurrence'],
    'Occurrence Date': ['date of occurrence','occurance date of report dd mm yy','reported date date of occ','reported date occurrence date','reported date date of occurrence'],
    'Sources of Information': ['sources of infromation','hazard h sources of infromation','hazard sources of infromation'],
    'Hazard ID': ['hazard code id','hazard h hazard code id'],
    'Occurrence': ['occurrence code'],
    'Taxonomy': ['taxonomy type of area operation equipment','hazard h taxonomy type of area operation equipment'],
    'Priority': ['report prority level h m l','report priority level h m l'],
    'Status': ['status open closed','status open closed date completed','risk mitigation status date completed open closed'],
    'Concerned Department': ['concerned department personnel','responsible for mitigating action'],
    'Consequence': ['potential consequence reported projected'],
    'Flight Sector': ['flight sector from to'],
    'Remarks': ['csd remarks'],
}

def norm(value):
    return re.sub(r'[^a-z0-9]+', ' ', str(value).lower()).strip()

def text(value):
    if value is None or pd.isna(value):
        return ''
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat() if getattr(value, 'hour', 0) or getattr(value, 'minute', 0) or getattr(value, 'second', 0) else value.strftime('%Y-%m-%d')
    return str(value).strip()

def load_book(content):
    if len(content) > 20 * 1024 * 1024:
        raise ValueError('Workbook exceeds 20 MB.')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            if sum(i.file_size for i in z.infolist()) > 100 * 1024 * 1024:
                raise ValueError('Expanded workbook exceeds 100 MB.')
        # Only the header search region and ten-row sample are read per tab.
        return pd.read_excel(io.BytesIO(content), sheet_name=None, header=None, nrows=110, engine='openpyxl')
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('Cannot read this .xlsx workbook. Check that it is not encrypted or corrupted.') from exc

def detect(frame):
    scores = []
    for i in range(min(len(frame), 60)):
        cells = [norm(v) for v in frame.iloc[i] if text(v)]
        score = sum(any(k in c for k in ('date','description','status','hazard','sources','flight','remarks','severity','consequence','s n')) or c == 'sn' for c in cells)
        score += 4 * sum(c in ('sn', 's n', 'hazard id') for c in cells)
        scores.append(score)
    header = max(range(len(scores)), key=lambda i: scores[i]) if scores else 0
    depth = 1
    if header + 1 < len(frame):
        values = [text(v) for v in frame.iloc[header + 1]]
        # Data rows start with a serial/id/date; subheaders consist of label text.
        labels = sum(any(k in norm(v) for k in ('severity','probability','sources','hazard','taxonomy','corrective','follow up','date completed','occurrence','diversion')) for v in values if v)
        numeric = any(isinstance(v, (int, float, datetime, date)) and not pd.isna(v) for v in frame.iloc[header + 1])
        if labels >= 2 and not numeric:
            depth = 2
    return header, depth

def flatten(frame, header, depth):
    if header < 0 or header > 60 or depth not in (1, 2) or (len(frame) and header >= len(frame)):
        raise ValueError('Header row must be within the first 61 rows; depth must be 1 or 2.')
    headers = []
    parent = ''
    seen = {}
    for col in range(frame.shape[1]):
        top = text(frame.iloc[header, col]) if len(frame) else ''
        sub = text(frame.iloc[header + 1, col]) if depth == 2 and header + 1 < len(frame) else ''
        if top:
            parent = top
        # Carry merged parent labels only for a populated subheader.
        parts = [top or (parent if sub else ''), sub]
        label = ' / '.join(dict.fromkeys(p for p in parts if p)) or f'Column {col + 1}'
        seen[label] = seen.get(label, 0) + 1
        headers.append(label if seen[label] == 1 else f'{label} [{seen[label]}]')
    return headers

def suggest(headers, entity):
    mapping = {}
    for target in CONTRACTS.get(entity, []):
        candidates = [norm(target)] + [norm(v) for v in ALIASES.get(target, [])]
        for i, label in enumerate(headers):
            if norm(label) in candidates or norm(label.split(' / ')[-1]) in candidates:
                mapping[target] = i
                break
    return mapping

def csv_text(headers, rows):
    out = io.StringIO(newline='')
    writer = csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator='\r\n')
    writer.writerow(headers)
    writer.writerows(rows)
    return out.getvalue()

def filename(sheet):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', sheet).rstrip('. ') + '.csv'

def inspect_book(content):
    sheets = []
    for name, frame in load_book(content).items():
        header, depth = detect(frame)
        columns = flatten(frame, header, depth)
        entity = next((e for e, keyword in [('Diversion','diversion'),('Occurrence','occurrence'),('Hazard','hazard')] if keyword in name.lower()), 'Original')
        sheets.append({'name': name, 'header_row': header, 'header_depth': depth, 'columns': columns,
                       'entity': entity, 'mapping': suggest(columns, entity),
                       'grid': [[text(v) for v in row] for row in frame.itertuples(index=False, name=None)]})
    return {'contracts': CONTRACTS, 'sheets': sheets, 'sample_limit': 10}

def validate_row(row):
    errors, warnings = [], []
    if not row.get('Description', '').strip():
        errors.append('Description is required')
    for field in ('Reported Date', 'Occurrence Date'):
        value = row.get(field, '')
        if not value:
            continue  # Only Description and Status are required by this contract.
        fmt = '%Y-%m-%d' if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) else '%d/%m/%Y' if re.fullmatch(r'\d{2}/\d{2}/\d{4}', value) else None
        try:
            if not fmt:
                raise ValueError()
            row[field] = datetime.strptime(value, fmt).strftime('%Y-%m-%d')
        except ValueError:
            errors.append(f'{field}: expected a real date in YYYY-MM-DD or DD/MM/YYYY')
    if row.get('Status') not in ('Open', 'Closed'):
        errors.append('Status must be Open or Closed')
    for field, default, allowed in [('Priority', 'M', ('H','M','L')), ('Taxonomy', 'Organizational', ('Organizational','Technical','Human','Environmental'))]:
        if field in row:
            if not row[field]:
                row[field] = default
                warnings.append(f'{field} defaulted to {default}')
            elif row[field] not in allowed:
                errors.append(f'{field} must be one of {", ".join(allowed)}')
    return errors, warnings

def convert(content, configs, mode='split'):
    if mode not in ('split', 'mapped'):
        raise ValueError('Mode must be split or mapped.')
    book = load_book(content)
    if len(configs) != len(book) or {c['name'] for c in configs} != set(book):
        raise ValueError('Provide exactly one configuration for every workbook tab.')
    files, report = [], []
    used_names = set()
    for config in configs:
        name = config['name']
        frame = book[name]
        header, depth = int(config['header_row']), int(config['header_depth'])
        headers = flatten(frame, header, depth)
        entity = config.get('entity', 'Original') if mode == 'mapped' else 'Original'
        if entity != 'Original' and entity not in CONTRACTS:
            raise ValueError('Unknown entity.')
        mapping = config.get('mapping', {})
        if entity != 'Original':
            for target, index in mapping.items():
                if target not in CONTRACTS[entity] or not isinstance(index, int) or index < 0 or index >= len(headers):
                    raise ValueError('Invalid column mapping.')
        rows, rejected = [], 0
        # First ten physical data rows, not the first ten valid rows.
        data = frame.iloc[header + depth:header + depth + 10]
        for excel_index, values in data.iterrows():
            values = [text(v) for v in values]
            source_row = int(excel_index) + 1
            if entity == 'Original':
                rows.append(values)
                report.append([name, source_row, 'unmapped', 'Original columns preserved; validation deferred'])
                continue
            row = {field: values[mapping[field]] if field in mapping else str(config.get('constants', {}).get(field, '')).strip() for field in CONTRACTS[entity]}
            errors, warnings = validate_row(row)
            if errors:
                rejected += 1
            else:
                rows.append([row[field] for field in CONTRACTS[entity]])
            report.append([name, source_row, 'rejected' if errors else 'valid', '; '.join(errors + warnings)])
        output_name = filename(name)
        if output_name.casefold() in used_names or output_name.casefold() == 'validation_report.csv':
            raise ValueError('Tab filenames collide after sanitization; rename conflicting workbook tabs.')
        used_names.add(output_name.casefold())
        files.append({'name': output_name, 'csv': csv_text(headers if entity == 'Original' else CONTRACTS[entity], rows), 'rows': len(rows), 'rejected': rejected})
    files.append({'name': 'validation_report.csv', 'csv': csv_text(['Sheet','Excel Row','Result','Details'], report), 'rows': len(report), 'rejected': sum(r[2] == 'rejected' for r in report)})
    return {'files': files, 'mode': mode}

