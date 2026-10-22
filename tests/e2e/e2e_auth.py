import requests, json, sys, os

API_KEY = 'AIzaSyCdCtUuyOcUIoCBEaiWGbhp6_XwZKHsicc'
FIREBASE_AUTH_URL = 'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=' + API_KEY
BASE_API = 'https://aviasafe-unified-platform.onrender.com'

users = {
    'TENANT_ADMIN': {'email': 'sal@aviasafesystems.com', 'password': os.environ.get('AVIASAFE_PW_AIRLINE', '')},
    'STATE_SMD': {'email': 'smd@caanepal.gov.np', 'password': os.environ.get('AVIASAFE_PW_CAAN', '')},
    'super_admin': {'email': 'admin@aviasafesystems.com', 'password': os.environ.get('AVIASAFE_PW_ADMIN', '')},
    'safety': {'email': 'salsafety@aviasafesystems.com', 'password': os.environ.get('AVIASAFE_PW_SAFETY', '')},
}

missing = [name for name, c in users.items() if not c['password']]
if missing:
    print(f'ERROR: missing env vars for: {", ".join(missing)} (AVIASAFE_PW_AIRLINE/CAAN/ADMIN/SAFETY)')
    sys.exit(1)

tokens = {}
for name, creds in users.items():
    r = requests.post(FIREBASE_AUTH_URL, json={
        'email': creds['email'],
        'password': creds['password'],
        'returnSecureToken': True
    }, timeout=15)
    if r.status_code == 200:
        data = r.json()
        tokens[name] = data['idToken']
        expiry = data.get('expiresIn', '?')
        print(f'{name}: token obtained (expires in {expiry}s)')
    else:
        print(f'{name}: FAILED - {r.status_code} {r.text[:200]}')

if 'TENANT_ADMIN' in tokens:
    h = {'Authorization': 'Bearer ' + tokens['TENANT_ADMIN']}
    endpoints = [
        ('GET', '/api/v1/hazards/stats'),
        ('GET', '/api/v1/cans/stats'),
        ('GET', '/api/v1/verification/verifications/stats'),
        ('GET', '/api/v1/flight-diversions/stats'),
        ('GET', '/api/v1/reporting/quarterly'),
        ('GET', '/api/v1/dashboard/overview'),
        ('GET', '/api/v1/reports/'),
    ]
    print('\n--- Testing with TENANT_ADMIN ---')
    for method, path in endpoints:
        fn = getattr(requests, method.lower())
        r = fn(BASE_API + path, headers=h, timeout=15)
        ok = r.status_code in [200, 201, 404]
        status = 'OK' if ok else 'FAIL(' + str(r.status_code) + ')'
        print('  ' + method + ' ' + path + ': ' + status)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                keys = list(data.keys())[:6]
                print('    keys: ' + str(keys))
            elif isinstance(data, list):
                print('    count: ' + str(len(data)))

# Save tokens for later use
with open('e2e_tokens.json', 'w') as f:
    json.dump(tokens, f)
print('\nTokens saved to e2e_tokens.json')
