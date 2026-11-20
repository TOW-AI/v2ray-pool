'use strict';

const apiBase = String(window.ENGINE_CONFIG?.apiBase || '../data/api/v1').replace(/\/$/, '');
const cache = { stats: null, configs: [], rankings: null, countries: null };

function element(id) { return document.getElementById(id); }
function setText(node, value) { node.textContent = value === null || value === undefined || value === '' ? 'Not measured' : String(value); }
function makeNode(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}
function formatTime(value) {
  if (!value) return 'Not measured';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Not measured' : `${date.toISOString().replace('T', ' ').replace('.000Z', ' UTC')}`;
}
async function loadJson(name) {
  const response = await fetch(`${apiBase}/${name}`, { cache: 'no-store', credentials: 'omit', redirect: 'error' });
  if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`);
  return response.json();
}
function renderSummary(stats) {
  const totals = stats.totals || {};
  const values = [
    ['Discovered', totals.discovered], ['Validated', totals.validated],
    ['Fixed verified', stats.statuses?.FIXED_VERIFIED], ['Rotating', stats.statuses?.ROTATING],
    ['Publishable', totals.publishable]
  ];
  const grid = element('summary-cards');
  grid.replaceChildren();
  for (const [label, value] of values) {
    const card = makeNode('article', 'metric-card');
    card.append(makeNode('span', '', label), makeNode('strong', '', value ?? '—'));
    grid.append(card);
  }
}
function renderStatuses(stats) {
  const grid = element('status-breakdown');
  grid.replaceChildren();
  const statuses = stats.statuses || {};
  for (const [status, count] of Object.entries(statuses)) {
    const item = makeNode('div', 'status-item');
    item.append(makeNode('span', '', status.replaceAll('_', ' ')), makeNode('strong', '', count));
    grid.append(item);
  }
}
function renderRanking(id, rows, key, unit) {
  const list = element(id);
  list.replaceChildren();
  if (!Array.isArray(rows) || rows.length === 0) {
    list.append(makeNode('li', '', 'No measured data'));
    return;
  }
  for (const row of rows.slice(0, 5)) {
    const value = key === 'latency_ms' ? `${row[key]} ${unit}` : `${row.score} points`;
    list.append(makeNode('li', '', `${row.config_id.slice(0, 18)} · ${value}`));
  }
}
function renderCountries(countries) {
  const select = element('country-filter');
  const first = makeNode('option', '', 'All countries');
  first.value = '';
  select.replaceChildren(first);
  for (const item of countries?.countries || []) {
    const option = makeNode('option', '', `${item.country_code} (${item.config_count})`);
    option.value = item.country_code;
    select.append(option);
  }
}
function renderEvidence() {
  const fixedList = element('fixed-evidence-list');
  const rotatingList = element('rotating-evidence-list');
  fixedList.replaceChildren();
  rotatingList.replaceChildren();
  const fixed = cache.configs.filter((item) => item.status === 'FIXED_VERIFIED');
  const rotating = cache.configs.filter((item) => item.status === 'ROTATING');
  if (!fixed.length) fixedList.append(makeNode('li', '', 'No verified evidence'));
  for (const item of fixed.slice(0, 10)) {
    const evidence = item.ip_evidence || {};
    const family = ['ipv4', 'ipv6'].find((name) => item.ip_status?.[name] === 'FIXED_VERIFIED');
    const data = family ? evidence[family] || {} : {};
    fixedList.append(makeNode('li', '', `${item.config_id.slice(0, 14)} · ${family || 'unknown'} · ${data.run_count ?? 0} Runs · ${formatTime(data.first_observed_at)} to ${formatTime(data.last_observed_at)}`));
  }
  if (!rotating.length) rotatingList.append(makeNode('li', '', 'No verified IP changes'));
  for (const item of rotating.slice(0, 10)) {
    const evidence = item.ip_evidence || {};
    const changes = ['ipv4', 'ipv6'].map((family) => `${family}: ${(evidence[family]?.distinct_ips || []).length} IPs / ${evidence[family]?.change_count ?? 0} changes`).join(' · ');
    rotatingList.append(makeNode('li', '', `${item.config_id.slice(0, 14)} · ${changes}`));
  }
}
function renderDistribution(stats, countries) {
  const countryList = element('country-list');
  const protocolList = element('protocol-list');
  countryList.replaceChildren();
  protocolList.replaceChildren();
  const countryRows = countries?.countries || [];
  if (!countryRows.length) countryList.append(makeNode('li', '', `No GeoIP data · ${countries?.unknown_count ?? 0} unknown`));
  for (const item of countryRows.slice(0, 20)) {
    countryList.append(makeNode('li', '', `${item.country_code} · ${item.config_count} configs · ${item.fixed_verified} fixed · ${item.rotating} rotating`));
  }
  const protocols = Object.entries(stats.protocols || {}).sort(([a], [b]) => a.localeCompare(b));
  if (!protocols.length) protocolList.append(makeNode('li', '', 'No protocol data'));
  for (const [protocol, count] of protocols) {
    protocolList.append(makeNode('li', '', `${protocol} · ${count}`));
  }
}
function renderConfigs() {
  const tbody = element('config-table');
  tbody.replaceChildren();
  const protocol = element('protocol-filter').value;
  const status = element('status-filter').value;
  const country = element('country-filter').value;
  const search = element('search-filter').value.trim().toLowerCase();
  const rows = cache.configs.filter((item) => {
    return (!protocol || item.protocol === protocol)
      && (!status || item.status === status)
      && (!country || item.country_code === country)
      && (!search || item.config_id.toLowerCase().includes(search));
  });
  if (!rows.length) {
    const row = makeNode('tr');
    const cell = makeNode('td', '', 'No configurations match these filters.');
    cell.colSpan = 6;
    row.append(cell);
    tbody.append(row);
    return;
  }
  for (const item of rows.slice(0, 200)) {
    const row = makeNode('tr');
    row.append(
      makeNode('td', '', item.config_id.slice(0, 20)),
      makeNode('td', '', item.protocol || 'Unknown'),
      makeNode('td', 'status-tag', item.status || 'Unknown'),
      makeNode('td', '', item.egress_ip || 'Not verified'),
      makeNode('td', '', item.metrics?.latency_ms === null || item.metrics?.latency_ms === undefined ? 'Not measured' : `${item.metrics.latency_ms} ms`),
      makeNode('td', '', formatTime(item.last_test_at))
    );
    tbody.append(row);
  }
}
function renderHealth(stats, configs, rankings) {
  const tests = stats.tests || {};
  const lines = [
    `Run ID: ${stats.run_id || 'Not available'}`,
    `Generated at: ${formatTime(stats.generated_at)}`,
    `Data age: ${stats.data_age_seconds ?? 'Not measured'} seconds`,
    `Tests: ${tests.successful ?? 0} successful, ${tests.failed ?? 0} failed, ${tests.skipped ?? 0} skipped`,
    `Ranked entries: ${rankings.fixed?.length ?? 0} fixed, ${rankings.rotating?.length ?? 0} rotating, ${rankings.fastest?.length ?? 0} fastest, ${rankings.balanced?.length ?? 0} balanced`,
    `Published configuration records: ${configs.length}`
  ];
  element('health-panel').replaceChildren(...lines.map((line) => makeNode('p', '', line)));
}
async function refresh() {
  const state = element('system-state');
  const error = element('error-panel');
  const stale = element('stale-panel');
  error.hidden = true;
  stale.hidden = true;
  state.className = 'state-pill state-unknown';
  setText(state, 'Loading');
  try {
    const [stats, configs, rankings, countries] = await Promise.all([
      loadJson('stats.json'), loadJson('configs.json'), loadJson('rankings.json'), loadJson('countries.json')
    ]);
    cache.stats = stats;
    cache.configs = Array.isArray(configs.configs) ? configs.configs : [];
    cache.rankings = rankings;
    cache.countries = countries;
    renderSummary(stats);
    renderStatuses(stats);
    renderRanking('fastest-list', rankings.fastest, 'latency_ms', 'ms');
    renderRanking('balanced-list', rankings.balanced, 'score');
    renderRanking('fixed-list', rankings.fixed, 'score');
    renderRanking('rotating-list', rankings.rotating, 'score');
    renderCountries(countries);
    renderEvidence();
    renderDistribution(stats, countries);
    renderConfigs();
    renderHealth(stats, cache.configs, rankings);
    setText(element('generated-at'), `Generated ${formatTime(stats.generated_at)}`);
    const maxAge = Number(window.ENGINE_CONFIG?.staleAfterSeconds || 21600);
    const generatedAt = new Date(stats.generated_at).getTime();
    const generatedAge = Number.isNaN(generatedAt) ? Number.POSITIVE_INFINITY : Math.max(0, (Date.now() - generatedAt) / 1000);
    if (generatedAge > maxAge || Number(stats.data_age_seconds || 0) > maxAge) {
      stale.hidden = false;
      setText(stale, 'The data is older than the configured freshness limit. Do not treat it as live status.');
      state.className = 'state-pill state-warning';
      setText(state, 'Stale data');
    } else {
      state.className = 'state-pill state-ok';
      setText(state, 'Data loaded');
    }
  } catch (err) {
    error.hidden = false;
    setText(error, `Data load failed. ${err.message}`);
    setText(state, 'Unavailable');
  }
}

for (const id of ['protocol-filter', 'status-filter', 'country-filter', 'search-filter']) {
  element(id).addEventListener('input', renderConfigs);
}
element('refresh-button').addEventListener('click', refresh);
refresh();
