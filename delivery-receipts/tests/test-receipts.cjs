'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ids = {
  'albo-gestori-ambientali': 'dulaBRchXhuENMm3d',
  'pdf-text-pages': 'kdLRbOFI8lU7cdLWv',
  'html-markdown-batch': 'l0FzouietCktp3hSV',
  'json-csv-export': 'bAyeKMBTe1EvIMnTu',
};
const workflows = Object.fromEntries(Object.keys(ids).map(slug => [
  slug, JSON.parse(fs.readFileSync(path.join(__dirname, '../n8n', slug + '.json'), 'utf8')),
]));
function code(slug, name) {
  return workflows[slug].nodes.find(node => node.name === name).parameters.jsCode;
}
function fixture(slug) { return new Function(code(slug, 'Synthetic receipt'))()[0].json; }
function reference(slug) { return new Function(code(slug, 'Trusted job reference'))(); }
function project(slug, input, journal = reference(slug)) {
  const readPrior = name => {
    assert.equal(name, 'Trusted job reference');
    return {all: (output, run) => {
      assert.deepEqual([output, run], [0, 0]);
      return journal;
    }};
  };
  return new Function('$input', '$', '$runIndex', code(slug, 'Read delivered fields'))(
    {all: () => input.map(json => ({json}))}, readPrior, 0);
}
const expectedFields = {
  'albo-gestori-ambientali': {recordsSaved:1, regionsSearched:1, stopReason:'maxResults', decision:'LIMIT_REACHED_REVIEW_SCOPE'},
  'pdf-text-pages': {page:2, documentPages:2, text:'Approved delivery'},
  'html-markdown-batch': {markdown:'| Component | Status |\n| --- | --- |\n| Parser | Ready |\n| Exporter | Pending |'},
  'json-csv-export': {rowCount:2, csv:'sku,available\r\nBOX-A,8\r\nBOX-B,0\r\n'},
};
for (const slug of Object.keys(ids)) {
  const runId='SYNTHETIC-'+slug;
  test(slug + ' delivers the expected values and is repeatable', () => {
    const expected = [{json:{runId, ...expectedFields[slug]}}];
    assert.deepEqual(project(slug,[fixture(slug)]),expected);
    assert.deepEqual(project(slug,[fixture(slug)]),expected);
  });
  test(slug + ' has an independent expected run and fixed Actor', () => {
    const receipt = fixture(slug);
    assert.equal('expectedRunId' in receipt, false);
    assert.deepEqual(reference(slug), [{json:{expectedRunId:runId}}]);
    assert.equal(receipt.actId,ids[slug]);
    assert.equal(receipt.actor,slug);
    const names=workflows[slug].nodes.map(node => node.name);
    assert.deepEqual(names,['Manual review','Trusted job reference','Synthetic receipt','Read delivered fields']);
    for(let i=1;i<names.length;i++)
      assert.deepEqual(workflows[slug].connections[names[i-1]].main,[[{node:names[i],type:'main',index:0}]]);
    assert.equal(workflows[slug].active,false);
  });
  for(const other of Object.keys(ids).filter(other => other !== slug)) {
    test(slug + ' rejects a valid ' + other + ' delivery even with matching journal run',() => {
      const foreign = fixture(other);
      assert.throws(()=>project(slug,[foreign],[{json:{expectedRunId:foreign.runId}}]),/Actor, run/);
    });
  }
  for(const [label,change] of Object.entries({
    wrongActorId: {actId:'foreign'},
    wrongSlug: {actor:'foreign'},
    failedRun: {status:'FAILED'},
    receiptCannotOverrideJob: {runId:'foreign', expectedRunId:'foreign'},
    incompleteDelivery: slug.startsWith('albo') ? {summary:{}} : {rows:[]},
  })) test(slug+' rejects '+label,()=> assert.throws(()=>project(slug,[{...fixture(slug),...change}])));
  for(const [label,records] of Object.entries({
    absent:[], ambiguous:[{json:{expectedRunId:runId}},{json:{expectedRunId:runId}}],
    blank:[{json:{expectedRunId:' '}}], different:[{json:{expectedRunId:'other'}}],
  })) test(slug+' rejects '+label+' journal reference',()=>assert.throws(()=>project(slug,[fixture(slug)],records)));
  test(slug+' rejects ambiguous receipt batches',()=>assert.throws(()=>project(slug,[fixture(slug),fixture(slug)])));
}
