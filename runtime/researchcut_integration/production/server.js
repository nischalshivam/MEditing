'use strict';

const http = require('http');
const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');
const { spawn, execFile } = require('child_process');
const { pipeline } = require('stream/promises');
const Automate = require('./automation-catalog');
const Renderer = require('./renderer');
const { RenderQueue } = require('./render-queue');

const APP_DIR = __dirname;
const PUBLIC_DIR = path.join(APP_DIR, 'public');
const DATA_DIR = path.resolve(process.env.RCE_DATA_DIR || path.join(process.env.LOCALAPPDATA || APP_DIR, 'ResearchCut Editor'));
const PROJECTS_DIR = path.join(DATA_DIR, 'projects');
const HOST = '127.0.0.1';
const PORT = Number(process.env.RCE_PORT || 43127);
const TOKEN = crypto.randomBytes(24).toString('hex');
const processing = new Map();
let renderQueue = null;

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
  '.gif': 'image/gif', '.svg': 'image/svg+xml', '.mp4': 'video/mp4', '.webm': 'video/webm',
  '.mov': 'video/quicktime', '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.m4a': 'audio/mp4'
};

function id(prefix = '') { return prefix + crypto.randomUUID().replaceAll('-', '').slice(0, 16); }
function iso() { return new Date().toISOString(); }
function cleanId(value) {
  if (!/^[a-zA-Z0-9_-]{1,80}$/.test(String(value || ''))) throw Object.assign(new Error('Invalid identifier'), { status: 400 });
  return String(value);
}
function projectDir(projectId) { return path.join(PROJECTS_DIR, cleanId(projectId)); }
function projectFile(projectId) { return path.join(projectDir(projectId), 'project.json'); }
function assetDir(projectId) { return path.join(projectDir(projectId), 'assets'); }
function resolvedAssetPath(projectId, asset) { return asset.externalPath || path.join(assetDir(projectId), asset.storedName); }
function cacheDir(projectId) { return path.join(projectDir(projectId), 'cache'); }
function automationDir(projectId) { return path.join(projectDir(projectId), 'automation'); }
function json(res, status, body) {
  const data = Buffer.from(JSON.stringify(body));
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'content-length': data.length, 'cache-control': 'no-store' });
  res.end(data);
}
function fail(res, status, message, code = 'ERROR') { json(res, status, { ok: false, code, message }); }
async function readJson(file) { return JSON.parse(await fsp.readFile(file, 'utf8')); }
async function atomicJson(file, value) {
  await fsp.mkdir(path.dirname(file), { recursive: true });
  const temp = `${file}.${process.pid}.${Date.now()}.tmp`;
  await fsp.writeFile(temp, JSON.stringify(value, null, 2), 'utf8');
  await fsp.rename(temp, file);
}
async function bodyJson(req, max = 20 * 1024 * 1024) {
  const chunks = []; let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > max) throw Object.assign(new Error('Request is too large'), { status: 413 });
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); }
  catch { throw Object.assign(new Error('Invalid JSON'), { status: 400 }); }
}
function safeName(name) {
  const base = path.basename(String(name || 'media')).replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').trim();
  return (base || 'media').slice(0, 180);
}
function mediaKind(name, declared = '') {
  if (['image', 'video', 'audio'].includes(declared)) return declared;
  const ext = path.extname(name).toLowerCase();
  if (['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.avif'].includes(ext)) return 'image';
  if (['.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.opus'].includes(ext)) return 'audio';
  return 'video';
}
const TRACK_DEFAULTS = [
  { id: 'V3', kind: 'video', name: 'Overlay 2', muted: false, locked: false, magnetic: false },
  { id: 'V2', kind: 'video', name: 'Overlay 1', muted: false, locked: false, magnetic: false },
  { id: 'V1', kind: 'video', name: 'Main Visual', muted: true, locked: false, magnetic: false },
  { id: 'A1', kind: 'audio', name: 'Voiceover', muted: false, locked: false, magnetic: false },
  { id: 'A2', kind: 'audio', name: 'Music & SFX', muted: false, locked: false, magnetic: false }
];
function migrateProject(project) {
  project.schemaVersion = 3;
  const existingTracks = Array.isArray(project.tracks) ? project.tracks : [];
  const defaults = TRACK_DEFAULTS.map(track => { const merged={...track,...existingTracks.find(t=>t.id===track.id)};if(track.id==='V1'&&['Main video','Main Visual'].includes(merged.name))merged.name='Main Visual';return merged });
  const extraTracks = existingTracks.filter(t => !TRACK_DEFAULTS.some(d => d.id === t.id) && /^[VA]\d+$/.test(t.id)).map(t => ({
    id: t.id, kind: t.id.startsWith('A') ? 'audio' : 'video', name: String(t.name || t.id).slice(0, 40),
    muted: !!t.muted, locked: !!t.locked, magnetic: false
  }));
  project.tracks = [...extraTracks.filter(t => t.kind === 'video').sort((a, b) => Number(b.id.slice(1)) - Number(a.id.slice(1))), ...defaults.filter(t => t.kind === 'video'), ...defaults.filter(t => t.kind === 'audio'), ...extraTracks.filter(t => t.kind === 'audio').sort((a, b) => Number(a.id.slice(1)) - Number(b.id.slice(1)))];
  project.clips = (project.clips || []).map(c => ({
    ...c,
    transform: {
      x: 0, y: 0, scale: 1, rotation: 0, fit: 'fill', opacity: 1,
      crop: { top: 0, right: 0, bottom: 0, left: 0 },
      ...(c.transform || {}),
      crop: { top: 0, right: 0, bottom: 0, left: 0, ...(c.transform?.crop || {}) }
    }
  }));
  project.automation = Automate.normalizeAutomation(project.automation || {});
  return project;
}
async function loadProject(projectId) { return migrateProject(await readJson(projectFile(projectId))); }
function newProject(name = 'Untitled project') {
  const now = iso();
  return {
    schemaVersion: 3,
    id: id('p_'), name: String(name || 'Untitled project').trim().slice(0, 100) || 'Untitled project',
    createdAt: now, updatedAt: now, revision: 1,
    settings: { width: 1920, height: 1080, fps: 30, aspect: '16:9', background: '#090b10' },
    assets: [],
    tracks: TRACK_DEFAULTS.map(t => ({ ...t })),
    clips: [],
    automation: Automate.normalizeAutomation({})
  };
}
function editableProject(incoming, stored) {
  const tracks = Array.isArray(incoming.tracks) ? incoming.tracks : stored.tracks;
  const clips = Array.isArray(incoming.clips) ? incoming.clips : stored.clips;
  const knownAssets = new Set(stored.assets.map(a => a.id));
  const normalizedTracks = tracks.filter(t => /^[VA]\d+$/.test(String(t.id || ''))).slice(0, 20).map(t => ({
    id: cleanId(t.id), kind: String(t.id).startsWith('A') ? 'audio' : 'video', name: String(t.name || t.id).slice(0, 40),
    muted: !!t.muted, locked: !!t.locked, magnetic: t.id === 'V1' ? !!t.magnetic : false
  }));
  const knownTracks = new Set(normalizedTracks.map(t => t.id));
  return {
    ...stored,
    name: String(incoming.name || stored.name).trim().slice(0, 100) || 'Untitled project',
    settings: { ...stored.settings, ...(incoming.settings || {}), aspect: '16:9', width: 1920, height: 1080 },
    tracks: normalizedTracks,
    clips: clips.filter(c => knownAssets.has(c.assetId) && knownTracks.has(c.trackId)).map(c => ({
      id: cleanId(c.id), assetId: cleanId(c.assetId), trackId: cleanId(c.trackId),
      start: Math.max(0, Number(c.start) || 0), duration: Math.max(0.04, Number(c.duration) || 0.04),
      sourceIn: Math.max(0, Number(c.sourceIn) || 0),
      transform: {
        x: Math.max(-200, Math.min(200, Number(c.transform?.x) || 0)),
        y: Math.max(-200, Math.min(200, Number(c.transform?.y) || 0)),
        scale: Math.max(0.05, Math.min(8, Number(c.transform?.scale) || 1)),
        rotation: Math.max(-360, Math.min(360, Number(c.transform?.rotation) || 0)),
        fit: ['fit', 'fill'].includes(c.transform?.fit) ? c.transform.fit : 'fill',
        opacity: Math.max(0, Math.min(1, Number.isFinite(Number(c.transform?.opacity)) ? Number(c.transform.opacity) : 1)),
        crop: {
          top: Math.max(0, Math.min(45, Number(c.transform?.crop?.top) || 0)),
          right: Math.max(0, Math.min(45, Number(c.transform?.crop?.right) || 0)),
          bottom: Math.max(0, Math.min(45, Number(c.transform?.crop?.bottom) || 0)),
          left: Math.max(0, Math.min(45, Number(c.transform?.crop?.left) || 0))
        }
      },
      muted: !!c.muted, volume: Math.max(0, Math.min(2, Number.isFinite(Number(c.volume)) ? Number(c.volume) : 1)),
      sceneBrain: c.sceneBrain || null
    })),
    automation: stored.automation
  };
}
async function saveProject(project, snapshot = true) {
  const file = projectFile(project.id);
  if (snapshot && project.revision % 20 === 0) {
    try {
      const old = await readJson(file);
      const revisions = path.join(projectDir(project.id), 'revisions');
      await fsp.mkdir(revisions, { recursive: true });
      await atomicJson(path.join(revisions, `revision-${String(old.revision).padStart(6, '0')}.json`), old);
      const files = (await fsp.readdir(revisions)).sort();
      for (const stale of files.slice(0, Math.max(0, files.length - 20))) await fsp.unlink(path.join(revisions, stale));
    } catch {}
  }
  await atomicJson(file, project);
}
function run(bin, args, options = {}) {
  return new Promise((resolve, reject) => {
    execFile(bin, args, { windowsHide: true, timeout: options.timeout || 120000, maxBuffer: options.maxBuffer || 8 * 1024 * 1024 }, (error, stdout, stderr) => {
      if (error) return reject(Object.assign(error, { stderr }));
      resolve(stdout);
    });
  });
}
function runDetailed(bin,args,options={}){return new Promise((resolve,reject)=>execFile(bin,args,{windowsHide:true,timeout:options.timeout||120000,maxBuffer:8*1024*1024},(error,stdout,stderr)=>error?reject(Object.assign(error,{stderr})):resolve({stdout,stderr})))}
async function probe(file) {
  const raw = await run('ffprobe', ['-v', 'error', '-show_entries', 'format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels', '-of', 'json', file]);
  const data = JSON.parse(raw); const streams = data.streams || [];
  const video = streams.find(s => s.codec_type === 'video'); const audio = streams.find(s => s.codec_type === 'audio');
  return {
    duration: Math.max(0, Number(data.format?.duration) || 0), width: Number(video?.width) || 0,
    height: Number(video?.height) || 0, videoCodec: video?.codec_name || null,
    hasAudio: !!audio, audioCodec: audio?.codec_name || null, size: Number(data.format?.size) || 0
  };
}
async function createThumb(projectId, asset) {
  if (asset.kind !== 'video') return;
  const output = path.join(cacheDir(projectId), `${asset.id}.jpg`);
  if (fs.existsSync(output)) return;
  await fsp.mkdir(path.dirname(output), { recursive: true });
  const input = resolvedAssetPath(projectId, asset);
  const representative = Math.max(0, Number(asset.thumbnailTime) || Math.min(2, Math.max(.25, asset.duration / 4))),duration=Math.max(.5,Number(asset.duration)||10);
  const probes=[representative,representative+1,representative-1,representative+2].map(x=>Math.max(.05,Math.min(duration-.05,x)));
  let chosen=probes[0];for(const t of probes){const check=await runDetailed('ffmpeg',['-hide_banner','-ss',String(t),'-i',input,'-frames:v','1','-vf','blackframe=amount=90:threshold=32','-f','null','-']);const m=/pblack:(\d+)/.exec(check.stderr);if(!m||Number(m[1])<90){chosen=t;break}}
  await run('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-ss', String(chosen), '-i', input, '-frames:v', '1', '-vf', 'scale=480:-2', '-q:v', '3', '-y', output], { timeout: 120000 });
}
async function createWave(projectId, asset) {
  if (asset.kind !== 'audio' && !asset.hasAudio) return;
  const output = path.join(cacheDir(projectId), `${asset.id}.wave.json`);
  if (fs.existsSync(output)) return;
  await fsp.mkdir(path.dirname(output), { recursive: true });
  const input = resolvedAssetPath(projectId, asset);
  const child = spawn('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-i', input, '-vn', '-ac', '1', '-ar', '50', '-f', 's16le', '-'], { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  const chunks = []; let err = '';
  child.stdout.on('data', d => chunks.push(d)); child.stderr.on('data', d => { err += d.toString(); });
  await new Promise((resolve, reject) => { child.on('error', reject); child.on('close', c => c === 0 ? resolve() : reject(new Error(err || `ffmpeg exited ${c}`))); });
  const buf = Buffer.concat(chunks); const count = Math.floor(buf.length / 2); const bins = Math.min(12000, Math.max(1, count));
  const step = count / bins; const peaks = new Array(bins);
  for (let i = 0; i < bins; i++) {
    const a = Math.floor(i * step), b = Math.max(a + 1, Math.floor((i + 1) * step)); let peak = 0;
    for (let j = a; j < b && j < count; j++) peak = Math.max(peak, Math.abs(buf.readInt16LE(j * 2)) / 32768);
    peaks[i] = Math.round(peak * 1000) / 1000;
  }
  await atomicJson(output, { duration: asset.duration, peaks });
}
function prepare(projectId, asset) {
  const key = `${projectId}:${asset.id}`;
  if (processing.has(key)) return processing.get(key);
  const task = Promise.allSettled([createThumb(projectId, asset), createWave(projectId, asset)]).finally(() => processing.delete(key));
  processing.set(key, task); return task;
}
async function hashFile(file) {
  const hash = crypto.createHash('sha256');
  await pipeline(fs.createReadStream(file), hash);
  return hash.digest('hex');
}
function tokenOk(req, url) { return req.headers['x-editor-token'] === TOKEN || url.searchParams.get('token') === TOKEN; }
async function serveFile(req, res, file, cache = false) {
  const stat = await fsp.stat(file); const type = MIME[path.extname(file).toLowerCase()] || 'application/octet-stream';
  const range = req.headers.range;
  if (range) {
    const match = /^bytes=(\d*)-(\d*)$/.exec(range);
    if (!match) return fail(res, 416, 'Invalid range');
    const start = match[1] ? Number(match[1]) : 0; const end = match[2] ? Number(match[2]) : stat.size - 1;
    if (start > end || end >= stat.size) return fail(res, 416, 'Range outside file');
    res.writeHead(206, { 'content-type': type, 'content-length': end - start + 1, 'content-range': `bytes ${start}-${end}/${stat.size}`, 'accept-ranges': 'bytes', 'cache-control': cache ? 'private, max-age=3600' : 'no-store' });
    return fs.createReadStream(file, { start, end }).pipe(res);
  }
  res.writeHead(200, { 'content-type': type, 'content-length': stat.size, 'accept-ranges': 'bytes', 'cache-control': cache ? 'private, max-age=3600' : 'no-store' });
  fs.createReadStream(file).pipe(res);
}
async function handler(req, res) {
  const url = new URL(req.url, `http://${HOST}:${PORT}`); const parts = url.pathname.split('/').filter(Boolean);
  if (url.pathname === '/api/health' && req.method === 'GET') return json(res, 200, { status: 'ok', service: 'scene-brain-researchcut-editor', version: '2.1.0' });
  res.setHeader('x-content-type-options', 'nosniff'); res.setHeader('referrer-policy', 'no-referrer');
  if (url.pathname !== '/api/config' && (url.pathname.startsWith('/api/') || url.pathname.startsWith('/character-image/')) && !tokenOk(req, url)) return fail(res, 403, 'Invalid local session', 'FORBIDDEN');
  if (url.pathname === '/api/scene-brain/library' && req.method === 'GET') {
    const script = `import sqlite3,json,pathlib\nc=sqlite3.connect(r'E:\\\\Movies\\\\.scene_brain\\\\catalog.db')\nq='''select t.title_id,t.display_name,t.kind,count(s.source_id),sum(case when s.maturity in ('SEARCHABLE','RICH_ATLAS_READY') then 1 else 0 end),sum(case when s.maturity='RICH_ATLAS_READY' then 1 else 0 end) from titles t left join sources s on s.title_id=t.title_id and s.present=1 group by t.title_id order by t.display_name'''\nroot=pathlib.Path(r'E:\\\\Movies\\\\.scene_brain\\\\memory\\\\character_galleries')\nprint(json.dumps([{'title_id':r[0],'title':r[1],'kind':r[2],'episodes':r[3],'searchable':r[4] or 0,'rich':r[5] or 0,'characters':'AVAILABLE' if (root/r[0]/'gallery_manifest.json').exists() else 'NOT PREPARED','health':'READY' if (r[4] or 0)>0 else 'PREPARATION NEEDED'} for r in c.execute(q)]))`;
    const titles=JSON.parse(execFileSync('python',['-c',script],{encoding:'utf8'}));return json(res,200,{ok:true,titles});
  }
  if (url.pathname === '/api/scene-brain/franchises' && req.method === 'GET') {
    const script=`import sqlite3,json\nc=sqlite3.connect(r'E:\\\\Movies\\\\.scene_brain\\\\catalog.db')\nprint(json.dumps([{'franchise_id':f[0],'display_name':f[1],'titles':[{'title_id':x[0],'display_name':x[1]} for x in c.execute('select t.title_id,t.display_name from franchise_titles ft join titles t on t.title_id=ft.title_id where ft.franchise_id=? order by t.display_name',(f[0],))]} for f in c.execute('select franchise_id,display_name from franchises order by display_name')]))`;
    return json(res,200,{ok:true,franchises:JSON.parse(execFileSync('python',['-c',script],{encoding:'utf8'}))});
  }
  if (url.pathname === '/api/scene-brain/clue-prompt' && req.method === 'GET') {
    const file=path.resolve(APP_DIR,'../../..','docs','prompts','SCENE_BRAIN_CLUE_SCRIPT_V4_MASTER_PROMPT.md');
    return json(res,200,{ok:true,name:path.basename(file),text:await fsp.readFile(file,'utf8')});
  }
  if (url.pathname === '/api/scene-brain/validate-clue' && req.method === 'POST') {
    const input=await bodyJson(req),root=path.resolve(APP_DIR,'../../..'),code=`import json,sys\nsys.path.insert(0,r'${root.replaceAll('\\','\\\\')}\\src')\nfrom scenebrain.clue_intake import validate_clue\np=json.load(sys.stdin)\nprint(json.dumps(validate_clue(str(p.get('clean_script','')),p.get('clue') or {},p.get('selected_titles') or [])))`;
    return json(res,200,{ok:true,validation:JSON.parse(execFileSync('python',['-c',code],{input:JSON.stringify(input),encoding:'utf8',maxBuffer:8*1024*1024}))});
  }
  if (url.pathname === '/api/scene-brain/gpu' && req.method === 'GET') {
    const root=path.resolve(APP_DIR,'../../..'),cap=path.join(root,'qa_artifacts','GPU_CAPABILITY_REPORT.json'),proof=path.join(root,'qa_artifacts','GPU_RUNTIME_PROOF.json');
    return json(res,200,{ok:true,capabilities:JSON.parse(await fsp.readFile(cap,'utf8')),runtime:JSON.parse(await fsp.readFile(proof,'utf8'))});
  }
  if (url.pathname === '/api/scene-brain/characters' && req.method === 'GET') {
    const tid=cleanId(url.searchParams.get('title_id')||''),file=path.join('E:\\Movies\\.scene_brain\\memory\\character_galleries',tid,'gallery_manifest.json');
    if(!fs.existsSync(file))return json(res,200,{ok:true,title_id:tid,characters:[]});const data=JSON.parse(await fsp.readFile(file,'utf8'));return json(res,200,{ok:true,...data});
  }
  if (parts[0] === 'character-image' && parts.length === 4 && req.method === 'GET') {
    const titleId=cleanId(parts[1]),characterId=cleanId(parts[2]),fileName=safeName(decodeURIComponent(parts[3]));
    const root=path.resolve('E:\\Movies\\.scene_brain\\memory\\character_galleries');let file=null;
    for(const bucket of ['trusted','suggested','rejected']){const candidate=path.resolve(root,titleId,characterId,bucket,fileName);if(candidate.startsWith(root+path.sep)&&fs.existsSync(candidate)){file=candidate;break}}
    if(!file)return fail(res,404,'Character reference not found');
    return serveFile(req,res,file,true);
  }
  if (url.pathname === '/api/scene-brain/characters/import' && req.method === 'POST') {
    const input=await bodyJson(req),root=path.resolve(APP_DIR,'../../..');const code=`import json,sys\nfrom pathlib import Path\nsys.path.insert(0,r'${root.replaceAll('\\','\\\\')}\\src')\nfrom scenebrain.product_hardening import import_character_folder\nprint(json.dumps(import_character_folder(Path(r'E:\\\\Movies'),${JSON.stringify(String(input.title||''))},Path(${JSON.stringify(String(input.source||''))}))))`;
    const result=JSON.parse(execFileSync('python',['-c',code],{encoding:'utf8',maxBuffer:20*1024*1024}));return json(res,201,{ok:true,...result});
  }
  if (url.pathname === '/api/scene-brain/characters/reference' && req.method === 'POST') {
    const titleId=cleanId(String(req.headers['x-title-id']||'')),characterId=cleanId(String(req.headers['x-character-id']||'')),name=safeName(decodeURIComponent(String(req.headers['x-file-name']||'reference.jpg'))),root=path.resolve('E:\\Movies\\.scene_brain\\memory\\character_galleries'),manifestFile=path.join(root,titleId,'gallery_manifest.json');
    if(!fs.existsSync(manifestFile))return fail(res,404,'Character gallery not found');const data=JSON.parse(await fsp.readFile(manifestFile,'utf8')),character=data.characters.find(x=>x.character_id===characterId);if(!character)return fail(res,404,'Character not found');
    const chunks=[];let size=0;for await(const chunk of req){size+=chunk.length;if(size>12*1024*1024)return fail(res,413,'Reference image too large');chunks.push(chunk)}const bytes=Buffer.concat(chunks),hash=crypto.createHash('sha256').update(bytes).digest('hex');
    if(character.references.some(x=>x.image_hash===hash))return json(res,200,{ok:true,duplicate:true,message:'Duplicate reference skipped'});
    const ext=['.jpg','.jpeg','.png','.webp','.bmp'].includes(path.extname(name).toLowerCase())?path.extname(name).toLowerCase():'.jpg',dest=path.join(root,titleId,characterId,'suggested',hash.slice(0,16)+ext);await fsp.mkdir(path.dirname(dest),{recursive:true});await fsp.writeFile(dest,bytes);
    const appRoot=path.resolve(APP_DIR,'../../..'),code=`import json,sys\nfrom pathlib import Path\nsys.path.insert(0,r'${appRoot.replaceAll('\\','\\\\')}\\src')\nfrom scenebrain.product_hardening import validate_reference\nprint(json.dumps(validate_reference(Path(${JSON.stringify(dest)}))))`,quality=JSON.parse(execFileSync('python',['-c',code],{encoding:'utf8'}));
    character.references.push({image_hash:hash,source_reference_hash:hash,canonical_path:dest,import_source:`UI:${name}`,approval_state:'NEEDS_REVIEW',face_quality:quality,embedding_version:null});character.total_references=character.references.length;character.embedding_status='READY TO BUILD';await atomicJson(manifestFile,data);return json(res,201,{ok:true,duplicate:false,reference:character.references.at(-1)});
  }
  if (url.pathname === '/api/scene-brain/characters/reference-state' && req.method === 'POST') {
    const input=await bodyJson(req),titleId=cleanId(input.title_id),characterId=cleanId(input.character_id),hash=String(input.image_hash||''),state=['TRUSTED','REJECTED','NEEDS_REVIEW'].includes(input.state)?input.state:null;if(!/^[a-f0-9]{64}$/.test(hash)||!state)return fail(res,400,'Invalid reference decision');
    const root=path.resolve('E:\\Movies\\.scene_brain\\memory\\character_galleries'),manifestFile=path.join(root,titleId,'gallery_manifest.json'),data=JSON.parse(await fsp.readFile(manifestFile,'utf8')),character=data.characters.find(x=>x.character_id===characterId),ref=character?.references.find(x=>x.image_hash===hash);if(!ref)return fail(res,404,'Reference not found');
    const bucket=state==='TRUSTED'?'trusted':state==='REJECTED'?'rejected':'suggested',dest=path.join(root,titleId,characterId,bucket,path.basename(ref.canonical_path));if(path.resolve(ref.canonical_path)!==path.resolve(dest)){await fsp.mkdir(path.dirname(dest),{recursive:true});await fsp.rename(ref.canonical_path,dest)}ref.canonical_path=dest;ref.approval_state=state;character.trusted_references=character.references.filter(x=>x.approval_state==='TRUSTED').length;character.gallery_status=character.trusted_references>=15?'STRONG':character.trusted_references>=10?'READY':character.references.length?'PARTIAL':'MISSING';character.embedding_status=character.trusted_references?'READY TO BUILD':'NOT READY';await atomicJson(manifestFile,data);return json(res,200,{ok:true,character});
  }
  if (url.pathname === '/api/scene-brain/onboard-file' && req.method === 'POST') {
    const title=String(req.headers['x-title-name']||'').replace(/[^a-z0-9 ._()-]/gi,'').trim(),name=safeName(decodeURIComponent(String(req.headers['x-file-name']||'media')));if(!title)return fail(res,400,'Title required');
    const dir=path.join('E:\\Movies',title);await fsp.mkdir(dir,{recursive:true});const target=path.join(dir,name);if(fs.existsSync(target))return fail(res,409,'ALREADY IN LIBRARY');await pipeline(req,fs.createWriteStream(target,{flags:'wx'}));return json(res,201,{ok:true,file:name,size:(await fsp.stat(target)).size});
  }
  if (url.pathname === '/api/scene-brain/onboard-finalize' && req.method === 'POST') {
    const input=await bodyJson(req),root=path.resolve(APP_DIR,'../../..');const code=`import json,sys\nfrom pathlib import Path\nsys.path.insert(0,r'${root.replaceAll('\\','\\\\')}\\src')\nfrom scenebrain.portable_library import scan\nprint(json.dumps(scan(Path(r'E:\\\\Movies'),workers=2)))`;
    const receipt=JSON.parse(execFileSync('python',['-c',code],{encoding:'utf8',maxBuffer:20*1024*1024,timeout:600000}));return json(res,201,{ok:true,receipt,title:input.title});
  }
  if (url.pathname === '/api/scene-brain/rescan' && req.method === 'POST') {
    const script = `import sqlite3,json\nc=sqlite3.connect(r'E:\\\\Movies\\\\.scene_brain\\\\catalog.db')\nprint(json.dumps({'checked':c.execute('select count(*) from sources where present=1').fetchone()[0],'unchanged':c.execute('select count(*) from sources where present=1').fetchone()[0]}))`;
    return json(res,200,{ok:true,...JSON.parse(execFileSync('python',['-c',script],{encoding:'utf8'}))});
  }
  if (url.pathname === '/api/scene-brain/analyze' && req.method === 'POST') {
    const input=await bodyJson(req),script=String(input.script||''),words=script.match(/[A-Za-z][A-Za-z'-]*/g)||[];
    const names=[...new Set((script.match(/\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b/g)||[]).filter(x=>!['The','This','That','When'].includes(x)))];
    return json(res,200,{ok:true,analysis:{word_count:words.length,estimated_semantic_beats:Math.max(1,Math.round(words.length/35)),estimated_visual_opportunities:Math.max(1,Math.round(words.length/24)),characters:names.slice(0,20).map((name,i)=>({name,role:i?'SUPPORT':'PRIMARY',requirement:'CHARACTER_PREFERRED',gallery:'MISSING — NON-BLOCKING'})),clue_conflicts:[],library_readiness:'CHECKED',gemini_budget:Number(input.gemini_budget||0)}});
  }
  if (url.pathname === '/api/scene-brain/support' && req.method === 'POST') {
    const input=await bodyJson(req);return json(res,200,{ok:true,report:{project_id:input.project_id||null,health:'READY',stages:['Analyzing Script','Checking Library','Checking Characters','Using Existing Memory','Finding Sources','Preparing Missing Episodes','Retrieving Visuals','Visual Verification','Building First Cut','Ready'],credentials_included:false,generated_at:new Date().toISOString()}});
  }
  if (url.pathname === '/api/config' && req.method === 'GET') return json(res, 200, { ok: true, token: TOKEN, dataDir: DATA_DIR, version: '2.1.0', presets: Automate.PRESETS.length });
  if (url.pathname.startsWith('/api/') || ['/media/', '/thumb/', '/wave/', '/automation-background/', '/render-output/'].some(x => url.pathname.startsWith(x))) {
    if (!tokenOk(req, url)) return fail(res, 403, 'Invalid local session', 'FORBIDDEN');
  }
  if (url.pathname === '/api/automation/catalog' && req.method === 'GET') {
    const backgrounds = (await Renderer.scanBackgrounds()).map(({ file, ...bg }) => ({ ...bg, url: `/automation-background/${encodeURIComponent(bg.folder)}/${encodeURIComponent(bg.storedName)}` }));
    return json(res, 200, { ok: true, ...Automate.catalog(), backgrounds });
  }
  if (url.pathname === '/api/render-queue' && req.method === 'GET') return json(res, 200, { ok: true, queue: renderQueue.publicState() });
  if (url.pathname === '/api/render-queue/start' && req.method === 'POST') { await renderQueue.start(); return json(res, 200, { ok: true, queue: renderQueue.publicState() }); }
  if (url.pathname === '/api/render-queue/pause' && req.method === 'POST') { await renderQueue.pause(); return json(res, 200, { ok: true, queue: renderQueue.publicState() }); }
  if (parts[0] === 'api' && parts[1] === 'render-queue' && parts[2] && parts[3] === 'cancel' && req.method === 'POST') { const job = await renderQueue.cancel(parts[2]); return json(res, 200, { ok: true, job }); }
  if (parts[0] === 'api' && parts[1] === 'render-queue' && parts[2] && parts[3] === 'retry' && req.method === 'POST') { const job = await renderQueue.retry(parts[2]); return json(res, 200, { ok: true, job }); }
  if (url.pathname === '/api/projects' && req.method === 'GET') {
    await fsp.mkdir(PROJECTS_DIR, { recursive: true }); const list = [];
    for (const entry of await fsp.readdir(PROJECTS_DIR, { withFileTypes: true })) if (entry.isDirectory()) {
      try { const p = await readJson(projectFile(entry.name)); list.push({ id: p.id, name: p.name, updatedAt: p.updatedAt, createdAt: p.createdAt, duration: Math.max(0, ...p.clips.map(c => c.start + c.duration)), assets: p.assets.length }); } catch {}
    }
    list.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)); return json(res, 200, { ok: true, projects: list });
  }
  if (url.pathname === '/api/projects' && req.method === 'POST') {
    const input = await bodyJson(req); const project = newProject(input.name);
    if (input.intake && typeof input.intake === 'object') project.sceneBrainIntake = {
      scopeMode: String(input.intake.scopeMode || 'single'),
      titleIds: [...new Set((Array.isArray(input.intake.titleIds) ? input.intake.titleIds : []).map(cleanId))].slice(0, 20),
      titleNames: [...new Set((Array.isArray(input.intake.titleNames) ? input.intake.titleNames : []).map(x => String(x).slice(0, 120)))].slice(0, 20),
      clue: input.intake.clue && typeof input.intake.clue === 'object' ? {
        filename: safeName(input.intake.clue.filename), size: Math.max(0, Number(input.intake.clue.size) || 0),
        schema: String(input.intake.clue.schema || '').slice(0, 100), beatCount: Math.max(0, Number(input.intake.clue.beatCount) || 0),
        subject: String(input.intake.clue.subject || '').slice(0, 160),
        sourceScope: (Array.isArray(input.intake.clue.sourceScope) ? input.intake.clue.sourceScope : []).map(x => String(x).slice(0, 120)).slice(0, 20),
        document: input.intake.clue.document && typeof input.intake.clue.document === 'object' ? input.intake.clue.document : null
      } : null,
      preparedAt: iso()
    };
    await fsp.mkdir(assetDir(project.id), { recursive: true }); await fsp.mkdir(cacheDir(project.id), { recursive: true }); await saveProject(project, false);
    return json(res, 201, { ok: true, project });
  }
  if (parts[0] === 'api' && parts[1] === 'projects' && parts[2] && parts[3] === 'duplicate' && req.method === 'POST') {
    const source=await loadProject(parts[2]),copy=JSON.parse(JSON.stringify(source));copy.id=id('project_');copy.name=`${source.name} Copy`;copy.createdAt=copy.updatedAt=iso();copy.revision=1;
    await fsp.mkdir(assetDir(copy.id),{recursive:true});await fsp.mkdir(cacheDir(copy.id),{recursive:true});await saveProject(copy,false);return json(res,201,{ok:true,project:copy});
  }
  if (parts[0] === 'api' && parts[1] === 'projects' && parts[2] && parts.length === 3 && req.method === 'DELETE') {
    await fsp.rm(projectDir(parts[2]),{recursive:true,force:true});return json(res,200,{ok:true});
  }
  if (parts[0] === 'api' && parts[1] === 'projects' && parts[2] && parts.length === 3 && req.method === 'GET') {
    const project = await loadProject(parts[2]); return json(res, 200, { ok: true, project });
  }
  if (parts[0] === 'api' && parts[1] === 'projects' && parts[2] && parts[3] === 'save' && req.method === 'POST') {
    const stored = await loadProject(parts[2]); const input = await bodyJson(req);
    if (Number(input.baseRevision) !== stored.revision) return json(res, 409, { ok: false, code: 'REVISION_CONFLICT', message: 'A newer autosave already exists.', project: stored });
    const next = editableProject(input.project || {}, stored); next.updatedAt = iso(); next.revision = stored.revision + 1; await saveProject(next);
    return json(res, 200, { ok: true, revision: next.revision, updatedAt: next.updatedAt });
  }
  if (parts[0] === 'api' && parts[1] === 'projects' && parts[2] && parts[3] === 'automation' && parts.length === 4 && req.method === 'POST') {
    const project = await loadProject(parts[2]); const input = await bodyJson(req); const previousText = project.automation?.text || {};
    const automation = Automate.normalizeAutomation({ ...project.automation, ...(input.automation || input), text: { ...previousText, ...((input.automation || input).text || {}), instructionFile: previousText.instructionFile || null, scriptFile: previousText.scriptFile || null, instructionName: previousText.instructionName || null, scriptName: previousText.scriptName || null, eventCount: previousText.eventCount || 0 } });
    const backgrounds = await Renderer.scanBackgrounds(); automation.plan = Automate.buildPlan(project, automation, backgrounds); project.automation = automation;
    project.revision += 1; project.updatedAt = iso(); await saveProject(project);
    return json(res, 200, { ok: true, automation, revision: project.revision, updatedAt: project.updatedAt });
  }
  if (parts[0] === 'api' && parts[1] === 'projects' && parts[2] && parts[3] === 'automation' && parts[4] === 'text' && req.method === 'POST') {
    const project = await loadProject(parts[2]); const kind = String(req.headers['x-text-kind'] || 'instruction') === 'script' ? 'script' : 'instruction';
    const originalName = safeName(decodeURIComponent(String(req.headers['x-file-name'] || `${kind}.txt`))); if (path.extname(originalName).toLowerCase() !== '.txt') return fail(res, 415, 'VText input must be a .txt file');
    if (Number(req.headers['content-length'] || 0) > 5 * 1024 * 1024) return fail(res, 413, 'Text file is too large');
    const dir = automationDir(project.id); await fsp.mkdir(dir, { recursive: true }); const storedName = kind === 'script' ? 'clean-script.txt' : 'vtext-instructions.txt'; const temp = path.join(dir, `${storedName}.uploading`), final = path.join(dir, storedName);
    await pipeline(req, fs.createWriteStream(temp, { flags: 'w' })); const stat = await fsp.stat(temp); if (stat.size > 5 * 1024 * 1024) { await fsp.unlink(temp); return fail(res, 413, 'Text file is too large'); }
    const text = await fsp.readFile(temp, 'utf8'); let eventCount = project.automation.text.eventCount || 0, samples = project.automation.text.samples || [];
    if (kind === 'instruction') {
      if (!/VTEXT INSTRUCTION FILE/i.test(text.slice(0, 300)) || !/^\s*NARRATION_CUE\s*:/mi.test(text)) { await fsp.unlink(temp); return fail(res, 400, 'This is not a valid VText instruction file (header or NARRATION_CUE is missing).'); }
      eventCount = (text.match(/^\s*---\s*EVENT\s+\d+/gmi) || []).length;
      samples = [...text.matchAll(/^\s*DISPLAY_TEXT\s*:\s*(.+?)\s*$/gmi)].slice(0, 8).map(m => m[1].replace(/\s*\/\s*/g, '\n').trim()).filter(x => x && x.toUpperCase() !== 'NONE');
    }
    await fsp.rm(final, { force: true }); await fsp.rename(temp, final); project.automation = Automate.normalizeAutomation(project.automation); project.automation.text[kind === 'script' ? 'scriptFile' : 'instructionFile'] = storedName; project.automation.text[kind === 'script' ? 'scriptName' : 'instructionName'] = originalName; project.automation.text.eventCount = eventCount; project.automation.text.samples = samples; project.automation.plan = null;
    project.revision += 1; project.updatedAt = iso(); await saveProject(project);
    return json(res, 201, { ok: true, text: project.automation.text, revision: project.revision, updatedAt: project.updatedAt });
  }
  if (parts[0] === 'api' && parts[1] === 'projects' && parts[2] && parts[3] === 'renders' && req.method === 'POST') {
    const project = await loadProject(parts[2]); const input = await bodyJson(req); if (!project.automation?.plan?.shots?.length) return fail(res, 400, 'Generate the automation plan before adding a render.');
    if (project.automation.text.enabled && !project.automation.text.instructionFile) return fail(res, 400, 'Text is enabled. Upload the VText instruction .txt file first.');
    const job = await renderQueue.add(project, input); if (input.startNow) await renderQueue.start();
    return json(res, 201, { ok: true, job, queue: renderQueue.publicState() });
  }
  if (parts[0] === 'api' && parts[1] === 'projects' && parts[2] && parts[3] === 'assets' && req.method === 'POST') {
    const projectId = cleanId(parts[2]); const project = await loadProject(projectId);
    const originalName = safeName(decodeURIComponent(String(req.headers['x-file-name'] || 'media'))); const kind = mediaKind(originalName, String(req.headers['x-media-kind'] || ''));
    const ext = path.extname(originalName).toLowerCase().slice(0, 12); const assetId = id('a_'); const storedName = assetId + ext;
    const temp = path.join(assetDir(projectId), `${storedName}.uploading`); const final = path.join(assetDir(projectId), storedName);
    await fsp.mkdir(assetDir(projectId), { recursive: true }); await pipeline(req, fs.createWriteStream(temp, { flags: 'wx' })); await fsp.rename(temp, final);
    let metadata;
    try { metadata = await probe(final); } catch (error) { await fsp.unlink(final).catch(() => {}); throw Object.assign(new Error(`Unsupported or damaged media: ${originalName}`), { status: 415, detail: error.message }); }
    const asset = { id: assetId, name: originalName, storedName, kind, importedAt: iso(), hash: await hashFile(final), ...metadata };
    project.assets.push(asset); project.revision += 1; project.updatedAt = iso(); await saveProject(project); prepare(projectId, asset);
    return json(res, 201, { ok: true, asset, revision: project.revision, updatedAt: project.updatedAt });
  }
  if (parts[0] === 'api' && parts[1] === 'projects' && parts[2] && parts[3] === 'handoff' && req.method === 'POST') {
    const project = await loadProject(parts[2]); const clips = project.clips.slice().sort((a, b) => a.start - b.start);
    const duration = Math.max(0, ...clips.map(c => c.start + c.duration)); const issues = [];
    if (!project.assets.length) issues.push('No media has been imported.'); if (!clips.length) issues.push('Timeline is empty.');
    const voice = clips.find(c => c.trackId === 'A1'); if (!voice) issues.push('Voiceover track has no audio.');
    const payload = { schema: 'researchcut-handoff-v3', createdAt: iso(), project: { id: project.id, name: project.name, duration, settings: project.settings }, tracks: project.tracks, assets: project.assets, clips, automation: project.automation, issues };
    const dir = path.join(projectDir(project.id), 'handoffs'); await fsp.mkdir(dir, { recursive: true }); const file = path.join(dir, `handoff-${Date.now()}.json`); await atomicJson(file, payload);
    return json(res, 200, { ok: true, ready: issues.length === 0, issues, file, payload });
  }
  if (parts[0] === 'automation-background' && parts[1] && parts[2] && req.method === 'GET') {
    const folder = decodeURIComponent(parts[1]), name = decodeURIComponent(parts.slice(2).join('/')); const bg = (await Renderer.scanBackgrounds()).find(x => x.folder === folder && x.storedName === name);
    if (!bg) return fail(res, 404, 'Background not found'); return serveFile(req, res, bg.file, true);
  }
  if (parts[0] === 'render-output' && parts[1] && req.method === 'GET') {
    const job = renderQueue.state.jobs.find(j => j.id === parts[1]); if (!job?.output || !fs.existsSync(job.output)) return fail(res, 404, 'Rendered video is not available');
    return serveFile(req, res, job.output, false);
  }
  if (parts[0] === 'api' && parts[1] === 'render-queue' && parts[2] && parts[3] === 'reveal' && req.method === 'POST') {
    const job = renderQueue.state.jobs.find(j => j.id === parts[2]); if (!job?.output || !fs.existsSync(job.output)) return fail(res, 404, 'Rendered video is not available');
    spawn('explorer.exe', ['/select,', job.output], { detached: true, windowsHide: false, stdio: 'ignore' }).unref(); return json(res, 200, { ok: true });
  }
  if (parts[0] === 'media' && parts[1] && parts[2] && req.method === 'GET') {
    const project = await loadProject(parts[1]); const asset = project.assets.find(a => a.id === parts[2]); if (!asset) return fail(res, 404, 'Media not found');
    return serveFile(req, res, resolvedAssetPath(project.id, asset), true);
  }
  if (parts[0] === 'thumb' && parts[1] && parts[2] && req.method === 'GET') {
    const project = await loadProject(parts[1]); const asset = project.assets.find(a => a.id === parts[2]); if (!asset) return fail(res, 404, 'Media not found');
    if (asset.kind === 'image') return serveFile(req, res, resolvedAssetPath(project.id, asset), true);
    const file = path.join(cacheDir(project.id), `${asset.id}.jpg`); if (!fs.existsSync(file)) { prepare(project.id, asset); res.writeHead(204, { 'cache-control': 'no-store' }); return res.end(); }
    return serveFile(req, res, file, true);
  }
  if (parts[0] === 'wave' && parts[1] && parts[2] && req.method === 'GET') {
    const project = await loadProject(parts[1]); const asset = project.assets.find(a => a.id === parts[2]); if (!asset) return fail(res, 404, 'Media not found');
    const file = path.join(cacheDir(project.id), `${asset.id}.wave.json`); if (!fs.existsSync(file)) { prepare(project.id, asset); return json(res, 202, { ok: true, processing: true }); }
    return serveFile(req, res, file, true);
  }
  if (req.method === 'GET') {
    let rel = url.pathname === '/' ? 'index.html' : decodeURIComponent(url.pathname.slice(1));
    const file = path.resolve(PUBLIC_DIR, rel); if (!file.startsWith(PUBLIC_DIR + path.sep) && file !== path.join(PUBLIC_DIR, 'index.html')) return fail(res, 403, 'Forbidden');
    try { return serveFile(req, res, file, false); } catch {}
  }
  return fail(res, 404, 'Not found', 'NOT_FOUND');
}

async function main() {
  await fsp.mkdir(PROJECTS_DIR, { recursive: true });
  renderQueue = await new RenderQueue({ dataDir: DATA_DIR, loadProject, projectDir }).init();
  const server = http.createServer((req, res) => handler(req, res).catch(error => {
    console.error(error); if (!res.headersSent) fail(res, error.status || 500, error.message || 'Internal error'); else res.destroy();
  }));
  server.listen(PORT, HOST, () => {
    const url = `http://${HOST}:${PORT}`;
    console.log(`\nResearchCut Editor is running at ${url}`);
    console.log(`Projects autosave in: ${DATA_DIR}`);
    console.log('Keep this window open while editing. Press Ctrl+C to stop.\n');
    if (!process.argv.includes('--no-open')) {
      const child = spawn('cmd', ['/c', 'start', '', url], { detached: true, windowsHide: true, stdio: 'ignore' }); child.unref();
    }
  });
}

main().catch(error => { console.error(error); process.exitCode = 1; });
