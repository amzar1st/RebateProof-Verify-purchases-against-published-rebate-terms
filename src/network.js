export const explorer = 'https://explorer-studio.genlayer.com';
export const txHashPattern = /^0x[0-9a-fA-F]{64}$/;
export const recordPattern = /^[0-9a-f]{64}$/;
export const addressPattern = /^0x[0-9a-fA-F]{40}$/;

export const sources = 'https://raw.githubusercontent.com/amzar1st/RebateProof-Verify-purchases-against-published-rebate-terms/main/public/fixtures/';

export const fields = {
  lock_policy: [['Policy JSON URL', 'url'], ['Policy SHA-256', 'hash']],
  submit_claim: [['Policy ID', 'hash'], ['Approved seller', 'token'], ['Receipt JSON URL', 'url'], ['Receipt SHA-256', 'hash'], ['Listing JSON URL', 'url'], ['Listing SHA-256', 'hash']],
  review_claim: [['Claim ID', 'hash']],
};

export function receiptState(tx) {
  const stage = tx.statusName ?? tx.status;
  const legacyLeader = [tx.consensus_data?.leader_receipt].flat().filter(Boolean).at(-1);
  const execution = tx.txExecutionResultName ?? tx.txExecutionResult ?? legacyLeader?.execution_result;
  if (['CANCELED', 'UNDETERMINED', 'VALIDATORS_TIMEOUT', 'LEADER_TIMEOUT'].includes(stage)) {
    return { terminal: true, label: `Consensus ended · ${stage}` };
  }
  if (stage === 'FINALIZED') {
    if (['FINISHED_WITH_RETURN', 'SUCCESS', 1].includes(execution)) return { terminal: true, label: 'Finalized · contract execution succeeded' };
    if (['FINISHED_WITH_ERROR', 'ERROR', 2].includes(execution)) return { terminal: true, label: 'Finalized · contract execution failed' };
    return { terminal: true, label: 'Finalized · execution result unavailable' };
  }
  return { terminal: false, label: `Awaiting finality · ${stage ?? 'status unavailable'}` };
}
