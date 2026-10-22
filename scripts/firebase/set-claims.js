const admin = require('firebase-admin');
const serviceAccount = require('./service-account.json');

admin.initializeApp({
    credential: admin.credential.cert(serviceAccount)
});

async function setClaims() {
    console.log('Setting custom claims...');

    const users = [
        { 
            email: 'admin@aviasafesystems.com', 
            uid: 'Z3uNhvyEP2RKBnwtXUowqFMy3Cg1', 
            claims: { role: 'SUPER_ADMIN' } 
        },
        { 
            email: 'sal@aviasafesystems.com', 
            uid: 'pl1YEWCBq5OC4rx8SNbOV9zVFwC2', 
            claims: { role: 'TENANT_ADMIN', tenant_id: 'sita-air' } 
        },
        { 
            email: 'salsafety@aviasafesystems.com', 
            uid: 'n46U3TB2wVXVkYqYpTwazps8Zx73', 
            claims: { role: 'TENANT_ADMIN', tenant_id: 'sita-air' } 
        },
        { 
            email: 'smd@caanepal.gov.np', 
            uid: 'WHmIerlq8sQCAjFtD1XNz6etRRg1', 
            claims: { role: 'STATE_SMD' } 
        }
    ];

    for (const user of users) {
        try {
            await admin.auth().setCustomUserClaims(user.uid, user.claims);
            console.log('✅ Claims set for', user.email, ':', user.claims);
        } catch (error) {
            console.error('❌ Error for', user.email, ':', error.message);
        }
    }

    console.log('✅ Done!');
}

setClaims();