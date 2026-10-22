import requests, json, os

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

def get_token(email, password):
    r = requests.post(FIREBASE_AUTH_URL, json={
        'email': email, 'password': password, 'returnSecureToken': True
    }, timeout=15)
    if r.status_code != 200:
        print(f'Auth failed for {email}: {r.text[:200]}')
        return None
    return r.json()['idToken']

# Get tokens
tokens = {}
for name, email, pw in E2E_USERS:
    tok = get_token(email, pw)
    tokens[name] = tok
    if tok:
        print(f'{name}: token OK')
    else:
        print(f'{name}: NO TOKEN')

def check_endpoint(method, path, token_name, desc):
    tok = tokens.get(token_name)
    if not tok:
        print(f'  [SKIP] {desc} ({token_name} unavailable)')
        return
    fn = getattr(requests, method.lower())
    headers = {'Authorization': 'Bearer ' + tok}
    r = fn(BASE_API + path, headers=headers, timeout=15)
    print(f'  [{r.status_code}] {desc}')
    if r.status_code not in [200, 201, 204]:
        try:
            data = r.json()
            print(f'    Error: {data.get("error", data.get("detail", "unknown"))[:100]}')
        except:
            print(f'    Body: {r.text[:150]}')

print('\n=== TOKEN DECODE (via Auth REST API) ===')
# See if we can get user info from Firebase
for name, email, pw in E2E_USERS:
    r = requests.post(FIREBASE_AUTH_URL, json={
        'email': email, 'password': pw, 'returnSecureToken': True
    }, timeout=15)
    if r.status_code == 200:
        data = r.json()
        # Decode the ID token (it's a JWT, middle part is payload)
        parts = data['idToken'].split('.')
        if len(parts) == 3:
            import base64, json
            # Pad for base64 decoding
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            try:
                decoded = json.loads(base64.b64decode(payload))
                print(f'\n{name} ({email}):')
                print(f'  uid: {decoded.get("user_id", "?")}')
                print(f'  email: {decoded.get("email", "?")}')
                print(f'  firebase claims: {json.dumps(decoded.get("firebase", {}), indent=4)}')
            except Exception as e:
                print(f'  Decode error: {e}')
    else:
        print(f'{email}: auth failed')

print('\n=== ENDPOINT DIAGNOSIS ===')
# Test basic accessible endpoints
check_endpoint('GET', '/api/v1/hazards/stats', 'TENANT_ADMIN', 'Hazards stats (airline)')
check_endpoint('GET', '/api/v1/hazards/stats', 'super_admin', 'Hazards stats (super)')
check_endpoint('GET', '/api/v1/cans/stats', 'TENANT_ADMIN', 'CAN stats (airline)')
check_endpoint('GET', '/api/v1/cans/stats', 'super_admin', 'CAN stats (super)')
check_endpoint('GET', '/api/v1/flight-diversions/stats', 'TENANT_ADMIN', 'Diversion stats (airline)')
check_endpoint('GET', '/api/v1/flight-diversions/stats', 'super_admin', 'Diversion stats (super)')
check_endpoint('GET', '/api/v1/dashboard/overview', 'super_admin', 'Dashboard overview (super)')
check_endpoint('GET', '/api/v1/dashboard/caan/overview', 'super_admin', 'CAAN overview (super)')
check_endpoint('GET', '/api/v1/dashboard/caan/overview', 'STATE_SMD', 'CAAN overview (caan)')

print('\n=== WRITE ENDPOINT DIAG ===')
check_endpoint('POST', '/api/v1/reports/vsr', 'super_admin', 'VSR submit (super)')
check_endpoint('POST', '/api/v1/reports/vsr', 'TENANT_ADMIN', 'VSR submit (airline)')

# Check verification routes
check_endpoint('GET', '/api/v1/verification/verifications/stats', 'TENANT_ADMIN', 'Verification stats (airline)')
check_endpoint('GET', '/api/v1/verification/verifications/stats', 'super_admin', 'Verification stats (super)')

# Try the non-v1 routes
check_endpoint('GET', '/api/hazards/stats', 'TENANT_ADMIN', 'Non-v1 hazards stats')

# Reporting
check_endpoint('POST', '/api/v1/reporting/quarterly', 'super_admin', 'Quarterly report (super)')

# Diversion create
check_endpoint('POST', '/api/v1/flight-diversions/', 'super_admin', 'Diversion create (super)')

# Airline admin admin endpoint
check_endpoint('GET', '/api/v1/admin/risk-matrix', 'TENANT_ADMIN', 'Admin: risk matrix (airline)')
check_endpoint('GET', '/api/v1/admin/risk-matrix', 'super_admin', 'Admin: risk matrix (super)')

# List endpoints
check_endpoint('GET', '/api/v1/hazards/', 'super_admin', 'Hazard list (super)')
check_endpoint('GET', '/api/v1/reports/', 'super_admin', 'Reports list (super)')
