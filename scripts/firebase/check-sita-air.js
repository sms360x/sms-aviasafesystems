// Verify (and optionally reset) Sita Air demo accounts in Firebase Auth.
// Reads backend/.env for service-account credentials.
// Usage:
//   node scripts/firebase/check-sita-air.js          # verify only
//   node scripts/firebase/check-sita-air.js --reset  # reset existing accounts to DEFAULT_SEED_PASSWORD
'use strict';

const fs = require('fs');
const path = require('path');
const admin = require('firebase-admin');

function loadEnv() {
    const raw = fs.readFileSync(path.join(__dirname, '..', '..', 'backend', '.env'), 'utf8');
    const env = {};
    for (const line of raw.split(/\r?\n/)) {
        const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)$/);
        if (m && !line.trim().startsWith('#')) {
            let v = m[2];
            if (v.length >= 2 && v[0] === '"' && v[v.length - 1] === '"') {
                v = v.slice(1, -1);
            }
            env[m[1]] = v;
        }
    }
    return env;
}

function buildCreds(env) {
    return {
        type: 'service_account',
        project_id: env.FIREBASE_PROJECT_ID,
        private_key: (env.FIREBASE_PRIVATE_KEY || '').replace(/\\n/g, '\n'),
        client_email: env.FIREBASE_CLIENT_EMAIL,
        token_uri: env.FIREBASE_TOKEN_URI || 'https://oauth2.googleapis.com/token',
    };
}

async function main() {
    const reset = process.argv.includes('--reset');
    const env = loadEnv();
    if (!env.FIREBASE_CLIENT_EMAIL || !env.FIREBASE_PRIVATE_KEY) {
        console.error('ERROR: FIREBASE_CLIENT_EMAIL / FIREBASE_PRIVATE_KEY missing from backend/.env');
        process.exit(1);
    }
    const password = env.DEFAULT_SEED_PASSWORD;
    if (!password) {
        console.error('ERROR: DEFAULT_SEED_PASSWORD missing from backend/.env');
        process.exit(1);
    }

    if (!admin.apps.length) admin.initializeApp({ credential: admin.credential.cert(buildCreds(env)) });
    const auth = admin.auth();

    const candidates = [
        'sm.sita-air@sitaair.com',            // the email that failed to log in
        'safety.sita-air@sitaair.com.np',     // seeded TENANT_ADMIN (correct domain)
        'ae.sita-air@sitaair.com.np',         // seeded TENANT_ADMIN
        'manager.sita-air@sitaair.com.np',    // seeded USER
    ];

    for (const email of candidates) {
        try {
            const user = await auth.getUserByEmail(email);
            console.log(`EXISTS  ${email}  uid=${user.uid}  claims=${JSON.stringify(user.customClaims || {})}`);
            if (reset) {
                await auth.updateUser(user.uid, { password });
                console.log(`  -> password reset to DEFAULT_SEED_PASSWORD`);
            }
        } catch (err) {
            if (err.code === 'auth/user-not-found') {
                console.log(`MISSING ${email}`);
            } else {
                console.log(`ERROR   ${email}  ${err.code || err.message}`);
            }
        }
    }
}

main().catch(err => { console.error(err); process.exit(1); });
