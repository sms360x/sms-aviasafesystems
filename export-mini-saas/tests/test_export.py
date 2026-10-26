import asyncio
import base64
import csv
import io
import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from app.main import Settings, app, make_csv, read_rows
from app.registers import REGISTERS

class ExportTests(unittest.TestCase):
    def test_auth_and_configuration_fail_closed(self):
        client=TestClient(app)
        with patch.dict(os.environ, {'EXPORT_PASSWORD':'secret','EXPORT_USERNAME':'export'}, clear=True):
            self.assertEqual(client.get('/api/registers').status_code,401)
            self.assertEqual(client.get('/api/registers',auth=('export','secret')).status_code,200)
            self.assertEqual(client.get('/api/preview',auth=('export','secret')).status_code,503)
            self.assertEqual(client.get('/api/preview?register=users',auth=('export','secret')).status_code,400)
            self.assertEqual(client.get('/api/preview?days=7',auth=('export','secret')).status_code,400)

    def test_pagination_tenant_filter_allowlist_and_get_only(self):
        requests=[]
        def handler(request):
            requests.append(request)
            offset=int(request.url.params['offset'])
            # Server caps pages below requested 1000; exporter must still fetch all.
            batch=[{'id':str(i),'hazard_id':f'H{i}'} for i in range(offset,min(offset+2,5))]
            return httpx.Response(200,json=batch)
        factory=httpx.AsyncClient
        with patch('app.main.httpx.AsyncClient',side_effect=lambda **kwargs:factory(transport=httpx.MockTransport(handler),**kwargs)):
            rows=asyncio.run(read_rows(REGISTERS['hazard'],Settings('https://test.supabase.co','private','2ec7c30d-bbdf-5ec1-b897-ea6a28f6c6fc'),30))
        self.assertEqual(len(rows),5)
        self.assertEqual([r.url.params['offset'] for r in requests],['0','2','4','5'])
        for request in requests:
            self.assertEqual(request.method,'GET')
            self.assertEqual(request.url.params['tenant_id'],'eq.2ec7c30d-bbdf-5ec1-b897-ea6a28f6c6fc')
            self.assertTrue(request.url.params['created_at'].startswith('gte.'))
            self.assertNotEqual(request.url.params['select'],'*')

    def test_preview_limit_csv_headers_nulls_unicode_and_formula_safety(self):
        spec=REGISTERS['hazard']
        output=make_csv(spec,[{'hazard_id':'H1','description':'=HYPERLINK("bad")','remarks':'नेपाल, "review"\nnext'}])
        rows=list(csv.reader(io.StringIO(output.lstrip('\ufeff'))))
        self.assertEqual(rows[0],[label for _,label in spec['fields']])
        self.assertEqual(rows[1][4], '\'=HYPERLINK("bad")')
        self.assertIn('नेपाल',rows[1][-1])
        self.assertEqual(rows[1][1],'')

    def test_upstream_error_is_sanitized(self):
        def handler(request):return httpx.Response(403,text='private database error')
        factory=httpx.AsyncClient
        with patch('app.main.httpx.AsyncClient',side_effect=lambda **kwargs:factory(transport=httpx.MockTransport(handler),**kwargs)):
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as result:
                asyncio.run(read_rows(REGISTERS['occurrence'],Settings('https://test.supabase.co','private','tenant'),0,True))
        self.assertEqual(result.exception.status_code,502)
        self.assertNotIn('private',result.exception.detail)

if __name__=='__main__':unittest.main()
