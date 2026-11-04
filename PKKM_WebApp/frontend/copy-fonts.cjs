const fs = require('node:fs');
const path = require('node:path');
const source = path.join(__dirname, '../node_modules/@fontsource/plus-jakarta-sans');
const destination = path.join(__dirname, '../static/fonts');
fs.mkdirSync(destination, { recursive: true });
for (const weight of [300, 400, 500, 600, 700, 800]) {
  const filename = `plus-jakarta-sans-latin-${weight}-normal.woff2`;
  fs.copyFileSync(path.join(source, 'files', filename), path.join(destination, filename));
}
fs.copyFileSync(path.join(source, 'LICENSE'), path.join(destination, 'LICENSE'));
