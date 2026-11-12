import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { createClient } from 'genlayer-js';
import { studionet } from 'genlayer-js/chains';
import { receiptState } from '../src/network.js';

const deployment = JSON.parse(await readFile(new URL('../public/deployment.json', import.meta.url)));
const source = await readFile(new URL('../contracts/rebate_proof.py', import.meta.url));
const client = createClient({ chain: studionet });
const { address } = deployment;
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');

assert.equal(await client.getChainId(), deployment.chainId);
const code = await client.getContractCode(address);
const deployed = code.startsWith('0x') ? Buffer.from(code.slice(2), 'hex') : Buffer.from(code);
assert.deepEqual(deployed, source);
assert.equal(sha256(deployed), deployment.sourceSha256);
console.log('Deployed source matches repository SHA-256');

const checks = [
  [deployment.deploymentHash, 'succeeded'], [deployment.policyHash, 'succeeded'],
  ...deployment.claims.flatMap(claim => [[claim.submitHash, 'succeeded'], [claim.reviewHash, 'succeeded']]),
  [deployment.rejectedReviewHash, 'failed'],
];
await Promise.all(checks.map(async ([hash, expected]) => {
  const tx = await client.getTransaction({ hash });
  assert.equal(tx.statusName ?? tx.status, 'FINALIZED');
  assert.equal((tx.to_address ?? tx.recipient).toLowerCase(), address.toLowerCase());
  assert.equal(tx.leader_only, false);
  assert.match(receiptState(tx).label, new RegExp(expected));
  console.log(hash, expected);
}));

const read = async (functionName, id) => JSON.parse(await client.readContract({
  address, functionName, args: [id], transactionHashVariant: 'latest-final',
}));
const policy = await read('get_policy', deployment.policyId);
assert.equal(policy.id, deployment.policyId);
assert.equal(policy.rules.models['AER-2400-PRO'], 15000);

for (const example of deployment.claims) {
  const record = await read('get_claim', example.id);
  assert.equal(record.policy_id, deployment.policyId);
  assert.equal(record.decision.model, example.label);
  assert.equal(record.decision.status, example.status);
  assert.equal(record.decision.rebate_minor, example.rebateMinor);
  assert.equal(record.decision.clauses['1.model'], example.status === 'ELIGIBLE');
  assert.equal(record.decision_sha256, example.decisionSha256);
  assert.equal(record.attempts, 1);
  console.log(record.decision.model, record.decision.status, record.decision.rebate_minor);
}
