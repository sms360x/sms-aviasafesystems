import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const exists = file => fs.existsSync(path.join(root, file));
const config = JSON.parse(read('firebase.json'));
const hosting = (Array.isArray(config.hosting) ? config.hosting : [config.hosting])
    .find(site => site.site === 'aerosafety-sms-prod');
assert(hosting && hosting.public === 'public', 'Production hosting must publish public/');
assert(exists('public/css/brand.css'), 'Shared brand.css is missing from the release');
const theme = read('public/css/brand.css');
assert(theme.includes('DM+Sans') && theme.includes('Manrope') && theme.includes('#1d5949'),
    'The release must include the approved fonts and green palette');
function pages(dir) {
    return fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
        if (entry.name === 'etl' || entry.name === '_hold') return [];
        const file = path.join(dir, entry.name);
        return entry.isDirectory() ? pages(file) : file.endsWith('.html') ? [file] : [];
    });
}
const applicationPages = pages(path.join(root, 'public'));
for (const file of applicationPages) {
    assert(fs.readFileSync(file, 'utf8').includes('/css/brand.css'),
        path.relative(root, file) + ' does not load the shared theme');
}
assert(exists('public/etl/index.html'), 'ETL entry point is missing from the release');
const entry = read('public/etl/index.html');
const assets = [...entry.matchAll(/(?:src|href)=["'](\/etl\/assets\/[^"']+)["']/g)].map(match => match[1]);
assert(assets.some(file => file.endsWith('.js')) && assets.some(file => file.endsWith('.css')),
    'ETL must reference its built JavaScript and CSS');
const checked = new Set();
function asset(file) {
    const relative = 'public' + file;
    assert(exists(relative), 'ETL asset missing: ' + file);
    if (checked.has(file)) return;
    checked.add(file);
    if (!/\.(js|css)$/.test(file)) return;
    const source = read(relative);
    for (const match of source.matchAll(/["'`](?:\.\/|\/etl\/assets\/)?([A-Za-z0-9_-]+-[A-Za-z0-9_-]+\.(?:js|css|png|svg|woff2))["'`]/g)) {
        asset('/etl/assets/' + match[1]);
    }
}
assets.forEach(asset);
assert((hosting.redirects || []).some(rule => rule.source === '/login' && rule.destination === '/login.html' && rule.type === 301),
    '/login must redirect to the login page instead of the homepage fallback');
const rewrites = hosting.rewrites || [];
const apiIndex = rewrites.findIndex(rule => rule.source === '/etl/api/**');
const etlIndex = rewrites.findIndex(rule => rule.source === '/etl/**');
const rootIndex = rewrites.findIndex(rule => rule.source === '**');
assert(apiIndex >= 0 && apiIndex < etlIndex && etlIndex < rootIndex,
    'ETL API and SPA routes must precede the homepage fallback');
assert(rewrites[apiIndex].run?.serviceId === 'etl360x' && rewrites[apiIndex].run?.region === 'asia-south1',
    'ETL API must route to its existing Cloud Run service');
assert(rewrites.some(rule => rule.source === '/etl' && rule.destination === '/etl/index.html'),
    '/etl must serve the ETL entry point');
assert(rewrites[etlIndex].destination === '/etl/index.html', 'ETL nested paths must serve ETL');
console.log('Hosting release verified: ' + applicationPages.length + ' themed pages; ' + checked.size + ' ETL runtime assets.');
