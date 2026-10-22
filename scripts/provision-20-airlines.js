const admin = require('firebase-admin');
const path = require('path');
const fs = require('fs');

// Password is env-driven — no hardcoded default. Provisioning fails fast if unset.
const STANDARD_PASSWORD = process.env.DEFAULT_PROVISION_PASSWORD;

if (!STANDARD_PASSWORD) {
  console.error('ERROR: DEFAULT_PROVISION_PASSWORD environment variable is required.');
  process.exit(1);
}

const AIRLINES = [
  { id: 'buddha-air', name: 'Buddha Air', icao: 'BHA', email: 'buddhaair@buddhaair.com' },
  { id: 'nepal-airlines', name: 'Nepal Airlines', icao: 'NAL', email: 'info@nac.com.np' },
  { id: 'shree-airlines', name: 'Shree Airlines', icao: 'SHA', email: 'info@shreeairlines.com' },
  { id: 'sita-air', name: 'Sita Air', icao: 'STA', email: 'info@sitaair.com' },
  { id: 'summit-air', name: 'Summit Air', icao: 'SMT', email: 'info@summitair.com.np' },
  { id: 'tara-air', name: 'Tara Air', icao: 'TRA', email: 'info@taraair.com' },
  { id: 'yeti-airlines', name: 'Yeti Airlines', icao: 'YET', email: 'info@yetiairlines.com' },
  { id: 'makalu-air', name: 'Makalu Air', icao: 'MKU', email: 'info@makaluair.com' },
  { id: 'himalaya-airlines', name: 'Himalaya Airlines', icao: 'HIM', email: 'info@himalaya-airlines.com' },
  { id: 'air-dynasty', name: 'Air Dynasty Heli Services', icao: 'ADH', email: 'info@airdynasty.com' },
  { id: 'altitude-air', name: 'Altitude Air', icao: 'ALT', email: 'info@altitudeair.com.np' },
  { id: 'annapurna-heli', name: 'Annapurna Helicopter', icao: 'ANH', email: 'info@annapurnaheli.com' },
  { id: 'fishtail-air', name: 'Fishtail Air', icao: 'FTA', email: 'info@fishtailair.com' },
  { id: 'heli-everest', name: 'Heli Everest', icao: 'HLE', email: 'info@helieverest.com' },
  { id: 'kailash-helicopter', name: 'Kailash Helicopter Services', icao: 'KHS', email: 'info@kailashhelicopter.com' },
  { id: 'manang-air', name: 'Manang Air', icao: 'MNA', email: 'info@manangair.com' },
  { id: 'mountain-helicopters', name: 'Mountain Helicopters', icao: 'MTH', email: 'info@mountainhelicopters.com' },
  { id: 'mustang-helicopter', name: 'Mustang Helicopter', icao: 'MSH', email: 'info@mustanghelicopter.com' },
  { id: 'prabhu-helicopters', name: 'Prabhu Helicopters', icao: 'PRB', email: 'info@prabhuhelicopters.com' },
  { id: 'simrik-air', name: 'Simrik Air', icao: 'SMK', email: 'info@simrikair.com' }
];

let serviceAccountPath = path.join(__dirname, '..', 'service-account.json');

let serviceAccount;
if (fs.existsSync(serviceAccountPath)) {
  serviceAccount = require(serviceAccountPath);
} else {
  serviceAccount = {
    type: 'service_account',
    project_id: process.env.FIREBASE_PROJECT_ID,
    private_key: (process.env.FIREBASE_PRIVATE_KEY || '').replace(/\\n/g, '\n'),
    client_email: process.env.FIREBASE_CLIENT_EMAIL,
    token_uri: process.env.FIREBASE_TOKEN_URI || 'https://oauth2.googleapis.com/token'
  };
}

admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });

async function provisionAirline(airline) {
  const db = admin.firestore();
  try {
    const user = await admin.auth().createUser({
      email: airline.email,
      password: STANDARD_PASSWORD,
      emailVerified: true,
      displayName: `${airline.name} Safety Manager`
    });

    await admin.auth().setCustomUserClaims(user.uid, {
      role: 'TENANT_ADMIN',
      tenant_id: airline.id
    });

    const now = new Date().toISOString();
    await db.collection('tenants').doc(airline.id).set({
      tenant_id: airline.id,
      name: airline.name,
      icao: airline.icao,
      country: 'Nepal',
      active: true,
      safety_manager: {
        email: airline.email,
        name: `${airline.name} Safety Manager`,
        uid: user.uid
      },
      survey_config: {
        open: true,
        open_date: '2026-08-01',
        close_date: '2026-08-31'
      },
      created_at: now,
      updated_at: now
    });

    return {
      airline: airline.name,
      tenant_id: airline.id,
      email: airline.email,
      uid: user.uid
    };
  } catch (error) {
    console.error(`  FAILED: ${airline.name} - ${error.message}`);
    return null;
  }
}

async function provisionAll() {
  console.log('Provisioning 20 airlines...\n');
  const results = [];

  for (const airline of AIRLINES) {
    process.stdout.write(`${airline.name} (${airline.id})... `);
    const result = await provisionAirline(airline);
    if (result) {
      results.push(result);
      console.log('OK');
    } else {
      console.log('FAILED');
    }
  }

  console.log(`\n${results.length}/${AIRLINES.length} airlines provisioned.`);
}

provisionAll().catch(console.error);
