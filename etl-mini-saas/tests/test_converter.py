import csv
import io
import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient
from api.converter import CONTRACTS, convert, inspect_book, validate_row
from api.main import app


def workbook(sheets):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        for name, rows in sheets.items():
            pd.DataFrame(rows).to_excel(writer, sheet_name=name, header=False, index=False)
    return out.getvalue()

class ConverterTests(unittest.TestCase):
    def test_split_preserves_all_tabs_limits_before_validation_and_has_no_zip(self):
        content = workbook({'Hazard':[['Title'],['SN','Description','Status']]+[[i,f'Row {i}','Open'] for i in range(1,14)],
                            'Risk':[['Hazard ID','Severity','Probability']]})
        inspected = inspect_book(content)
        result = convert(content, inspected['sheets'])
        self.assertEqual([f['name'] for f in result['files']], ['Hazard.csv','Risk.csv','validation_report.csv'])
        self.assertEqual(result['files'][0]['rows'], 10)
        self.assertEqual(result['files'][1]['rows'], 0)
        rows = list(csv.reader(io.StringIO(result['files'][0]['csv'])))
        self.assertEqual(rows[-1][0], '10')

    def test_mapped_contract_validation_and_report_source_rows(self):
        content = workbook({'Hazard':[['SN','Description','Status','Reported Date','Priority'],
                            [1,'Valid','Open',datetime(2026,4,2),''],
                            [2,'','Open','02/04/2026','H'],
                            [3,'Bad date','Closed','31/02/2026','M'],
                            [4,'Bad status','Pending','2026-04-02','M']]})
        config = inspect_book(content)['sheets']
        config[0].update(header_row=0, header_depth=1, entity='Hazard', mapping={'S.N':0,'Description':1,'Status':2,'Reported Date':3,'Priority':4})
        result = convert(content, config, 'mapped')
        rows = list(csv.reader(io.StringIO(result['files'][0]['csv'])))
        self.assertEqual(rows[0], CONTRACTS['Hazard'])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][1], '2026-04-02')
        self.assertEqual(rows[1][6], 'Organizational')
        self.assertEqual(rows[1][10], 'M')
        self.assertEqual(result['files'][0]['rejected'], 3)
        report = list(csv.reader(io.StringIO(result['files'][-1]['csv'])))
        self.assertIn('Description is required', report[2][3])
        self.assertEqual(report[2][1], '3')

    def test_strict_dates_enums_and_constants(self):
        for value in ['2026-2-01','01/02/26','2026-02-30','44900']:
            errors,_ = validate_row({'Description':'x','Status':'Open','Occurrence Date':value})
            self.assertTrue(errors, value)
        row={'Description':'x','Status':'Closed','Occurrence Date':'26/10/2026','Taxonomy':'Unknown'}
        self.assertTrue(validate_row(row)[0])
        self.assertEqual(row['Occurrence Date'],'2026-10-26')

    def test_two_headers_flattened_and_duplicate_columns_kept(self):
        content=workbook({'Risk':[['Hazard ID','Existing Risk',None,'Resultant Risk',None],
                                 [None,'Severity','Probability','Severity','Probability'],
                                 ['H1',3,4,2,2]]})
        config=inspect_book(content)['sheets']
        self.assertEqual(config[0]['header_depth'],2)
        result=convert(content,config)
        headers=next(csv.reader(io.StringIO(result['files'][0]['csv'])))
        self.assertEqual(headers,['Hazard ID','Existing Risk / Severity','Existing Risk / Probability','Resultant Risk / Severity','Resultant Risk / Probability'])

    def test_http_upload_convert_and_invalid_files(self):
        client=TestClient(app)
        content=workbook({'Occurrence':[['S.N','Description','Status'],[1,'Example','Open']]})
        inspected=client.post('/api/inspect',files={'file':('sample.xlsx',content)} )
        self.assertEqual(inspected.status_code,200)
        import json
        response=client.post('/api/convert',files={'file':('sample.xlsx',content)},data={'configuration':json.dumps(inspected.json()['sheets']),'mode':'split'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['files'][0]['name'],'Occurrence.csv')
        self.assertEqual(client.post('/api/inspect',files={'file':('bad.xlsx',b'broken')}).status_code,400)
        self.assertEqual(client.post('/api/inspect',files={'file':('bad.csv',b'abc')}).status_code,400)

    def test_actual_sample_files_have_correct_row_limits(self):
        folder=Path(__file__).resolve().parents[1]/'sample-output'
        for path in folder.glob('*.csv'):
            if path.name=='validation_report.csv':continue
            rows=list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig'))))
            self.assertLessEqual(len(rows)-1,10)
            self.assertTrue(rows[0])

if __name__ == '__main__':
    unittest.main()
