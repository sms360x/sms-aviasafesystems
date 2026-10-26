import csv
import io
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from .registers import REGISTERS

@dataclass
class Settings:
    url: str
    key: str
    tenant: str

    @classmethod
    def load(cls):
        url = os.getenv('SUPABASE_URL', '').rstrip('/')
        key = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
        tenant = os.getenv('EXPORT_TENANT_ID', '')
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.query or parsed.fragment or parsed.path not in ('', '/') or not key:
            raise HTTPException(503, 'Configure a valid HTTPS SUPABASE_URL and server-side SUPABASE_SERVICE_ROLE_KEY.')
        try:
            tenant = str(UUID(tenant))
        except ValueError:
            raise HTTPException(503, 'Configure EXPORT_TENANT_ID as the airline tenant UUID.')
        return cls(url, key, tenant)

security = HTTPBasic(auto_error=False)
def authorize(credentials: HTTPBasicCredentials | None = Depends(security)):
    password = os.getenv('EXPORT_PASSWORD', '')
    username = os.getenv('EXPORT_USERNAME', 'export')
    if not password:
        raise HTTPException(503, 'Set EXPORT_PASSWORD before using this exporter.')
    valid = credentials is not None and secrets.compare_digest(credentials.username.encode(), username.encode()) and secrets.compare_digest(credentials.password.encode(), password.encode())
    if not valid:
        raise HTTPException(401, 'Sign in to export airline data.', headers={'WWW-Authenticate':'Basic'})

app = FastAPI(title='Airline Register Export', docs_url=None, redoc_url=None)

def specification(register, days):
    if register not in REGISTERS or days not in (0,30,60,90):
        raise HTTPException(400, 'Choose a supported register and date range.')
    return REGISTERS[register]

async def read_rows(spec, settings, days, preview=False):
    params = {'select': ','.join(dict.fromkeys(['id']+[f for f,_ in spec['fields']])),
              'tenant_id': 'eq.' + settings.tenant, 'order': spec['date'] + '.asc.nullslast,id.asc'}
    if days:
        params[spec['date']] = 'gte.' + (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    headers = {'apikey':settings.key, 'Authorization':'Bearer '+settings.key, 'Accept':'application/json'}
    rows, offset = [], 0
    # GET only: no RPC or arbitrary table/field input. Pagination respects server page caps.
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        while True:
            count = 10 if preview else 1000
            query = {**params, 'offset':str(offset), 'limit':str(count)}
            try:
                response = await client.get(f'{settings.url}/rest/v1/{spec["table"]}', params=query, headers=headers)
                response.raise_for_status()
                batch = response.json()
                if not isinstance(batch, list) or any(not isinstance(row, dict) for row in batch):
                    raise ValueError('Unexpected register response')
                if any(row.get('id') is None for row in batch):
                    raise ValueError('Register response has no stable row IDs')
            except (httpx.HTTPError, ValueError) as exc:
                # Do not send credentials or upstream response bodies to the browser.
                raise HTTPException(502, 'Unable to read this register. Check database connectivity, permissions, and deployed field names.') from exc
            if not batch:
                return rows
            rows.extend(batch)
            if preview:
                return rows[:10]
            offset += len(batch)
            if len(rows) > 100000:
                raise HTTPException(413, 'Export exceeds 100,000 rows. Choose a shorter date range.')

def csv_value(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    result = str(value)
    # Register exports are opened in spreadsheet apps; quote alone does not stop formulas.
    return "'"+result if result.lstrip().startswith(('=','+','-','@','\t','\r')) else result

def make_csv(spec, rows):
    out = io.StringIO(newline='')
    writer = csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator='\r\n')
    writer.writerow([label for _,label in spec['fields']])
    writer.writerows([[csv_value(row.get(field)) for field,_ in spec['fields']] for row in rows])
    return '\ufeff'+out.getvalue()

@app.get('/api/registers', dependencies=[Depends(authorize)])
def registers():
    return [{'id':key,'label':spec['label'],'date_field':spec['date']} for key,spec in REGISTERS.items()]

@app.get('/api/preview', dependencies=[Depends(authorize)])
async def preview(register: str = Query('hazard'), days: int = Query(0)):
    spec = specification(register, days)
    rows = await read_rows(spec, Settings.load(), days, preview=True)
    return {'headers':[label for _,label in spec['fields']], 'rows':[[row.get(field) for field,_ in spec['fields']] for row in rows], 'date_field':spec['date']}

@app.get('/api/export', dependencies=[Depends(authorize)])
async def export(register: str = Query('hazard'), days: int = Query(0)):
    spec = specification(register, days)
    rows = await read_rows(spec, Settings.load(), days)
    filename = f'{register}_{"all-time" if not days else str(days)+"-days"}_{datetime.now(timezone.utc):%Y-%m-%d}.csv'
    return Response(make_csv(spec, rows), media_type='text/csv; charset=utf-8', headers={'Content-Disposition':f'attachment; filename="{filename}"','Cache-Control':'no-store'})

@app.middleware('http')
async def no_cache(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

app.mount('/', StaticFiles(directory=Path(__file__).resolve().parents[1]/'static', html=True), name='web')
