// TerraTwin search workflow: target → regional cell → screening search → Earth candidates → evidence → compare → export.
// Talks to /api/v1 (terratwin_service.py) and to the globe only through window.GLOBE, so it works without WebGL.
'use strict';
window.TT = (() => {
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const isNum = v => typeof v === 'number' && Number.isFinite(v);
  const fmt = (v, d = 2) => isNum(v) ? v.toFixed(d) : '—';
  const pct = v => isNum(v) ? `${(v * 100).toFixed(1)}%` : '—';
  const normLon = lon => ((((lon + 180) % 360) + 360) % 360) - 180;
  const UNIT = { deg: '°', m: ' m' };
  const BODY = { moon: 'Moon', mars: 'Mars', earth: 'Earth' };
  const STATUS_TEXT = {
    ok: 'Candidates found',
    no_candidates_under_filters: 'No qualifying Earth regions under these filters',
    target_insufficient_evidence: 'Insufficient terrain evidence for this target',
    profile_unavailable: 'Profile unavailable',
  };

  const state = {
    meta: null, metaError: null, dem: null,
    target: null,          // {body, lat, lon, lonSupplied, name, kind, note, cell, error, loading}
    targetSeq: 0, targetAbort: null,
    telemetry: null, telSeq: 0,
    result: null, resultKey: null, searching: false, searchError: null, staleNotice: null,
    searchSeq: 0, searchAbort: null,
    selected: null, compare: [],
    tab: 'target',
    showStudies: false, studyGeo: {},
    savedCases: null,
    earthNote: null,
    reveal: null,          // {stage: 'travel'|'emerge'|'done', t, result}; null when no reveal applies
    revealSeq: 0,
  };
  let chart = null;

  // ------------------------------------------------------------------ API
  async function api(path, opts = {}) {
    let r;
    try {
      r = await fetch(path, { headers: { 'content-type': 'application/json' }, ...opts });
    } catch (e) {
      if (e.name === 'AbortError') throw e;
      return { ok: false, status: 0, data: null, message: 'The TerraTwin server could not be reached.' };
    }
    let data = null;
    try { data = await r.json(); } catch { /* non-JSON error body */ }
    let message = null;
    if (!r.ok) {
      const d = data?.detail;
      if (r.status === 422) message = 'Invalid input: ' + (Array.isArray(data?.detail) ? data.detail.map(x => `${(x.loc || []).filter(l => l !== 'body').join('.') || 'request'} ${x.msg}`).join('; ') : 'rejected');
      else if (r.status === 503) message = d?.error === 'busy' ? 'The search service is busy; retry shortly.' : `Search data unavailable: ${d?.detail || 'release not loaded'}`;
      else message = `Service error (HTTP ${r.status}). This is not a scientific result.`;
    }
    return { ok: r.ok, status: r.status, data, message };
  }

  // ------------------------------------------------------------------ helpers
  const profileById = id => state.meta?.profiles.find(p => p.id === id);
  const feat = (body, name) => state.meta?.features?.[body]?.[name] || {};
  const label = name => feat('mars', name).label || feat('earth', name).label || name;
  const unitOf = (body, name) => UNIT[feat(body, name).units] ?? (feat(body, name).units ? ` ${feat(body, name).units}` : '');
  const say = msg => { $('live').textContent = msg; };
  const aridityClass = ai => !isNum(ai) ? '' : ai < 0.03 ? 'hyper-arid' : ai < 0.2 ? 'arid' : ai < 0.5 ? 'semi-arid' : ai < 0.65 ? 'dry sub-humid' : 'humid';

  function settings() {
    const val = id => $(id).value.trim();
    const num = id => (val(id) === '' ? null : Number(val(id)));
    const profile = document.querySelector('input[name="profile"]:checked')?.value || 'dry_barren_terrain';
    return { profile, limit: Number($('sLimit').value), originLat: num('sOriginLat'), originLon: num('sOriginLon'),
             radius: num('sRadius'), purpose: val('sPurpose'), includeOrigin: $('sIncludeOrigin').checked };
  }
  function queryKey() {
    const t = state.target, s = settings();
    if (!t) return null;
    return JSON.stringify([t.body, t.lat, t.lon, s.profile, s.limit, s.originLat, s.originLon, s.radius]);
  }

  // Anything that changes the question discards the previous answer: old data never describes a new selection.
  function invalidate(reason) {
    cancelReveal();
    state.searchAbort?.abort();
    state.searchSeq++;
    state.searching = false;
    if (state.result && !state.result.saved_fixture) state.staleNotice = reason;
    state.result = null; state.resultKey = null; state.selected = null; state.compare = []; state.searchError = null;
    renderAll();
  }

  // ------------------------------------------------------------------ target
  async function setTarget(body, lat, lon, name, kind, note) {
    if (!['moon', 'mars'].includes(body)) return;
    state.targetAbort?.abort();
    const ctl = state.targetAbort = new AbortController();
    const seq = ++state.targetSeq;
    state.target = { body, lat, lon: normLon(lon), lonSupplied: lon, name: name || 'Surface point', kind: kind || 'click', note, loading: true };
    state.telemetry = null;
    state.earthNote = null;
    $('fBody').value = body; $('fLat').value = +lat.toFixed(5); $('fLon').value = +normLon(lon).toFixed(5);
    invalidate('The target changed after the last search. Run the search again for the new target.');
    state.staleNotice = null;
    if (GLOBE.world() !== body) GLOBE.setWorld(body);
    GLOBE.flyTo(lat, normLon(lon));
    if (matchMedia('(max-width: 767px)').matches) $('targetForm').open = false; // give the globe room on phones
    showTab('target');
    say(`Resolving the regional cell containing ${body} ${lat.toFixed(3)}, ${normLon(lon).toFixed(3)}`);
    let r;
    try {
      r = await api(`/api/v1/target?body=${body}&lat=${lat}&lon=${lon}`, { signal: ctl.signal });
    } catch { return; } // aborted by a newer selection
    if (seq !== state.targetSeq) return;
    state.target.loading = false;
    if (r.ok) state.target.cell = r.data.target;
    else state.target.error = r.message;
    renderTarget(); GLOBE.refresh();
    if (r.ok) say(`Selected regional cell ${r.data.target.feature_id}`);
    if (body === 'moon' && state.dem?.available) fetchTelemetry(lat, lon);
  }

  async function fetchTelemetry(lat, lon) {
    const seq = ++state.telSeq;
    const r = await api(`/api/query?lat=${lat}&lng=${lon}`).catch(() => null);
    if (seq !== state.telSeq || !r) return;
    state.telemetry = r.ok ? r.data : { error: r.message };
    renderTarget();
  }

  // ------------------------------------------------------------------ search
  function validateSettings() {
    const s = settings(), errs = [];
    const hasLat = s.originLat !== null, hasLon = s.originLon !== null;
    if (hasLat !== hasLon) errs.push('Enter both origin latitude and longitude, or neither.');
    if (hasLat && (!Number.isFinite(s.originLat) || s.originLat < -90 || s.originLat > 90)) errs.push('Origin latitude must be between −90 and 90.');
    if (hasLon && (!Number.isFinite(s.originLon) || Math.abs(s.originLon) > 540)) errs.push('Origin longitude must be a number (east-positive).');
    if (s.radius !== null && (!Number.isFinite(s.radius) || s.radius < 0 || s.radius > 20038)) errs.push('Radius must be between 0 and 20,038 km.');
    if (s.radius !== null && !hasLat) errs.push('A radius needs an Earth origin.');
    return errs;
  }

  async function runSearch() {
    if (!state.target) { $('searchMsg').innerHTML = `<div class="tt-error">Select a Moon or Mars target first.</div>`; return; }
    const errs = validateSettings();
    if (errs.length) { $('searchMsg').innerHTML = `<div class="tt-error" role="alert">${errs.map(esc).join('<br>')}</div>`; return; }
    const s = settings(), t = state.target;
    const payload = { body: t.body, lat: t.lat, lon: t.lonSupplied, profile: s.profile, limit: s.limit };
    if (s.originLat !== null) payload.origin = { lat: s.originLat, lon: s.originLon };
    if (s.radius !== null) payload.radius_km = s.radius;
    cancelReveal();
    state.searchAbort?.abort();
    const ctl = state.searchAbort = new AbortController();
    const seq = ++state.searchSeq, key = queryKey();
    Object.assign(state, { searching: true, searchError: null, result: null, staleNotice: null, selected: null, compare: [] });
    showTab('results'); renderAll(); say('Searching Earth cells…'); // loading, errors and results all appear here
    const started = performance.now();
    let r;
    try {
      r = await api('/api/v1/search', { method: 'POST', body: JSON.stringify(payload), signal: ctl.signal });
    } catch { return; }
    if (seq !== state.searchSeq || key !== queryKey()) return; // superseded or settings changed meanwhile
    state.searching = false;
    if (!r.ok) { state.searchError = r.message; renderAll(); say(r.message); return; }
    r.data.client = { purpose: s.purpose, browser_roundtrip_ms: Math.round(performance.now() - started), origin: payload.origin || null };
    state.result = r.data; state.resultKey = key;
    showTab('results'); renderAll(); GLOBE.refresh();
    say(`${STATUS_TEXT[r.data.status]}: ${r.data.candidates.length} candidates`);
    if (r.data.status === 'ok' && r.data.candidates.length) reveal(r.data); // never for empty/unsupported outcomes
  }

  async function loadSavedCase(id) {
    const r = await api(`/api/v1/cases/${encodeURIComponent(id)}`);
    if (!r.ok) { $('savedMsg').innerHTML = `<div class="tt-error">${esc(r.message)}</div>`; return; }
    const d = r.data, t = d.target;
    await setTarget(t.body, t.requested_lat, t.requested_lon, d.saved_fixture.title, 'saved');
    d.client = { purpose: '', origin: d.configuration.origin ? { lat: d.configuration.origin[0], lon: d.configuration.origin[1] } : null };
    cancelReveal(); // saved fixtures are not a completed live search, so they never get the reveal
    state.result = d; state.resultKey = null; state.staleNotice = null;
    showTab('results'); renderAll(); GLOBE.refresh();
  }

  function selectCandidate(i, fly = true) {
    const c = state.result?.candidates?.[i];
    if (!c) return;
    interrupt();
    state.selected = i;
    if (fly) { GLOBE.setWorld('earth'); GLOBE.flyTo(c.lat, c.lon, 0.12); }
    showTab('evidence'); renderAll(); GLOBE.refresh();
    say(`Candidate ${i + 1}: terrain resemblance ${fmt(c.observed_fit, 1)}`);
  }
  function toggleCompare(i) {
    const k = state.compare.indexOf(i);
    if (k >= 0) state.compare.splice(k, 1);
    else { state.compare.push(i); if (state.compare.length > 2) state.compare.shift(); }
    renderResults(); renderCompare(); renderTabs();
  }
  function returnToTarget() {
    const t = state.target;
    if (!t) return;
    interrupt();
    GLOBE.setWorld(t.body); GLOBE.flyTo(t.lat, t.lon, 0.9); showTab('target');
  }

  // ------------------------------------------------------------------ Moon/Mars → Earth reveal
  // Runs only after a completed real search with candidates. Uses the returned top candidate's coordinates and
  // footprint. The final state (Earth view, #1 selected, all footprints selectable) is identical whether the
  // animation plays, is skipped, or is replaced by reduced motion / no WebGL.
  const sleep = ms => new Promise(res => setTimeout(res, ms));
  const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches || !GLOBE.available;
  const ease = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

  async function reveal(result) {
    const token = ++state.revealSeq, top = result.candidates[0], t = state.target;
    const alive = () => token === state.revealSeq && state.result === result;
    state.reveal = { stage: 'travel', t: 0, result };
    renderReveal();
    if (reducedMotion()) return finishReveal(token, true);
    GLOBE.flyTo(t.lat, t.lon, 2.6, 900);                 // pull back from the planetary target
    await sleep(950); if (!alive()) return;
    GLOBE.fade(false);
    await sleep(380); if (!alive()) return;
    GLOBE.setWorld('earth');
    GLOBE.flyTo(top.lat, top.lon, 3.0, 0);              // arrive above the returned candidate's true location
    GLOBE.fade(true);
    await sleep(200); if (!alive()) return;
    GLOBE.flyTo(top.lat, top.lon, 0.2, 2200);
    await sleep(2250); if (!alive()) return;
    state.reveal.stage = 'emerge'; GLOBE.refresh(); renderReveal();
    const start = performance.now();
    while (alive()) {                                    // footprint rises and brightens at its returned geometry
      const k = Math.min(1, (performance.now() - start) / 1100);
      state.reveal.t = ease(k); GLOBE.repaint();
      if (k >= 1) break;
      await new Promise(requestAnimationFrame);
    }
    if (alive()) finishReveal(token, false);
  }

  function finishReveal(token, jump) {
    if (token !== state.revealSeq || !state.reveal) return;
    const top = state.reveal.result.candidates[0];
    state.reveal = { ...state.reveal, stage: 'done', t: 1 };
    GLOBE.fade(true);
    if (GLOBE.world() !== 'earth') GLOBE.setWorld('earth');
    if (jump) GLOBE.flyTo(top.lat, top.lon, 0.2, 0);
    state.selected = 0;
    showTab('evidence'); renderAll(); GLOBE.refresh(); renderReveal();
    say(`Best Earth match: candidate 1, terrain resemblance ${fmt(top.observed_fit, 1)}.`);
  }
  function skipReveal() { if (state.reveal && state.reveal.stage !== 'done') finishReveal(state.revealSeq, true); }
  // User action during the animation: finish instantly so the result state is consistent, then let them act.
  function interrupt() { if (state.reveal && state.reveal.stage !== 'done') { const tok = state.revealSeq; finishRevealQuiet(tok); } }
  function finishRevealQuiet(token) {
    if (token !== state.revealSeq || !state.reveal) return;
    state.revealSeq++;
    state.reveal = { ...state.reveal, stage: 'done', t: 1 };
    GLOBE.fade(true); renderReveal(); GLOBE.refresh();
  }
  function cancelReveal() {
    state.revealSeq++;
    if (state.reveal) { state.reveal = null; GLOBE.fade(true); }
    renderReveal();
  }

  function renderReveal() {
    const el = $('reveal'), rv = state.reveal;
    if (!rv) { el.classList.add('hidden'); el.innerHTML = ''; return; }
    const r = rv.result, top = r.candidates[0], s = strongest(top), src = BODY[r.target.body];
    const route = `<div class="tt-route"><span class="from">${esc(src)} · ${esc(r.target.feature_id)}</span><span class="line"></span><span class="to">Earth · best match</span></div>`;
    if (rv.stage !== 'done') {
      el.innerHTML = `${route}<div class="flex items-center justify-between gap-2 mt-2">
        <p class="tt-note">${rv.stage === 'travel' ? `<span class="tt-spin"></span> Search complete — moving to the highest-ranked Earth region…` : 'Revealing the returned regional footprint at its true location…'}</p>
        <button id="revealSkip" class="tt-btn px-2 py-1">Skip animation</button></div>`;
      $('revealSkip').onclick = skipReveal;
    } else {
      el.innerHTML = `${route}
        <div class="flex justify-between items-start gap-2 mt-2"><div>
          <p class="text-slate-50">#1 · ${esc(top.feature_id)} · ${fmt(top.lat, 3)}°, ${fmt(top.lon, 3)}°E</p>
          <p class="tt-note">Closest on ${esc(label(s.feature))}; largest mismatch ${esc(label(top.largest_numeric_mismatch))}.</p></div>
          <div class="text-right"><div class="text-green-300 text-base">${fmt(top.observed_fit, 1)}</div><div class="tt-note">Terrain resemblance</div></div></div>
        <p class="tt-note mt-1">A data match between ~15 km regional terrain summaries — not a route, a certified site or a verified analog. ${r.candidates.length - 1} other candidate${r.candidates.length === 2 ? '' : 's'} shown as selectable footprints.</p>
        <div class="flex gap-2 mt-2 flex-wrap"><button id="revealEvidence" class="tt-btn-primary px-2 py-1">Evidence</button>
          <button id="revealOthers" class="tt-btn px-2 py-1">All candidates</button>
          <button id="revealBack" class="tt-btn px-2 py-1">Return to ${esc(src)}</button>
          <button id="revealClose" class="tt-btn px-2 py-1 ml-auto" aria-label="Dismiss match summary">×</button></div>`;
      $('revealEvidence').onclick = () => selectCandidate(0, false);
      $('revealOthers').onclick = () => showTab('results');
      $('revealBack').onclick = returnToTarget;
      $('revealClose').onclick = () => { el.classList.add('hidden'); };
      if (matchMedia('(max-width: 767px)').matches) { // phones: the evidence sheet carries the same facts
        const tok = state.revealSeq;
        setTimeout(() => { if (tok === state.revealSeq) el.classList.add('hidden'); }, 5000);
      }
    }
    el.classList.remove('hidden');
  }

  // ------------------------------------------------------------------ rendering
  function showTab(tab) {
    state.tab = tab;
    document.querySelectorAll('[data-panel]').forEach(p => p.classList.toggle('hidden', p.dataset.panel !== tab));
    renderTabs();
  }
  function renderTabs() {
    const n = state.result?.candidates?.length;
    document.querySelectorAll('[data-tab]').forEach(b => {
      b.setAttribute('aria-selected', b.dataset.tab === state.tab);
      b.tabIndex = b.dataset.tab === state.tab ? 0 : -1;
      const base = { target: 'Target', results: 'Results', evidence: 'Evidence', compare: 'Compare', investigations: 'Local studies' }[b.dataset.tab];
      const count = b.dataset.tab === 'results' && state.result ? (n || '0') : b.dataset.tab === 'compare' && state.compare.length ? state.compare.length : '';
      b.innerHTML = `${base}${count !== '' ? `<span class="tt-count">${count}</span>` : ''}`;
    });
    const t = state.target, w = GLOBE.world();
    const show = t && w !== t.body;
    $('returnBar').classList.toggle('hidden', !show);
    if (show) $('returnText').textContent = w === 'earth' ? `Viewing Earth candidates for ${t.name}` : `Target is on ${BODY[t.body]}`;
  }

  function terrainRows(cell) {
    const rows = state.meta.core_terrain.map(f => {
      const v = cell.core_terrain[f], scored = f !== 'tri_mean_m';
      return `<tr><td>${esc(label(f))}${scored ? '' : ''}</td><td class="num">${v === null ? '<span class="text-rose-300">missing</span>' : esc(fmt(v, f.endsWith('_deg') ? 2 : 1)) + unitOf(cell.body, f)}</td></tr>`;
    });
    return `<table class="tt-table"><tbody>${rows.join('')}</tbody></table>`;
  }

  function renderTarget() {
    const el = $('targetInfo'), t = state.target;
    if (!state.meta) {
      el.innerHTML = state.metaError ? `<div class="tt-error">${esc(state.metaError)} <button class="tt-btn px-2 ml-1" id="retryMeta">Retry</button></div>`
                                     : `<p class="tt-note"><span class="tt-spin"></span> Loading release…</p>`;
      if ($('retryMeta')) $('retryMeta').onclick = init;
      return;
    }
    if (!t) {
      el.innerHTML = `<div class="tt-card"><p class="text-slate-200">No target selected.</p>
        <p class="tt-note mt-1">Click the Moon or Mars globe, enter coordinates, or choose an example on the left. TerraTwin compares the whole regional cell containing your point — about 15 km across — with Earth cells.</p></div>
        ${state.earthNote ? `<div class="tt-warn mt-2">${state.earthNote}</div>` : ''}`;
      return;
    }
    const c = t.cell;
    const aliased = Math.abs(t.lonSupplied - t.lon) > 1e-9;
    let html = `<div class="flex items-start justify-between gap-2">
        <div><div class="tt-h">${esc(BODY[t.body])} target · ${esc({ click: 'globe click', coords: 'entered coordinates', example: 'example', site: 'reference site', saved: 'saved example' }[t.kind] || t.kind)}</div>
        <h2 class="text-sm text-slate-50">${esc(t.name)}</h2>
        <p class="tt-note">Point ${fmt(t.lat, 4)}°, ${fmt(t.lon, 4)}°E${aliased ? ` (entered as ${esc(t.lonSupplied)}°)` : ''}</p></div></div>
      ${t.note ? `<p class="tt-note">${esc(t.note)}</p>` : ''}
      ${state.earthNote ? `<div class="tt-warn">${state.earthNote}</div>` : ''}`;
    if (t.loading) html += `<p class="tt-note"><span class="tt-spin"></span> Resolving regional cell…</p>`;
    else if (t.error) html += `<div class="tt-error">${esc(t.error)} <button class="tt-btn px-2 ml-1" id="retryTarget">Retry</button></div>`;
    else if (c) {
      const eligible = Object.values(c.terrain_eligible).some(Boolean);
      const src = c.feature_sources?.slope_median_deg || {};
      html += `<div class="tt-card space-y-1">
        <div class="tt-h" style="color:#7dd3fc">Regional cell containing this point</div>
        <p><span class="text-slate-100">${esc(c.feature_id)}</span> · centre ${fmt(c.cell_center.lat, 3)}°, ${fmt(c.cell_center.lon, 3)}°E</p>
        <p class="tt-note">Area ${fmt(c.area_km2, 1)} km² · grid ${esc(c.grid.res_deg)}° (≈${esc(c.grid.cell_size_km_at_equator)} km at the equator) · terrain from ${esc(src.native_resolution || 'source DEM')} (${esc(src.source || '')})</p>
        ${terrainRows(c)}
        <p class="tt-note">Regional summaries of the whole cell, not values at your click. Terrain ruggedness index is a quality diagnostic and is not scored.</p>
        ${eligible ? `<div class="tt-ok">Complete regional terrain: this cell can be searched.</div>`
                   : `<div class="tt-error">Insufficient integrated terrain: ${esc(c.missing_terrain.join(', ') || 'quality checks failed')}. A search will report this rather than produce matches.</div>`}
        <p class="tt-note">Precision note: a click a few metres across a cell edge selects a different ~15 km cell and can change every result. Watch the outlined footprint.</p>
      </div>`;
    }
    if (t.body === 'moon') {
      const d = state.telemetry;
      html += `<div class="tt-card"><div class="tt-h">Local lunar DEM telemetry (not used for matching)</div>`;
      if (!state.dem?.available) html += `<p class="tt-note">Lunar DEM not installed on this server; telemetry unavailable. Search is unaffected.</p>`;
      else if (!d) html += `<p class="tt-note"><span class="tt-spin"></span> Sampling…</p>`;
      else if (d.error) html += `<p class="tt-note">${esc(d.error)}</p>`;
      else html += `<div class="grid grid-cols-3 gap-2 text-center my-1">
          <div><div class="tt-note">Elevation</div><div class="text-slate-50">${fmt(d.elev_m, 0)} m</div></div>
          <div><div class="tt-note">Mean slope</div><div class="text-slate-50">${fmt(d.slope_deg, 1)}°</div></div>
          <div><div class="tt-note">Elev. std</div><div class="text-slate-50">±${fmt(d.roughness_m, 0)} m</div></div></div>
          <div class="h-28"><canvas id="profile" aria-label="West to east elevation profile"></canvas></div>
          <p class="tt-note">${esc(d.source)} · ${esc(d.m_per_px)} m/px · 5×5-pixel window and 21-pixel W→E profile at the click. Different footprint and definitions from the regional median/p90 slope and RMS roughness above; never substituted for them.${Math.abs(t.lat) > 80 ? ' High-latitude slope uses an approximate east–west spacing.' : ''}</p>`;
      html += `</div>`;
    }
    el.innerHTML = html;
    if ($('retryTarget')) $('retryTarget').onclick = () => setTarget(t.body, t.lat, t.lonSupplied, t.name, t.kind, t.note);
    const d = state.telemetry;
    if (d && !d.error && $('profile') && window.Chart) {
      chart?.destroy();
      chart = new Chart($('profile'), {
        type: 'line',
        data: { labels: d.profile.map((_, i) => ((i - 10) * d.profile_step_km).toFixed(1)),
                datasets: [{ data: d.profile, borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,.15)', fill: true, pointRadius: 0, tension: .3, borderWidth: 2 }] },
        options: { maintainAspectRatio: false, animation: false, plugins: { legend: { display: false } },
                   scales: { x: { ticks: { color: '#94a3b8', maxTicksLimit: 5 }, grid: { color: '#1e293b' }, title: { display: true, text: 'km from click', color: '#94a3b8' } },
                             y: { ticks: { color: '#94a3b8' }, grid: { color: '#1e293b' } } } },
      });
    }
  }

  function renderSearchForm() {
    const m = state.meta;
    if (!m) return;
    const avail = m.profiles.filter(p => p.available), unavail = m.profiles.filter(p => !p.available);
    const explain = {
      terrain_screening: 'Every eligible Earth land cell. Vegetation, water, cities and cropland are not screened.',
      dry_barren_terrain: 'Same terrain score, but only Earth cells that were ≥80% barren-class land cover (2017), ≤5% water, ≤1% built-up, ≤5% cropland, and aridity index ≤0.20 (1970–2000). Fewer, drier candidates.',
    };
    $('searchForm').innerHTML = `
      <div class="tt-h mt-1">Search Earth</div>
      <fieldset class="space-y-1"><legend class="tt-note mb-1">Screening mode — both use the identical terrain resemblance score; they differ in which Earth cells are eligible.</legend>
        ${avail.map(p => `<label class="flex gap-2 items-start tt-card cursor-pointer"><input type="radio" name="profile" value="${esc(p.id)}" ${p.id === 'dry_barren_terrain' ? 'checked' : ''} class="mt-0.5">
          <span><span class="text-slate-100">${esc(p.id === 'dry_barren_terrain' ? 'Historical dry/barren screening' : 'Terrain screening')}</span><br><span class="tt-note">${esc(explain[p.id] || p.purpose)}</span></span></label>`).join('')}
        <details class="tt-note"><summary class="cursor-pointer">Unavailable investigation profiles (${unavail.length})</summary>
          ${unavail.map(p => `<label class="flex gap-2 items-start mt-1"><input type="radio" name="profile" value="${esc(p.id)}" class="mt-0.5">
          <span>${esc(p.id.replace(/_/g, ' '))} — <em>${esc(p.status.replace(/_/g, ' '))}</em>; missing ${esc(p.missing_evidence.join(', ').replace(/_/g, ' '))}</span></label>`).join('')}
          <p class="mt-1">Selecting one returns an explanation of the missing evidence, never invented results.</p></details>
      </fieldset>
      <label class="block tt-note">Investigation purpose (goes in the brief)
        <input id="sPurpose" class="tt-input mt-1 w-full" maxlength="200" placeholder="e.g. rover navigation trials on gentle, low-relief plains"></label>
      <details id="originBox" class="tt-card"><summary class="cursor-pointer text-slate-200">Optional: limit to a distance from an Earth origin</summary>
        <div class="grid grid-cols-3 gap-2 mt-2 items-end">
          <label class="tt-note">Origin lat °<input id="sOriginLat" class="tt-input mt-1 w-full" inputmode="decimal" autocomplete="off"></label>
          <label class="tt-note">Origin lon °E<input id="sOriginLon" class="tt-input mt-1 w-full" inputmode="decimal" autocomplete="off"></label>
          <label class="tt-note">Radius km<input id="sRadius" class="tt-input mt-1 w-full" inputmode="decimal" autocomplete="off"></label>
        </div>
        <div class="flex gap-2 mt-2 flex-wrap">
          <button type="button" id="geoBtn" class="tt-btn px-2 py-1">Use my location</button>
          <button type="button" id="clearOrigin" class="tt-btn px-2 py-1">Clear</button>
        </div>
        <p class="tt-note mt-1">Straight-line distance between cell centres, not travel time or access. The origin is sent only for this calculation, is not stored, and is left out of exports unless you tick the box below.</p>
        <label class="tt-note flex gap-2 mt-1"><input type="checkbox" id="sIncludeOrigin"> Include my origin and distances in exports</label>
        <p id="geoMsg" class="tt-note"></p>
      </details>
      <div class="flex items-end gap-2">
        <label class="tt-note">Results<select id="sLimit" class="tt-input mt-1 block"><option>5</option><option selected>10</option><option>20</option></select></label>
        <button id="searchBtn" class="tt-btn-primary flex-1 py-2">Find Earth candidates</button>
      </div>
      <div id="searchMsg"></div>`;
    $('searchForm').querySelectorAll('input[name="profile"], #sLimit').forEach(i => i.addEventListener('change',
      () => invalidate('The screening settings changed after the last search. Run the search again.')));
    ['sOriginLat', 'sOriginLon', 'sRadius'].forEach(id => $(id).addEventListener('input',
      () => invalidate('The distance constraint changed after the last search. Run the search again.')));
    $('searchBtn').onclick = runSearch;
    $('clearOrigin').onclick = () => { ['sOriginLat', 'sOriginLon', 'sRadius'].forEach(id => $(id).value = ''); invalidate('The distance constraint was cleared. Run the search again.'); };
    $('geoBtn').onclick = () => {
      if (!navigator.geolocation) { $('geoMsg').textContent = 'Geolocation is unavailable; enter the origin manually.'; return; }
      $('geoMsg').textContent = 'Requesting location…';
      navigator.geolocation.getCurrentPosition(p => {
        $('sOriginLat').value = p.coords.latitude.toFixed(3); $('sOriginLon').value = p.coords.longitude.toFixed(3);
        $('geoMsg').textContent = 'Origin filled from your device (rounded to ~0.1 km). Not stored.';
        invalidate('The distance constraint changed after the last search. Run the search again.');
      }, e => { $('geoMsg').textContent = `Location not available (${e.message}); enter the origin manually.`; }, { timeout: 10000 });
    };
  }

  function strongest(c) { return c.comparisons.reduce((a, b) => (b.normalized_distance < a.normalized_distance ? b : a)); }

  function countsLine(r) {
    const parts = [];
    if (isNum(r.eligible_after_area_filter)) parts.push(`${r.eligible_after_area_filter.toLocaleString()} eligible Earth cells of comparable area`);
    if (r.configuration?.radius_km !== null && r.configuration?.radius_km !== undefined && isNum(r.eligible_after_radius_filter)) parts.push(`${r.eligible_after_radius_filter.toLocaleString()} within ${r.configuration.radius_km} km`);
    if (isNum(r.above_minimum_fit)) parts.push(`${r.above_minimum_fit.toLocaleString()} scored ≥ ${r.configuration.minimum_fit}`);
    return parts.join(' → ');
  }

  function renderResults() {
    const el = $('panelResults'), r = state.result;
    if (state.searching) { el.innerHTML = `<p class="tt-note"><span class="tt-spin"></span> Searching Earth cells with the ${esc(state.meta?.dataset_version)} release…</p>`; return; }
    if (state.searchError) {
      el.innerHTML = `<div class="tt-error" role="alert">${esc(state.searchError)}</div><button id="retrySearch" class="tt-btn px-3 py-1 mt-2">Retry search</button>`;
      $('retrySearch').onclick = runSearch; return;
    }
    if (!r) {
      el.innerHTML = (state.staleNotice ? `<div class="tt-warn">${esc(state.staleNotice)}</div>` : '') +
        `<p class="tt-note mt-2">${state.target ? 'Choose a screening mode on the Target tab and press “Find Earth candidates”.' : 'Select a target first.'}</p>`;
      return;
    }
    const t = r.target, cfg = r.configuration || {};
    let html = r.saved_fixture ? `<div class="tt-warn"><strong>Saved example</strong> from release ${esc(r.dataset_version)} fixtures (${esc(r.saved_fixture.created_utc.slice(0, 10))}). Not a newly executed query.</div>` : '';
    html += `<div class="tt-card space-y-1"><div class="tt-h">${esc(STATUS_TEXT[r.status] || r.status)}</div>
      <p class="tt-note">${esc(BODY[t?.body] || '')} ${esc(t?.feature_id || '')} · ${esc(r.profile.replace(/_/g, ' '))} · data ${esc(r.dataset_version)}</p>
      ${countsLine(r) ? `<p class="tt-note">${esc(countsLine(r))}</p>` : ''}</div>`;
    if (r.status === 'no_candidates_under_filters') {
      html += `<div class="tt-warn">No Earth cell meets every selected filter. This is a valid result, not an error, and nothing was relaxed automatically.
        You may widen the search yourself:</div><div class="flex gap-2 flex-wrap">
        ${cfg.radius_km !== null && cfg.radius_km !== undefined ? `<button class="tt-btn px-2 py-1" id="dropRadius">Remove the radius</button>` : ''}
        ${r.profile === 'dry_barren_terrain' ? `<button class="tt-btn px-2 py-1" id="useTerrain">Switch to terrain screening</button>` : ''}</div>
        <p class="tt-note">These buttons only change settings; press “Find Earth candidates” to run the new search.</p>`;
    } else if (r.status === 'target_insufficient_evidence') {
      html += `<div class="tt-error">The integrated table lacks required terrain for this regional cell (missing: ${esc((r.missing_terrain || []).join(', ') || 'quality checks failed')}). No candidates are produced and no other target is substituted.</div>
        ${t?.body === 'moon' && t.requested_lat < -85 ? `<p class="tt-note">Separate polar LOLA context exists for Shackleton but has different definitions and does not fill these fields.</p>` : ''}`;
    } else if (r.status === 'profile_unavailable') {
      html += `<div class="tt-warn">This investigation profile is not available: missing ${esc((r.missing_evidence || []).join(', ').replace(/_/g, ' '))}. No results are invented.</div>`;
    }
    if (r.candidates.length) {
      html += `<p class="tt-note">Score: <strong class="text-slate-200">${esc(r.score_label || 'Terrain resemblance')}</strong> — ${esc(state.meta.score.explanation)} Shown: top ${r.candidates.length}, at least ${esc(cfg.minimum_separation_km)} km apart.</p><ol class="space-y-1">`;
      r.candidates.forEach((c, i) => {
        const s = strongest(c);
        html += `<li><div class="tt-result" role="button" tabindex="0" data-cand="${i}" aria-current="${state.selected === i}">
          <div class="flex justify-between gap-2"><span class="text-slate-100">#${i + 1} · ${fmt(c.lat, 3)}°, ${fmt(c.lon, 3)}°E</span><span class="text-green-300">${fmt(c.observed_fit, 1)}</span></div>
          <div class="tt-bar my-1"><span style="width:${Math.max(0, Math.min(100, c.observed_fit))}%"></span></div>
          <div class="tt-note">${fmt(c.area_km2, 0)} km² cell${isNum(c.distance_from_origin_km) ? ` · ${fmt(c.distance_from_origin_km, 0)} km from origin` : ''} · closest: ${esc(label(s.feature))} · largest mismatch: ${esc(label(c.largest_numeric_mismatch))}</div>
          <div class="flex justify-between items-center mt-1"><span class="tt-note">Unreviewed screening candidate</span>
          <label class="tt-note flex gap-1 items-center" onclick="event.stopPropagation()"><input type="checkbox" data-compare="${i}" ${state.compare.includes(i) ? 'checked' : ''}> compare</label></div>
        </div></li>`;
      });
      html += `</ol>`;
    }
    html += `<div class="tt-card space-y-1"><div class="tt-h">Export this query</div><div class="flex gap-2 flex-wrap">
      <button class="tt-btn px-2 py-1" id="exJson">Results JSON</button>
      <button class="tt-btn px-2 py-1" id="exGeo" ${r.candidates.length ? '' : 'disabled'}>Earth candidates GeoJSON</button>
      <button class="tt-btn-primary px-2 py-1" id="exBrief">Investigation brief</button></div>
      <p class="tt-note">${r.client?.origin && !settings().includeOrigin ? 'Your travel origin and distances are omitted (opt in on the Target tab).' : 'Exports reproduce this query, its version and status exactly, including nulls.'}</p></div>`;
    el.innerHTML = html;
    el.querySelectorAll('[data-cand]').forEach(b => {
      b.onclick = () => selectCandidate(+b.dataset.cand);
      b.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectCandidate(+b.dataset.cand); } };
    });
    el.querySelectorAll('[data-compare]').forEach(b => b.onchange = () => toggleCompare(+b.dataset.compare));
    if ($('dropRadius')) $('dropRadius').onclick = () => { $('sRadius').value = ''; invalidate('Radius removed. Run the search again.'); showTab('target'); $('searchBtn').focus(); };
    if ($('useTerrain')) $('useTerrain').onclick = () => { document.querySelector('input[value="terrain_screening"]').checked = true; invalidate('Switched to terrain screening. Run the search again.'); showTab('target'); $('searchBtn').focus(); };
    $('exJson').onclick = () => download(exportName('json'), JSON.stringify(exportPayload(), null, 2), 'application/json');
    $('exGeo').onclick = () => download(exportName('geojson'), JSON.stringify(exportGeoJSON(), null, 2), 'application/geo+json');
    $('exBrief').onclick = () => openBrief(state.selected);
  }

  function comparisonTable(r, c) {
    const body = r.target.body;
    return `<table class="tt-table"><thead><tr><th>Scored feature</th><th class="num">${esc(BODY[body])}</th><th class="num">Earth</th><th class="num">|Δ|</th><th class="num">Tol.</th><th class="num">Points</th></tr></thead><tbody>
      ${c.comparisons.map(x => {
        const tol = r.configuration.tolerances[x.feature], u = unitOf(body, x.feature), d = x.feature.endsWith('_deg') ? 2 : 1;
        return `<tr${x.feature === c.largest_numeric_mismatch ? ' style="color:#fde68a"' : ''}><td>${esc(label(x.feature))}</td><td class="num">${fmt(x.target_value, d)}${u}</td><td class="num">${fmt(x.earth_value, d)}${u}</td>
          <td class="num">${fmt(x.absolute_difference, d)}</td><td class="num">${esc(tol)}${u}</td><td class="num">${fmt(x.fit_contribution, 1)}/${fmt(100 * x.normalized_weight, 0)}</td></tr>`;
      }).join('')}
      <tr><td colspan="5">Total terrain resemblance</td><td class="num text-green-300">${fmt(c.observed_fit, 1)}</td></tr></tbody></table>`;
  }

  function envSection(c, r) {
    const e = c.earth_environment_context || {}, ev = r.target ? (profileById(r.profile)?.environment_evidence || {}) : {};
    return `<div class="tt-card space-y-1"><div class="tt-h">Earth-only historical context (not part of the score)</div>
      <table class="tt-table"><tbody>
        <tr><td>Barren class / water / built / crops (land cover ${esc(ev.landcover?.period || '2017')})</td><td class="num">${pct(e.landcover_barren_class_fraction)} / ${pct(e.landcover_water_class_fraction)} / ${pct(e.landcover_built_class_fraction)} / ${pct(e.landcover_cropland_or_mosaic_class_fraction)}</td></tr>
        <tr><td>Land-cover classified coverage</td><td class="num">${pct(e.landcover_strict_area_coverage)}</td></tr>
        <tr><td>Aridity index P/PET (${esc(ev.aridity?.period || '1970–2000')})</td><td class="num">${fmt(e.aridity_index, 3)} ${esc(aridityClass(e.aridity_index))}</td></tr>
        <tr><td>Mean NDVI, provisional scale (${esc(ev.ndvi?.period || '2001–2017')})</td><td class="num">${fmt(e.ndvi_mean_provisional, 3)}</td></tr>
        <tr><td>NDVI months · gap-filled share</td><td class="num">${isNum(e.ndvi_valid_month_count) ? e.ndvi_valid_month_count : '—'} · ${pct(e.ndvi_gapfilled_area_time_fraction)}</td></tr>
      </tbody></table>
      <p class="tt-note">Land-cover and aridity gates applied: ${c.land_cover_screened ? 'yes' : 'no'} / ${c.aridity_screened ? 'yes' : 'no'}. Vegetation gate: no (NDVI never affects eligibility or rank). “—” means no data, not zero. These describe past conditions, not today's site.</p></div>`;
  }

  function nextMeasurements(r, c) {
    const body = r.target.body, worst = c && c.comparisons.find(x => x.feature === c.largest_numeric_mismatch);
    const out = [];
    if (c) {
      out.push('Acquire a finer Earth DEM (e.g. 30 m Copernicus DSM) over this cell and recompute slope distributions at a common baseline; ~14 km regional summaries hide sub-cell variation (see the Gobi local study).');
      if (worst) out.push(`Examine the largest mismatch, ${label(worst.feature)}: Earth ${fmt(worst.earth_value, 1)} vs ${BODY[body]} ${fmt(worst.target_value, 1)}${unitOf(body, worst.feature)} — check whether part of the cell matches better.`);
      out.push(r.profile === 'dry_barren_terrain' ? 'Check current imagery and land cover: the screening used 2017 land cover and 1970–2000 climate.'
                                                  : 'Land cover, water and aridity were not screened in this mode: inspect vegetation, water bodies and settlement before planning.');
      out.push('Assess exposed materials and geology separately; mineralogy, boulders and mechanical strength are not part of this score.');
      out.push('Verify access, land ownership, permits and safety before any field use; nothing here establishes them.');
    }
    out.push(`Characterise the ${BODY[body]} target at finer scale (${body === 'mars' ? 'HiRISE/CTX DTMs' : 'LOLA gridded or LROC NAC DTMs'}); the target values describe a whole ~15 km cell, not a landing ellipse or base footprint.`);
    return out;
  }

  function renderEvidence() {
    const el = $('panelEvidence'), r = state.result, c = r?.candidates?.[state.selected];
    if (!c) { el.innerHTML = `<p class="tt-note">${r?.candidates?.length ? 'Select a candidate in Results or on the Earth globe.' : 'Run a search to inspect candidate evidence.'}</p>`; return; }
    const i = state.selected, s = strongest(c), studies = c.feature_id === 'earth:1090899';
    el.innerHTML = `${r.saved_fixture ? `<div class="tt-warn">Saved example — not a newly executed query.</div>` : ''}
      <div class="flex justify-between items-start gap-2"><div><div class="tt-h">Candidate #${i + 1} · ${esc(c.feature_id)}</div>
        <p class="text-slate-100">${fmt(c.lat, 4)}°, ${fmt(c.lon, 4)}°E</p></div>
        <div class="text-right"><div class="text-green-300 text-base">${fmt(c.observed_fit, 1)}</div><div class="tt-note">Terrain resemblance</div></div></div>
      <p class="tt-note">Closest agreement: ${esc(label(s.feature))}. Largest mismatch: ${esc(label(c.largest_numeric_mismatch))} (highlighted).</p>
      ${comparisonTable(r, c)}
      <p class="tt-note">Each term: points = weight × 100 × (1 − min(|Δ| / tolerance, 1)). Tolerances, the 50-point cutoff and equal weights are uncalibrated engineering defaults.</p>
      <div class="tt-card"><div class="tt-h">Footprints</div><p class="tt-note">${esc(BODY[r.target.body])} cell ${esc(r.target.feature_id)}: ${fmt(r.target.area_km2, 0)} km² · Earth cell: ${fmt(c.area_km2, 0)} km² (ratio ${fmt(c.target_area_ratio, 2)}; allowed ${fmt(r.configuration.area_ratio[0], 2)}–${fmt(r.configuration.area_ratio[1], 2)})${isNum(c.distance_from_origin_km) ? ` · ${fmt(c.distance_from_origin_km, 0)} km straight-line from origin` : ''}.</p></div>
      ${envSection(c, r)}
      <div class="tt-card"><div class="tt-h">Review status</div><p class="tt-note">Unreviewed screening candidate · local site verified: no · rank stability: not evaluated for this live query · scientific validation: ${esc(r.scientific_validation.replace(/_/g, ' '))}.</p></div>
      ${studies ? `<div class="tt-ok">This cell has a finer local study (Gobi). <button class="tt-btn px-2 ml-1" id="openStudy">Open local study</button></div>` : ''}
      <div class="tt-card"><div class="tt-h">Proposed next measurements</div><ol class="list-decimal ml-4 tt-note space-y-1">${nextMeasurements(r, c).map(x => `<li>${esc(x)}</li>`).join('')}</ol></div>
      <details class="tt-card"><summary class="cursor-pointer text-slate-200">Sources and limitations</summary>${provenanceHtml(r)}</details>
      <div class="flex gap-2 flex-wrap"><button class="tt-btn px-2 py-1" id="evFly">Show on Earth</button><button class="tt-btn-primary px-2 py-1" id="evBrief">Brief for this candidate</button></div>`;
    $('evFly').onclick = () => { GLOBE.setWorld('earth'); GLOBE.flyTo(c.lat, c.lon, 0.12); };
    $('evBrief').onclick = () => openBrief(i);
    if ($('openStudy')) $('openStudy').onclick = () => showTab('investigations');
  }

  function provenanceHtml(r) {
    const body = r.target.body, ev = profileById(r.profile)?.environment_evidence || {};
    const srcs = [...new Set(Object.keys(r.configuration.weights).map(f => feat(body, f).source).filter(Boolean))];
    const esrcs = [...new Set(Object.keys(r.configuration.weights).map(f => feat('earth', f).source).filter(Boolean))];
    return `<ul class="tt-note list-disc ml-4 mt-1 space-y-1">
      <li>Dataset ${esc(r.dataset_version)}, profile ${esc(r.profile)}, API v${esc(r.api_version || '1')}${r.served_at_utc ? `, served ${esc(r.served_at_utc)}` : ''}.</li>
      <li>${esc(BODY[body])} terrain source: ${esc(srcs.join(', '))} (${esc(feat(body, 'slope_median_deg').native_resolution || '')}). Earth terrain source: ${esc(esrcs.join(', '))}.</li>
      ${Object.entries(ev).map(([k, v]) => `<li>${esc(k)} ${esc(v.period)}: <a href="${esc(v.source)}" target="_blank" rel="noopener">${esc(v.source)}</a> — ${esc(v.meaning)}</li>`).join('')}
      ${(r.limitations || []).map(x => `<li>${esc(x)}</li>`).join('')}
    </ul>`;
  }

  function renderCompare() {
    const el = $('panelCompare'), r = state.result;
    if (!r?.candidates?.length) { el.innerHTML = `<p class="tt-note">Run a search, then tick “compare” on two candidates from the same query.</p>`; return; }
    if (state.compare.length < 2) { el.innerHTML = `<p class="tt-note">Tick “compare” on ${2 - state.compare.length} more candidate${state.compare.length ? '' : 's'} in Results. Comparison is limited to one query and profile.</p>`; return; }
    const [ia, ib] = [...state.compare].sort((a, b) => a - b), a = r.candidates[ia], b = r.candidates[ib], body = r.target.body;
    const rows = a.comparisons.map((x, k) => ({ f: x.feature, t: x.target_value, ea: x.earth_value, eb: b.comparisons[k].earth_value,
                                                pa: x.fit_contribution, pb: b.comparisons[k].fit_contribution }));
    const top = rows.reduce((m, x) => (Math.abs(x.pa - x.pb) > Math.abs(m.pa - m.pb) ? x : m));
    const diff = a.observed_fit - b.observed_fit;
    el.innerHTML = `<div class="tt-h">#${ia + 1} vs #${ib + 1} · same ${esc(BODY[body])} target ${esc(r.target.feature_id)}, profile ${esc(r.profile)}</div>
      <table class="tt-table"><thead><tr><th>Feature</th><th class="num">Target</th><th class="num">#${ia + 1}</th><th class="num">#${ib + 1}</th><th class="num">Pts #${ia + 1}</th><th class="num">Pts #${ib + 1}</th></tr></thead><tbody>
      ${rows.map(x => { const d = x.f.endsWith('_deg') ? 2 : 0, u = unitOf(body, x.f); return `<tr><td>${esc(label(x.f))}</td><td class="num">${fmt(x.t, d)}${u}</td><td class="num">${fmt(x.ea, d)}${u}</td><td class="num">${fmt(x.eb, d)}${u}</td><td class="num">${fmt(x.pa, 1)}</td><td class="num">${fmt(x.pb, 1)}</td></tr>`; }).join('')}
      <tr><td colspan="4">Terrain resemblance</td><td class="num text-green-300">${fmt(a.observed_fit, 1)}</td><td class="num text-green-300">${fmt(b.observed_fit, 1)}</td></tr></tbody></table>
      <p class="tt-note mt-2">#${ia + 1} scores ${fmt(Math.abs(diff), 2)} points ${diff >= 0 ? 'higher' : 'lower'}. The largest share of the difference comes from ${esc(label(top.f))} (${fmt(top.pa - top.pb, 2)} points). Differences under a point are well inside the uncalibrated tolerances and should not be read as a meaningful preference.</p>
      <div class="tt-card"><div class="tt-h">Earth context</div><table class="tt-table"><tbody>
        <tr><td>Barren class (2017)</td><td class="num">${pct(a.earth_environment_context?.landcover_barren_class_fraction)}</td><td class="num">${pct(b.earth_environment_context?.landcover_barren_class_fraction)}</td></tr>
        <tr><td>Aridity index (1970–2000)</td><td class="num">${fmt(a.earth_environment_context?.aridity_index, 3)}</td><td class="num">${fmt(b.earth_environment_context?.aridity_index, 3)}</td></tr>
        <tr><td>Cell area</td><td class="num">${fmt(a.area_km2, 0)} km²</td><td class="num">${fmt(b.area_km2, 0)} km²</td></tr>
        ${isNum(a.distance_from_origin_km) ? `<tr><td>Distance from origin</td><td class="num">${fmt(a.distance_from_origin_km, 0)} km</td><td class="num">${fmt(b.distance_from_origin_km, 0)} km</td></tr>` : ''}
      </tbody></table><p class="tt-note">Context only — it does not change either score.</p></div>`;
  }

  async function renderInvestigations() {
    const el = $('panelInvestigations'), m = state.meta;
    if (!m) { el.innerHTML = ''; return; }
    el.innerHTML = `<p class="tt-note">Finer, local investigations prepared separately from live search. They are not field-verified or newly discovered analogs.</p>
      ${m.investigations.map(s => `<div class="tt-card space-y-1">
        <div class="tt-h" style="color:#fdba74">${esc(s.title)}</div><p class="tt-note"><em>${esc(s.status.replace(/_/g, ' '))}</em></p>
        <p class="text-slate-300 text-[11px] leading-snug">${esc(s.summary)}</p>
        <ul class="tt-note list-disc ml-4">${s.caveats.map(c => `<li>${esc(c)}</li>`).join('')}</ul>
        <img loading="lazy" src="/api/v1/evidence/${esc(s.id)}/${esc(s.files.find(f => f.endsWith('.png')))}" alt="${esc(s.title)} context figure" class="w-full rounded border border-slate-700 bg-white">
        <div class="flex gap-2 flex-wrap"><button class="tt-btn px-2 py-1" data-study="${esc(s.id)}">Show footprint on Earth</button>
        ${s.files.filter(f => !f.endsWith('.png')).map(f => `<a href="/api/v1/evidence/${esc(s.id)}/${esc(f)}" target="_blank" rel="noopener" class="text-[11px]">${esc(f)}</a>`).join(' ')}</div>
      </div>`).join('')}
      <p class="tt-note"><a href="/api/v1/evidence/known_sites/review.md" target="_blank" rel="noopener">Known analog site review scope</a> — the portal feed is incomplete, so no novelty verdict is possible.</p>
      <div class="tt-card space-y-1"><div class="tt-h">Saved examples (offline demonstration)</div>
        <p class="tt-note">Release fixtures for use when live search or imagery is unavailable. Always labeled as saved; never shown as a new query.</p>
        <div id="savedList" class="flex gap-2 flex-wrap"><span class="tt-note">Loading…</span></div><div id="savedMsg"></div></div>`;
    el.querySelectorAll('[data-study]').forEach(b => b.onclick = () => showStudy(b.dataset.study));
    if (!state.savedCases) {
      const r = await api('/api/v1/cases');
      state.savedCases = r.ok ? r.data.cases : [];
    }
    if ($('savedList')) {
      $('savedList').innerHTML = state.savedCases.length ? state.savedCases.map(c => `<button class="tt-btn px-2 py-1" data-saved="${esc(c.id)}">${esc(c.title)}</button>`).join('') : '<span class="tt-note">None available.</span>';
      $('savedList').querySelectorAll('[data-saved]').forEach(b => b.onclick = () => loadSavedCase(b.dataset.saved));
    }
  }

  async function showStudy(id) {
    const s = state.meta.investigations.find(x => x.id === id);
    if (!state.studyGeo[id]) {
      const file = s.files.find(f => f.endsWith('.geojson'));
      const r = await api(`/api/v1/evidence/${id}/${file}`);
      if (!r.ok) return;
      state.studyGeo[id] = r.data.features.map((f, k) => ({ category: 'investigation', geometry: f.geometry,
        label: id === 'gobi' ? 'Gobi regional cell (local study)' : `Jaflong local patch ${k + 1} · ${f.properties.worldcover_class_name || ''} · no planetary score` }));
    }
    state.showStudies = true;
    GLOBE.setWorld('earth'); GLOBE.flyTo(s.lat, s.lon, id === 'jaflong' ? 0.02 : 0.15); GLOBE.refresh();
  }

  function renderAll() { renderTabs(); renderTarget(); renderResults(); renderEvidence(); renderCompare(); }

  // ------------------------------------------------------------------ exports
  function exportPayload() {
    const r = structuredClone(state.result), keep = settings().includeOrigin;
    const hadOrigin = !!r.client?.origin;
    if (hadOrigin && !keep) {
      if (r.configuration) r.configuration.origin = null;
      r.candidates.forEach(c => { c.distance_from_origin_km = null; });
      r.client.origin = null;
    }
    return { terratwin_export: { exported_at_utc: new Date().toISOString(), purpose: r.client?.purpose || null,
               origin_included: hadOrigin && keep, origin_omitted: hadOrigin && !keep,
               saved_fixture: r.saved_fixture || null,
               note: 'Experimental regional terrain screening. Scores are terrain resemblance indices, not accuracy, probability or suitability.' },
             ...r };
  }
  function exportGeoJSON() {
    const r = exportPayload();
    return { type: 'FeatureCollection',
             terratwin: { dataset_version: r.dataset_version, profile: r.profile, status: r.status, target_feature_id: r.target?.feature_id,
                          target_body: r.target?.body, score_label: r.score_label || 'Terrain resemblance', limitations: r.limitations,
                          export: r.terratwin_export, note: 'Earth candidate cell footprints only (WGS84). The planetary target cell is a different body and is in the JSON export.' },
             features: r.candidates.map((c, i) => { const { geometry, ...props } = c; return { type: 'Feature', geometry, properties: { rank: i + 1, ...props } }; }) };
  }
  function exportName(ext) {
    const r = state.result;
    return `terratwin_${r.dataset_version}_${(r.target?.feature_id || 'target').replace(':', '-')}_${r.profile}${r.saved_fixture ? '_saved' : ''}.${ext}`;
  }
  function download(name, text, type) {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const a = Object.assign(document.createElement('a'), { href: url, download: name });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  function briefHtml(index) {
    const r = exportPayload(), t = r.target, body = t?.body, x = r.terratwin_export, prof = profileById(r.profile);
    const c = isNum(index) ? r.candidates[index] : r.candidates[0];
    const ci = c ? r.candidates.indexOf(c) : -1;
    const row = (k, v) => `<tr><th>${esc(k)}</th><td>${v}</td></tr>`;
    const cmp = c ? `<table><thead><tr><th>Scored feature</th><th>${esc(BODY[body])}</th><th>Earth</th><th>|Δ|</th><th>Tolerance</th><th>Points</th></tr></thead><tbody>${c.comparisons.map(k => {
      const u = unitOf(body, k.feature), d = k.feature.endsWith('_deg') ? 2 : 1;
      return `<tr><td>${esc(label(k.feature))}</td><td>${fmt(k.target_value, d)}${u}</td><td>${fmt(k.earth_value, d)}${u}</td><td>${fmt(k.absolute_difference, d)}</td><td>${esc(r.configuration.tolerances[k.feature])}${u}</td><td>${fmt(k.fit_contribution, 2)} / ${fmt(100 * k.normalized_weight, 0)}</td></tr>`; }).join('')}
      <tr><td colspan="5"><strong>Terrain resemblance</strong></td><td><strong>${fmt(c.observed_fit, 2)}</strong></td></tr></tbody></table>` : '';
    const e = c?.earth_environment_context || {};
    const outcome = { ok: `${r.candidates.length} Earth candidate cells met the filters.`,
      no_candidates_under_filters: 'No Earth cell met every selected filter. This is a valid scientific outcome; no filter was relaxed.',
      target_insufficient_evidence: `The target cell lacks required integrated terrain (missing: ${(r.missing_terrain || []).join(', ')}). No candidates were produced.`,
      profile_unavailable: `The selected profile is unavailable; missing evidence: ${(r.missing_evidence || []).join(', ')}.` }[r.status];
    return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TerraTwin investigation brief</title><style>
body{font:14px/1.5 system-ui,sans-serif;color:#0f172a;background:#fff;max-width:860px;margin:2rem auto;padding:0 1rem}
h1{font-size:1.4rem;margin:0}h2{font-size:1.05rem;margin:1.6rem 0 .4rem;border-bottom:1px solid #cbd5e1;padding-bottom:.2rem}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:.25rem .4rem;border-bottom:1px solid #e2e8f0;vertical-align:top}
th{color:#475569;font-weight:600;width:34%}.warn{border:1px solid #f59e0b;background:#fffbeb;padding:.5rem .7rem;border-radius:6px}
.muted{color:#475569;font-size:12px}button{margin:.6rem 0;padding:.4rem .8rem}@media print{button{display:none}body{margin:0}}
</style></head><body>
<button onclick="print()">Print / save as PDF</button>
<h1>TerraTwin investigation brief</h1>
<p class="muted">Exported ${esc(x.exported_at_utc)} · dataset ${esc(r.dataset_version)} · profile ${esc(r.profile)} · API v${esc(r.api_version || '1')}${r.served_at_utc ? ` · query served ${esc(r.served_at_utc)}` : ''}</p>
${r.saved_fixture ? `<p class="warn"><strong>Saved example</strong> from release fixtures (${esc(r.saved_fixture.created_utc)}). Not a newly executed query.</p>` : ''}
<p class="warn">Experimental regional screening. “Terrain resemblance” is an uncalibrated index of agreement between four ~15 km regional terrain summaries. It is not accuracy, confidence, probability, safety or predicted hardware performance. No candidate is a verified or newly discovered analog.</p>
<h2>Purpose</h2><p>${esc(x.purpose || prof?.purpose || 'Not stated')}</p>
<h2>Planetary target</h2><table>
${row('Body', esc(BODY[body]))}${row('Requested point', `${fmt(t?.requested_lat, 4)}°, ${fmt(t?.requested_lon, 4)}°E`)}
${row('Regional cell containing this point', `${esc(t?.feature_id)} · centre ${fmt(t?.cell_center?.lat, 3)}°, ${fmt(t?.cell_center?.lon, 3)}°E · ${fmt(t?.area_km2, 1)} km²`)}
${row('Cell bounds (W, S, E, N)', t?.geometry ? esc([0, 0, 2, 2].map((p, k) => t.geometry.coordinates[0][p][k % 2]).join(', ')) : '—')}
${state.meta.core_terrain.map(f => row(label(f), t?.core_terrain?.[f] === null || t?.core_terrain?.[f] === undefined ? 'missing' : `${fmt(t.core_terrain[f], 2)}${unitOf(body, f)}`)).join('')}
${row('Interpretation', esc(t?.interpretation || ''))}</table>
<h2>Query and outcome</h2><table>
${row('Screening mode', esc(prof?.name || r.profile))}${row('Status', `${esc(r.status)} — ${esc(outcome)}`)}
${row('Filter counts', esc(countsLine(r) || '—'))}
${row('Distance constraint', r.configuration?.radius_km !== null && r.configuration?.radius_km !== undefined ? `${esc(r.configuration.radius_km)} km from ${x.origin_included ? `${esc(r.configuration.origin?.join(', '))}` : 'a private origin (omitted)'}` : (x.origin_omitted ? 'Origin used for distances only (omitted)' : 'None'))}
${row('Score parameters', `weights ${esc(JSON.stringify(r.configuration?.weights || {}))}; tolerances ${esc(JSON.stringify(r.configuration?.tolerances || {}))}; minimum ${esc(r.configuration?.minimum_fit)}; separation ${esc(r.configuration?.minimum_separation_km)} km; area ratio ${esc((r.configuration?.area_ratio || []).map(v => v.toFixed(3)).join('–'))}`)}</table>
${r.candidates.length ? `<h2>Candidates</h2><table><thead><tr><th>#</th><th>Cell</th><th>Centre</th><th>Area km²</th><th>Resemblance</th><th>Largest mismatch</th></tr></thead><tbody>
${r.candidates.map((k, i) => `<tr><td>${i + 1}</td><td>${esc(k.feature_id)}</td><td>${fmt(k.lat, 3)}, ${fmt(k.lon, 3)}</td><td>${fmt(k.area_km2, 0)}</td><td>${fmt(k.observed_fit, 2)}</td><td>${esc(label(k.largest_numeric_mismatch))}</td></tr>`).join('')}</tbody></table>` : ''}
${c ? `<h2>Selected candidate #${ci + 1}: ${esc(c.feature_id)}</h2><p>Earth cell centred ${fmt(c.lat, 4)}°, ${fmt(c.lon, 4)}°E, ${fmt(c.area_km2, 1)} km² (area ratio ${fmt(c.target_area_ratio, 3)})${isNum(c.distance_from_origin_km) ? `, ${fmt(c.distance_from_origin_km, 0)} km straight-line from the origin` : ''}.</p>${cmp}
<h2>Earth-only historical context (not scored)</h2><table>
${row('Land cover 2017: barren / water / built / crops', `${pct(e.landcover_barren_class_fraction)} / ${pct(e.landcover_water_class_fraction)} / ${pct(e.landcover_built_class_fraction)} / ${pct(e.landcover_cropland_or_mosaic_class_fraction)} (coverage ${pct(e.landcover_strict_area_coverage)})`)}
${row('Aridity index 1970–2000', `${fmt(e.aridity_index, 3)} ${aridityClass(e.aridity_index)} (coverage ${pct(e.aridity_index_area_coverage)})`)}
${row('NDVI 2001–2017 (provisional, unscored)', `mean ${fmt(e.ndvi_mean_provisional, 3)}, ${isNum(e.ndvi_valid_month_count) ? e.ndvi_valid_month_count : '—'} months, gap-filled ${pct(e.ndvi_gapfilled_area_time_fraction)}`)}
${row('Screening flags', `land cover ${c.land_cover_screened}, aridity ${c.aridity_screened}, vegetation ${c.vegetation_screened}, local site verified ${c.local_site_verified}, rank stability ${c.rank_stability === null ? 'not evaluated' : esc(c.rank_stability)}`)}
${row('Review status', esc(c.review_status))}</table>` : ''}
<h2>Proposed next measurements</h2><ol>${nextMeasurements(r, c).map(k => `<li>${esc(k)}</li>`).join('')}</ol>
<h2>Sources and limitations</h2>${provenanceHtml(r).replace(/class="[^"]*"/g, '')}
<p class="muted">Generated by TerraTwin from the response fields of this query. Missing values are shown as “—” or “missing”, never zero.</p>
</body></html>`;
  }
  function openBrief(index) {
    const html = briefHtml(index), url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
    const w = window.open(url, '_blank', 'noopener');
    if (!w) download(exportName('brief.html'), html, 'text/html'); // pop-up blocked: save instead
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  // ------------------------------------------------------------------ globe overlays + events
  function overlayPoints(w) {
    const out = [], t = state.target;
    if (t && t.body === w) out.push({ category: 'target', lat: t.lat, lng: t.lon, name: t.name, label: `${t.name} (selected point)` });
    if (w === 'earth' && state.result) visibleCandidates().forEach(i => {
      const c = state.result.candidates[i];
      out.push({ category: 'candidate', lat: c.lat, lng: c.lon, name: i === 0 ? '#1 · best match' : `#${i + 1}`, idx: i, pulse: (i === 0 && state.reveal?.stage === 'emerge') || (state.selected === i && state.reveal?.stage !== 'travel'),
                 label: `#${i + 1} · terrain resemblance ${fmt(c.observed_fit, 1)}` });
    });
    return out;
  }
  // GeoJSON exports keep RFC 7946 winding (exterior counter-clockwise). globe.gl draws with d3-geo's spherical
  // convention, where a counter-clockwise exterior means "the whole sphere except this cell", so display copies
  // get clockwise exteriors and counter-clockwise holes.
  function ringArea(ring) { let a = 0; for (let i = 0; i < ring.length - 1; i++) a += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]; return a / 2; }
  function orient(ring, clockwise) { return (ringArea(ring) < 0) === clockwise ? ring : [...ring].reverse(); }
  function forGlobe(g) {
    const poly = rings => rings.map((r, k) => orient(r, k === 0));
    if (g?.type === 'Polygon') return { type: 'Polygon', coordinates: poly(g.coordinates) };
    if (g?.type === 'MultiPolygon') return { type: 'MultiPolygon', coordinates: g.coordinates.map(poly) };
    return g;
  }
  // During the reveal no Earth candidate is drawn until the top one emerges; the others appear when it is done.
  function visibleCandidates() {
    const n = state.result?.candidates?.length || 0, stage = state.reveal?.stage;
    if (!n || stage === 'travel') return [];
    return stage === 'emerge' ? [0] : [...Array(n).keys()];
  }
  function overlayPolygons(w) {
    return rawPolygons(w).map(d => {
      const out = { ...d, geometry: forGlobe(d.geometry) };
      if (d.category === 'candidate' && d.idx === 0 && state.reveal?.stage === 'emerge') {
        Object.defineProperty(out, 'alpha', { get: () => 0.05 + 0.6 * state.reveal.t });
        Object.defineProperty(out, 'altitude', { get: () => 0.0005 + 0.02 * Math.sin(Math.PI * state.reveal.t) + 0.0035 * state.reveal.t });
      }
      return out;
    });
  }
  function rawPolygons(w) {
    const out = [], t = state.target;
    if (t?.cell && t.body === w) out.push({ category: 'target', geometry: t.cell.geometry, label: `Regional cell containing this point · ${t.cell.feature_id}` });
    if (w === 'earth') {
      visibleCandidates().forEach(i => { const c = state.result.candidates[i]; out.push({ category: 'candidate', geometry: c.geometry, idx: i,
        selected: state.selected === i, label: `#${i + 1} ${c.feature_id} · terrain resemblance ${fmt(c.observed_fit, 1)}` }); });
      if (state.showStudies) Object.values(state.studyGeo).forEach(list => out.push(...list));
    }
    return out;
  }
  function onGlobeClick(lat, lng) {
    const w = GLOBE.world();
    if (w === 'earth') {
      state.earthNote = 'Earth is where candidates appear. Earth points cannot be search targets; select a Moon or Mars region.';
      showTab('target'); renderTarget(); return;
    }
    setTarget(w, lat, lng, 'Surface point', 'click');
  }
  function onPolygonClick(d, lat, lng) {
    if (d.category === 'candidate') return selectCandidate(d.idx, false);
    if (d.category === 'investigation') return showTab('investigations');
    onGlobeClick(lat, lng);
  }
  function onPointClick(d) {
    if (d.category === 'candidate') return selectCandidate(d.idx, false);
    if (d.category === 'target') return showTab('target');
    const w = GLOBE.world();
    if (w === 'earth') {
      state.earthNote = `${esc(d.name)} is a known Earth analog shown for reference. It is not a retrieved candidate and was not scored.`;
      showTab('target'); renderTarget(); return;
    }
    const note = d.category === 'landing' ? 'Landing point: resolves to its own regional cell, which can differ from a named crater-centre cell.' : null;
    setTarget(w, d.lat, d.lng, d.name, 'site', note);
  }
  function onWorldChanged() { renderTabs(); }

  // ------------------------------------------------------------------ init
  async function init() {
    state.metaError = null; renderTarget();
    const [m, h] = await Promise.all([api('/api/v1/meta'), api('/api/v1/health')]);
    state.dem = h.data?.lunar_dem || null;
    if (!m.ok) { state.metaError = m.message; $('dataVersion').textContent = 'unavailable'; renderTarget(); return; }
    state.meta = m.data;
    $('dataVersion').textContent = `release ${m.data.dataset_version}`;
    $('examples').innerHTML = `<option value="">Choose an example…</option>` + m.data.examples.map(e => `<option value="${esc(e.id)}">${esc(e.label)}</option>`).join('');
    renderSearchForm(); renderAll(); renderInvestigations();
  }

  function wireStatic() {
    document.querySelectorAll('[data-tab]').forEach(b => b.onclick = () => { showTab(b.dataset.tab); if (b.dataset.tab === 'investigations') renderInvestigations(); });
    $('tabs').addEventListener('keydown', e => {
      if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
      const tabs = [...document.querySelectorAll('[data-tab]')], i = tabs.findIndex(t => t.dataset.tab === state.tab);
      const next = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
      showTab(next.dataset.tab); next.focus();
    });
    $('collapseBtn').onclick = () => {
      const c = $('card').classList.toggle('tt-collapsed');
      $('collapseBtn').setAttribute('aria-expanded', !c); $('collapseBtn').textContent = c ? '▴' : '▾';
    };
    $('returnBtn').onclick = returnToTarget;
    $('coordForm').onsubmit = e => {
      e.preventDefault();
      const lat = Number($('fLat').value.trim()), lon = Number($('fLon').value.trim()), body = $('fBody').value;
      const bad = $('fLat').value.trim() === '' || !Number.isFinite(lat) || lat < -90 || lat > 90 ? 'Latitude must be a number from −90 to 90.'
                : $('fLon').value.trim() === '' || !Number.isFinite(lon) || Math.abs(lon) > 540 ? 'Longitude must be a number (east-positive, e.g. −102.5 or 257.5).' : '';
      $('fLat').setAttribute('aria-invalid', bad.startsWith('Lat')); $('fLon').setAttribute('aria-invalid', bad.startsWith('Lon'));
      $('coordError').textContent = bad; $('coordError').classList.toggle('hidden', !bad);
      if (!bad) setTarget(body, lat, lon, `Entered point`, 'coords');
    };
    $('examples').onchange = async () => {
      const ex = state.meta?.examples.find(e => e.id === $('examples').value);
      $('exampleNote').textContent = ex?.note || '';
      if (!ex) return;
      await setTarget(ex.body, ex.lat, ex.lon, ex.label, 'example', ex.note);
      const radio = document.querySelector(`input[name="profile"][value="${ex.profile}"]`);
      if (radio) radio.checked = true;
      $('sOriginLat').value = ex.origin?.lat ?? ''; $('sOriginLon').value = ex.origin?.lon ?? ''; $('sRadius').value = ex.radius_km ?? '';
      $('originBox').open = !!ex.origin;
      runSearch();
    };
  }

  wireStatic();
  showTab('target');
  init();
  return { overlayPoints, overlayPolygons, onGlobeClick, onPolygonClick, onPointClick, onWorldChanged, interrupt, skipReveal,
           state, setTarget, runSearch, selectCandidate };
})();
GLOBE.refresh();
