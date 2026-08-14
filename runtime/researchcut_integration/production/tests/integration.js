'use strict';

const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const { spawn } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const DATA = process.env.RCE_TEST_MEDIA || 'C:\\Users\\Dell\\Desktop\\Data';
const STORE = path.join(__dirname, '.integration-store');
const PORT = 43291;
let child;

function assert(value, message) { if (!value) throw new Error(message); }
async function start() {
  child = spawn(process.execPath, ['server.js', '--no-open'], { cwd: ROOT, env: { ...process.env, RCE_DATA_DIR: STORE, RCE_PORT: String(PORT) }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  child.stderr.on('data', d => process.stderr.write(d));
  for (let i = 0; i < 80; i++) { try { const r = await fetch(`http://127.0.0.1:${PORT}/api/config`); if (r.ok) return r.json(); } catch {} await new Promise(r => setTimeout(r, 100)); }
  throw new Error('Server did not start');
}
async function stop() { if (!child) return; child.kill(); await new Promise(r => setTimeout(r, 250)); child = null; }
async function call(route, token, options = {}) {
  const response = await fetch(`http://127.0.0.1:${PORT}${route}`, { ...options, headers: { ...(options.headers || {}), 'x-editor-token': token } });
  const value = await response.json(); if (!response.ok) throw new Error(`${response.status} ${value.message}`); return value;
}
async function upload(projectId, file, kind, token) {
  const body = await fsp.readFile(file);
  return call(`/api/projects/${projectId}/assets`, token, { method: 'POST', headers: { 'x-file-name': encodeURIComponent(path.basename(file)), 'x-media-kind': kind, 'content-type': 'application/octet-stream' }, body });
}
async function main() {
  await fsp.mkdir(STORE, { recursive: true });
  let cfg = await start(); const token = cfg.token;
  assert(cfg.version === '2.1.0', 'Server should report the 2.1.0 editor build');
  const catalog = await call('/api/automation/catalog', token);
  assert(catalog.presets.length >= 50, 'Automation catalog should expose at least 50 presets');
  const made = await call('/api/projects', token, { method: 'POST', body: JSON.stringify({ name: 'Real media acceptance' }), headers: { 'content-type': 'application/json' } });
  const p = made.project;
  const image = (await upload(p.id, path.join(DATA, 'image_01.jpg'), 'image', token)).asset;
  let result = await upload(p.id, path.join(DATA, 'clip_01.mp4'), 'video', token); const video = result.asset;
  result = await upload(p.id, path.join(DATA, 'voiceover.mp3'), 'audio', token); const audio = result.asset;
  const loaded = (await call(`/api/projects/${p.id}`, token)).project;
  assert(loaded.assets.length === 3, 'Three real media assets should persist');
  assert(video.duration > 0 && audio.duration > 60, 'FFprobe metadata should be present');
  loaded.name = 'Renamed and autosaved';
  loaded.tracks.unshift({ id: 'V4', kind: 'video', name: 'Overlay 3', muted: false, locked: false, magnetic: false });
  loaded.tracks.push({ id: 'A3', kind: 'audio', name: 'Audio 3', muted: false, locked: false, magnetic: false });
  loaded.clips = [
    { id: 'c_main_image', assetId: image.id, trackId: 'V1', start: 0, duration: 5, sourceIn: 0, transform: { x: 0, y: 0, scale: 1, rotation: 0, fit: 'fill', opacity: 1 }, muted: false, volume: 1 },
    { id: 'c_main_video', assetId: video.id, trackId: 'V1', start: 5, duration: Math.min(5, video.duration), sourceIn: 0, transform: { x: 0, y: 0, scale: 1, rotation: 0, fit: 'fill', opacity: 1 }, muted: false, volume: 1 },
    { id: 'c_overlay', assetId: image.id, trackId: 'V2', start: 2, duration: 3, sourceIn: 0, transform: { x: 20, y: -10, scale: .42, rotation: 0, fit: 'fit', opacity: 1, crop: { top: 3, right: 7, bottom: 4, left: 6 } }, muted: false, volume: 1 },
    { id: 'c_voice', assetId: audio.id, trackId: 'A1', start: 0, duration: audio.duration, sourceIn: 0, transform: { x: 0, y: 0, scale: 1, rotation: 0, fit: 'fill', opacity: 1 }, muted: false, volume: 1 },
    { id: 'c_sfx', assetId: audio.id, trackId: 'A2', start: 10, duration: 2, sourceIn: 4, transform: { x: 0, y: 0, scale: 1, rotation: 0, fit: 'fill', opacity: 1 }, muted: false, volume: .35 },
    { id: 'c_extra_visual', assetId: image.id, trackId: 'V4', start: 12, duration: 2, sourceIn: 0, transform: { x: -15, y: 10, scale: .35, rotation: 0, fit: 'fit', opacity: .9 }, muted: false, volume: 1 },
    { id: 'c_extra_audio', assetId: audio.id, trackId: 'A3', start: 13, duration: 1, sourceIn: 8, transform: { x: 0, y: 0, scale: 1, rotation: 0, fit: 'fill', opacity: 1 }, muted: false, volume: .2 }
  ];
  const saved = await call(`/api/projects/${p.id}/save`, token, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ baseRevision: loaded.revision, project: loaded }) });
  assert(saved.revision > loaded.revision, 'Autosave revision should advance');
  const handoff = await call(`/api/projects/${p.id}/handoff`, token, { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' });
  assert(handoff.ready && handoff.payload.clips.length === 7, 'Automation handoff should include scalable visual/audio layers');
  assert(handoff.payload.schema === 'researchcut-handoff-v3', 'Automation handoff should use schema v3');
  assert(handoff.payload.clips.find(c => c.id === 'c_overlay').transform.crop.left === 6, 'Manual crop should persist in handoff');
  assert(fs.existsSync(handoff.file), 'Handoff file should exist on disk');
  await stop(); cfg = await start();
  const projects = await call('/api/projects', cfg.token); const restored = projects.projects.find(x => x.id === p.id);
  assert(restored && restored.name === 'Renamed and autosaved', 'Project should reopen after server restart');
  const final = (await call(`/api/projects/${p.id}`, cfg.token)).project;
  assert(final.tracks.length === 7 && final.clips.some(c => c.trackId === 'V4') && final.clips.some(c => c.trackId === 'A3'), 'Added visual/audio layers should survive restart');
  console.log(JSON.stringify({ ok: true, project: final.id, assets: final.assets.length, clips: final.clips.length, audioDuration: audio.duration, handoff: handoff.file }, null, 2));
}
main().catch(error => { console.error(error.stack || error); process.exitCode = 1; }).finally(stop);
