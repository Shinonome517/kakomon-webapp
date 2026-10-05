const katex = require('../app/static_src/vendor/katex/katex.min.js');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  const invalid = JSON.parse(input).map(text => {
    const parts = text.match(/\$\$[\s\S]*?\$\$|\$[^$\n]+?\$/g) || [];
    if (text.replace(/\$\$[\s\S]*?\$\$|\$[^$\n]+?\$/g, '').includes('$')) return true;
    try {
      for (const part of parts) {
        const delim = part.startsWith('$$') ? 2 : 1;
        katex.renderToString(part.slice(delim, -delim), {throwOnError:true, trust:false, strict:'error', maxExpand:1000, maxSize:20});
      }
      return false;
    } catch { return true; }
  });
  process.stdout.write(JSON.stringify(invalid));
});
