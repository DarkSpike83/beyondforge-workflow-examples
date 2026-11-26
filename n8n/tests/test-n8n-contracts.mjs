import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';

const require=createRequire(import.meta.url);
const get=(file)=>JSON.parse(readFileSync(new URL(file,import.meta.url)));
const flows=Object.fromEntries(['merchant','supplier','migration','rss'].map(f=>[f,get('../workflows/n8n-'+f+'.json')]));
function run(flow,name,input={},references={},configure=false){
  let script=flows[flow].nodes.find(n=>n.name===name).parameters.jsCode;
  if(configure)script=script.replace('const enabled = false;', 'const enabled = true;')
    .replace("'YOUR_OWNER'","'example-org'").replace("'YOUR_PRIVATE_REPOSITORY'","'example-state'");
  const first=k=>({first:()=>({json:references[k]})});
  return new Function('$json','$input','$','require','Buffer','$execution',script)(
    input,{all:()=>[{json:input}]},first,require,Buffer,{id:'SyntheticExecution'})[0].json;
}
const digest=value=>createHash('sha256').update(value).digest('hex');
const canonical=x=>Array.isArray(x)?'['+x.map(canonical).join(',')+']':
  x!==null&&typeof x==='object'?'{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+canonical(x[k])).join(',')+'}':JSON.stringify(x);
for(const [flow,wf] of Object.entries(flows)){
  test(flow+' imports disabled and selectors never forward credentials to source URLs',()=>{
    assert.equal(wf.active,false);assert.equal(wf.settings.saveManualExecutions,false);
    assert(!wf.nodes.some(n=>n.type.includes('chedule')||n.type.toLowerCase().includes('webhook')));
    const http=wf.nodes.filter(n=>n.type.endsWith('httpRequest'));
    assert(http.length>5);
    for(const n of http){
      assert.equal(n.parameters.authentication,'genericCredentialType');
      assert.equal(n.parameters.options.redirect.redirect.followRedirects,false);
      assert.equal(n.retryOnFail,false);assert(!n.credentials);
      assert(/^=\{\{ 'https:\/\/api\.(github|apify)\.com\//.test(n.parameters.url));
    }
    assert.equal(http.filter(n=>n.parameters.method==='POST').length,1);
    assert.throws(()=>run(flow,'Configure connection',get('../fixtures/'+flow+'-observation.json')),/Setup required/);
    const launch=run(flow,'Configure connection',get('../fixtures/'+flow+'-observation.json'),{},true);
    assert.match(launch.signature,/^[a-f0-9]{64}$/);
  });
}
const req=run('merchant','Configure connection',get('../fixtures/merchant-observation.json'),{},true);
function inspect(state, request=req){
 const file={type:'file',encoding:'base64',sha:'a'.repeat(40),content:Buffer.from(JSON.stringify(state)).toString('base64')};
 return run('merchant','Inspect state',{body:file},{'Configure connection':request}).action;
}
const seed=get('../fixtures/private-state-seed.json');
test('every expression has a single closing delimiter and each conditional PUT sends the prepared state',()=>{
 function checkExpressions(value){
  if(typeof value==='string'&&value.startsWith('={{')){
   assert.equal(value.indexOf('}}'),value.length-2,'Premature end of n8n interpolation: '+value);
  }else if(value && typeof value==='object'){
   for(const field of Object.values(value))checkExpressions(field);
  }
 }
 for(const [flow,wf] of Object.entries(flows)){
  for(const node of wf.nodes)checkExpressions(node.parameters);
  const writes=wf.nodes.filter(n=>n.type.endsWith('httpRequest')&&n.parameters.method==='PUT');
  assert.equal(writes.length,3);
  for(const node of writes) assert.equal(node.parameters.jsonBody,'={{ $json.journalWrite }}');
  const firstSha='a'.repeat(40),claimSha='b'.repeat(40),receiptSha='c'.repeat(40);
  const refs={
   'Configure connection':{sequence:7,signature:digest('source7')},
   'Inspect state':{state:seed,sha:firstSha},'Claim operation':{body:{content:{sha:claimSha}}},
   'Prepare lookup':{stateSha:receiptSha,runId:'Known7'}
  };
  const read=(name,input,sha)=>{
   const {journalWrite}=run(flow,name,input,refs);
   assert.equal(journalWrite.sha,sha);
   return JSON.parse(Buffer.from(journalWrite.content,'base64').toString('utf8'));
  };
  const claim=read('Prepare claim write',{},firstSha);
  const receipt=read('Prepare run receipt write',{runId:'Known7'},claimSha);
  assert.equal(claim.pending.runId,null);
  assert.deepEqual(receipt.pending,{...claim.pending,runId:'Known7'});
  assert.equal(receipt.pending.sequence,7);
  const committed=read('Prepare completion write',{route:'TEST',baselineStore:null,baselineDigest:null},receiptSha);
  assert.deepEqual(committed,{version:1,lastSequence:7,baselineStore:null,baselineDigest:null,pending:null,lastRunId:'Known7',lastRoute:'TEST'});
 }
});
test('the settled authenticated reading, rather than provisional costs, feeds the billing gate',()=>{
 for(const wf of Object.values(flows)){
  const next=n=>wf.connections[n].main[0][0].node;
  assert.equal(next('Read final status'),'Require terminal state');
  assert.equal(next('Require terminal state'),'Allow billing to settle');
  const wait=wf.nodes.find(n=>n.name==='Allow billing to settle');
  assert.equal(wait.parameters.amount,10);assert.equal(wait.parameters.unit,'seconds');
  assert.equal(next(wait.name),'Read settled accounting');assert.equal(next('Read settled accounting'),'Check run identity');
 }
});
test('an acknowledged new revision is required before submission and before result routing',()=>{
 const previous='a'.repeat(40), confirmed='b'.repeat(40);
 const refs={'Inspect state':{sha:previous},'Prepare lookup':{stateSha:previous}};
 assert.throws(()=>run('merchant','Confirm claim',{body:{}},refs),/No new journal/);
 assert.throws(()=>run('merchant','Confirm claim',{body:{content:{sha:previous}}},refs));
 assert.equal(run('merchant','Confirm claim',{body:{content:{sha:confirmed}}},refs).acknowledged,true);
 assert.throws(()=>run('merchant','Deliver verified result',{body:{content:{sha:previous}}},refs),/unconfirmed/);
});
test('same-size changes to the previous supplier catalog or RSS checkpoint hold the next start',()=>{
 const capture={rows:[{sku:'P',price:'1'}]};
 const config={flow:'supplier',input:{incoming:{rows:[{sku:'P',price:'3'}]}}};
 const st={baselineStore:'Kvs1',baselineDigest:digest(canonical(capture))};
 const refs={'Configure connection':config,'Inspect state':{state:st}};
 assert.deepEqual(run('supplier','Prepare Actor input',{body:{incoming:capture}},refs).input.baseline,capture);
 assert.throws(()=>run('supplier','Prepare Actor input',{body:{incoming:{rows:[{sku:'P',price:'2'}]}}},refs),/Prior capture changed/);
 const cp={version:1,entries:{abc:{title:digest('hello')}}};
 const rss={'Configure connection':{flow:'rss',input:{feedXml:'<rss/>'}},'Inspect state':{state:{baselineStore:'Kvs1',baselineDigest:digest(canonical(cp))}}};
 assert.deepEqual(run('rss','Prepare Actor input',{body:cp},rss).input.baseline,cp);
 assert.throws(()=>run('rss','Prepare Actor input',{body:{...cp,entries:{abc:{title:digest('world')}}}},rss),/Prior capture changed/);
 assert.throws(()=>inspect({...seed,baselineStore:'Kvs1'}),/fingerprint/);
});
test('claim, replay, missing receipt, known run and concurrent observations',()=>{
 assert.equal(inspect(seed),'start');assert.equal(inspect({...seed,lastSequence:req.sequence}),'duplicate');
 const pending={sequence:req.sequence,signature:req.signature,runId:null};
 assert.throws(()=>inspect({...seed,pending}),/Unresolved/);
 assert.equal(inspect({...seed,pending:{...pending,runId:'KnownRun'}}),'resume');
 assert.throws(()=>inspect({...seed,pending:{...pending,runId:'KnownRun'}},{...req,sequence:req.sequence+1}),/Unresolved/);
 assert.throws(()=>inspect({...seed,pending:{...pending,signature:'changed',runId:'KnownRun'}}),/Unresolved/);
});
test('operator budget and excluded billing controls stop before dispatch',()=>{
 for (const invalid of [0,-3,'5',5001,1.1]) {
  assert.throws(()=>run('merchant','Configure connection',{sequence:1,expectedOffers:1,input:{offers:[],maxResults:invalid}}, {},true),/whole number/);
  assert.throws(()=>run('rss','Configure connection',{sequence:1,input:{feedXml:'<rss/>',maxResults:invalid}}, {},true),/whole number/);
 }
 assert.throws(()=>run('merchant','Configure connection',{sequence:1,expectedOffers:5000,input:{feedXml:'<rss/>',maxResults:5000}}, {},true),/cap cannot cover/);
 assert.throws(()=>run('supplier','Configure connection',{sequence:1,input:{demoCase:'stockout',billDemoReport:true}}, {},true),/Unexpected Actor/);
 assert.throws(()=>run('rss','Configure connection',{sequence:1,input:{feedXml:'<rss/>',completionReceipt:true}}, {},true),/Unexpected Actor/);
});
function validate(flow,input,summary,rows,ledger,detail){
 return run(flow,'Verify delivery and charges',{},{
  'Configure connection':{flow,input,expectedOffers:1},'Read run summary':{body:{outcome:'complete',...summary}},
  'Check run identity':{id:'Run1',defaultKeyValueStoreId:'Kvs1',defaultDatasetId:'Ds1',chargedEventCounts:ledger},
  'Read delivered rows':{body:rows},'Read detail':{body:detail},'Inspect state':{state:{baselineStore:'Previous1'}}
 });
}
test('Merchant rejects truncated, duplicated, overcharged and partial deliveries',()=>{
 const summary={matched:1,returned:1,uniqueOffers:1,inputOffers:1,event:'offer-audited'};
 const row={id:'offer1',status:'review',findings:[{code:'SALE_PRICE'}]};
 assert.equal(validate('merchant',{},summary,[row],{'offer-audited':1}).route,'HOLD_EXPORT');
 assert.throws(()=>validate('merchant',{},summary,[],{'offer-audited':1}));
 assert.throws(()=>validate('merchant',{},summary,[row],{'offer-audited':2}));
 assert.throws(()=>validate('merchant',{}, {...summary,outcome:'free_limit'},[row],{'offer-audited':1}));
 assert.throws(()=>validate('merchant',{},summary,[row],{'offer-audited':1,'apify-actor-start':2}));
});
test('RSS empty capture holds last baseline and distinguishes rotated source windows',()=>{
 const summary={entries:0,matched:0,returned:0,checkpointReady:true,unchanged:0,previousOnly:4,event:'feed-change'};
 const checkpoint={version:1,feedKey:digest('source'),entries:{}};
 const out=validate('rss',{},summary,[],{},checkpoint);
 assert.equal(out.route,'EMPTY_FEED');assert.equal(out.baselineStore,'Previous1');
 assert.throws(()=>validate('rss',{},summary,[],{'comparison-receipt':1},checkpoint));
 const fields=Object.fromEntries(['content','link','published','title','updated'].map(f=>[f,digest(f)]));
 const nonempty={...checkpoint,entries:{[digest('entry')]:fields}};
 assert.equal(validate('rss',{}, {...summary,entries:1,unchanged:1},[],{},nonempty).route,'FEED_WINDOW_CHANGED');
});
test('Supplier custom exception report checks rows, counters and full hash before promoting',()=>{
 const report={kind:'catalog-reconciliation',schemaVersion:1,outputMode:'audit',outcome:'differences',demoCase:null,matchedSkus:1,unionSkus:1,exceptionSkus:1,counts:{stockout:1},exceptions:[{sku:'P-1',reasons:['stockout']}],incoming:{sourceRows:1,uniqueSkus:1,snapshotSha256:digest('sku')}};
 const overview={...report,reportSha256:digest(canonical(report))};
 const summary={deliveredReports:1,outputMode:'audit',chargedEvents:1,eventName:'catalog-reconciled',reportSha256:overview.reportSha256};
 const input={incoming:{rows:[{sku:'P-1'}]}};
 const out=validate('supplier',input,summary,[overview],{'catalog-reconciled':1},report);
 assert.equal(out.route,'REVIEW_CATALOG_CHANGES');assert.equal(out.baselineStore,'Kvs1');
 assert.throws(()=>validate('supplier',input,summary,[overview],{},report));
 assert.throws(()=>validate('supplier',input,summary,[overview],{'catalog-reconciled':1},{...report,exceptions:[]}));
});
test('Migration report without trace cannot approve even when it hashes correctly',()=>{
 const report={kind:'migration-redirect-audit',schemaVersion:1,outputMode:'audit',outcome:'clean',demoCase:null,mappedUrls:1,fullyTracedUrls:1,flaggedUrls:0,findingCounts:{},comparison:null,results:[]};
 const overview={...report,reportSha256:digest(canonical(report))};
 const summary={deliveredReports:1,outputMode:'audit',chargedEvents:1,eventName:'migration-audited',reportSha256:overview.reportSha256};
 assert.throws(()=>validate('migration',{},summary,[overview],{'migration-audited':1},report),/traces/);
});
