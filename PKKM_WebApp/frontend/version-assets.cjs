const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');
const staticDir = path.join(__dirname, '../static');
const filename = path.join(staticDir, 'index.html');
let html = fs.readFileSync(filename, 'utf8');
for (const asset of ['app.js', 'app.css']) {
  const hash = crypto.createHash('sha256').update(fs.readFileSync(path.join(staticDir, asset))).digest('hex').slice(0, 12);
  const escaped = asset.replace('.', '\\.');
  html = html.replace(new RegExp(`/static/${escaped}(?:\\?v=[a-z0-9]+)?`, 'g'), `/static/${asset}?v=${hash}`);
}
fs.writeFileSync(filename, html);
