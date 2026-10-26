import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from .converter import convert, inspect_book

app = FastAPI(title='Logsheet Studio', docs_url='/api/docs')

async def workbook(file):
    if not (file.filename or '').lower().endswith('.xlsx'):
        raise HTTPException(400, 'Choose an .xlsx file.')
    content = await file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, 'Workbook exceeds 20 MB.')
    return content

@app.post('/api/inspect')
async def inspect(file: UploadFile = File(...)):
    content = await workbook(file)
    from starlette.concurrency import run_in_threadpool
    try:
        return await run_in_threadpool(inspect_book, content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

@app.post('/api/convert')
async def conversion(file: UploadFile = File(...), configuration: str = Form(...), mode: str = Form('split')):
    content = await workbook(file)
    from starlette.concurrency import run_in_threadpool
    try:
        configs = json.loads(configuration)
        return await run_in_threadpool(convert, content, configs, mode)
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise HTTPException(400, f'Invalid workbook configuration: {exc}') from exc

dist = Path(__file__).resolve().parents[1] / 'web' / 'dist'
if dist.is_dir():
    app.mount('/', StaticFiles(directory=dist, html=True), name='web')
