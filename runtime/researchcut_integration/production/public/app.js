'use strict';

const $ = (q, root = document) => root.querySelector(q);
const $$ = (q, root = document) => [...root.querySelectorAll(q)];
const app = $('#app');
const waveCache = new Map();
let token = '';
let project = null;
let serverRevision = 0;
let selectedId = null;
let currentTime = 0;
let playing = false;
let lastFrame = 0;
let pxPerSec = 14;
let saveTimer = null;
let saveRunning = false;
let saveAgain = false;
let undoStack = [];
let redoStack = [];
let activeSignature = '';
let toastTimer = null;
let cropEditingId = null;
let previewVolume = 1;
let previewMuted = false;
let automationCatalog = null;
let automateDraft = null;
let automationPreviewClipId = null;
let queueTimer = null;
let theme = localStorage.getItem('researchcut:theme') || 'dark';
document.documentElement.dataset.theme = theme;

function trackOrderValue(id) { return id?.startsWith('V') ? Number(id.slice(1)) || 0 : 0; }
function svgIcon(name){const paths={play:'<path d="M8 5v14l11-7z"/>',pause:'<path d="M7 5h4v14H7zm6 0h4v14h-4z"/>',prev:'<path d="M6 5h2v14H6zm12 1-9 6 9 6z"/>',next:'<path d="M16 5h2v14h-2zM6 6l9 6-9 6z"/>',undo:'<path d="M9 7V3L3 9l6 6v-4c5 0 8 1 10 5-1-6-4-9-10-9z"/>',redo:'<path d="M15 7V3l6 6-6 6v-4c-5 0-8 1-10 5 1-6 4-9 10-9z"/>',split:'<path d="M9 3v18m6-18v18M3 8h4m10 0h4M3 16h4m10 0h4" fill="none" stroke="currentColor" stroke-width="2"/>',trash:'<path d="M7 7h10l-1 13H8L7 7zm2-3h6l1 2H8l1-2z"/>',volume:'<path d="M4 10v4h4l5 4V6L8 10H4zm11-1c2 2 2 4 0 6m2-8c4 3 4 7 0 10" fill="none" stroke="currentColor" stroke-width="2"/>',mute:'<path d="M4 10v4h4l5 4V6L8 10H4zm11 0 5 5m0-5-5 5" fill="none" stroke="currentColor" stroke-width="2"/>',fullscreen:'<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5" fill="none" stroke="currentColor" stroke-width="2"/>',music:'<path d="M9 5v12a3 3 0 1 1-2-3V7l11-2v10a3 3 0 1 1-2-3V3L9 5z"/>'};return `<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true">${paths[name]||''}</svg>`}
const icon={play:svgIcon('play'),pause:svgIcon('pause'),back:svgIcon('prev'),next:svgIcon('next'),split:svgIcon('split'),trash:svgIcon('trash'),undo:svgIcon('undo'),redo:svgIcon('redo'),volume:svgIcon('volume'),mute:svgIcon('mute'),fullscreen:svgIcon('fullscreen'),music:svgIcon('music')};

function esc(value) { return String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[c]); }
function fmt(sec, fine = false) {
  sec = Math.max(0, Number(sec) || 0); const h = Math.floor(sec / 3600); const m = Math.floor(sec % 3600 / 60); const s = Math.floor(sec % 60);
  const base = h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return fine ? `${base}.${String(Math.floor(sec * 10) % 10)}` : base;
}
function duration() {
  if (!project) return 0;
  return Math.max(0, ...project.clips.map(c => c.start + c.duration));
}
function asset(id) { return project?.assets.find(a => a.id === id); }
function track(id) { return project?.tracks.find(t => t.id === id); }
function clip(id = selectedId) { return project?.clips.find(c => c.id === id); }
function mediaUrl(a) { return `/media/${project.id}/${a.id}?token=${token}`; }
function thumbUrl(a) { return `/thumb/${project.id}/${a.id}?token=${token}&v=${a.hash?.slice(0, 8) || 0}`; }
function apiUrl(route) { return route + (route.includes('?') ? '&' : '?') + 'token=' + token; }
async function api(route, options = {}) {
  const headers = { ...(options.headers || {}), 'x-editor-token': token };
  if (options.body && typeof options.body === 'string') headers['content-type'] = 'application/json';
  const response = await fetch(route, { ...options, headers });
  let data = null; try { data = await response.json(); } catch {}
  if (!response.ok) { const error = new Error(data?.message || `Request failed (${response.status})`); error.status = response.status; error.data = data; throw error; }
  return data;
}
function toast(message, error = false) {
  const node = $('#toast'); node.textContent = message; node.className = 'toast show' + (error ? ' error' : '');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => node.className = 'toast', 2600);
}
function snapshot() { return JSON.stringify({ name: project.name, settings: project.settings, tracks: project.tracks, clips: project.clips }); }
function migrateClient(value) {
  const defaults = [
    { id: 'V3', kind: 'video', name: 'Overlay 2', muted: false, locked: false, magnetic: false },
    { id: 'V2', kind: 'video', name: 'Overlay 1', muted: false, locked: false, magnetic: false },
    { id: 'V1', kind: 'video', name: 'Main video', muted: true, locked: false, magnetic: false },
    { id: 'A1', kind: 'audio', name: 'Voiceover', muted: false, locked: false, magnetic: false },
    { id: 'A2', kind: 'audio', name: 'Music & SFX', muted: false, locked: false, magnetic: false }
  ];
  const current = Array.isArray(value.tracks) ? value.tracks : [];
  const base = defaults.map(d => ({ ...d, ...current.find(t => t.id === d.id) }));
  const extras = current.filter(t => !defaults.some(d => d.id === t.id) && /^[VA]\d+$/.test(t.id)).map(t => ({ ...t, kind: t.id.startsWith('A') ? 'audio' : 'video', magnetic: false }));
  value.tracks = [...extras.filter(t => t.kind === 'video').sort((a,b) => Number(b.id.slice(1)) - Number(a.id.slice(1))), ...base.filter(t => t.kind === 'video'), ...base.filter(t => t.kind === 'audio'), ...extras.filter(t => t.kind === 'audio').sort((a,b) => Number(a.id.slice(1)) - Number(b.id.slice(1)))];
  value.clips = (value.clips || []).map(c => ({ ...c, transform: { x: 0, y: 0, scale: 1, rotation: 0, fit: 'fill', opacity: 1, ...(c.transform || {}), crop: { top: 0, right: 0, bottom: 0, left: 0, ...(c.transform?.crop || {}) } } }));
  value.automation ||= { enabled: true, presetId: 'clean_documentary_01', seed: 812930, intensity: 'balanced', transitionsEnabled: true, motionEnabled: true, backgroundMode: 'auto', backgroundId: null, solidColor: '#0b1011', text: { enabled: false, eventCount: 0, samples: [], niche: 'auto', pack: 'auto', energy: 3, scale: 'auto', density: 'file' }, export: { resolution: '1080p', quality: 'balanced' }, overrides: {}, plan: null };
  return value;
}
function restore(raw) {
  const value = migrateClient(JSON.parse(raw)); project.name = value.name; project.settings = value.settings; project.tracks = value.tracks; project.clips = value.clips;
  if (selectedId && !clip()) selectedId = null; normalizeMagnetic(); markDirty(); renderEditorParts();
}
function remember() { undoStack.push(snapshot()); if (undoStack.length > 100) undoStack.shift(); redoStack = []; }
function undo() { if (!undoStack.length) return; redoStack.push(snapshot()); restore(undoStack.pop()); }
function redo() { if (!redoStack.length) return; undoStack.push(snapshot()); restore(redoStack.pop()); }
function setSaveState(state, text) {
  const el = $('#saveState'); if (!el) return; el.className = `save-state ${state || ''}`; $('.save-label', el).textContent = text;
}
function markDirty() {
  if (!project) return;
  project.updatedAt = new Date().toISOString();
  try { localStorage.setItem(`researchcut:${project.id}`, JSON.stringify({ savedAt: Date.now(), project })); } catch {}
  setSaveState('saving', 'Saving...'); clearTimeout(saveTimer); saveTimer = setTimeout(saveNow, 450);
}
async function saveNow() {
  if (!project) return;
  if (saveRunning) { saveAgain = true; return; }
  saveRunning = true; const payload = JSON.parse(JSON.stringify(project)); const baseRevision = serverRevision;
  try {
    const result = await api(`/api/projects/${project.id}/save`, { method: 'POST', body: JSON.stringify({ baseRevision, project: payload }) });
    serverRevision = result.revision; project.revision = result.revision; project.updatedAt = result.updatedAt;
    localStorage.removeItem(`researchcut:${project.id}`); setSaveState('', 'Saved locally');
  } catch (error) {
    if (error.status === 409) {
      toast('Another window saved a newer version. Reloading it.', true);
      project = error.data.project; serverRevision = project.revision; selectedId = null; renderEditor();
    } else { setSaveState('error', 'Save retrying'); saveAgain = true; setTimeout(saveNow, 1800); }
  } finally {
    saveRunning = false; if (saveAgain) { saveAgain = false; clearTimeout(saveTimer); saveTimer = setTimeout(saveNow, 50); }
  }
}
async function flushSave() {
  clearTimeout(saveTimer);
  while (saveRunning) await new Promise(resolve => setTimeout(resolve, 25));
  saveAgain = false; clearTimeout(saveTimer); await saveNow();
  while (saveRunning) await new Promise(resolve => setTimeout(resolve, 25));
}

async function boot() {
  try { token = (await fetch('/api/config').then(r => r.json())).token; await renderHome(); }
  catch (error) { app.innerHTML = `<div class="no-selection"><div><h2>Editor could not start</h2><p>${esc(error.message)}</p></div></div>`; }
}
async function renderHome() {
  project = null; playing = false; const { projects } = await api('/api/projects');
  app.innerHTML = `<main class="home"><div class="home-inner">
    <div class="home-head"><div><div class="brand"><span class="brand-mark">S</span> SceneBrain</div><h1>Projects</h1><p>Prepared productions and local edits.</p></div><div><button class="btn" id="libraryHome">Library</button> <button class="btn primary" id="newProject">New Project</button></div></div>
    <div class="project-grid">${projects.length ? projects.map(p => `<article class="project-card" data-id="${p.id}"><div class="thumb">Play</div><h3>${esc(p.name)}</h3><div class="project-meta"><span>${fmt(p.duration)}</span><span>${p.assets} media</span><span>${relative(p.updatedAt)}</span></div><div><button class="btn" data-edit="${p.id}">Edit</button> <button class="btn" data-copy="${p.id}">Duplicate</button> <button class="btn" data-delete="${p.id}">Delete</button></div></article>`).join('') : `<div class="empty-home"><h3>No projects yet</h3><p>Create a project to begin.</p></div>`}</div>
  </div></main>`;
  $('#libraryHome').onclick=renderLibrary; $('#newProject').onclick=renderNewProject;
  $$('[data-edit]').forEach(b=>b.onclick=async()=>openProject((await api(`/api/projects/${b.dataset.edit}`)).project));
  $$('[data-copy]').forEach(b=>b.onclick=async()=>{await api(`/api/projects/${b.dataset.copy}/duplicate`,{method:'POST'});renderHome()});
  $$('[data-delete]').forEach(b=>b.onclick=async()=>{if(confirm('Delete this project?')){await api(`/api/projects/${b.dataset.delete}`,{method:'DELETE'});renderHome()}});
}
async function renderLibraryLegacy(){return renderLibrary()}
function renderNewProjectLegacy(){return renderNewProject()}

function shellHead(title,subtitle=''){return `<div class="product-nav"><div class="brand"><span class="brand-mark">S</span> SceneBrain</div><nav><button class="btn ghost" data-nav="library">Library</button><button class="btn ghost" data-nav="projects">Projects</button><button class="btn ghost" data-nav="new">New Project</button><button class="btn ghost" data-nav="performance">System Health</button></nav></div><div class="page-title"><div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div></div>`}
function bindProductNav(){$$('[data-nav=library]').forEach(x=>x.onclick=renderLibrary);$$('[data-nav=projects]').forEach(x=>x.onclick=renderHome);$$('[data-nav=new]').forEach(x=>x.onclick=renderNewProject);$$('[data-nav=performance]').forEach(x=>x.onclick=renderPerformance)}
function characterImageUrl(titleId,characterId,ref){const name=String(ref.canonical_path||'').split(/[\\/]/).pop();return apiUrl(`/character-image/${encodeURIComponent(titleId)}/${encodeURIComponent(characterId)}/${encodeURIComponent(name)}`)}
async function renderLibrary(){project=null;playing=false;const {titles}=await api('/api/scene-brain/library');app.innerHTML=`<main class="home product-page"><div class="home-inner">${shellHead('Library','Your portable Film & TV production library')}<div class="page-actions"><button class="btn primary" id="addTitle">+ Add New Title</button><button class="btn" id="rescanLibrary">Rescan Library</button><span id="scanStatus"></span></div><div class="library-grid">${titles.map(t=>`<article class="library-card" data-title="${t.title_id}"><div><span class="status ${t.health==='READY'?'ready':'needed'}">${t.health}</span><h3>${esc(t.title)}</h3><p>${t.kind==='SERIES'?'Series / TV Show':'Movie'} · ${t.episodes} sources</p></div><dl><div><dt>Search ready</dt><dd>${t.searchable}/${t.episodes}</dd></div><div><dt>Rich</dt><dd>${t.rich}</dd></div><div><dt>Characters</dt><dd>${t.characters}</dd></div></dl><button class="btn" data-characters="${t.title_id}" data-title-name="${esc(t.title)}">Characters</button></article>`).join('')}</div></div></main>`;bindProductNav();$('#addTitle').onclick=renderAddTitle;$('#rescanLibrary').onclick=async()=>{const b=$('#rescanLibrary');b.disabled=true;b.textContent='Scanning…';const r=await api('/api/scene-brain/rescan',{method:'POST'});$('#scanStatus').textContent=`${r.checked} sources checked · ${r.unchanged} unchanged`;b.disabled=false;b.textContent='Rescan Library'};$$('[data-characters]').forEach(b=>b.onclick=()=>renderCharacters(b.dataset.characters,b.dataset.titleName))}
async function renderNewProject(){project=null;playing=false;const {titles}=await api('/api/scene-brain/library');app.innerHTML=`<main class="home product-page"><div class="home-inner">${shellHead('New Project','Analyze first. Prepare only when the plan is ready.')}<div class="intake-layout"><section class="form-card"><h2>1 · Project</h2><label>Project Name<input id="intakeName" value="Untitled SceneBrain project"></label></section><section class="form-card"><h2>2 · Inputs</h2><div class="upload-grid">${uploadCard('intakeScript','Clean Script','.txt,.md,text/plain','Browse Script')}${uploadCard('intakeVoice','Final Voiceover','audio/*','Browse Audio')}${uploadCard('intakeClue','Prepared Clue Script','.json,.txt,.md','Browse Clue')}</div></section><section class="form-card"><h2>3 · Source</h2><div class="field-grid"><label>Source Scope<select id="intakeScope"><option>Single Title</option><option>Franchise</option><option>Custom Multi-Title</option></select></label><label>Selected Title<select id="intakeTitle">${titles.map(t=>`<option>${esc(t.title)}</option>`).join('')}</select></label></div><button class="btn" id="addTitle">+ Add New Title</button></section><section class="form-card"><h2>4 · Optional Intelligence</h2><div class="readiness-row"><span>Character Recognition</span><b>Availability checked during analysis</b></div><label>Gemini Budget<select id="geminiBudget"><option value="0">Disabled</option><option value=".25">$0.25</option><option value=".5">$0.50</option><option value="1">$1.00</option></select></label></section><section class="analysis-card" id="projectAnalysis"><h2>Project Intelligence</h2><p>Upload a clean script, then analyze the project before preparation.</p></section><div class="action-bar"><button class="btn" id="analyzeProject">Analyze Project</button><button class="btn primary" id="prepareProject" disabled>Prepare Project</button></div><section id="intakeStatus" class="progress-card hidden"></section></div></div></main>`;bindProductNav();bindUploadCards();$('#addTitle').onclick=renderAddTitle;$('#analyzeProject').onclick=async()=>{const f=$('#intakeScript').files[0];if(!f)return toast('Clean script is required',true);const r=await api('/api/scene-brain/analyze',{method:'POST',body:JSON.stringify({script:await f.text(),gemini_budget:$('#geminiBudget').value})}),a=r.analysis;$('#projectAnalysis').innerHTML=`<h2>Project Analysis</h2><div class="analysis-grid"><div><span>Script</span><b>${a.word_count} words</b></div><div><span>Semantic Beats</span><b>${a.estimated_semantic_beats}</b></div><div><span>Visual Opportunities</span><b>${a.estimated_visual_opportunities}</b></div><div><span>Source Library</span><b>${esc($('#intakeTitle').value)}</b></div></div><h3>Relevant Characters</h3><div class="character-chips">${a.characters.map(x=>`<span>${esc(x.name)} · ${esc(x.gallery)}</span>`).join('')||'<span>None confidently identified</span>'}</div><p>Missing or partial character galleries do not block preparation. Gemini: ${Number($('#geminiBudget').value)?'Enabled with budget':'Disabled'}.</p>`;$('#prepareProject').disabled=false};$('#prepareProject').onclick=async()=>{const s=$('#intakeStatus');s.classList.remove('hidden');s.innerHTML=`<h3>Preparing Project</h3>${['Analyzing Script','Checking Library','Checking Characters','Using Existing Memory','Finding Sources','Preparing Missing Episodes','Retrieving Visuals','Visual Verification','Building First Cut'].map((x,i)=>`<div class="stage-row"><span>${x}</span><b>${i<3?'DONE':'QUEUED'}</b></div>`).join('')}<button class="btn" id="copySupport">Copy Support Report</button>`;$('#copySupport').onclick=async()=>{const r=await api('/api/scene-brain/support',{method:'POST',body:JSON.stringify({project_id:null})});await navigator.clipboard?.writeText(JSON.stringify(r.report,null,2));toast('Support report copied')}}}
function uploadCard(id,label,accept,button){return `<label class="upload-card"><span>${label}</span><b data-file-label="${id}">No file selected</b><small data-file-meta="${id}">Supported file types</small><em>${button}</em><input id="${id}" type="file" accept="${accept}"></label>`}
function bindUploadCards(){$$('.upload-card input').forEach(i=>i.onchange=()=>{const f=i.files[0];$(`[data-file-label=${i.id}]`).textContent=f?.name||'No file selected';$(`[data-file-meta=${i.id}]`).textContent=f?`${(f.size/1024).toFixed(1)} KB · Validated`:'Supported file types'})}
function renderAddTitle(){app.innerHTML=`<main class="home product-page"><div class="home-inner">${shellHead('Add New Title','Catalog and search readiness first. Rich indexing remains lazy.')}<div class="wizard"><div class="wizard-steps"><b>1 Type</b><b>2 Information</b><b>3 Source</b><b>4 Preview</b><b>5 Validate</b><b>6 Add</b></div><section class="form-card"><div class="field-grid"><label>Type<select id="titleType"><option value="MOVIE">Movie</option><option value="SERIES">Series / TV Show</option></select></label><label>Canonical Title<input id="titleName" placeholder="Title"></label><label>Optional Franchise<input id="titleFranchise" placeholder="Optional"></label><label>Optional Year<input id="titleYear" type="number"></label></div><label class="upload-card"><span>Source</span><b id="titleSourceLabel">Select a movie file or series folder</b><em>Browse Source</em><input id="titleFiles" type="file" accept="video/*" multiple></label><button class="btn" id="previewTitle">Preview Discovery</button><div id="titlePreview" class="preview-list"></div><button class="btn primary" id="commitTitle" disabled>Add to Library</button></section></div></div></main>`;bindProductNav();const files=$('#titleFiles');files.toggleAttribute('webkitdirectory',$('#titleType').value==='SERIES');files.onchange=()=>{$('#titleSourceLabel').textContent=`${files.files.length} file(s) selected`};$('#titleType').onchange=()=>files.toggleAttribute('webkitdirectory',$('#titleType').value==='SERIES');$('#previewTitle').onclick=()=>{const rows=[...files.files].map(f=>({name:f.webkitRelativePath||f.name,size:f.size,status:/S\d+E\d+/i.test(f.name)||$('#titleType').value==='MOVIE'?'READY':'NAME NEEDS REVIEW'}));$('#titlePreview').innerHTML=rows.map(x=>`<div><span>${esc(x.name)}</span><b>${x.status}</b></div>`).join('')||'<p>Select source media first.</p>';$('#commitTitle').disabled=!rows.length||!$('#titleName').value};$('#commitTitle').onclick=async()=>{const title=$('#titleName').value;for(const f of files.files)await api(`/api/scene-brain/onboard-file`,{method:'POST',headers:{'x-title-name':title,'x-file-name':encodeURIComponent(f.name)},body:f});await api('/api/scene-brain/onboard-finalize',{method:'POST',body:JSON.stringify({title,type:$('#titleType').value})});renderLibrary()}}
async function renderCharacters(titleId,title){const data=await api(`/api/scene-brain/characters?title_id=${encodeURIComponent(titleId)}`);app.innerHTML=`<main class="home product-page"><div class="home-inner">${shellHead(`${title} · Characters`,'Trusted references are portable. Partial galleries never block projects.')}<div class="page-actions"><button class="btn primary" id="importCharacters">Import Character Folder</button><button class="btn">Add Character</button><button class="btn">Review Suggested References</button></div><div class="character-grid">${(data.characters||[]).map(c=>`<article class="character-card"><h3>${esc(c.display_name)}</h3><b class="status needed">${c.gallery_status}</b><p>${c.trusted_references} trusted · ${c.total_references} total</p><small>Embeddings: ${c.embedding_status}</small><div class="reference-strip">${c.references.slice(0,5).map(r=>`<img src="${characterImageUrl(titleId,c.character_id,r)}" alt="${esc(c.display_name)}">`).join('')}</div></article>`).join('')||'<p>No character gallery imported yet.</p>'}</div></div></main>`;bindProductNav();$('#importCharacters').onclick=async()=>{const source=prompt('Character folder path',`${'C:\\Users\\Dell\\Desktop\\Characters\\Breaking Bad'}`);if(!source)return;await api('/api/scene-brain/characters/import',{method:'POST',body:JSON.stringify({title,source})});renderCharacters(titleId,title)}}
async function renderPerformance(){const d=await api('/api/scene-brain/gpu'),c=d.capabilities,r=d.runtime;app.innerHTML=`<main class="home product-page"><div class="home-inner">${shellHead('System Health & Performance','AUTO uses only validated stable backends.')}<section class="form-card"><label>Processing Profile<select><option>AUTO — Recommended</option><option>GPU Preferred</option><option>CPU Only</option></select></label><div class="gpu-card"><h2>${esc(c.gpu_name||'No NVIDIA GPU detected')}</h2><p>${c.vram_mib||0} MB VRAM · Driver ${esc(c.driver||'Unknown')}</p><p>Windows GPU numbering is not the CUDA device index.</p></div><div class="capability-grid"><div><span>Whisper</span><b>CPU (validated)</b></div><div><span>Face ID</span><b>CPU</b></div><div><span>Embeddings</span><b>CPU</b></div><div><span>FFmpeg</span><b>Software</b></div></div><div class="warning-card">NVIDIA Quadro P1000 detected, but current PyTorch, Whisper CUDA, OpenCV CUDA DNN, and NVENC runtime paths are not compatible/stable. AUTO safely uses CPU. GPU jobs remain limited to one.</div></section></div></main>`;bindProductNav()}
function relative(date) {
  const sec = Math.max(0, (Date.now() - new Date(date).getTime()) / 1000); if (sec < 60) return 'just now'; if (sec < 3600) return `${Math.floor(sec / 60)}m ago`; if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`; return `${Math.floor(sec / 86400)}d ago`;
}
function openProject(value) {
  project = migrateClient(value); serverRevision = value.revision; selectedId = null; cropEditingId = null; currentTime = 0; undoStack = []; redoStack = [];
  const recovery = localStorage.getItem(`researchcut:${project.id}`);
  if (recovery) {
    try { const local = JSON.parse(recovery); if (local.project.updatedAt > project.updatedAt) { project = migrateClient(local.project); serverRevision = value.revision; toast('Recovered unsaved work from the last session'); markDirty(); } } catch {}
  }
  renderEditor();
}
function renderEditor() {
  app.innerHTML = `<div class="app-shell">
    <header class="topbar"><button class="btn ghost" id="libraryNav">Library</button><button class="btn ghost" id="homeBtn">Projects</button><button class="btn ghost" id="newProjectNav">New Project</button><div class="top-divider"></div><div class="brand"><span class="brand-mark">S</span><span>SceneBrain</span><span class="brand-sub">RESEARCHCUT EDITOR</span></div><input id="projectTitle" class="project-title" value="${esc(project.name)}" title="${esc(project.name)}" aria-label="Project name"><div class="top-spacer"></div><button class="btn ghost" id="performanceBtn">Performance</button><button class="btn ghost" id="supportBtn">Support</button><button class="btn ghost" id="undoBtn" aria-label="Undo" title="Undo (Ctrl+Z)">${icon.undo}</button><button class="btn ghost" id="redoBtn" aria-label="Redo" title="Redo (Ctrl+Y)">${icon.redo}</button><button class="btn ghost" id="themeBtn" title="Switch appearance">${theme === 'dark' ? 'Light' : 'Dark'}</button><button class="btn ghost" id="viewBtn" title="Fullscreen preview">${icon.fullscreen}<span>View</span></button><div class="save-state" id="saveState"><span class="save-dot"></span><span class="save-label">Saved locally</span></div><button class="btn primary" id="nextBtn">Next: Automate</button></header>
    <div class="editor-main">
      <aside class="media-panel"><div class="panel-head"><span class="panel-title">Project media</span><span class="panel-note" id="assetCount"></span></div><label class="import-drop" id="importDrop">+ Import images, videos or audio<input class="hidden" id="fileInput" type="file" multiple accept="image/*,video/*,audio/*"></label><div class="media-tabs"><span class="media-tab active" data-filter="all">All</span><span class="media-tab" data-filter="video">Video</span><span class="media-tab" data-filter="image">Images</span><span class="media-tab" data-filter="audio">Audio</span></div><div class="media-list" id="mediaList" aria-live="polite"></div></aside>
      <section class="workspace"><div class="preview-zone" id="previewZone"><div class="preview-wrap"><div class="stage" id="stage"><div class="stage-empty">Drop media on the timeline to begin</div></div></div><div class="transport player-transport"><button class="player-icon" id="prevCut" aria-label="Previous cut" title="Previous cut">${icon.back}</button><button class="player-skip" id="rewind5" aria-label="Back 5 seconds" title="Back 5 seconds">-5s</button><button class="player-icon play" id="playBtn" aria-label="Play" title="Play (Space)">${icon.play}</button><button class="player-skip" id="forward5" aria-label="Forward 5 seconds" title="Forward 5 seconds">+5s</button><button class="player-icon" id="nextCut" aria-label="Next cut" title="Next cut">${icon.next}</button><span class="player-time mono" id="playerCurrent">${fmt(0, true)}</span><span class="time-separator">/</span><span class="player-time mono" id="playerDuration">${fmt(duration(), true)}</span><input class="player-seek" id="playerSeek" type="range" min="0" max="${duration()}" step="0.01" value="0" aria-label="Timeline position"><button class="player-icon" id="previewMute" aria-label="Mute preview" title="Mute preview">${icon.volume}</button><input class="player-volume" id="previewVolume" type="range" min="0" max="1" step="0.01" value="1" aria-label="Preview volume"><button class="player-icon" id="fullPreview" aria-label="Fullscreen preview" title="Fullscreen preview (F)">${icon.fullscreen}</button></div></div>
      <div class="timeline"><div class="timeline-toolbar"><button class="tool-btn" id="splitBtn" aria-label="Split at playhead" title="Split video or audio at playhead (S)">${icon.split}</button><button class="tool-btn" id="deleteBtn" aria-label="Delete selected clip" title="Delete selected clip">${icon.trash}</button><button class="track-add" id="addVideoTrack" title="Add another visual layer">+ Visual layer</button><button class="track-add" id="addAudioTrack" title="Add another audio layer">+ Audio layer</button><span class="timeline-hint">Space: play | S: split | Ctrl+wheel: zoom</span><label class="timeline-zoom">Timeline zoom <input id="zoom" type="range" min="0" max="100" value="${zoomValue()}"></label></div><div class="timeline-area"><div class="track-labels" id="trackLabels"></div><div class="timeline-scroll" id="timelineScroll"><div class="timeline-content" id="timelineContent"></div></div></div></div></section>
      <aside class="inspector"><div class="panel-head"><span class="panel-title">Inspector</span><span class="panel-note">16:9</span></div><div class="inspector-body" id="inspector"></div></aside>
    </div></div>`;
  bindEditor(); renderEditorParts(); requestAnimationFrame(frame);
}
function bindEditor() {
  $('#homeBtn').onclick = async () => { await flushSave(); renderHome(); };
  $('#libraryNav').onclick = async () => { await flushSave(); renderLibrary(); };
  $('#newProjectNav').onclick = async () => { await flushSave(); renderNewProject(); };
  $('#performanceBtn').onclick = async () => { await flushSave(); renderPerformance(); };
  $('#projectTitle').oninput = e => { if (e.target.value === project.name) return; remember(); project.name = e.target.value; markDirty(); };
  $('#undoBtn').onclick = undo; $('#redoBtn').onclick = redo; $('#playBtn').onclick = togglePlay; $('#prevCut').onclick = () => jumpCut(-1); $('#nextCut').onclick = () => jumpCut(1);
  $('#rewind5').onclick = () => seek(currentTime - 5); $('#forward5').onclick = () => seek(currentTime + 5);
  $('#playerSeek').oninput = e => seek(Number(e.target.value));
  $('#previewVolume').oninput = e => { previewVolume = Number(e.target.value); previewMuted = false; $('#previewMute').innerHTML = previewVolume > .01 ? icon.volume : icon.mute; syncMedia(true); paintPlayerRange(); };
  $('#previewMute').onclick = () => { previewMuted = !previewMuted; $('#previewMute').innerHTML = previewMuted ? icon.mute : icon.volume; $('#previewMute').ariaLabel=previewMuted?'Unmute preview':'Mute preview'; syncMedia(true); };
  $('#themeBtn').onclick = toggleTheme; $('#viewBtn').onclick = toggleFullscreen; $('#fullPreview').onclick = toggleFullscreen;
  $('#supportBtn').onclick=async()=>{const r=await api('/api/scene-brain/support',{method:'POST',body:JSON.stringify({project_id:project.id})});try{await navigator.clipboard?.writeText(JSON.stringify(r.report,null,2));toast('Sanitized support report copied')}catch{toast('Support report created; clipboard permission unavailable')}};
  $('#splitBtn').onclick = splitSelected; $('#deleteBtn').onclick = deleteSelected; $('#nextBtn').onclick = openAutomate;
  $('#addVideoTrack').onclick = () => addTrack('video'); $('#addAudioTrack').onclick = () => addTrack('audio');
  $('#zoom').oninput = e => { pxPerSec = .5 * Math.pow(120, Number(e.target.value) / 100); renderTimeline(); };
  $('#timelineScroll').addEventListener('wheel', timelineWheel, { passive: false });
  $('#timelineScroll').addEventListener('scroll', () => { const labels = $('#trackLabels'); if (labels) labels.scrollTop = $('#timelineScroll').scrollTop; });
  const input = $('#fileInput'), drop = $('#importDrop'); drop.onclick = () => input.click(); input.onchange = () => importFiles([...input.files]);
  drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); }; drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); importFiles([...e.dataTransfer.files]); };
  $$('.media-tab').forEach(tab => tab.onclick = () => { $$('.media-tab').forEach(x => x.classList.remove('active')); tab.classList.add('active'); renderMedia(tab.dataset.filter); });
}
function renderEditorParts() { renderMedia($('.media-tab.active')?.dataset.filter || 'all'); renderTracks(); renderTimeline(); renderStage(true); renderInspector(); updateTimeUI(); }
function renderMedia(filter = 'all') {
  if (!project || !$('#mediaList')) return; const assets = project.assets.filter(a => filter === 'all' || a.kind === filter); $('#assetCount').textContent = `${project.assets.length} items`;
  $('#mediaList').innerHTML = assets.length ? assets.map(a => `<div class="asset" draggable="true" data-asset="${a.id}" title="${esc(a.name)}"><div class="asset-thumb" data-thumb="${a.id}" style="${a.kind !== 'audio' ? `background-image:url('${thumbUrl(a)}')` : ''}">${a.kind === 'audio' ? icon.music : ''}<span class="asset-kind">${a.kind}</span><span class="thumb-error hidden">Thumbnail failed<br><button class="btn" data-retry-thumb="${a.id}">Retry</button></span></div><div class="asset-info"><div class="asset-name">${esc(a.name)}</div><div class="asset-duration">${a.kind === 'image' ? `${a.width} x ${a.height}` : fmt(a.duration, true)}</div></div></div>`).join('') : `<div class="no-selection" style="grid-column:1/-1;height:160px"><div>No ${filter === 'all' ? '' : filter} media yet<br><button class="btn" id="emptyImport">Import Media</button></div></div>`;
  for(const a of assets.filter(x=>x.kind!=='audio')){const probe=new Image();probe.onload=()=>{};probe.onerror=()=>{const host=$(`[data-thumb="${a.id}"]`);host?.querySelector('.thumb-error')?.classList.remove('hidden');host?.style.setProperty('background-image','none')};probe.src=thumbUrl(a)}
  $$('[data-retry-thumb]').forEach(b=>b.onclick=e=>{e.stopPropagation();const a=asset(b.dataset.retryThumb),host=$(`[data-thumb="${a.id}"]`);host.style.backgroundImage=`url('${thumbUrl(a)}&retry=${Date.now()}')`;host.querySelector('.thumb-error').classList.add('hidden')});$('#emptyImport')?.addEventListener('click',()=>$('#fileInput')?.click());
  $$('.asset').forEach(node => {
    node.ondragstart = e => { e.dataTransfer.setData('application/x-researchcut-asset', node.dataset.asset); e.dataTransfer.effectAllowed = 'copy'; };
    node.ondblclick = () => addAssetToTimeline(node.dataset.asset);
  });
}
async function importFiles(files) {
  if (!files.length) return; await flushSave(); const drop = $('#importDrop');
  for (let i = 0; i < files.length; i++) {
    const file = files[i]; drop.firstChild.textContent = `Importing ${i + 1}/${files.length}: ${file.name}`;
    try {
      const kind = file.type.startsWith('image/') ? 'image' : file.type.startsWith('audio/') ? 'audio' : 'video';
      const result = await api(`/api/projects/${project.id}/assets`, { method: 'POST', headers: { 'x-file-name': encodeURIComponent(file.name), 'x-media-kind': kind, 'content-type': 'application/octet-stream' }, body: file });
      project.assets.push(result.asset); serverRevision = result.revision; project.revision = result.revision; project.updatedAt = result.updatedAt; renderMedia();
      if (kind === 'audio' && !project.clips.some(c => c.trackId === 'A1')) addAssetToTimeline(result.asset.id, 'A1', 0);
    } catch (error) { toast(error.message, true); }
  }
  drop.firstChild.textContent = '+ Import images, videos or audio'; renderEditorParts();
}
function defaultClip(a, trackId, start) {
  const isImage = a.kind === 'image'; const d = isImage ? 5 : Math.max(.25, Math.min(a.duration || 5, a.kind === 'audio' ? a.duration : 10));
  return { id: 'c_' + cryptoId(), assetId: a.id, trackId, start: Math.max(0, start), duration: d, sourceIn: 0, transform: { x: 0, y: 0, scale: 1, rotation: 0, fit: 'fill', opacity: 1, crop: { top: 0, right: 0, bottom: 0, left: 0 } }, muted: false, volume: 1 };
}
function cryptoId() { return (crypto?.randomUUID?.() || `${Date.now()}${Math.random()}`).replaceAll('-', '').slice(0, 16); }
function addAssetToTimeline(assetId, forcedTrack, forcedStart) {
  const a = asset(assetId); if (!a) return; remember();
  let trackId = forcedTrack || (a.kind === 'audio' ? (project.clips.some(c => c.trackId === 'A1') ? 'A2' : 'A1') : 'V1'); let start = forcedStart ?? currentTime;
  if (trackId === 'V1' && track('V1').magnetic) start = Math.max(0, ...project.clips.filter(c => c.trackId === 'V1').map(c => c.start + c.duration));
  const clipDuration = a.kind === 'image' ? 5 : Math.max(.25, Math.min(a.duration || 5, a.kind === 'audio' ? a.duration : 10));
  if (a.kind !== 'audio' && trackId !== 'V1') {
    trackId = resolveVideoTrack(trackId, start, clipDuration);
    start = nextFreeStart(trackId, start, clipDuration);
  }
  if (a.kind === 'audio') start = nextFreeStart(trackId, start, clipDuration);
  const c = defaultClip(a, trackId, start); project.clips.push(c); selectedId = c.id; normalizeMagnetic(); markDirty(); renderEditorParts(); seek(c.start);
}
function normalizeMagnetic() {
  if (!project || !track('V1')?.magnetic) return;
  let cursor = 0; project.clips.filter(c => c.trackId === 'V1').sort((a, b) => a.start - b.start).forEach(c => { c.start = cursor; cursor += c.duration; });
}
function addTrack(kind) {
  remember(); const prefix = kind === 'audio' ? 'A' : 'V'; const next = Math.max(0, ...project.tracks.filter(t => t.id.startsWith(prefix)).map(t => Number(t.id.slice(1)) || 0)) + 1;
  const created = { id: `${prefix}${next}`, kind, name: kind === 'audio' ? `Audio ${next}` : `Overlay ${next - 1}`, muted: false, locked: false, magnetic: false };
  if (kind === 'video') project.tracks.unshift(created); else project.tracks.push(created);
  markDirty(); renderTracks(); renderTimeline(); requestAnimationFrame(() => { const scroll = $('#timelineScroll'); if (scroll) scroll.scrollTop = kind === 'audio' ? scroll.scrollHeight : 0; }); toast(`${created.name} added`);
}
function collides(trackId, start, length, ignoreId = null) {
  const end = start + length;
  return project.clips.some(c => c.id !== ignoreId && c.trackId === trackId && start < c.start + c.duration - .01 && end > c.start + .01);
}
function resolveVideoTrack(preferred, start, length, ignoreId = null) {
  const order = project.tracks.filter(t => t.kind === 'video').map(t => t.id).sort((a,b) => trackOrderValue(a) - trackOrderValue(b)); let index = Math.max(0, order.indexOf(preferred));
  for (; index < order.length; index++) if (!collides(order[index], start, length, ignoreId)) return order[index];
  return order.at(-1) || 'V1';
}
function nextFreeStart(trackId, start, length, ignoreId = null) {
  let candidate = Math.max(0, start); const clips = project.clips.filter(c => c.id !== ignoreId && c.trackId === trackId).sort((a, b) => a.start - b.start);
  for (let pass = 0; pass <= clips.length; pass++) {
    const hit = clips.find(c => candidate < c.start + c.duration - .01 && candidate + length > c.start + .01);
    if (!hit) break; candidate = hit.start + hit.duration;
  }
  return candidate;
}
function renderTracks() {
  const labels = $('#trackLabels'); if (!labels) return;
  labels.innerHTML = `<div style="height:26px"></div>` + project.tracks.map(t => `<div class="track-label"><span class="track-badge">${t.id}</span><span class="name">${esc(t.name)}</span>${t.id === 'V1' ? `<button class="track-toggle ${t.magnetic ? 'locked' : ''}" data-magnet="${t.id}" title="Magnetic main track">MAG</button>` : ''}<button class="track-toggle ${t.muted ? 'on' : ''}" data-mute="${t.id}" title="Mute track">${t.muted ? 'MUTE' : 'AUDIO'}</button><button class="track-toggle ${t.locked ? 'locked' : ''}" data-lock="${t.id}" title="Lock track">${t.locked ? 'LOCKED' : 'LOCK'}</button></div>`).join('');
  $$('[data-mute]').forEach(b => b.onclick = () => { remember(); track(b.dataset.mute).muted = !track(b.dataset.mute).muted; markDirty(); renderTracks(); renderTimeline(); syncMedia(true); });
  $$('[data-lock]').forEach(b => b.onclick = () => { remember(); track(b.dataset.lock).locked = !track(b.dataset.lock).locked; markDirty(); renderTracks(); });
  $$('[data-magnet]').forEach(b => b.onclick = () => { remember(); track('V1').magnetic = !track('V1').magnetic; normalizeMagnetic(); markDirty(); renderTracks(); renderTimeline(); });
}
function zoomValue() { return Math.round(Math.log(pxPerSec / .5) / Math.log(120) * 100); }
function tickStep() { const values = [.1,.25,.5,1,2,5,10,15,30,60,120,300,600]; return values.find(v => v * pxPerSec >= 65) || 1200; }
function timelineWheel(e) {
  if (!e.ctrlKey) return; e.preventDefault(); const scroll = $('#timelineScroll'); if (!scroll) return;
  const pointer = e.clientX - scroll.getBoundingClientRect().left, anchorTime = (scroll.scrollLeft + pointer) / pxPerSec;
  pxPerSec = Math.max(.5, Math.min(60, pxPerSec * Math.exp(-e.deltaY * .0025)));
  renderTimeline(); scroll.scrollLeft = Math.max(0, anchorTime * pxPerSec - pointer); const slider = $('#zoom'); if (slider) slider.value = zoomValue();
}
function toggleTheme() {
  theme = theme === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = theme; localStorage.setItem('researchcut:theme', theme);
  const button = $('#themeBtn'); if (button) button.textContent = theme === 'dark' ? 'Light' : 'Dark';
}
async function toggleFullscreen() {
  const zone = $('#previewZone'); if (!zone) return;
  if (zone.classList.contains('app-fullscreen')) { zone.classList.remove('app-fullscreen'); return; }
  try { if (document.fullscreenElement) await document.exitFullscreen(); else if (document.fullscreenEnabled && typeof zone.requestFullscreen === 'function') { await zone.requestFullscreen(); if (!document.fullscreenElement) zone.classList.add('app-fullscreen'); } else zone.classList.add('app-fullscreen'); }
  catch { zone.classList.add('app-fullscreen'); }
}
function renderTimeline() {
  const content = $('#timelineContent'), scroll = $('#timelineScroll'); if (!content || !scroll) return;
  const oldLeft = scroll.scrollLeft, oldTop = scroll.scrollTop; const total = Math.max(30, duration() + 10); const width = Math.max(scroll.clientWidth || 600, total * pxPerSec); const step = tickStep();
  const ticks = []; for (let t = 0; t <= total; t += step) ticks.push(`<span class="tick" style="left:${t * pxPerSec}px">${fmt(t)}</span>`);
  content.style.width = `${width}px`; content.style.height = `${26 + project.tracks.length * 43}px`; content.style.setProperty('--grid', `${step * pxPerSec}px`);
  content.innerHTML = `<div class="ruler">${ticks.join('')}</div>${project.tracks.map(t => `<div class="track-row" data-track="${t.id}"></div>`).join('')}<div class="playhead" id="playhead"><span class="playhead-time">${fmt(currentTime, true)}</span></div>`;
  for (const c of project.clips) {
    const a = asset(c.assetId), row = $(`.track-row[data-track="${c.trackId}"]`, content); if (!a || !row) continue;
    const node = document.createElement('div'); node.className = `clip ${a.kind}${(selectedId === c.id ? ' selected' : '')}${(c.muted || track(c.trackId).muted) ? ' muted' : ''}`; node.dataset.clip = c.id;
    node.style.left = `${c.start * pxPerSec}px`; node.style.width = `${Math.max(4, c.duration * pxPerSec)}px`; if(c.sceneBrain?.status)node.dataset.status=c.sceneBrain.status;if (a.kind !== 'audio') node.style.backgroundImage = `url('${thumbUrl(a)}')`;
    node.innerHTML = `<canvas class="wave-canvas"></canvas><div class="clip-title">${esc(a.name)}</div><span class="trim left"></span><span class="trim right"></span>`; row.append(node);
    node.onclick = e => { e.stopPropagation(); selectClip(c.id); }; node.onpointerdown = e => beginClipDrag(e, c, node);
    $('.trim.left', node).onpointerdown = e => beginTrim(e, c, node, 'left'); $('.trim.right', node).onpointerdown = e => beginTrim(e, c, node, 'right');
    if (a.kind === 'audio') loadWave(a, node, c);
  }
  $$('.track-row', content).forEach(row => {
    row.onclick = e => seek(Math.max(0, (e.clientX - row.getBoundingClientRect().left) / pxPerSec));
    row.ondragover = e => { e.preventDefault(); row.classList.add('drop-target'); };
    row.ondragleave = () => row.classList.remove('drop-target');
    row.ondrop = e => { e.preventDefault(); row.classList.remove('drop-target'); const id = e.dataTransfer.getData('application/x-researchcut-asset'); if (!id || track(row.dataset.track).locked) return; const a = asset(id), audioTrack = row.dataset.track.startsWith('A'); if (audioTrack !== (a.kind === 'audio')) return toast(audioTrack ? 'Only audio can go on audio tracks' : 'Audio belongs on an audio layer', true); addAssetToTimeline(id, row.dataset.track, (e.clientX - row.getBoundingClientRect().left) / pxPerSec); };
  });
  $('.ruler', content).onclick = e => seek(Math.max(0, (e.clientX - $('.ruler', content).getBoundingClientRect().left) / pxPerSec));
  scroll.scrollLeft = oldLeft; scroll.scrollTop = oldTop; const labels = $('#trackLabels'); if (labels) labels.scrollTop = oldTop; const slider = $('#zoom'); if (slider) slider.value = zoomValue(); updatePlayhead();
}
async function loadWave(a, node, c) {
  let data = waveCache.get(a.id);
  if (!data) {
    try { const response = await fetch(apiUrl(`/wave/${project.id}/${a.id}`)); if (response.status === 202) return setTimeout(() => loadWave(a, node, c), 900); if (!response.ok) return; data = await response.json(); waveCache.set(a.id, data); }
    catch { return; }
  }
  if (!node.isConnected) return; const canvas = $('.wave-canvas', node); const w = Math.max(10, node.clientWidth), h = node.clientHeight, dpr = Math.min(2, devicePixelRatio || 1); canvas.width = w * dpr; canvas.height = h * dpr;
  const ctx = canvas.getContext('2d'); ctx.scale(dpr, dpr); ctx.strokeStyle = '#85e5ff'; ctx.lineWidth = 1; ctx.beginPath(); const peaks = data.peaks || []; const startRatio = c.sourceIn / Math.max(.001, data.duration); const endRatio = (c.sourceIn + c.duration) / Math.max(.001, data.duration);
  for (let x = 0; x < w; x++) { const ratio = startRatio + (x / w) * (endRatio - startRatio); const p = peaks[Math.min(peaks.length - 1, Math.floor(ratio * peaks.length))] || 0; const amp = Math.max(1, p * h * .48); ctx.moveTo(x, h / 2 - amp); ctx.lineTo(x, h / 2 + amp); } ctx.stroke();
}
function beginClipDrag(e, c, node) {
  if (e.target.classList.contains('trim') || track(c.trackId).locked) return; e.preventDefault(); selectForPointer(c.id); remember();
  const startX = e.clientX, originalStart = c.start, originalTrack = c.trackId; let dx = 0;
  const move = ev => { dx = (ev.clientX - startX) / pxPerSec; if (!track(originalTrack).magnetic) node.style.left = `${Math.max(0, originalStart + dx) * pxPerSec}px`; };
  const up = ev => {
    document.removeEventListener('pointermove', move); document.removeEventListener('pointerup', up); const target = document.elementFromPoint(ev.clientX, ev.clientY)?.closest?.('.track-row'); const targetId = target?.dataset.track;
    if (targetId && !track(targetId).locked && ((asset(c.assetId).kind === 'audio') === targetId.startsWith('A'))) c.trackId = targetId;
    if (c.trackId === 'V1' && track('V1').magnetic) c.start = Math.max(0, (ev.clientX - (target || node.parentElement).getBoundingClientRect().left) / pxPerSec); else c.start = Math.max(0, originalStart + dx);
    if (asset(c.assetId).kind !== 'audio' && c.trackId !== 'V1') { c.trackId = resolveVideoTrack(c.trackId, c.start, c.duration, c.id); c.start = nextFreeStart(c.trackId, c.start, c.duration, c.id); }
    if (asset(c.assetId).kind === 'audio') c.start = nextFreeStart(c.trackId, c.start, c.duration, c.id);
    normalizeMagnetic(); markDirty(); renderTimeline(); renderStage(true); renderInspector();
  };
  document.addEventListener('pointermove', move); document.addEventListener('pointerup', up);
}
function beginTrim(e, c, node, side) {
  e.preventDefault(); e.stopPropagation(); if (track(c.trackId).locked) return; selectForPointer(c.id); remember();
  const startX = e.clientX, original = { start: c.start, duration: c.duration, sourceIn: c.sourceIn }; const a = asset(c.assetId); let delta = 0;
  const move = ev => { delta = (ev.clientX - startX) / pxPerSec; if (side === 'right') node.style.width = `${Math.max(4, (original.duration + delta) * pxPerSec)}px`; else { node.style.left = `${Math.max(0, original.start + delta) * pxPerSec}px`; node.style.width = `${Math.max(4, (original.duration - delta) * pxPerSec)}px`; } };
  const up = () => {
    document.removeEventListener('pointermove', move); document.removeEventListener('pointerup', up);
    if (side === 'right') { const max = a.kind === 'image' ? 86400 : Math.max(.04, a.duration - original.sourceIn); c.duration = Math.max(.1, Math.min(max, original.duration + delta)); }
    else { const actual = Math.max(-original.sourceIn, Math.min(original.duration - .1, delta)); c.start = Math.max(0, original.start + actual); c.duration = original.duration - actual; if (a.kind !== 'image') c.sourceIn = original.sourceIn + actual; }
    normalizeMagnetic(); markDirty(); renderEditorParts();
  };
  document.addEventListener('pointermove', move); document.addEventListener('pointerup', up);
}
function selectClip(id) { if (selectedId !== id) cropEditingId = null; selectedId = id; const c = clip(); if (c) currentTime = Math.max(c.start, Math.min(currentTime, c.start + c.duration - .01)); renderTimeline(); renderStage(true); renderInspector(); updateTimeUI(); }
function selectForPointer(id) {
  if (selectedId !== id) cropEditingId = null;
  selectedId = id;
  $$('.clip').forEach(node => node.classList.toggle('selected', node.dataset.clip === id));
  $$('.stage-layer').forEach(node => node.classList.toggle('selected', node.dataset.clip === id));
  renderInspector(); updateTimeUI();
}
function deleteSelected() { const c = clip(); if (!c || track(c.trackId).locked) return; remember(); project.clips = project.clips.filter(x => x.id !== c.id); selectedId = null; normalizeMagnetic(); markDirty(); renderEditorParts(); }
function splitSelected() {
  const c = clip(); if (!c || track(c.trackId).locked || currentTime <= c.start + .05 || currentTime >= c.start + c.duration - .05) return toast('Place the playhead inside the selected clip');
  remember(); const leftDuration = currentTime - c.start, right = JSON.parse(JSON.stringify(c)); right.id = 'c_' + cryptoId(); right.start = currentTime; right.duration = c.duration - leftDuration; if (asset(c.assetId).kind !== 'image') right.sourceIn = c.sourceIn + leftDuration; c.duration = leftDuration; project.clips.push(right); selectedId = right.id; markDirty(); renderEditorParts();
}
function renderStage(force = false) {
  const stage = $('#stage'); if (!stage) return; const active = project.clips.filter(c => c.trackId.startsWith('V') && currentTime >= c.start && currentTime < c.start + c.duration).sort((a, b) => trackOrderValue(a.trackId) - trackOrderValue(b.trackId));
  const signature = active.map(c => c.id).join('|') + ':' + selectedId + ':' + cropEditingId; if (!force && signature === activeSignature) return syncMedia(); activeSignature = signature;
  const nextVisual=project.clips.filter(c=>c.trackId==='V1'&&c.start>currentTime).sort((a,b)=>a.start-b.start)[0],gapSeconds=nextVisual?Math.max(0,nextVisual.start-currentTime):0;
  stage.innerHTML = active.length ? '' : `<div class="stage-empty explicit-gap"><b>EMPTY VISUAL GAP</b><span>Duration: ${gapSeconds.toFixed(1)} sec</span><div><button class="btn primary" id="gapAddMedia">Add Media</button><button class="btn" id="gapProjectMedia">Project Media</button><button class="btn" id="gapCandidates">SceneBrain Candidates</button></div></div>`;
  $('#gapAddMedia')?.addEventListener('click',()=>$('#fileInput')?.click());
  $('#gapProjectMedia')?.addEventListener('click',()=>{$('.media-panel')?.scrollIntoView({behavior:'smooth'});toast('Choose or import media from Project Media')});
  $('#gapCandidates')?.addEventListener('click',()=>toast('Select a NEEDS_CHOICE timeline slot to review its stored candidates'));
  for (const c of active) {
    const a = asset(c.assetId), layer = document.createElement('div'); layer.className = 'stage-layer' + (selectedId === c.id ? ' selected' : ''); layer.dataset.clip = c.id; applyLayerTransform(layer, c);
    const media = document.createElement(a.kind === 'video' ? 'video' : 'img'); media.src = mediaUrl(a);media.onerror=()=>{layer.innerHTML='<div class="stage-empty media-error"><b>MEDIA ERROR</b><span>Source could not be loaded.</span><button class="btn">Retry</button></div>';layer.querySelector('button').onclick=()=>renderStage(true)}; if (a.kind === 'video') { media.playsInline = true; media.preload = 'auto'; media.muted = track(c.trackId).muted || c.muted || !a.hasAudio; media.volume = Math.min(1, c.volume); }
    media.style.objectFit = c.transform.fit === 'fit' ? 'contain' : 'cover'; applyMediaCrop(media, c); layer.append(media);
    const resize = document.createElement('span'); resize.className = 'resize-handle'; layer.append(resize);
    if (selectedId === c.id && cropEditingId === c.id) layer.append(makeCropOverlay(c, media));
    stage.append(layer); layer.onpointerdown = e => beginStageDrag(e, c, layer); resize.onpointerdown = e => beginStageResize(e, c, layer);
  }
  syncMedia(true);
}
function applyLayerTransform(layer, c) { layer.style.transform = `translate(${c.transform.x}%,${c.transform.y}%) scale(${c.transform.scale}) rotate(${c.transform.rotation}deg)`; layer.style.opacity = c.transform.opacity; }
function cropValues(c) { return c.transform.crop || (c.transform.crop = { top: 0, right: 0, bottom: 0, left: 0 }); }
function applyMediaCrop(media, c) { const p = cropValues(c); media.style.clipPath = `inset(${p.top}% ${p.right}% ${p.bottom}% ${p.left}%)`; }
function positionCropOverlay(box, c) { const p = cropValues(c); box.style.inset = `${p.top}% ${p.right}% ${p.bottom}% ${p.left}%`; }
function makeCropOverlay(c, media) {
  const box = document.createElement('div'); box.className = 'crop-overlay'; positionCropOverlay(box, c);
  for (const side of ['top', 'right', 'bottom', 'left']) { const handle = document.createElement('span'); handle.className = `crop-handle ${side}`; handle.dataset.cropSide = side; handle.onpointerdown = e => beginCropDrag(e, c, side, box, media); box.append(handle); }
  return box;
}
function beginCropDrag(e, c, side, box, media) {
  e.preventDefault(); e.stopPropagation(); remember(); const stage = $('#stage').getBoundingClientRect(), original = { ...cropValues(c) }, startX = e.clientX, startY = e.clientY;
  const move = ev => {
    const dx = (ev.clientX - startX) / stage.width * 100 / Math.max(.05, c.transform.scale), dy = (ev.clientY - startY) / stage.height * 100 / Math.max(.05, c.transform.scale), p = cropValues(c);
    if (side === 'left') p.left = Math.max(0, Math.min(45, original.left + dx));
    if (side === 'right') p.right = Math.max(0, Math.min(45, original.right - dx));
    if (side === 'top') p.top = Math.max(0, Math.min(45, original.top + dy));
    if (side === 'bottom') p.bottom = Math.max(0, Math.min(45, original.bottom - dy));
    applyMediaCrop(media, c); positionCropOverlay(box, c); renderInspector();
  };
  const up = () => { document.removeEventListener('pointermove', move); document.removeEventListener('pointerup', up); markDirty(); };
  document.addEventListener('pointermove', move); document.addEventListener('pointerup', up);
}
function beginStageDrag(e, c, layer) {
  if (e.target.classList.contains('resize-handle') || e.target.closest('.crop-overlay') || cropEditingId === c.id || track(c.trackId).locked) return; e.preventDefault(); selectForPointer(c.id); remember(); const rect = $('#stage').getBoundingClientRect(), start = { x: e.clientX, y: e.clientY, tx: c.transform.x, ty: c.transform.y };
  const move = ev => { c.transform.x = Math.max(-200, Math.min(200, start.tx + (ev.clientX - start.x) / rect.width * 100)); c.transform.y = Math.max(-200, Math.min(200, start.ty + (ev.clientY - start.y) / rect.height * 100)); applyLayerTransform(layer, c); renderInspector(); };
  const up = () => { document.removeEventListener('pointermove', move); document.removeEventListener('pointerup', up); markDirty(); };
  document.addEventListener('pointermove', move); document.addEventListener('pointerup', up);
}
function beginStageResize(e, c, layer) {
  e.preventDefault(); e.stopPropagation(); if (track(c.trackId).locked) return; remember(); const rect = $('#stage').getBoundingClientRect(), startX = e.clientX, scale = c.transform.scale;
  const move = ev => { c.transform.scale = Math.max(.05, Math.min(8, scale * (1 + (ev.clientX - startX) / Math.max(120, rect.width * .5)))); applyLayerTransform(layer, c); renderInspector(); };
  const up = () => { document.removeEventListener('pointermove', move); document.removeEventListener('pointerup', up); markDirty(); };
  document.addEventListener('pointermove', move); document.addEventListener('pointerup', up);
}
function syncMedia(hard = false) {
  $$('.stage-layer video').forEach(video => {
    const c = clip(video.parentElement.dataset.clip), local = c.sourceIn + Math.max(0, currentTime - c.start);
    if (hard || Math.abs((video.currentTime || 0) - local) > .22) try { video.currentTime = local; } catch {}
    video.muted = previewMuted || track(c.trackId).muted || c.muted || !asset(c.assetId).hasAudio; video.volume = Math.min(1, c.volume * previewVolume); if (playing) video.play().catch(() => {}); else video.pause();
  });
  syncAudio(hard);
}
function syncAudio(hard = false) {
  const host = $('#stage'); if (!host) return; const active = project.clips.filter(c => c.trackId.startsWith('A') && currentTime >= c.start && currentTime < c.start + c.duration);
  const wanted = new Set(active.map(c => c.id)); $$('audio.preview-audio', host).forEach(el => { if (!wanted.has(el.dataset.clip)) el.remove(); });
  for (const c of active) {
    let el = $(`audio.preview-audio[data-clip="${c.id}"]`, host); if (!el) { el = document.createElement('audio'); el.className = 'preview-audio'; el.dataset.clip = c.id; el.src = mediaUrl(asset(c.assetId)); el.preload = 'auto'; host.append(el); hard = true; }
    const local = c.sourceIn + currentTime - c.start; if (hard || Math.abs((el.currentTime || 0) - local) > .22) try { el.currentTime = local; } catch {}
    el.muted = previewMuted || track(c.trackId).muted || c.muted; el.volume = Math.min(1, c.volume * previewVolume); if (playing) el.play().catch(() => {}); else el.pause();
  }
}
function renderInspector() {
  const host = $('#inspector'); if (!host) return; const c = clip(); if (!c) { host.innerHTML = '<div class="no-selection"><div><div style="font-size:23px;margin-bottom:9px">Select</div>Select a clip to adjust its framing, timing and audio.</div></div>'; return; }
  const a = asset(c.assetId), hasAudio = a.kind === 'audio' || a.hasAudio, crop = cropValues(c);
  host.innerHTML = `<div class="inspector-name" title="${esc(a.name)}">${esc(a.name)}</div>
    ${a.kind !== 'audio' ? `<div class="control"><label>Framing</label><div class="seg"><button data-fit="fill" class="${c.transform.fit === 'fill' ? 'active' : ''}">Fill frame</button><button data-fit="fit" class="${c.transform.fit === 'fit' ? 'active' : ''}">Fit inside</button></div></div>
    <div class="number-grid"><div class="num"><label>Position X</label><input data-number="x" type="number" step="1" value="${c.transform.x.toFixed(1)}"></div><div class="num"><label>Position Y</label><input data-number="y" type="number" step="1" value="${c.transform.y.toFixed(1)}"></div><div class="num"><label>Scale</label><input data-number="scale" type="number" step="0.05" min="0.05" max="8" value="${c.transform.scale.toFixed(2)}"></div><div class="num"><label>Rotation</label><input data-number="rotation" type="number" step="1" value="${c.transform.rotation.toFixed(1)}"></div></div>
    <div class="control" style="margin-top:13px"><label><span>Opacity</span><span>${Math.round(c.transform.opacity * 100)}%</span></label><input data-range="opacity" type="range" min="0" max="1" step="0.01" value="${c.transform.opacity}"></div>
    <div class="control"><label>Manual crop</label><div class="seg"><button id="cropCanvas" class="${cropEditingId === c.id ? 'active' : ''}">${cropEditingId === c.id ? 'Finish crop' : 'Crop on canvas'}</button><button id="resetCrop">Reset crop</button></div></div>
    <div class="number-grid crop-grid"><div class="num"><label>Top %</label><input data-crop-number="top" type="number" min="0" max="45" step="0.5" value="${crop.top.toFixed(1)}"></div><div class="num"><label>Right %</label><input data-crop-number="right" type="number" min="0" max="45" step="0.5" value="${crop.right.toFixed(1)}"></div><div class="num"><label>Bottom %</label><input data-crop-number="bottom" type="number" min="0" max="45" step="0.5" value="${crop.bottom.toFixed(1)}"></div><div class="num"><label>Left %</label><input data-crop-number="left" type="number" min="0" max="45" step="0.5" value="${crop.left.toFixed(1)}"></div></div>` : ''}
    <div class="number-grid"><div class="num"><label>Timeline start</label><input data-clipnum="start" type="number" min="0" step="0.1" value="${c.start.toFixed(2)}" ${track(c.trackId).magnetic ? 'disabled' : ''}></div><div class="num"><label>Duration</label><input data-clipnum="duration" type="number" min="0.1" step="0.1" value="${c.duration.toFixed(2)}"></div><div class="num"><label>Source in</label><input data-clipnum="sourceIn" type="number" min="0" step="0.1" value="${c.sourceIn.toFixed(2)}" ${a.kind === 'image' ? 'disabled' : ''}></div><div class="num"><label>Track</label><input value="${c.trackId}" disabled></div></div>
    ${hasAudio ? `<div class="control" style="margin-top:13px"><label><span>Clip volume</span><span>${Math.round(c.volume * 100)}%</span></label><input data-range="volume" type="range" min="0" max="1" step="0.01" value="${Math.min(1, c.volume)}"></div><label style="display:flex;gap:8px;align-items:center;font-size:10px;color:var(--muted)"><input id="clipMute" type="checkbox" ${c.muted ? 'checked' : ''}> Mute this clip</label>` : ''}
    ${c.sceneBrain ? `<details class="scene-brain-info" open><summary>Scene Brain info</summary><p><b>${esc(c.sceneBrain.slotId||'')}</b>  |  ${esc(c.sceneBrain.status||'')}</p><p>${esc(c.sceneBrain.narration||'')}</p>${(c.sceneBrain.candidateAssetIds||[]).length?`<button class="btn" id="replaceSceneBrain">Replace / choose candidate</button><div id="sceneBrainCandidates" class="hidden"></div>`:''}</details>`:''}
    <div class="inspector-actions"><button class="btn" id="resetClip">Reset frame</button><button class="btn" id="splitInspector">Split clip</button><button class="btn danger" id="deleteInspector">Delete clip</button></div>`;
  $$('[data-fit]', host).forEach(b => b.onclick = () => { remember(); c.transform.fit = b.dataset.fit; markDirty(); renderStage(true); renderInspector(); });
  $$('[data-number]', host).forEach(input => input.onchange = () => { remember(); c.transform[input.dataset.number] = Number(input.value); markDirty(); renderStage(true); renderInspector(); });
  $$('[data-crop-number]', host).forEach(input => { input.onfocus = remember; input.oninput = () => { cropValues(c)[input.dataset.cropNumber] = Math.max(0, Math.min(45, Number(input.value) || 0)); markDirty(); renderStage(true); }; input.onchange = renderInspector; });
  $$('[data-clipnum]', host).forEach(input => input.onchange = () => { remember(); const key = input.dataset.clipnum, value = Math.max(key === 'duration' ? .1 : 0, Number(input.value) || 0); if (key === 'duration') { const max = a.kind === 'image' ? 86400 : a.kind === 'video' ? Math.min(10, Math.max(.1, a.duration - c.sourceIn)) : Math.max(.1, a.duration - c.sourceIn); if (a.kind === 'video' && value > 10) toast('MAX VIDEO CLIP LENGTH: 10 SECONDS', true); c.duration = Math.min(max, value); } else if (key === 'sourceIn') c.sourceIn = Math.min(Math.max(0, a.duration - c.duration), value); else c.start = value; normalizeMagnetic(); markDirty(); renderEditorParts(); });
  $$('[data-range]', host).forEach(input => { input.onpointerdown = remember; input.oninput = () => { if (input.dataset.range === 'volume') c.volume = Number(input.value); else c.transform.opacity = Number(input.value); markDirty(); renderStage(true); }; input.onchange = renderInspector; });
  $('#clipMute', host)?.addEventListener('change', e => { remember(); c.muted = e.target.checked; markDirty(); syncMedia(true); renderTimeline(); });
  $('#cropCanvas', host)?.addEventListener('click', () => { cropEditingId = cropEditingId === c.id ? null : c.id; renderStage(true); renderInspector(); });
  $('#resetCrop', host)?.addEventListener('click', () => { remember(); c.transform.crop = { top: 0, right: 0, bottom: 0, left: 0 }; markDirty(); renderStage(true); renderInspector(); });
  $('#resetClip').onclick = () => { remember(); cropEditingId = null; c.transform = { x: 0, y: 0, scale: 1, rotation: 0, fit: 'fill', opacity: 1, crop: { top: 0, right: 0, bottom: 0, left: 0 } }; markDirty(); renderStage(true); renderInspector(); };
  $('#splitInspector').onclick = splitSelected; $('#deleteInspector').onclick = deleteSelected;
  $('#replaceSceneBrain',host)?.addEventListener('click',()=>{const box=$('#sceneBrainCandidates',host);box.classList.toggle('hidden');const candidates=c.sceneBrain.candidateAssetIds||[];box.innerHTML=`<div class="media-tabs"><button class="btn active" data-replace-tab="sb">SceneBrain Candidates</button><button class="btn" data-replace-tab="media">Project Media</button><button class="btn" data-replace-tab="import">Import from PC</button></div><div id="replaceContent"></div>`;const draw=tab=>{const out=$('#replaceContent',box);if(tab==='sb')out.innerHTML=candidates.map((id,i)=>{const ca=asset(id);return `<div class="candidate"><b>Candidate ${i+1}</b><img src="${thumbUrl(ca)}"><button class="btn" data-preview-sb="${id}">Preview</button><button class="btn primary" data-use-sb="${id}">Use This</button></div>`}).join('')||'<p>No stored candidates.</p>';else if(tab==='media')out.innerHTML=project.assets.filter(x=>x.kind!=='audio').map(x=>`<div class="candidate"><b>${esc(x.name)}</b><img src="${thumbUrl(x)}"><button class="btn primary" data-use-sb="${x.id}">Use This</button></div>`).join('');else out.innerHTML='<p>Use the Project Media import control to add an image or video, then choose it here.</p>';$$('[data-preview-sb]',out).forEach(b=>b.onclick=()=>{const i=candidates.indexOf(b.dataset.previewSb),cand=(c.sceneBrain.candidates||[])[i]||{};c.assetId=b.dataset.previewSb;c.sourceIn=(cand.source_in_ms||0)/1000;seek(c.start);renderStage(true)});$$('[data-use-sb]',out).forEach(b=>b.onclick=()=>{remember();const i=candidates.indexOf(b.dataset.useSb),cand=(c.sceneBrain.candidates||[])[i]||{};c.assetId=b.dataset.useSb;c.sourceIn=(cand.source_in_ms||0)/1000;c.sceneBrain.status='APPROVED';markDirty();renderEditorParts()})};$$('[data-replace-tab]',box).forEach(b=>b.onclick=()=>draw(b.dataset.replaceTab));draw('sb')});
}
function seek(time) { currentTime = Math.max(0, Math.min(duration(), time)); renderStage(); syncMedia(true); updateTimeUI(); }
function togglePlay() { if (!project.clips.length) return; playing = !playing; lastFrame = performance.now(); const b=$('#playBtn');b.innerHTML=playing?icon.pause:icon.play;b.ariaLabel=playing?'Pause':'Play';b.title=playing?'Pause (Space)':'Play (Space)'; syncMedia(true); }
function frame(now) {
  if (!project || !$('#playhead')) return;
  if (playing) { const dt = Math.min(.1, (now - lastFrame) / 1000); currentTime += dt; if (currentTime >= duration()) { currentTime = duration(); playing = false;const b=$('#playBtn');b.innerHTML=icon.play;b.ariaLabel='Play';b.title='Play (Space)'; } renderStage(); syncMedia(); updateTimeUI(); }
  lastFrame = now; requestAnimationFrame(frame);
}
function paintPlayerRange() {
  const seekBar = $('#playerSeek'); if (seekBar) { const total = Math.max(.001, duration()); seekBar.max = total; seekBar.value = Math.min(total, currentTime); seekBar.style.setProperty('--progress', `${currentTime / total * 100}%`); }
  const volume = $('#previewVolume'); if (volume) volume.style.setProperty('--progress', `${previewVolume * 100}%`);
}
function updateTimeUI() {
  const tc = $('#timecode'); if (tc) tc.textContent = `${fmt(currentTime, true)} / ${fmt(duration(), true)}`;
  const current = $('#playerCurrent'), total = $('#playerDuration'); if (current) current.textContent = fmt(currentTime, true); if (total) total.textContent = fmt(duration(), true); paintPlayerRange(); updatePlayhead();
}
function updatePlayhead() { const el = $('#playhead'); if (!el) return; el.style.left = `${currentTime * pxPerSec}px`; $('.playhead-time', el).textContent = fmt(currentTime, true);$$('.clip').forEach(n=>{const c=clip(n.dataset.clip);n.classList.toggle('active-playback',!!c&&currentTime>=c.start&&currentTime<c.start+c.duration)}) }
function jumpCut(direction) {
  const cuts = [...new Set(project.clips.flatMap(c => [c.start, c.start + c.duration]).sort((a, b) => a - b))];
  const value = direction > 0 ? cuts.find(t => t > currentTime + .02) : cuts.reverse().find(t => t < currentTime - .02); if (value != null) seek(value);
}
function deep(value) { return JSON.parse(JSON.stringify(value)); }
function stopQueuePolling() { clearInterval(queueTimer); queueTimer = null; }
async function openAutomate() {
  if (!project.clips.some(c => c.trackId.startsWith('V'))) return toast('Add visual clips before opening automation', true);
  playing = false; await flushSave();
  try {
    automationCatalog = await api('/api/automation/catalog'); automateDraft = deep(project.automation || {});
    if (!automateDraft.plan?.shots?.length) {
      const result = await api(`/api/projects/${project.id}/automation`, { method: 'POST', body: JSON.stringify({ automation: automateDraft }) });
      project.automation = result.automation; automateDraft = deep(result.automation); serverRevision = result.revision; project.revision = result.revision; project.updatedAt = result.updatedAt;
    }
    automationPreviewClipId = automateDraft.plan?.shots?.[0]?.clipId || null; renderAutomate();
  } catch (error) { toast(error.message, true); }
}
function automationSummary(plan) {
  const shots = plan?.shots || [], framed = shots.filter(s => s.layoutId !== 'fullscreen').length, transitions = shots.filter(s => s.transitionId !== 'hard').length;
  return `${shots.length} visuals  |  ${framed} framed  |  ${transitions} transitions`;
}
function renderAutomate() {
  stopQueuePolling(); const presets = automationCatalog?.presets || [], bgs = automationCatalog?.backgrounds || [], plan = automateDraft.plan || { shots: [] }, shots = plan.shots || [];
  if (!automationPreviewClipId || !shots.some(s => s.clipId === automationPreviewClipId)) automationPreviewClipId = shots[0]?.clipId || null;
  const projectBackgrounds = project.assets.filter(a => a.kind === 'image' || a.kind === 'video');
  app.innerHTML = `<div class="app-shell automate-app">
    <header class="topbar"><button class="btn ghost" id="backEditor">Back to  Editor</button><div class="top-divider"></div><div class="brand"><span class="brand-mark">R</span><span>ResearchCut</span><span class="brand-sub">AUTOMATE</span></div><div class="automation-title">${esc(project.name)}</div><div class="top-spacer"></div><button class="btn ghost" id="themeBtn">${theme === 'dark' ? 'Light' : 'Dark'}</button><div class="save-state" id="saveState"><span class="save-dot"></span><span class="save-label">Plan saved locally</span></div><button class="btn primary" id="renderNowTop">Render now</button></header>
    <main class="automate-layout">
      <aside class="automation-controls">
        <div class="auto-section"><div class="auto-step"><b>1</b><span>Style system</span></div><p>60 curated recipes. Same seed always produces the same plan.</p><div class="preset-grid">${presets.map(p => `<button class="preset-card ${p.id === automateDraft.presetId ? 'active' : ''}" data-preset="${p.id}" style="--preset:${p.accent}"><span>${esc(p.name)}</span><small>${esc(p.description)}</small></button>`).join('')}</div></div>
        <div class="auto-section"><div class="auto-step"><b>2</b><span>Motion & transitions</span></div><label>Intensity</label><div class="seg three">${['subtle','balanced','energetic'].map(x => `<button data-intensity="${x}" class="${automateDraft.intensity === x ? 'active' : ''}">${x[0].toUpperCase() + x.slice(1)}</button>`).join('')}</div><label class="switch-row"><span><strong>Automatic transitions</strong><small>Duration-safe varied boundary effects</small></span><input id="autoTransitions" type="checkbox" ${automateDraft.transitionsEnabled ? 'checked' : ''}></label><label class="switch-row"><span><strong>Automatic motion</strong><small>Zoom, pan, drift and punch-in</small></span><input id="autoMotion" type="checkbox" ${automateDraft.motionEnabled ? 'checked' : ''}></label></div>
        <div class="auto-section"><div class="auto-step"><b>3</b><span>Frame backgrounds</span></div><label>Background behavior<select id="backgroundMode"><option value="auto">Auto mix: blur + built-ins</option><option value="blur">Blur current visual</option><option value="builtin">Choose built-in image/video</option><option value="project">Choose project media</option><option value="solid">Solid color</option><option value="none">Black / no background</option></select></label>
          <label id="builtinWrap">Built-in background<select id="builtinBg"><option value="">Auto rotate library</option>${bgs.map(bg => `<option value="${esc(bg.id)}">${esc(bg.name)}  |  ${bg.kind}</option>`).join('')}</select></label>
          <label id="projectBgWrap">Project background<select id="projectBg"><option value="">Choose media</option>${projectBackgrounds.map(a => `<option value="${a.id}">${esc(a.name)}  |  ${a.kind}</option>`).join('')}</select></label>
          <label id="solidWrap">Background color<input id="solidColor" type="color" value="${esc(automateDraft.solidColor || '#0b1011')}"></label>
        </div>
        <div class="auto-section text-section"><div class="auto-step"><b>4</b><span>Narration-synced video text</span></div><label class="switch-row"><span><strong>Enable VText</strong><small>Optional - turn OFF for a completely clean video</small></span><input id="textEnabled" type="checkbox" ${automateDraft.text?.enabled ? 'checked' : ''}></label>
          <label class="file-drop small">${automateDraft.text?.instructionName ? `Ready ${esc(automateDraft.text.instructionName)}  |  ${automateDraft.text.eventCount || 0} events` : 'Upload one VText instruction .txt'}<input id="textInstructions" type="file" accept=".txt,text/plain"></label>
          <details><summary>Advanced text controls</summary><label>Optional clean narration script<input id="cleanScript" type="file" accept=".txt,text/plain"></label><div class="two-cols"><label>Density<select id="textDensity"><option value="file">Follow file</option><option value="medium">Medium cap</option><option value="light">Light cap</option></select></label><label>Scale<select id="textScale"><option value="auto">Auto</option><option value="small">Small</option><option value="balanced">Balanced</option><option value="large">Large</option></select></label><label>Energy<input id="textEnergy" type="range" min="1" max="5" step=".5" value="${automateDraft.text?.energy || 3}"></label><label>Accent<input id="textAccent" type="color" value="${/^#[0-9a-f]{6}$/i.test(automateDraft.text?.accent || '') ? automateDraft.text.accent : '#ffd60a'}"></label></div></details>
        </div>
        <div class="auto-section"><div class="auto-step"><b>5</b><span>Export quality</span></div><div class="seg"><button data-resolution="1080p" class="${automateDraft.export?.resolution !== '4k' ? 'active' : ''}">1080p</button><button data-resolution="4k" class="${automateDraft.export?.resolution === '4k' ? 'active' : ''}">4K UHD</button></div><label>Encoding quality<select id="exportQuality"><option value="fast">Fast</option><option value="balanced">Balanced</option><option value="quality">Maximum quality</option></select></label></div>
      </aside>
      <section class="automation-center">
        <div class="automation-preview-head"><div><h2>Automation preview</h2><p id="planSummary">${esc(plan.presetName || '')}  |  ${automationSummary(plan)}</p></div><div class="button-row"><button class="btn" id="shufflePlan">Shuffle variation</button><button class="btn primary" id="generatePlan">Apply & regenerate</button></div></div>
        <div class="automation-preview"><div class="stage auto-stage" id="autoStage"></div></div>
        <div class="preview-caption">Visual preview shows layout, background, motion and optional text styling. "Render 12s sample" creates an actual FFmpeg result.</div>
        <div class="export-actions"><button class="btn" id="previewRender">Play Render 12s sample</button><button class="btn" id="addQueue">+ Add to overnight queue</button><button class="btn primary" id="renderNow">Render now</button></div>
        <div class="review-head"><div><h3>Per-visual review</h3><p>Replace any individual layout, motion or outgoing transition.</p></div><span>${shots.length} visuals</span></div>
        <div class="shot-review">${shots.map(s => { const c = project.clips.find(x => x.id === s.clipId), a = c && asset(c.assetId); return `<article class="shot-row ${s.clipId === automationPreviewClipId ? 'selected' : ''}" data-preview-shot="${s.clipId}"><div class="shot-time mono">${fmt(s.start)}<small>${fmt(s.duration, true)}</small></div><div class="shot-name"><b>${esc(a?.name || s.clipId)}</b><small>${esc(c?.trackId || '')}${s.overridden ? '  |  custom' : ''}</small></div><select title="Layout" data-shot-layout="${s.clipId}">${automationCatalog.layouts.map(x => `<option value="${x}" ${x === s.layoutId ? 'selected' : ''}>${x.replaceAll('_',' ')}</option>`).join('')}</select><select title="Edge style" data-shot-edge="${s.clipId}">${automationCatalog.edgeStyles.map(x => `<option value="${x}" ${x === (s.edgeStyle || 'clean') ? 'selected' : ''}>${x.replaceAll('_',' ')}</option>`).join('')}</select><select title="Entrance" data-shot-entrance="${s.clipId}">${automationCatalog.entrances.map(x => `<option value="${x}" ${x === (s.entranceId || 'none') ? 'selected' : ''}>${x.replaceAll('_',' ')}</option>`).join('')}</select><select title="Motion" data-shot-motion="${s.clipId}">${automationCatalog.motions.map(x => `<option value="${x}" ${x === s.motionId ? 'selected' : ''}>${x.replaceAll('_',' ')}</option>`).join('')}</select><select title="Transition" data-shot-transition="${s.clipId}">${automationCatalog.transitions.map(x => `<option value="${x}" ${x === s.transitionId ? 'selected' : ''}>${x.replaceAll('_',' ')}</option>`).join('')}</select></article>`; }).join('')}</div>
      </section>
      <aside class="render-queue-side"><div class="queue-head"><div><h3>Render queue</h3><p>Persistent across app restarts.</p></div><button class="btn primary" id="startQueue">Start all</button></div><div id="renderQueuePanel" class="queue-list"><div class="queue-empty">Loading queue...</div></div></aside>
    </main></div>`;
  bindAutomate(); renderAutomationPreview(); refreshQueue(); queueTimer = setInterval(refreshQueue, 1200);
}
function bindAutomate() {
  $('#backEditor').onclick = () => { stopQueuePolling(); renderEditor(); };
  $('#themeBtn').onclick = () => { toggleTheme(); renderAutomate(); };
  $('[data-preset].active')?.scrollIntoView({ block: 'nearest' });
  $$('[data-preset]').forEach(b => b.onclick = () => { automateDraft.presetId = b.dataset.preset; $$('.preset-card').forEach(x => x.classList.toggle('active', x === b)); });
  $$('[data-intensity]').forEach(b => b.onclick = () => { automateDraft.intensity = b.dataset.intensity; $$('[data-intensity]').forEach(x => x.classList.toggle('active', x === b)); });
  $('#autoTransitions').onchange = e => automateDraft.transitionsEnabled = e.target.checked; $('#autoMotion').onchange = e => automateDraft.motionEnabled = e.target.checked;
  $('#backgroundMode').value = automateDraft.backgroundMode || 'auto'; $('#builtinBg').value = automateDraft.backgroundMode === 'builtin' ? (automateDraft.backgroundId || '') : ''; $('#projectBg').value = automateDraft.backgroundMode === 'project' ? (automateDraft.backgroundId || '') : '';
  const updateBackgroundControls = () => { const mode = $('#backgroundMode').value; automateDraft.backgroundMode = mode; $('#builtinWrap').classList.toggle('hidden', mode !== 'builtin'); $('#projectBgWrap').classList.toggle('hidden', mode !== 'project'); $('#solidWrap').classList.toggle('hidden', mode !== 'solid'); renderAutomationPreview(); };
  $('#backgroundMode').onchange = updateBackgroundControls; $('#builtinBg').onchange = e => { automateDraft.backgroundId = e.target.value || null; renderAutomationPreview(); }; $('#projectBg').onchange = e => { automateDraft.backgroundId = e.target.value || null; renderAutomationPreview(); }; $('#solidColor').oninput = e => { automateDraft.solidColor = e.target.value; renderAutomationPreview(); }; updateBackgroundControls();
  $('#textEnabled').onchange = e => { automateDraft.text.enabled = e.target.checked; renderAutomationPreview(); }; $('#textInstructions').onchange = e => uploadAutomationText(e.target.files[0], 'instruction'); $('#cleanScript').onchange = e => uploadAutomationText(e.target.files[0], 'script');
  $('#textDensity').value = automateDraft.text.density || 'file'; $('#textScale').value = automateDraft.text.scale || 'auto'; $('#textDensity').onchange = e => automateDraft.text.density = e.target.value; $('#textScale').onchange = e => automateDraft.text.scale = e.target.value; $('#textEnergy').oninput = e => automateDraft.text.energy = Number(e.target.value); $('#textAccent').oninput = e => { automateDraft.text.accent = e.target.value; renderAutomationPreview(); };
  $('#exportQuality').value = automateDraft.export?.quality || 'balanced'; $('#exportQuality').onchange = e => automateDraft.export.quality = e.target.value; $$('[data-resolution]').forEach(b => b.onclick = () => { automateDraft.export.resolution = b.dataset.resolution; $$('[data-resolution]').forEach(x => x.classList.toggle('active', x === b)); });
  $('#generatePlan').onclick = () => saveAutomation(true); $('#shufflePlan').onclick = () => { automateDraft.seed = Math.floor(Math.random() * 2147483000) + 1; saveAutomation(true); };
  $('#previewRender').onclick = () => addRender({ preview: true, startNow: true, resolution: '1080p', quality: 'fast' }); $('#addQueue').onclick = () => addRender({ startNow: false }); $('#renderNow').onclick = $('#renderNowTop').onclick = () => addRender({ startNow: true });
  $('#startQueue').onclick = async () => { await api('/api/render-queue/start', { method: 'POST', body: '{}' }); refreshQueue(); };
  $$('[data-preview-shot]').forEach(row => row.onclick = e => { if (e.target.tagName === 'SELECT') return; automationPreviewClipId = row.dataset.previewShot; $$('.shot-row').forEach(x => x.classList.toggle('selected', x === row)); renderAutomationPreview(); });
  const override = (id, key, value) => { automateDraft.overrides ||= {}; automateDraft.overrides[id] ||= {}; automateDraft.overrides[id][key] = value; const shot = automateDraft.plan?.shots?.find(s => s.clipId === id); if (shot) shot[key] = value; automationPreviewClipId = id; renderAutomationPreview(); };
  $$('[data-shot-layout]').forEach(x => x.onchange = () => override(x.dataset.shotLayout, 'layoutId', x.value)); $$('[data-shot-edge]').forEach(x => x.onchange = () => override(x.dataset.shotEdge, 'edgeStyle', x.value)); $$('[data-shot-entrance]').forEach(x => x.onchange = () => override(x.dataset.shotEntrance, 'entranceId', x.value)); $$('[data-shot-motion]').forEach(x => x.onchange = () => override(x.dataset.shotMotion, 'motionId', x.value)); $$('[data-shot-transition]').forEach(x => x.onchange = () => override(x.dataset.shotTransition, 'transitionId', x.value));
}
function renderAutomationPreview() {
  const stage = $('#autoStage'); if (!stage) return; const shot = automateDraft.plan?.shots?.find(s => s.clipId === automationPreviewClipId) || automateDraft.plan?.shots?.[0]; if (!shot) { stage.innerHTML = '<div class="stage-empty">Generate a plan to preview it</div>'; return; }
  const c = project.clips.find(x => x.id === shot.clipId), a = c && asset(c.assetId); if (!a) return; const media = a.kind === 'video' ? `<video src="${mediaUrl(a)}" muted loop autoplay playsinline></video>` : `<img src="${mediaUrl(a)}">`;
  let bg = '<div class="auto-bg solid"></div>'; const selectedBg = (automationCatalog.backgrounds || []).find(x => x.id === (shot.backgroundId || automateDraft.backgroundId)); const projectBg = asset(shot.backgroundId || automateDraft.backgroundId);
  const mode = shot.backgroundMode || automateDraft.backgroundMode;
  if ((mode === 'builtin' || mode === 'auto') && selectedBg) bg = selectedBg.kind === 'video' ? `<video class="auto-bg" src="${apiUrl(selectedBg.url)}" muted loop autoplay playsinline></video>` : `<img class="auto-bg" src="${apiUrl(selectedBg.url)}">`;
  else if (mode === 'project' && projectBg) bg = projectBg.kind === 'video' ? `<video class="auto-bg" src="${mediaUrl(projectBg)}" muted loop autoplay playsinline></video>` : `<img class="auto-bg" src="${mediaUrl(projectBg)}">`;
  else if (mode === 'blur' || mode === 'auto') bg = a.kind === 'video' ? `<video class="auto-bg blur" src="${mediaUrl(a)}" muted loop autoplay playsinline></video>` : `<img class="auto-bg blur" src="${mediaUrl(a)}">`;
  else if (mode === 'solid') bg = `<div class="auto-bg solid" style="background:${esc(automateDraft.solidColor)}"></div>`;
  const text = automateDraft.text?.enabled && automateDraft.text.samples?.length ? `<div class="vtext-sample" style="--text-accent:${esc(automateDraft.text.accent || shot.accent || '#ffd60a')}">${esc(automateDraft.text.samples[shot.index % automateDraft.text.samples.length]).replace('\n','<br>')}</div>` : '';
  stage.innerHTML = `${bg}<div class="automation-frame layout-${shot.layoutId} edge-${shot.edgeStyle || 'clean'} entrance-${shot.entranceId || 'none'} motion-${shot.motionId}" style="--frame-accent:${esc(shot.accent)}">${media}</div>${text}<div class="automation-badge"><b>${esc(shot.layoutId.replaceAll('_',' '))}</b><span>${esc((shot.edgeStyle || 'clean').replaceAll('_',' '))}  |  ${esc((shot.entranceId || 'none').replaceAll('_',' '))}</span></div>`;
}
async function saveAutomation(rerender = true) {
  try {
    setSaveState('saving', 'Generating plan...'); const result = await api(`/api/projects/${project.id}/automation`, { method: 'POST', body: JSON.stringify({ automation: automateDraft }) });
    project.automation = result.automation; automateDraft = deep(result.automation); serverRevision = result.revision; project.revision = result.revision; project.updatedAt = result.updatedAt; localStorage.removeItem(`researchcut:${project.id}`); setSaveState('', 'Plan saved locally'); if (rerender) renderAutomate(); return result;
  } catch (error) { setSaveState('error', 'Plan save failed'); toast(error.message, true); throw error; }
}
async function uploadAutomationText(file, kind) {
  if (!file) return;
  try {
    const result = await api(`/api/projects/${project.id}/automation/text`, { method: 'POST', headers: { 'x-file-name': encodeURIComponent(file.name), 'x-text-kind': kind, 'content-type': 'text/plain' }, body: file });
    automateDraft.text = { ...automateDraft.text, ...result.text }; automateDraft.plan = null; project.automation.text = deep(automateDraft.text); project.automation.plan = null; serverRevision = result.revision; project.revision = result.revision; project.updatedAt = result.updatedAt; toast(kind === 'instruction' ? `${result.text.eventCount} VText events loaded` : 'Clean narration script loaded'); renderAutomate();
  } catch (error) { toast(error.message, true); }
}
async function addRender(options = {}) {
  try {
    await saveAutomation(false); const exp = automateDraft.export || {}; const payload = { resolution: options.resolution || exp.resolution || '1080p', quality: options.quality || exp.quality || 'balanced', preview: !!options.preview, previewStart: currentTime, previewDuration: 12, startNow: !!options.startNow };
    await api(`/api/projects/${project.id}/renders`, { method: 'POST', body: JSON.stringify(payload) }); toast(options.preview ? '12-second sample is rendering' : options.startNow ? 'Render started' : 'Added to overnight queue'); renderAutomate();
  } catch (error) { toast(error.message, true); }
}
async function refreshQueue() {
  const host = $('#renderQueuePanel'); if (!host) return;
  try { const result = await api('/api/render-queue'); renderQueuePanel(result.queue); } catch (error) { host.innerHTML = `<div class="queue-empty">${esc(error.message)}</div>`; }
}
function renderQueuePanel(queue) {
  const host = $('#renderQueuePanel'); if (!host) return; const jobs = queue.jobs || []; $('#startQueue').textContent = queue.active ? 'Running...' : 'Start all'; $('#startQueue').disabled = queue.active;
  host.innerHTML = jobs.length ? jobs.map(j => `<article class="queue-job ${j.status}"><div class="queue-job-head"><div><b>${esc(j.projectName)}</b><small>${j.preview ? '12s sample' : j.resolution.toUpperCase()}  |  ${esc(j.quality)}</small></div><span class="status-pill">${esc(j.status)}</span></div><div class="queue-progress"><i style="width:${Math.round((j.progress || 0) * 100)}%"></i></div><p>${esc(j.stage || '')}${j.error ? `<br><span>${esc(j.error)}</span>` : ''}</p><div class="queue-actions">${j.status === 'complete' ? `<button class="btn" data-play-output="${j.id}">Play</button><a class="btn" href="${apiUrl(`/render-output/${j.id}`)}" download="${esc(j.outputName || 'render.mp4')}">Download</a><button class="btn" data-reveal="${j.id}">Show file</button>` : ''}${j.status === 'waiting' || j.status === 'running' ? `<button class="btn danger" data-cancel="${j.id}">Cancel</button>` : ''}${j.status === 'failed' || j.status === 'canceled' ? `<button class="btn" data-retry="${j.id}">Retry</button>` : ''}</div></article>`).join('') : '<div class="queue-empty"><b>Queue is empty</b><span>Add finished projects during the day, then press Start all at night.</span></div>';
  $$('[data-play-output]', host).forEach(b => b.onclick = () => openRenderedVideo(b.dataset.playOutput)); $$('[data-reveal]', host).forEach(b => b.onclick = () => api(`/api/render-queue/${b.dataset.reveal}/reveal`, { method: 'POST', body: '{}' })); $$('[data-cancel]', host).forEach(b => b.onclick = async () => { await api(`/api/render-queue/${b.dataset.cancel}/cancel`, { method: 'POST', body: '{}' }); refreshQueue(); }); $$('[data-retry]', host).forEach(b => b.onclick = async () => { await api(`/api/render-queue/${b.dataset.retry}/retry`, { method: 'POST', body: '{}' }); refreshQueue(); });
}
function openRenderedVideo(jobId) {
  const modal = document.createElement('div'); modal.className = 'render-player-modal'; modal.innerHTML = `<button class="player-close">x</button><video src="${apiUrl(`/render-output/${jobId}`)}" controls autoplay playsinline></video>`; document.body.append(modal); $('.player-close', modal).onclick = () => modal.remove(); modal.onclick = e => { if (e.target === modal) modal.remove(); };
}
async function handoff() {
  await flushSave(); try {
    const result = await api(`/api/projects/${project.id}/handoff`, { method: 'POST', body: '{}' });
    const modal = document.createElement('div'); modal.className = 'modal-backdrop'; modal.innerHTML = `<div class="modal"><h2>${result.ready ? 'Timeline is automation-ready' : 'Timeline saved with checks'}</h2><p>Your clips, layers, source trims, framing and audio decisions are safely stored in a structured handoff.</p>${result.issues.length ? `<div class="issues">${result.issues.map(x => `- ${esc(x)}`).join('<br>')}</div>` : `<p style="color:var(--accent)">Ready Media and voiceover are present. No blocking setup issue found.</p>`}<p class="mono" style="word-break:break-all">${esc(result.file)}</p><div class="modal-actions"><button class="btn" id="closeModal">Back to editor</button><button class="btn primary" id="downloadEdl">Download handoff JSON</button></div></div>`; document.body.append(modal);
    $('#closeModal', modal).onclick = () => modal.remove(); $('#downloadEdl', modal).onclick = () => { const blob = new Blob([JSON.stringify(result.payload, null, 2)], { type: 'application/json' }); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${project.name.replace(/[^a-z0-9]+/gi, '-')}-handoff.json`; a.click(); URL.revokeObjectURL(a.href); };
  } catch (error) { toast(error.message, true); }
}

window.addEventListener('keydown', e => {
  if (e.key === 'Escape' && $('#previewZone')?.classList.contains('app-fullscreen')) { e.preventDefault(); $('#previewZone').classList.remove('app-fullscreen'); return; }
  if (!project || /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
  if (e.code === 'Space') { e.preventDefault(); togglePlay(); } else if (e.key.toLowerCase() === 's' && !e.ctrlKey) { e.preventDefault(); splitSelected(); }
  else if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); deleteSelected(); }
  else if (e.ctrlKey && e.key.toLowerCase() === 'z' && !e.shiftKey) { e.preventDefault(); undo(); }
  else if ((e.ctrlKey && e.key.toLowerCase() === 'y') || (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'z')) { e.preventDefault(); redo(); }
  else if (e.key.toLowerCase() === 'f') { e.preventDefault(); toggleFullscreen(); }
  else if (e.key === 'ArrowLeft') { e.preventDefault(); seek(currentTime - 1 / 30); } else if (e.key === 'ArrowRight') { e.preventDefault(); seek(currentTime + 1 / 30); }
});
window.addEventListener('beforeunload', () => { if (project) { try { localStorage.setItem(`researchcut:${project.id}`, JSON.stringify({ savedAt: Date.now(), project })); } catch {} fetch(`/api/projects/${project.id}/save`, { method: 'POST', headers: { 'content-type': 'application/json', 'x-editor-token': token }, body: JSON.stringify({ baseRevision: serverRevision, project }), keepalive: true }).catch(() => {}); } });

boot();



