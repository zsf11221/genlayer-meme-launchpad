import { createClient, createAccount } from 'genlayer-js';
import { studionet } from 'genlayer-js/chains';
import { TransactionStatus, TransactionHashVariant } from 'genlayer-js/types';
import { I18N } from './i18n.js';

// ---------- constants (verified on-chain, see evidence/live-verification.md) ----------
const CONTRACT = '0x26Ad5661901355C952a2109c53eAe6A5BdBE93D8';
const EXPLORER = 'https://explorer-studio.genlayer.com';
const CHAIN_ID = 61999;
const CHAIN_ID_HEX = '0xf223';
const RPC_URL = 'https://studio.genlayer.com/api';
const MICRO = 1000000n;
const CURVE_SUPPLY = 793100000n;
const K = 30000000n * CURVE_SUPPLY; // constant product
const LAUNCH_PRICE_RAW = 37826n; // microGEN per token, scaled by 1e6, at launch
const GRADUATION_NET = 85000000n;

const $ = (id) => document.getElementById(id);
const readClient = createClient({ chain: studionet });

// ---------- i18n ----------
let lang = localStorage.getItem('ml-lang') || 'zh';
const t = (key, vars) => {
  let s = (I18N[lang] && I18N[lang][key]) ?? I18N.en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s;
};
const fmtInt = (n) => new Intl.NumberFormat(lang === 'zh' ? 'zh-CN' : 'en-US').format(n);
const fmtNum = (n, d = 2) => new Intl.NumberFormat(lang === 'zh' ? 'zh-CN' : 'en-US', { minimumFractionDigits: d, maximumFractionDigits: d }).format(n);

function applyLang(next) {
  lang = next;
  localStorage.setItem('ml-lang', lang);
  document.documentElement.lang = lang === 'zh' ? 'zh' : 'en';
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  $('lang-en').setAttribute('aria-pressed', String(lang === 'en'));
  $('lang-zh').setAttribute('aria-pressed', String(lang === 'zh'));
  renderAll();
}

// ---------- state ----------
const state = {
  listings: [], // {id,name,symbol,description,evidence,creator,status,review_reason,review_history,gen_reserve,token_reserve,net_bought,sold_tokens,creator_fees,platform_fees,fill_pct_bp}
  prices: {}, // id -> raw price string
  selectedId: '1',
  mode: 'buy',
  signer: null, // {kind:'wallet', address, provider} | {kind:'test', account}
  testAccount: null,
  balances: { gen: null, tokens: null },
  feed: [],
  updatedAt: null,
};

const shortAddr = (a) => (a ? `${a.slice(0, 6)}…${a.slice(-4)}` : '—');
const txUrl = (h) => `${EXPLORER}/tx/${h}`;
const fmtMicroGen = (micro) => fmtNum(Number(micro) / 1e6, 6); // microGEN -> GEN with 6dp
const priceMicroPerToken = (raw) => Number(raw) / 1e6; // raw scaled by 1e6 -> microGEN per token
const fillPct = (bp) => Number(bp) / 100;

// ---------- toast ----------
let toastTimer = null;
function toast(msg) {
  const el = $('toast');
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 4500);
}

// ---------- chain reads ----------
function asArray(v) {
  if (Array.isArray(v)) return v;
  if (v && typeof v === 'object') return Object.values(v);
  return [];
}
function asObject(v) {
  if (v instanceof Map) return Object.fromEntries(v);
  return v && typeof v === 'object' ? v : {};
}

async function readView(fn, args) {
  return readClient.readContract({
    address: CONTRACT,
    functionName: fn,
    args,
    transactionHashVariant: TransactionHashVariant.LATEST_FINAL,
  });
}

async function loadBoard() {
  try {
    const raw = await readView('list_listings', []);
    const obj = asObject(raw);
    const listings = Object.values(obj).map(asObject).sort((a, b) => Number(a.id) - Number(b.id));
    const prices = {};
    for (const l of listings) {
      try { prices[l.id] = String(await readView('get_price', [String(l.id)])); } catch { prices[l.id] = '0'; }
    }
    state.listings = listings;
    state.prices = prices;
    state.updatedAt = new Date();
    if (!listings.find((l) => String(l.id) === state.selectedId) && listings.length) {
      state.selectedId = String(listings[0].id);
    }
    renderAll();
  } catch (e) {
    console.error('loadBoard', e);
    const body = $('lb-body');
    body.innerHTML = `<tr><td colspan="6" class="empty">${t('board.loadFailed')}</td></tr>`;
    toast(t('trade.networkError'));
  }
}

async function refreshBalances() {
  if (!state.signer) {
    $('balance-line').textContent = t('balance.noWallet');
    return;
  }
  const addr = state.signer.address;
  try {
    const gen = await readView('get_gen_balance', [addr]);
    const tok = await readView('get_token_balance', [state.selectedId, addr]);
    state.balances = { gen: BigInt(String(gen)), tokens: BigInt(String(tok)) };
    const listing = selectedListing();
    $('balance-line').textContent =
      t('balance.gen', { gen: fmtMicroGen(state.balances.gen) }) +
      (listing ? t('balance.tokens', { tokens: fmtInt(state.balances.tokens), symbol: listing.symbol }) : '');
  } catch (e) {
    console.error('balances', e);
  }
}

const selectedListing = () => state.listings.find((l) => String(l.id) === state.selectedId);

// ---------- rendering ----------
function renderAll() {
  renderHero();
  renderPickers();
  renderBoard();
  renderDetail();
  renderPreview();
  renderSignerLine();
  if (state.updatedAt) {
    const time = state.updatedAt.toLocaleTimeString(lang === 'zh' ? 'zh-CN' : 'en-US');
    $('updated-line').textContent = t('board.updated', { time });
    $('foot-updated').textContent = t('board.updated', { time });
  }
}

function renderHero() {
  const l = selectedListing();
  if (!l) {
    $('hero-name').textContent = '—';
    $('hero-price').textContent = '—';
    $('hero-mult').textContent = '—';
    $('hero-fill').textContent = '—';
    return;
  }
  const raw = BigInt(state.prices[l.id] || '0');
  $('hero-name').textContent = l.name;
  $('hero-desc').textContent = l.description || '';
  $('hero-count').textContent = `#${l.id} ${l.symbol}`;
  const chip = $('hero-status');
  chip.textContent = l.status;
  chip.className = `chip chip-${l.status.toLowerCase().replace('_review', '-pending').replace('pending_review', 'pending')}`;
  $('hero-price').textContent = fmtNum(priceMicroPerToken(raw), 6);
  const mult = raw > 0n ? Number(raw) / Number(LAUNCH_PRICE_RAW) : 0;
  $('hero-mult').textContent = `×${fmtNum(mult, 2)}`;
  $('hero-fill').textContent = `${fmtNum(fillPct(l.fill_pct_bp), 2)}%`;
  drawCurve();
}

function renderPickers() {
  const wrap = $('listing-pickers');
  wrap.innerHTML = '';
  for (const l of state.listings) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'picker';
    b.textContent = `#${l.id} ${l.symbol}`;
    b.setAttribute('aria-pressed', String(String(l.id) === state.selectedId));
    b.addEventListener('click', () => {
      state.selectedId = String(l.id);
      renderAll();
      refreshBalances();
    });
    wrap.appendChild(b);
  }
}

function renderBoard() {
  const body = $('lb-body');
  if (!state.listings.length) {
    body.innerHTML = `<tr><td colspan="6" class="empty">${t('board.loading')}</td></tr>`;
    return;
  }
  const rows = [...state.listings].sort((a, b) => Number(b.fill_pct_bp) - Number(a.fill_pct_bp));
  body.innerHTML = '';
  rows.forEach((l, i) => {
    const tr = document.createElement('tr');
    if (String(l.id) === state.selectedId) tr.classList.add('sel');
    const raw = BigInt(state.prices[l.id] || '0');
    tr.innerHTML = `<td>${i + 1}</td>
      <td class="name-cell">${escapeHtml(l.name)}<small>${escapeHtml(l.symbol)} · #${l.id}</small></td>
      <td><span class="chip chip-${l.status.toLowerCase().replace('pending_review', 'pending')}">${l.status}</span></td>
      <td>${fmtNum(priceMicroPerToken(raw), 4)} μGEN</td>
      <td>${fmtNum(fillPct(l.fill_pct_bp), 2)}%</td>
      <td>${fmtMicroGen(BigInt(l.net_bought || '0'))} GEN</td>`;
    tr.addEventListener('click', () => {
      state.selectedId = String(l.id);
      renderAll();
      refreshBalances();
      document.getElementById('trade').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    body.appendChild(tr);
  });
}

function renderDetail() {
  const l = selectedListing();
  if (!l) return;
  $('detail-name').textContent = `#${l.id} ${l.name} (${l.symbol})`;
  $('detail-creator').textContent = l.creator || '—';
  $('detail-review').textContent = l.status === 'PENDING_REVIEW'
    ? t('detail.notDecided')
    : `${l.status} · ${l.review_reason || ''}`.trim();
  $('detail-sold').textContent = `${fmtInt(BigInt(l.sold_tokens || '0'))} / ${fmtInt(CURVE_SUPPLY)}`;
  const fees = BigInt(l.creator_fees || '0') + BigInt(l.platform_fees || '0');
  $('detail-fees').textContent = fees > 0n
    ? `${fmtMicroGen(fees)} GEN (${t('trade.previewFee')} 1%)`
    : t('detail.noFees');
  $('detail-history').textContent = (l.review_history || '').replaceAll('\n', ' → ') || '—';
  $('detail-evidence').textContent = l.evidence || '—';
  const srcEl = $('detail-evidence-source');
  srcEl.innerHTML = '';
  if (l.evidence_source) {
    const a = document.createElement('a');
    a.href = l.evidence_source;
    a.target = '_blank';
    a.rel = 'noopener';
    a.textContent = l.evidence_source;
    srcEl.appendChild(a);
  } else {
    srcEl.textContent = '—';
  }
  $('review-btn').hidden = l.status !== 'PENDING_REVIEW';
  $('graduate-btn').hidden = l.status !== 'LISTED';
}

function renderSignerLine() {
  const el = $('signer-line');
  if (!state.signer) { el.textContent = ''; return; }
  if (state.signer.kind === 'wallet') {
    el.textContent = `${t('wallet.connected')}: ${state.signer.address}`;
  } else {
    el.innerHTML = '';
    const span = document.createElement('span');
    span.textContent = `${t('wallet.testAccount')}: ${state.signer.address} — ${t('trade.testAccountNote')}`;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-ghost';
    btn.style.marginLeft = '0.6rem';
    btn.textContent = t('wallet.discardTest');
    btn.addEventListener('click', discardTestAccount);
    el.append(span, btn);
  }
}

function escapeHtml(s) {
  return String(s ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
}

// ---------- curve chart (the trade surface) ----------
function curvePoint(sold) {
  // sold: BigInt tokens sold -> {x: 0..100, y: 0..100, priceRaw: BigInt}
  const tokenReserve = CURVE_SUPPLY - sold;
  const genReserve = K / tokenReserve;
  const priceRaw = (genReserve * MICRO) / tokenReserve;
  return { priceRaw, genReserve, tokenReserve };
}

function drawCurve() {
  const l = selectedListing();
  const svg = $('curve-svg');
  if (!l) return;
  const soldNow = BigInt(l.sold_tokens || '0');
  const maxSold = (CURVE_SUPPLY * 97n) / 100n;
  const pMin = curvePoint(0n).priceRaw;
  const pMax = curvePoint(maxSold).priceRaw;
  const yOf = (p) => {
    const s = Math.sqrt(Number(p));
    const sMin = Math.sqrt(Number(pMin));
    const sMax = Math.sqrt(Number(pMax));
    return 96 - ((s - sMin) / (sMax - sMin)) * 88;
  };
  const xOf = (s) => (Number(s) / Number(maxSold)) * 100;
  let line = '';
  let area = '';
  const steps = 60;
  for (let i = 0; i <= steps; i++) {
    const s = (maxSold * BigInt(i)) / BigInt(steps);
    const p = curvePoint(s).priceRaw;
    const x = xOf(s).toFixed(2);
    const y = yOf(p).toFixed(2);
    line += `${i === 0 ? 'M' : 'L'}${x} ${y} `;
    area += `${i === 0 ? `M${x} 100 L${x} ${y}` : `L${x} ${y}`} `;
  }
  area += `L100 100 Z`;
  $('curve-line').setAttribute('d', line.trim());
  $('curve-area').setAttribute('d', area.trim());
  const now = curvePoint(soldNow);
  const nx = xOf(soldNow > maxSold ? maxSold : soldNow);
  const ny = yOf(now.priceRaw);
  const v = $('curve-now-v');
  const h = $('curve-now-h');
  v.setAttribute('x1', nx); v.setAttribute('x2', nx); v.setAttribute('y1', ny); v.setAttribute('y2', 100);
  h.setAttribute('x1', 0); h.setAttribute('x2', nx); h.setAttribute('y1', ny); h.setAttribute('y2', ny);
  positionHandleFromAmount();
  $('curve-pos').textContent = t('curve.pos', {
    sold: fmtInt(soldNow),
    price: fmtNum(priceMicroPerToken(now.priceRaw), 4),
  });
  // grid ticks
  const grid = $('curve-grid');
  grid.innerHTML = '';
  for (const f of [0.25, 0.5, 0.75]) {
    const ln = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    ln.setAttribute('x1', (f * 100).toFixed(1)); ln.setAttribute('x2', (f * 100).toFixed(1));
    ln.setAttribute('y1', 4); ln.setAttribute('y2', 97);
    ln.setAttribute('stroke', 'rgba(22,36,28,0.12)'); ln.setAttribute('stroke-width', '0.3');
    grid.appendChild(ln);
  }
}

function positionHandleFromAmount() {
  const l = selectedListing();
  if (!l) return;
  const micro = parseGenToMicro($('amount').value);
  const soldNow = BigInt(l.sold_tokens || '0');
  const genNow = BigInt(l.gen_reserve || '30000000');
  let targetSold = soldNow;
  if (state.mode === 'buy' && micro && micro > 0n) {
    const fee = micro / 100n;
    const newGen = genNow + (micro - fee);
    const newTok = K / newGen;
    targetSold = CURVE_SUPPLY - newTok;
  } else if (state.mode === 'sell') {
    const tok = parseTokenAmount($('amount').value);
    if (tok && tok > 0n) targetSold = soldNow - (tok > soldNow ? soldNow : tok);
  }
  const maxSold = (CURVE_SUPPLY * 97n) / 100n;
  const clamped = targetSold < 0n ? 0n : targetSold > maxSold ? maxSold : targetSold;
  const x = (Number(clamped) / Number(maxSold)) * 100;
  const p = curvePoint(clamped).priceRaw;
  const pMin = curvePoint(0n).priceRaw;
  const pMax = curvePoint(maxSold).priceRaw;
  const y = 96 - ((Math.sqrt(Number(p)) - Math.sqrt(Number(pMin))) / (Math.sqrt(Number(pMax)) - Math.sqrt(Number(pMin)))) * 88;
  const handle = $('curve-handle');
  handle.setAttribute('transform', `translate(${x.toFixed(2)} ${y.toFixed(2)})`);
  handle.setAttribute('aria-valuenow', String(Math.round((Number(clamped) / Number(maxSold)) * 100)));
}

// ---------- amount parsing (string math only, no floats) ----------
function parseGenToMicro(str) {
  const s = String(str ?? '').trim();
  const m = /^(\d+)(?:\.(\d{1,6}))?$/.exec(s);
  if (!m) return null;
  const frac = (m[2] || '').padEnd(6, '0');
  return BigInt(m[1]) * MICRO + BigInt(frac || '0');
}
function parseTokenAmount(str) {
  const s = String(str ?? '').trim();
  if (!/^\d+$/.exec(s)) return null;
  return BigInt(s);
}

// ---------- preview (local only, labelled as such) ----------
function renderPreview() {
  const l = selectedListing();
  if (!l) return;
  const outEl = $('preview-out');
  const feeEl = $('preview-fee');
  const genR = BigInt(l.gen_reserve || '30000000');
  const tokR = BigInt(l.token_reserve || '793100000');
  if (state.mode === 'buy') {
    const micro = parseGenToMicro($('amount').value);
    if (!micro || micro <= 0n) { outEl.textContent = '—'; feeEl.textContent = '—'; return; }
    const fee = micro / 100n;
    const newGen = genR + (micro - fee);
    const out = tokR - K / newGen;
    if (out <= 0n) { outEl.textContent = t('trade.tooSmall'); feeEl.textContent = '—'; return; }
    outEl.textContent = `${fmtInt(out)} ${l.symbol}`;
    feeEl.textContent = `${fmtMicroGen(fee)} GEN`;
  } else {
    const tok = parseTokenAmount($('amount').value);
    if (!tok || tok <= 0n) { outEl.textContent = '—'; feeEl.textContent = '—'; return; }
    const newTok = tokR + tok;
    const gross = genR - K / newTok;
    if (gross <= 0n) { outEl.textContent = t('trade.tooSmall'); feeEl.textContent = '—'; return; }
    const fee = gross / 100n;
    outEl.textContent = `${fmtMicroGen(gross - fee)} GEN`;
    feeEl.textContent = `${fmtMicroGen(fee)} GEN`;
  }
}

// ---------- wallet ----------
function injectedProvider() {
  return typeof window !== 'undefined' ? window.ethereum : undefined;
}

async function connectWallet() {
  const provider = injectedProvider();
  if (!provider) {
    toast(t('wallet.noWallet'));
    offerTestAccount();
    return;
  }
  try {
    const accounts = await provider.request({ method: 'eth_requestAccounts' });
    const address = accounts && accounts[0];
    if (!address) throw new Error('no account');
    state.signer = { kind: 'wallet', address, provider };
    $('wallet-btn').textContent = shortAddr(address);
    renderSignerLine();
    await ensureChain(provider);
    await refreshBalances();
    toast(t('wallet.connected'));
  } catch (e) {
    console.error('connectWallet', e);
    if (isUserRejection(e)) toast(t('wallet.userRejected'));
    else toast(t('wallet.connectFailed'));
  }
}

async function ensureChain(provider) {
  const chainId = await provider.request({ method: 'eth_chainId' });
  if (Number(chainId) === CHAIN_ID) return;
  try {
    await provider.request({
      method: 'wallet_switchEthereumChain',
      params: [{ chainId: CHAIN_ID_HEX }],
    });
  } catch (e) {
    if (e && (e.code === 4902 || String(e.message || '').includes('4902'))) {
      try {
        await provider.request({
          method: 'wallet_addEthereumChain',
          params: [{
            chainId: CHAIN_ID_HEX,
            chainName: 'GenLayer Stable Studionet',
            rpcUrls: [RPC_URL],
            blockExplorerUrls: [EXPLORER],
            nativeCurrency: { name: 'GEN', symbol: 'GEN', decimals: 18 },
          }],
        });
      } catch (addErr) {
        throw new Error('switch-failed');
      }
    } else if (isUserRejection(e)) {
      throw e;
    } else {
      throw new Error('switch-failed');
    }
  }
  const after = await provider.request({ method: 'eth_chainId' });
  if (Number(after) !== CHAIN_ID) throw new Error('switch-failed');
}

function offerTestAccount() {
  if (state.signer) return;
  if (!confirm(t('wallet.useTest') + '?\n\n' + t('trade.testAccountNote'))) return;
  createTestAccount();
}

function createTestAccount() {
  const account = createAccount();
  state.testAccount = account;
  state.signer = { kind: 'test', address: account.address, account };
  $('wallet-btn').textContent = `${t('wallet.testAccount')}: ${shortAddr(account.address)}`;
  renderSignerLine();
  refreshBalances();
  toast(t('toast.testAccountCreated'));
}

function discardTestAccount() {
  state.testAccount = null;
  if (state.signer && state.signer.kind === 'test') {
    state.signer = null;
    $('wallet-btn').textContent = t('wallet.connect');
    renderSignerLine();
    refreshBalances();
    toast(t('toast.testAccountDiscarded'));
  }
}

function isUserRejection(e) {
  const m = String((e && (e.message || e)) || '').toLowerCase();
  return e?.code === 4001 || m.includes('user denied') || m.includes('user rejected') || m.includes('rejected the request');
}

// ---------- writes: submit -> wait FINALIZED -> read back ----------
function setSteps(stage) {
  // stage: null | 'submit' | 'consensus' | 'final'
  const ol = $('tx-steps');
  if (!stage) { ol.hidden = true; return; }
  ol.hidden = false;
  const order = ['submit', 'consensus', 'final'];
  const idx = order.indexOf(stage);
  ol.querySelectorAll('li').forEach((li) => {
    const i = order.indexOf(li.dataset.step);
    li.classList.toggle('on', i === idx);
    li.classList.toggle('done', i < idx);
  });
}

function friendlyError(e, fallbackKey = 'trade.generic') {
  const m = String((e && (e.message || e)) || '');
  if (isUserRejection(e)) return t('wallet.userRejected');
  if (/switch-failed/.test(m)) return t('wallet.switchFailed');
  if (/Insufficient GEN/i.test(m)) return t('trade.insufficient');
  if (/not tradable/i.test(m)) return t('trade.notTradable');
  if (/already claimed/i.test(m)) return t('trade.alreadyClaimed');
  if (/already reviewed/i.test(m)) return t('review.failed');
  if (/Graduation needs/i.test(m)) return t('graduate.failed');
  if (/network|fetch|Failed to fetch|ECONN/i.test(m)) return t('trade.networkError');
  return t(fallbackKey);
}

function addFeedEntry({ method, hash, note, state: st }) {
  const entry = { method, hash, note, state: st, time: new Date() };
  state.feed.unshift(entry);
  renderFeed();
  return entry;
}

function renderFeed() {
  const ul = $('tx-feed');
  ul.innerHTML = '';
  if (!state.feed.length) {
    const li = document.createElement('li');
    li.className = 'empty';
    li.textContent = t('activity.empty');
    ul.appendChild(li);
    return;
  }
  for (const e of state.feed) {
    const li = document.createElement('li');
    const stateLabel = e.state === 'final' ? t('steps.final')
      : e.state === 'wait' ? t('steps.consensus')
      : e.state === 'error' ? t('trade.failed') : e.state;
    const stateClass = e.state === 'final' ? 'final' : e.state === 'wait' ? 'wait' : 'err';
    li.innerHTML = `<span class="tx-method">${escapeHtml(e.method)}</span>
      <span class="tx-state ${stateClass}">${escapeHtml(stateLabel)}</span>
      <span>${escapeHtml(e.note || '')}</span>
      ${e.hash ? `<a class="tx-hash" href="${txUrl(e.hash)}" target="_blank" rel="noopener">${e.hash.slice(0, 10)}…${e.hash.slice(-6)} ↗</a>` : ''}
      <span class="tx-time">${e.time.toLocaleTimeString(lang === 'zh' ? 'zh-CN' : 'en-US')}</span>`;
    ul.appendChild(li);
  }
}

async function runWrite({ method, args, successNote, readBack }) {
  if (!state.signer) {
    $('trade-error').hidden = false;
    $('trade-error').textContent = t('trade.needSigner');
    offerTestAccount();
    throw new Error('no-signer');
  }
  const signer = state.signer;
  // Wallet: make sure we are on Studionet before signing.
  if (signer.kind === 'wallet') {
    try { await ensureChain(signer.provider); }
    catch (e) {
      const msg = isUserRejection(e) ? t('wallet.userRejected') : t('wallet.switchFailed');
      throw new Error(msg);
    }
  }
  const account = signer.kind === 'wallet' ? signer.address : signer.account;
  const writeClient = createClient({
    chain: studionet,
    account,
    ...(signer.kind === 'wallet' ? { provider: signer.provider } : {}),
  });
  setSteps('submit');
  $('tx-status').textContent = t('trade.submitted');
  let hash;
  try {
    hash = await writeClient.writeContract({
      account,
      address: CONTRACT,
      functionName: method,
      args,
      value: 0n,
    });
  } catch (e) {
    setSteps(null);
    $('tx-status').textContent = '';
    throw new Error(friendlyError(e));
  }
  const entry = addFeedEntry({ method, hash, note: '', state: 'wait' });
  $('tx-status').innerHTML = `${t('trade.waiting')} <a href="${txUrl(hash)}" target="_blank" rel="noopener">${hash.slice(0, 10)}…${hash.slice(-6)} ↗</a>`;
  setSteps('consensus');
  try {
    const receipt = await readClient.waitForTransactionReceipt({
      hash,
      status: TransactionStatus.FINALIZED,
      interval: 10000,
      retries: 150,
    });
    const exec = receipt?.txExecutionResult ?? receipt?.execution_result ?? receipt?.executionResult;
    const failedExec = typeof exec === 'string' && !/success/i.test(exec);
    setSteps('final');
    entry.state = failedExec ? 'error' : 'final';
    // Read back: the durable proof, whatever the receipt shape says.
    let note = successNote || '';
    try {
      if (readBack) note = await readBack();
    } catch { /* read-back failure is reported below by the refresh */ }
    entry.note = note;
    renderFeed();
    await loadBoard();
    await refreshBalances();
    $('tx-status').textContent = failedExec
      ? t('trade.failed')
      : `${t('trade.finalized')} ${note ? t('trade.readback', { text: note }) : ''}`;
    if (failedExec) throw new Error(t('trade.failed'));
    return { hash, receipt };
  } catch (e) {
    if (String(e.message || '').includes(t('trade.failed'))) throw e;
    entry.state = 'wait';
    renderFeed();
    setSteps('consensus');
    $('tx-status').textContent = t('trade.timeout');
    throw new Error(t('trade.timeout'));
  }
}

// ---------- trade form ----------
function setMode(mode) {
  state.mode = mode;
  $('mode-buy').classList.toggle('active', mode === 'buy');
  $('mode-sell').classList.toggle('active', mode === 'sell');
  $('mode-buy').dataset.mode = 'buy';
  $('amount-label').textContent = mode === 'buy' ? 'Amount (GEN)' : 'Amount (tokens)';
  $('amount-unit').textContent = mode === 'buy' ? 'GEN' : selectedListing()?.symbol || '';
  $('trade-submit').textContent = t(mode === 'buy' ? 'trade.submitBuy' : 'trade.submitSell');
  $('amount').value = mode === 'buy' ? '1' : '100000';
  renderPreview();
  positionHandleFromAmount();
}

async function onTrade(e) {
  e.preventDefault();
  const errEl = $('trade-error');
  errEl.hidden = true;
  const l = selectedListing();
  if (!l || l.status !== 'LISTED') {
    errEl.hidden = false;
    errEl.textContent = t('trade.notTradable');
    return;
  }
  const btn = $('trade-submit');
  btn.disabled = true;
  try {
    if (state.mode === 'buy') {
      const micro = parseGenToMicro($('amount').value);
      if (!micro || micro <= 0n) throw new Error(t('trade.amountInvalid'));
      if (state.signer) {
        await refreshBalances();
        if (state.balances.gen !== null && state.balances.gen < micro) throw new Error(t('trade.claimFirst'));
      }
      const before = BigInt(l.sold_tokens || '0');
      await runWrite({
        method: 'buy',
        args: [String(l.id), micro.toString()],
        successNote: '',
        readBack: async () => {
          const after = asObject(await readView('get_listing', [String(l.id)]));
          const got = BigInt(after.sold_tokens || '0') - before;
          return t('activity.bought', { out: fmtInt(got) });
        },
      });
      toast(t('trade.finalized'));
    } else {
      const tok = parseTokenAmount($('amount').value);
      if (!tok || tok <= 0n) throw new Error(t('trade.amountInvalid'));
      const before = state.balances.tokens ?? null;
      await runWrite({
        method: 'sell',
        args: [String(l.id), tok.toString()],
        successNote: '',
        readBack: async () => {
          const after = asObject(await readView('get_listing', [String(l.id)]));
          const gen = await readView('get_gen_balance', [state.signer.address]);
          return t('activity.sold', { out: fmtMicroGen(BigInt(String(gen))) }) +
            ` · ${t('detail.tokensSold')}: ${fmtInt(BigInt(after.sold_tokens || '0'))}`;
        },
      });
      toast(t('trade.finalized'));
    }
  } catch (err) {
    errEl.hidden = false;
    errEl.textContent = err.message || t('trade.generic');
  } finally {
    btn.disabled = false;
  }
}

async function onClaim() {
  const btn = $('claim-btn');
  btn.disabled = true;
  try {
    await runWrite({
      method: 'claim_test_gen',
      args: [],
      successNote: t('claim.success'),
      readBack: async () => {
        const gen = await readView('get_gen_balance', [state.signer.address]);
        return `${t('claim.success')} ${t('balance.gen', { gen: fmtMicroGen(BigInt(String(gen))) })}`;
      },
    });
    toast(t('claim.success'));
  } catch (err) {
    const el = $('trade-error');
    el.hidden = false;
    el.textContent = err.message || t('trade.generic');
  } finally {
    btn.disabled = false;
  }
}

async function onReview() {
  const l = selectedListing();
  if (!l) return;
  const btn = $('review-btn');
  btn.disabled = true;
  try {
    await runWrite({
      method: 'review_listing',
      args: [String(l.id)],
      successNote: '',
      readBack: async () => {
        const after = asObject(await readView('get_listing', [String(l.id)]));
        return t('activity.reviewed', { verdict: `${after.status} · ${after.review_reason || ''}` });
      },
    });
    toast(t('review.started'));
  } catch (err) {
    const el = $('trade-error');
    el.hidden = false;
    el.textContent = err.message || t('trade.generic');
  } finally {
    btn.disabled = false;
  }
}

async function onGraduate() {
  const l = selectedListing();
  if (!l) return;
  const btn = $('graduate-btn');
  btn.disabled = true;
  try {
    await runWrite({
      method: 'graduate',
      args: [String(l.id)],
      successNote: '',
      readBack: async () => {
        const after = asObject(await readView('get_listing', [String(l.id)]));
        return t('activity.graduated', { fill: fmtNum(fillPct(after.fill_pct_bp), 2) });
      },
    });
    toast(t('trade.finalized'));
  } catch (err) {
    const el = $('trade-error');
    el.hidden = false;
    el.textContent = err.message || t('trade.generic');
  } finally {
    btn.disabled = false;
  }
}

async function onLaunch(e) {
  e.preventDefault();
  const errEl = $('launch-error');
  errEl.hidden = true;
  const fd = new FormData(e.target);
  const name = String(fd.get('name') || '').trim();
  const symbol = String(fd.get('symbol') || '').trim();
  const description = String(fd.get('description') || '').trim();
  const evidence = String(fd.get('evidence') || '').trim();
  const evidenceSource = String(fd.get('evidence_source') || '').trim();
  if (!name || !symbol || !description || !evidence || !evidenceSource) {
    errEl.hidden = false; errEl.textContent = t('launch.empty'); return;
  }
  if (evidence.length > 2000) {
    errEl.hidden = false; errEl.textContent = t('launch.evidenceLong'); return;
  }
  if (!evidenceSource.startsWith('https://') || evidenceSource.length > 500) {
    errEl.hidden = false; errEl.textContent = t('launch.evidenceSourceBad'); return;
  }
  const btn = e.target.querySelector('button[type="submit"]');
  btn.disabled = true;
  try {
    const beforeIds = new Set(state.listings.map((l) => String(l.id)));
    await runWrite({
      method: 'submit_listing',
      args: [name, symbol, description, evidence, evidenceSource],
      successNote: '',
      readBack: async () => {
        const raw = asObject(await readView('list_listings', []));
        const ids = Object.keys(raw).filter((id) => !beforeIds.has(id));
        const id = ids[0] || String(Math.max(...Object.keys(raw).map(Number)));
        return t('activity.listed', { id });
      },
    });
    e.target.reset();
    toast(t('launch.success'));
  } catch (err) {
    errEl.hidden = false;
    errEl.textContent = err.message || t('trade.generic');
  } finally {
    btn.disabled = false;
  }
}

// ---------- curve drag ----------
function bindCurveDrag() {
  const svg = $('curve-svg');
  const handle = $('curve-handle');
  let dragging = false;

  const amountFromX = (clientX) => {
    const rect = svg.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const l = selectedListing();
    if (!l) return;
    const genNow = BigInt(l.gen_reserve || '30000000');
    const soldNow = BigInt(l.sold_tokens || '0');
    const maxSold = (CURVE_SUPPLY * 97n) / 100n;
    const targetSold = (maxSold * BigInt(Math.round(frac * 1000))) / 1000n;
    if (state.mode === 'buy') {
      if (targetSold <= soldNow) { $('amount').value = '0'; renderPreview(); positionHandleFromAmount(); return; }
      const targetTok = CURVE_SUPPLY - targetSold;
      const targetGen = K / targetTok;
      const net = targetGen - genNow;
      if (net <= 0n) { $('amount').value = '0'; }
      else {
        const amountMicro = (net * 100n) / 99n;
        $('amount').value = fmtNum(Number(amountMicro) / 1e6, 2);
      }
    } else {
      const tokens = soldNow > targetSold ? soldNow - targetSold : 0n;
      $('amount').value = tokens.toString();
    }
    renderPreview();
    positionHandleFromAmount();
  };

  const onMove = (ev) => { if (dragging) amountFromX(ev.clientX); };
  const onUp = () => { dragging = false; window.removeEventListener('pointermove', onMove); window.removeEventListener('pointerup', onUp); };

  const onDown = (ev) => {
    dragging = true;
    svg.setPointerCapture?.(ev.pointerId);
    amountFromX(ev.clientX);
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    ev.preventDefault();
  };
  svg.addEventListener('pointerdown', onDown);
  handle.addEventListener('keydown', (ev) => {
    const step = state.mode === 'buy' ? 0.5 : 10000;
    const cur = parseFloat($('amount').value || '0') || 0;
    if (ev.key === 'ArrowRight' || ev.key === 'ArrowUp') { $('amount').value = String(cur + step); renderPreview(); positionHandleFromAmount(); ev.preventDefault(); }
    if (ev.key === 'ArrowLeft' || ev.key === 'ArrowDown') { $('amount').value = String(Math.max(0, cur - step)); renderPreview(); positionHandleFromAmount(); ev.preventDefault(); }
  });
}

// ---------- scroll narrative ----------
function bindStory() {
  const beats = document.querySelectorAll('[data-beat]');
  const io = new IntersectionObserver((entries) => {
    for (const en of entries) if (en.isIntersecting) en.target.classList.add('in');
  }, { threshold: 0.25 });
  beats.forEach((b) => io.observe(b));
  const story = $('story');
  const progress = $('story-progress');
  const onScroll = () => {
    const r = story.getBoundingClientRect();
    const total = r.height - window.innerHeight * 0.6;
    const done = Math.min(1, Math.max(0, -r.top / Math.max(total, 1)));
    progress.style.transform = `scaleY(${done})`;
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

// ---------- init ----------
function bindAll() {
  $('lang-en').addEventListener('click', () => applyLang('en'));
  $('lang-zh').addEventListener('click', () => applyLang('zh'));
  $('wallet-btn').addEventListener('click', async () => {
    if (state.signer) {
      if (state.signer.kind === 'test') discardTestAccount();
      else {
        state.signer = null;
        $('wallet-btn').textContent = t('wallet.connect');
        renderSignerLine();
        refreshBalances();
      }
      return;
    }
    await connectWallet();
  });
  $('mode-buy').addEventListener('click', () => setMode('buy'));
  $('mode-sell').addEventListener('click', () => setMode('sell'));
  $('amount').addEventListener('input', () => { renderPreview(); positionHandleFromAmount(); });
  $('trade-form').addEventListener('submit', onTrade);
  $('claim-btn').addEventListener('click', onClaim);
  $('review-btn').addEventListener('click', onReview);
  $('graduate-btn').addEventListener('click', onGraduate);
  $('launch-form').addEventListener('submit', onLaunch);
  $('refresh-btn').addEventListener('click', loadBoard);
  if (injectedProvider()) {
    injectedProvider().on?.('accountsChanged', (accs) => {
      if (!accs || !accs.length) {
        state.signer = null;
        $('wallet-btn').textContent = t('wallet.connect');
        renderSignerLine();
        refreshBalances();
      } else if (state.signer?.kind === 'wallet') {
        state.signer.address = accs[0];
        $('wallet-btn').textContent = shortAddr(accs[0]);
        renderSignerLine();
        refreshBalances();
      }
    });
    injectedProvider().on?.('chainChanged', () => { loadBoard(); refreshBalances(); });
  }
  bindCurveDrag();
  bindStory();
  // Refresh while visible; reads are cheap views and stay well under the RPC budget.
  setInterval(() => { if (!document.hidden) loadBoard(); }, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) loadBoard(); });
}

applyLang(lang);
setMode('buy');
bindAll();
loadBoard();
refreshBalances();
renderFeed();
