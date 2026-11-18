const fs = require('fs');
const path = require('path');

const apiRoot = process.env.SITEFORGE_API_ROOT || process.env.API_ROOT || '/api/v1';
const wsBase = process.env.SITEFORGE_WS_BASE || process.env.WS_BASE || '';

let content = `window.__sf = window.__sf || {};\nwindow.__sf.apiRoot = ${JSON.stringify(apiRoot)};\n`;
if (wsBase) {
  content += `window.__sf.wsBase = ${JSON.stringify(wsBase)};\n`;
}

const out = path.join(__dirname, '..', 'src', 'assets', 'runtime-config.js');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, content, 'utf8');
console.log('[runtime-config] apiRoot=%s wsBase=%s -> %s', apiRoot, wsBase || '(derived)', out);
