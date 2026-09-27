const fs = require('node:fs');
fs.mkdirSync('app/static_src/vendor/katex', {recursive:true});
for (const name of ['katex.min.js','katex.min.css','fonts','contrib/auto-render.min.js']) {
  fs.cpSync('node_modules/katex/dist/'+name, 'app/static_src/vendor/katex/'+name, {recursive:true});
}
fs.copyFileSync('node_modules/katex/LICENSE','app/static_src/vendor/katex/LICENSE');
