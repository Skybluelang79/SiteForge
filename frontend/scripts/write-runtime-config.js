const fs = require('fs');
const path = require('path');

const apiRoot = process.env.SITEFORGE_API_ROOT || process.env.API_ROOT || '/api/v1';
const wsBase = process.env.SITEFORGE_WS_BASE || process.env.WS_BASE || '';
const turnstileSiteKey = process.env.TURNSTILE_SITE_KEY || '';
const cloudflareAccessEnabled = ['1', 'true', 'yes', 'on'].includes(
  (process.env.CLOUDFLARE_ACCESS_ENABLED || '').toLowerCase(),
);

let content = `window.__sf = window.__sf || {};\nwindow.__sf.apiRoot = ${JSON.stringify(apiRoot)};\n`;
if (wsBase) {
  content += `window.__sf.wsBase = ${JSON.stringify(wsBase)};\n`;
}
if (turnstileSiteKey) {
  content += `window.__sf.turnstileSiteKey = ${JSON.stringify(turnstileSiteKey)};\n`;
}
content += `window.__sf.cloudflareAccessEnabled = ${cloudflareAccessEnabled};\n`;


const out = path.join(__dirname, '..', 'src', 'assets', 'runtime-config.js');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, content, 'utf8');
console.log('[runtime-config] apiRoot=%s wsBase=%s -> %s', apiRoot, wsBase || '(derived)', out);
