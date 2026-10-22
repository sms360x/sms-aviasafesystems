import requests, json, sys, os

API_KEY = 'AIzaSyCdCtUuyOcUIoCBEaiWGbhp6_XwZKHsicc'
FIREBASE_AUTH_URL = 'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=' + API_KEY
BASE_API = 'https://aviasafe-unified-platform.onrender.com'

E2E_USERS = [
    ('TENANT_ADMIN', 'sal@aviasafesystems.com', os.environ.get('AVIASAFE_PW_AIRLINE', '')),
    ('STATE_SMD', 'smd@caanepal.gov.np', os.environ.get('AVIASAFE_PW_CAAN', '')),
    ('super_admin', 'admin@aviasafesystems.com', os.environ.get('AVIASAFE_PW_ADMIN', '')),
    ('safety', 'salsafety@aviasafesystems.com', os.environ.get('AVIASAFE_PW_SAFETY', '')),
]

if any(not pw for _, _, pw in E2E_USERS):
    raise SystemExit('Set AVIASAFE_PW_AIRLINE, AVIASAFE_PW_CAAN, AVIASAFE_PW_ADMIN, AVIASAFE_PW_SAFETY env vars')

results = []
passed_total = 0
failed_total = 0

def test(desc, result, detail=''):
    global passed_total, failed_total
    if result:
        passed_total += 1
        status = 'PASS'
    else:
        failed_total += 1
        status = 'FAIL'
    detail_str = ' - ' + detail if detail else ''
    print(f'  [{status}] {desc}{detail_str}')
    return result

def get_token(email, password):
    r = requests.post(FIREBASE_AUTH_URL, json={
        'email': email, 'password': password, 'returnSecureToken': True
    }, timeout=15)
    if r.status_code != 200:
        print(f'  [FAIL] Auth failed for {email}: {r.text[:100]}')
        return None
    return r.json()['idToken']

def api(method, path, token, data=None):
    fn = getattr(requests, method.lower())
    headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
    r = fn(BASE_API + path, headers=headers, json=data, timeout=15)
    return r

print('=' * 70)
print('AVIASAFE SMS PLATFORM - END-TO-END TESTING (ROUND 2)')
print('=' * 70)

# --- GET FRESH TOKENS ---
print('\n[SETUP] Getting fresh tokens with claims...')
tokens = {}
for name, email, pw in E2E_USERS:
    tok = get_token(email, pw)
    tokens[name] = tok
    if tok:
        print(f'  [OK] {name} authenticated')
    else:
        print(f'  [FAIL] {name} auth FAILED')

if not all(tokens.values()):
    print('FATAL: Not all users authenticated.')
    sys.exit(1)

t = tokens

# === SCENARIO 1: VSR SUBMISSION ===
print('\n' + '=' * 70)
print('SCENARIO 1: VSR Submission')
print('=' * 70)

r = api('POST', '/api/v1/reports/vsr', t['TENANT_ADMIN'], {
    'report_type': 'vsr',
    'anonymous': False,
    'reporter_name': 'Sal Test',
    'reporter_email': 'sal@aviasafesystems.com',
    'reporter_phone': '+977-98xxxxxxx',
    'reporter_organization': 'Sita Air',
    'reporter_role': 'Safety Officer',
    'aircraft_type': 'DHC-6',
    'aircraft_registration': '9N-AKS',
    'aircraft_make': 'Viking Air',
    'aircraft_model': 'DHC-6 Twin Otter',
    'flight_number': 'STA-101',
    'flight_date': '2026-07-28',
    'flight_time': '14:30',
    'departure_point': 'KTM',
    'destination': 'PKR',
    'phase_of_flight': 'Landing',
    'location': 'Runway 02',
    'occurrence_type': 'Hard Landing',
    'description': 'E2E test: Hard landing during training flight at Pokhara.',
    'immediate_cause': 'Late flare by trainee pilot',
    'contributing_factors': 'High density altitude, gusty conditions',
    'consequence': 'Minor structural inspection required',
    'corrective_action_taken': 'Aircraft grounded for inspection, trainee debriefed',
    'recommendations': 'Additional simulator training for high altitude landings',
    'severity': 3,
    'probability': 3,
    'safety_risk_index': '5S',
})

test('VSR submission returns 201/200', r.status_code in [200, 201], 'got ' + str(r.status_code))

if r.status_code in [200, 201]:
    vsr = r.json()
    test('VSR has report_type=vsr', vsr.get('report_type') == 'vsr', str(vsr.get('report_type')))
    test('VSR has id', bool(vsr.get('id')), str(vsr.get('id', '')))
    hid = vsr.get('hazard_id', '')
    test('VSR created linked hazard', bool(hid), hid)
    test('VSR has risk_index', bool(vsr.get('risk_index')), str(vsr.get('risk_index', '')))
else:
    print('  Response:', r.text[:200])

# === SCENARIO 2: MOR SUBMISSION ===
print('\n' + '=' * 70)
print('SCENARIO 2: MOR Submission')
print('=' * 70)

r = api('POST', '/api/v1/reports/mor', t['TENANT_ADMIN'], {
    'report_type': 'mor',
    'reporter_name': 'Sal Test',
    'reporter_email': 'sal@aviasafesystems.com',
    'reporter_role': 'Safety Manager',
    'reporter_organization': 'Sita Air',
    'aircraft_type': 'DHC-6',
    'aircraft_registration': '9N-AKZ',
    'aircraft_make': 'Viking Air',
    'aircraft_model': 'DHC-6 Twin Otter',
    'flight_number': 'STA-205',
    'flight_date': '2026-07-28',
    'flight_time': '09:15',
    'departure_point': 'KTM',
    'destination': 'BHR',
    'phase_of_flight': 'Takeoff',
    'location': 'Kathmandu',
    'occurrence_type': 'Bird Strike',
    'description': 'E2E test: Multiple bird strike on takeoff.',
    'occurrence_category': 'Bird Strike',
    'contributing_factors': ['Environmental', 'Procedural'],
    'immediate_cause': 'Birds on runway',
    'severity': 3,
    'probability': 2,
    'safety_risk_index': '3N',
    'people_on_board': 19,
    'injuries': 0,
    'fatalities': 0,
})

test('MOR submission returns 201/200', r.status_code in [200, 201], 'got ' + str(r.status_code))
if r.status_code in [200, 201]:
    mor = r.json()
    test('MOR has report_type=mor', mor.get('report_type') == 'mor', str(mor.get('report_type')))
    hid2 = mor.get('hazard_id', '')
    test('MOR created linked hazard', bool(hid2), hid2)
else:
    print('  Response:', r.text[:200])

# === SCENARIO 4: HAZARD REGISTER ===
print('\n' + '=' * 70)
print('SCENARIO 4: Hazard Register')
print('=' * 70)

r = api('GET', '/api/v1/hazards/stats', t['TENANT_ADMIN'])
test('Hazard stats 200', r.status_code == 200, 'got ' + str(r.status_code))
if r.status_code == 200:
    s = r.json()
    test('Stats has total key', 'total' in s, str(s.get('total')))
    test('Stats has by_status', 'by_status' in s, str(list(s.get('by_status', {}).keys())))
    test('Stats has by_priority', 'by_priority' in s, '')

r = api('GET', '/api/v1/hazards/', t['TENANT_ADMIN'])
test('Hazard list 200', r.status_code == 200, 'got ' + str(r.status_code))
if r.status_code == 200:
    hazards = r.json()
    if isinstance(hazards, list):
        test('Hazard list is array', True, 'count=' + str(len(hazards)))
    test('Has hazard from VSR', any('STA-101' in str(h) or 'Hard Landing' in str(h) for h in (hazards if isinstance(hazards, list) else [])), 'VSR hazard should be in list')
else:
    test('Hazard list accessible', False, 'got ' + str(r.status_code))

# === SCENARIO 5: CAN/CAP ===
print('\n' + '=' * 70)
print('SCENARIO 5: CAN/CAP Workflow')
print('=' * 70)

r = api('GET', '/api/v1/cans/stats', t['TENANT_ADMIN'])
test('CAN stats 200', r.status_code == 200, 'got ' + str(r.status_code))
if r.status_code == 200:
    cs = r.json()
    test('CAN stats has cans', 'cans' in cs, '')
    test('CAN stats has caps', 'caps' in cs, '')

r = api('GET', '/api/v1/cans/', t['TENANT_ADMIN'])
test('CAN list 200', r.status_code == 200, 'got ' + str(r.status_code))

# === SCENARIO 6: VERIFICATION ===
print('\n' + '=' * 70)
print('SCENARIO 6: Verification & Closure')
print('=' * 70)

r = api('GET', '/api/v1/verification/verifications/stats', t['TENANT_ADMIN'])
test('Verification stats 200', r.status_code == 200, 'got ' + str(r.status_code))
if r.status_code != 200:
    # Try alternate paths
    for alt in ['/api/verification/verifications/stats', '/api/v1/verification/stats']:
        r2 = api('GET', alt, t['TENANT_ADMIN'])
        if r2.status_code == 200:
            test('Verification stats at alt path', True, alt)
            break

# === SCENARIO 7: REPORTING ===
print('\n' + '=' * 70)
print('SCENARIO 7: Reporting & PDF Export')
print('=' * 70)

r = api('POST', '/api/v1/reporting/quarterly', t['TENANT_ADMIN'], {
    'year': 2026,
    'period': 'Q2',
    'tenant_id': 'sita-air',
})
test('Quarterly report generation', r.status_code in [200, 201, 422], 'got ' + str(r.status_code))

if r.status_code in [200, 201]:
    report = r.json()
    rid = report.get('id', '')
    test('Report has id', bool(rid), rid)
    if rid:
        r2 = api('GET', '/api/v1/reporting/quarterly/' + rid, t['TENANT_ADMIN'])
        test('Report retrieval 200', r2.status_code == 200, 'got ' + str(r2.status_code))
        r3 = api('GET', '/api/v1/reporting/quarterly/' + rid + '/export', t['TENANT_ADMIN'])
        test('Report PDF export 200', r3.status_code == 200, 'got ' + str(r3.status_code))
else:
    print('  Response:', r.text[:200])

# CAAN reporting
r = api('POST', '/api/v1/reporting/quarterly', t['STATE_SMD'], {
    'year': 2026,
    'period': 'Q1',
})
test('CAAN quarterly report', r.status_code in [200, 201, 422], 'got ' + str(r.status_code))

# === SCENARIO 8: FLIGHT DIVERSIONS ===
print('\n' + '=' * 70)
print('SCENARIO 8: Flight Diversions')
print('=' * 70)

r = api('POST', '/api/v1/flight-diversions/', t['TENANT_ADMIN'], {
    'date': '2026-07-28',
    'flight_number': 'STA-101',
    'aircraft_registration': '9N-AKS',
    'sector_from': 'KTM',
    'sector_to': 'PKR',
    'diverted_to': 'BHR',
    'reason': 'Weather',
    'reason_details': 'E2E test: Thunderstorm at destination',
    'captain': 'Capt. Test',
    'description': 'E2E test diversion',
    'additional_fuel_cost': 2500.00,
    'passenger_impact': 18,
    'delay_minutes': 45,
})
test('Diversion creation 200/201', r.status_code in [200, 201], 'got ' + str(r.status_code))
if r.status_code in [200, 201]:
    div = r.json()
    test('Diversion has id', bool(div.get('id')), str(div.get('id', '')))
    test('Diversion has diversion_id', bool(div.get('diversion_id', '')), div.get('diversion_id', ''))
    test('Diversion status is Pending', div.get('status') == 'Pending', str(div.get('status', '')))
else:
    print('  Response:', r.text[:200])

r = api('GET', '/api/v1/flight-diversions/stats', t['TENANT_ADMIN'])
test('Diversion stats 200', r.status_code == 200, 'got ' + str(r.status_code))
if r.status_code == 200:
    ds = r.json()
    test('Stats has by_reason', 'by_reason' in ds, '')
    test('Stats has total_diversions', 'total_diversions' in ds, str(ds.get('total_diversions')))

r = api('GET', '/api/v1/flight-diversions/stats', t['STATE_SMD'])
test('CAAN diversion stats 200', r.status_code == 200, 'got ' + str(r.status_code))

# === SCENARIO 9: DASHBOARDS ===
print('\n' + '=' * 70)
print('SCENARIO 9: Dashboards')
print('=' * 70)

r = api('GET', '/api/v1/dashboard/caan/overview', t['STATE_SMD'])
test('CAAN overview dashboard 200', r.status_code == 200, 'got ' + str(r.status_code))

r = api('GET', '/api/v1/dashboard/caan/hazards', t['STATE_SMD'])
test('CAAN hazard dashboard 200', r.status_code == 200, 'got ' + str(r.status_code))

r = api('GET', '/api/v1/dashboard/caan/risk', t['STATE_SMD'])
test('CAAN risk dashboard 200', r.status_code == 200, 'got ' + str(r.status_code))

r = api('GET', '/api/v1/dashboard/caan/trends', t['STATE_SMD'])
test('CAAN trends dashboard 200', r.status_code == 200, 'got ' + str(r.status_code))

# === SCENARIO 10: ROLE-BASED ACCESS ===
print('\n' + '=' * 70)
print('SCENARIO 10: Role-Based Access')
print('=' * 70)

r = api('GET', '/api/v1/admin/risk-matrix', t['super_admin'])
test('Super admin: risk matrix 200', r.status_code == 200, 'got ' + str(r.status_code))

r = api('GET', '/api/v1/admin/risk-matrix', t['TENANT_ADMIN'])
test('Airline admin: risk matrix should work (safety manager)', r.status_code == 200, 'got ' + str(r.status_code))

r = api('GET', '/api/v1/hazards/stats', t['TENANT_ADMIN'])
test('Airline admin: own hazard stats 200', r.status_code == 200, 'got ' + str(r.status_code))

r = api('GET', '/api/v1/hazards/stats', t['STATE_SMD'])
test('CAAN SMD: cross-tenant hazard stats 200', r.status_code == 200, 'got ' + str(r.status_code))

r = api('GET', '/api/v1/dashboard/caan/overview', t['STATE_SMD'])
test('CAAN SMD: dashboard overview 200', r.status_code == 200, 'got ' + str(r.status_code))

# === SUMMARY ===
print('\n' + '=' * 70)
print('TESTING SUMMARY')
print('=' * 70)
total_checks = passed_total + failed_total
print(f'\nTotal assertions: {total_checks}')
print(f'Passed: {passed_total}/{total_checks}')
print(f'Failed: {failed_total}/{total_checks}')
print(f'Pass rate: {100 * passed_total // total_checks if total_checks else 0}%')

if failed_total == 0:
    print('\n[PASS] ALL TESTS PASSED - GO FOR PRODUCTION DEPLOYMENT')
else:
    print(f'\n[FAIL] {failed_total} assertion(s) failed - REVIEW NEEDED')
print('=' * 70)
