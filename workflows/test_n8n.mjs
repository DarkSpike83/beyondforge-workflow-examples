import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const workflow = JSON.parse(readFileSync(new URL('./n8n-migration-gate.json', import.meta.url)));
const nodes = new Map(workflow.nodes.map(node => [node.name, node]));
assert.equal(workflow.active, false);
assert.equal(nodes.size, 4);
for (const [source, outputs] of Object.entries(workflow.connections)) {
  assert.ok(nodes.has(source));
  for (const endpoint of outputs.main.flat()) assert.ok(nodes.has(endpoint.node));
}
const sample = new Function(nodes.get('Synthetic preview').parameters.jsCode)()[0].json;
const route = new Function('$input', nodes.get('Route verified audit').parameters.jsCode);
const evaluate = item => route({all: () => [{json: item}]})[0].json.route;
assert.equal(evaluate(sample), 'DEMO_ONLY');
const paid = structuredClone(sample);
paid.summary.outputMode = paid.overview.outputMode = 'audit';
paid.summary.eventName = 'migration-audited';
paid.summary.chargedEvents = 1;
paid.decision = 'HOLD_RELEASE';
assert.equal(evaluate(paid), 'HOLD_RELEASE');
paid.overview.flaggedUrls = 0;
paid.overview.outcome = 'clean';
paid.decision = 'READY_FOR_SIGN_OFF';
assert.equal(evaluate(paid), 'READY_FOR_SIGN_OFF');
assert.throws(() => evaluate({...paid, decision: 'HOLD_RELEASE'}));
assert.throws(() => evaluate({...paid, summary: {...paid.summary, chargedEvents: 0}}));
assert.throws(() => evaluate({...paid, overview: {...paid.overview, fullyTracedUrls: 0}}));
assert.throws(() => evaluate({...paid, overview: {...paid.overview, reportSha256: 'f'.repeat(64)}}));
console.log('Verified import JSON graph plus 7 JavaScript routes / rejection cases. No network.');
