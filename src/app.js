import { createClient } from 'genlayer-js';
import { studionet } from 'genlayer-js/chains';
import { addressPattern, explorer, fields, receiptState, recordPattern, sources, txHashPattern } from './network.js';

const client = createClient({ chain: studionet });
const byId = id => document.getElementById(id);
const lookup = byId('lookup');
const tracker = byId('tracker');
const prepare = byId('prepare');
let deployment = {};
let trackingRun = 0;

function element(tag, content, className) {
  const node = document.createElement(tag);
  node.textContent = content;
  if (className) node.className = className;
  return node;
}

function link(text, url) {
  const node = element('a', text);
  node.href = url;
  node.target = '_blank';
  node.rel = 'noopener';
  return node;
}

function showRecord(record) {
  const box = byId('record');
  if (record.decision) {
    const decision = record.decision;
    box.append(element('p', decision.status.replaceAll('_', ' '), 'record-status'));
    if (decision.currency) {
      const money = new Intl.NumberFormat(undefined, { style: 'currency', currency: decision.currency });
      const units = money.resolvedOptions().maximumFractionDigits;
      box.append(element('p', `${decision.model} · ${money.format(decision.rebate_minor / 10 ** units)}`));
    }
    for (const [clause, passed] of Object.entries(decision.clauses ?? {})) {
      box.append(element('p', `${clause.replaceAll('_', ' ')} · ${passed ? 'Pass' : 'Fail'}`));
    }
  }
  const sources = element('div', '', 'evidence');
  const urls = record.decision ? [['Receipt', record.receipt_url], ['Listing', record.listing_url]] : [['Policy', record.url]];
  for (const [label, url] of urls) {
    if (typeof url === 'string' && url.startsWith('https://')) sources.append(link(label + ' evidence ↗', url));
  }
  box.append(sources);
  const details = element('details', '');
  details.append(element('summary', 'View raw chain record'), element('pre', JSON.stringify(record, null, 2)));
  box.append(details);
}

lookup.addEventListener('submit', async event => {
  event.preventDefault();
  const button = lookup.querySelector('button');
  const status = byId('read-status');
  byId('record').replaceChildren();
  const data = new FormData(lookup);
  const address = data.get('address');
  const kind = data.get('kind');
  const id = data.get('id');
  if (!addressPattern.test(address) || !recordPattern.test(id) || !['claim', 'policy'].includes(kind)) return;
  button.disabled = true;
  status.textContent = 'Reading contract state…';
  try {
    const value = await client.readContract({ address, functionName: `get_${kind}`, args: [id], transactionHashVariant: 'latest-final' });
    if (!value) {
      status.textContent = 'No record found for that ID.';
      return;
    }
    const record = JSON.parse(value);
    if (record.id !== id) throw new Error('Returned record ID differs from the requested ID.');
    showRecord(record);
    status.textContent = 'Record returned from finalized StudioNet state.';
  } catch (error) {
    status.textContent = `Read failed. ${error.shortMessage ?? error.message}`;
  } finally {
    button.disabled = false;
  }
});

tracker.addEventListener('submit', async event => {
  event.preventDefault();
  const hash = new FormData(tracker).get('hash');
  if (!txHashPattern.test(hash)) return;
  const run = ++trackingRun;
  const status = byId('tx-status');
  status.textContent = 'Looking up transaction…';
  byId('tx-result').replaceChildren(link('Open in Studio Explorer ↗', `${explorer}/tx/${hash}`));
  for (let attempt = 0; attempt < 24; attempt++) {
    try {
      const tx = await client.getTransaction({ hash });
      if (run !== trackingRun) return;
      const state = receiptState(tx);
      status.textContent = state.label;
      if (state.terminal) return;
    } catch {
      if (run !== trackingRun) return;
      status.textContent = 'StudioNet has not returned a receipt. Retrying…';
    }
    await new Promise(resolve => setTimeout(resolve, 5000));
    if (run !== trackingRun) return;
  }
  status.textContent = 'Polling paused. Check the same hash again to resume.';
});

function renderInputs() {
  const args = byId('args');
  args.replaceChildren();
  byId('arguments').replaceChildren();
  byId('prepare-status').textContent = '';
  for (const [name, type] of fields[prepare.elements.method.value]) {
    const label = element('label', name);
    const input = document.createElement('input');
    input.required = true;
    input.dataset.kind = type;
    input.maxLength = type === 'url' ? 400 : type === 'token' ? 40 : 64;
    if (type === 'url') input.type = 'url';
    if (type === 'hash') input.pattern = '[a-f0-9]{64}';
    if (type === 'token') input.pattern = '[A-Z0-9][A-Z0-9\\-]{0,39}';
    label.append(input);
    args.append(label);
  }
}

async function fixtureHash(path) {
  const response = await fetch(`/fixtures/${path}`);
  if (!response.ok) throw new Error('Fixture unavailable');
  const bytes = await crypto.subtle.digest('SHA-256', await response.arrayBuffer());
  return [...new Uint8Array(bytes)].map(byte => byte.toString(16).padStart(2, '0')).join('');
}

prepare.elements.method.addEventListener('change', renderInputs);
byId('load-demo').addEventListener('click', async () => {
  const method = prepare.elements.method.value;
  const status = byId('prepare-status');
  try {
    const values = {
      lock_policy: async () => [`${sources}policy.json`, await fixtureHash('policy.json')],
      submit_claim: async () => [deployment.policyId, 'NORTHLINE', `${sources}receipts/pro.json`, await fixtureHash('receipts/pro.json'), `${sources}listings/pro.json`, await fixtureHash('listings/pro.json')],
      review_claim: async () => [deployment.claims?.[0]?.id],
    };
    const args = await values[method]();
    if (method !== prepare.elements.method.value) return;
    [...byId('args').querySelectorAll('input')].forEach((input, index) => { input.value = args[index] ?? ''; });
    status.textContent = args.some(arg => !arg) ? 'Fill in the ID from your Studio transaction.' : 'Example loaded. Demo receipts are tied to the demo claimant address.';
  } catch {
    status.textContent = 'Could not load example evidence.';
  }
});

prepare.addEventListener('submit', event => {
  event.preventDefault();
  const args = [...byId('args').querySelectorAll('input')];
  const method = prepare.elements.method.value;
  const list = byId('arguments');
  list.replaceChildren();
  if (args.some(input => input.dataset.kind === 'url' && !input.value.startsWith('https://'))) {
    byId('prepare-status').textContent = 'Evidence URLs must use HTTPS.';
    return;
  }
  byId('prepare-status').textContent = `In Studio Run and Debug, open ${method} under Write Methods and enter these arguments in order.`;
  for (const [index, input] of args.entries()) {
    const item = element('li', fields[method][index][0]);
    const copy = element('button', 'Copy', 'button secondary');
    copy.type = 'button';
    copy.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(input.value);
        copy.textContent = 'Copied';
      } catch {
        copy.textContent = 'Select the value to copy';
      }
    });
    item.append(element('code', input.value, 'argument'), copy);
    list.append(item);
  }
});

async function initialize() {
  renderInputs();
  try {
    const response = await fetch('/deployment.json', { cache: 'no-cache' });
    if (!response.ok) throw new Error('Missing deployment configuration');
    deployment = await response.json();
    if (deployment.chainId !== studionet.id || !addressPattern.test(deployment.address)) {
      byId('network').textContent = 'No default contract configured. Enter a StudioNet deployment address to read it.';
      return;
    }
    lookup.elements.address.value = deployment.address;
    byId('network').textContent = 'Chain 61999 · ';
    byId('network').append(link('View contract ↗', `${explorer}/address/${deployment.address}`));
    if (txHashPattern.test(deployment.deploymentHash)) {
      byId('network').append(' · ', link('Deployment ↗', `${explorer}/tx/${deployment.deploymentHash}`));
      tracker.elements.hash.value = deployment.deploymentHash;
    }
    const transactions = [
      ...(deployment.claims ?? []).map(claim => [claim.label + ' review', claim.reviewHash]),
      ['Rejected review', deployment.rejectedReviewHash],
    ];
    for (const [label, hash] of transactions.filter(([, hash]) => txHashPattern.test(hash))) {
      const button = element('button', label, 'button secondary');
      button.type = 'button';
      button.addEventListener('click', () => {
        tracker.elements.hash.value = hash;
        tracker.requestSubmit();
      });
      byId('transaction-examples').append(button);
    }
    const records = [{ id: deployment.policyId, label: 'Locked policy', kind: 'policy' },
      ...(deployment.claims ?? []).map(claim => ({ ...claim, kind: 'claim' }))];
    for (const record of records.filter(record => recordPattern.test(record.id))) {
      const button = element('button', record.label, 'button secondary');
      button.type = 'button';
      button.addEventListener('click', () => {
        lookup.elements.kind.value = record.kind;
        lookup.elements.id.value = record.id;
        lookup.requestSubmit();
      });
      byId('live-records').append(button);
    }
  } catch {
    byId('network').textContent = 'Deployment configuration unavailable.';
  }
}

initialize();
