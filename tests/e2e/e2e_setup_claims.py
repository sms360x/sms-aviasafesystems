import os
import requests

BASE = 'https://aviasafe-unified-platform.onrender.com'

TOKEN = os.environ.get('SUPER_ADMIN_ID_TOKEN')
SETUP_KEY = os.environ.get('SETUP_SECRET')

if not TOKEN or not SETUP_KEY:
    raise SystemExit('SUPER_ADMIN_ID_TOKEN and SETUP_SECRET env vars are required')

payload = {
    'setup_key': SETUP_KEY,
    'users': [
        {'email': 'admin@aviasafesystems.com', 'role': 'SUPER_ADMIN'},
        {'email': 'sal@aviasafesystems.com', 'role': 'TENANT_ADMIN', 'tenant_id': 'sita-air'},
        {'email': 'salsafety@aviasafesystems.com', 'role': 'TENANT_ADMIN', 'tenant_id': 'sita-air'},
        {'email': 'smd@caanepal.gov.np', 'role': 'STATE_SMD'},
    ]
}

headers = {'Authorization': f'Bearer {TOKEN}'}
r = requests.post(BASE + '/api/v1/admin/setup-claims', json=payload, headers=headers, timeout=30)

print('Status:', r.status_code)
data = r.json()
for result in data.get('results', []):
    email = result['email']
    status = result['status']
    role = result.get('role', '?')
    tenant = result.get('tenant_id', 'none')
    print(f'  {email}: {status} (role={role}, tenant={tenant})')
