const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const fixture=require('./synthetic-export.json'),html=fs.readFileSync(path.join(__dirname,'own-data-preview.html'),'utf8');
const src=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const document={querySelector:()=>({})};const ctx={document};vm.runInNewContext(src,ctx);
const rows=fixture.current.rows;
assert.match(ctx.checkSample(rows),/accepted/);
for(const sample of [[],[...rows,...rows],[rows[0],rows[0]],[{...rows[0],stock:-1}],[{...rows[0],price:'1.00001'}],[{...rows[0],currency:'usd'}],[{...rows[0],packSize:0}]])assert.doesNotMatch(ctx.checkSample(sample),/accepted/);
assert.ok(html.includes("connect-src 'none'"));assert.doesNotMatch(src,/fetch\(|XMLHttpRequest|localStorage|indexedDB|sendBeacon/);
console.log('8 sample checks and offline boundary passed');
