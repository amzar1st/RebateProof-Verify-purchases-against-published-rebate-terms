import { test } from 'node:test';
import assert from 'node:assert/strict';
import { receiptState } from '../src/network.js';

test('accepted transactions are still pending finality', () => {
  assert.equal(receiptState({ statusName: 'ACCEPTED', txExecutionResult: 1 }).terminal, false);
});

test('finalized receipts distinguish success and failure', () => {
  assert.match(receiptState({ status: 'FINALIZED', txExecutionResult: 1 }).label, /succeeded/);
  assert.match(receiptState({ status: 'FINALIZED', txExecutionResultName: 'FINISHED_WITH_ERROR' }).label, /failed/);
  assert.match(receiptState({ status: 'FINALIZED' }).label, /unavailable/);
});

test('terminal consensus failures stop polling', () => {
  for (const statusName of ['CANCELED', 'UNDETERMINED', 'VALIDATORS_TIMEOUT', 'LEADER_TIMEOUT']) {
    assert.equal(receiptState({ statusName }).terminal, true);
  }
});

test('reads StudioNet legacy leader receipts without treating consensus agreement as execution success', () => {
  const legacy = (execution_result, statusName = 'FINALIZED') => ({
    statusName, result_name: 'MAJORITY_AGREE',
    consensus_data: { leader_receipt: [{ execution_result }] },
  });
  assert.match(receiptState(legacy('SUCCESS')).label, /succeeded/);
  assert.match(receiptState(legacy('ERROR')).label, /failed/);
  assert.equal(receiptState(legacy('ERROR', 'ACCEPTED')).terminal, false);
});
