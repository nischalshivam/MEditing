'use strict';

const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const { spawn, spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const DATA = process.env.RCE_TEST_MEDIA || 'C:\\Users\\Dell\\Desktop\\Data';
const STORE = path.join(__dirname, '.render-store');
const PORT = 43317;
let child;

function assert(value, message) { if (!value) throw new Error(message); }
async function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
async function start() {
  child = spawn(process.execPath, ['server.js', '--no-open'], { cwd: ROOT, env: { ...process.env, RCE_DATA_DIR: STORE, RCE_PORT: String(PORT) }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  child.stderr.on('data', d => process.stderr.write(d));
  for (let i = 0; i < 100; i++) { try { const r = await fetch(`http://127.0.0.1:${PORT}/api/config`); if (r.ok) return r.json(); } catch {} await sleep(100); }
  throw new Error('Server did not start');
}
async function stop() { if (!child) return; child.kill(); await sleep(300); child = null; }
async function call(route, token, options = {}) {
  const response = await fetch(`http://127.0.0.1:${PORT}${route}`, { ...options, headers: { ...(options.headers || {}), 'x-editor-token': token } });
  const value = await response.json(); if (!response.ok) throw new Error(`${response.status} ${value.message}`); return value;
}
async function upload(projectId, file, kind, token) {
  return call(`/api/projects/${projectId}/assets`, token, { method: 'POST', headers: { 'x-file-name': encodeURIComponent(path.basename(file)), 'x-media-kind': kind, 'content-type': 'application/octet-stream' }, body: await fsp.readFile(file) });
}
async function main() {
  await fsp.mkdir(STORE, { recursive: true }); const cfg = await start(), token = cfg.token;
  const made = await call('/api/projects', token, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name: 'Automated render acceptance' }) });
  const image = (await upload(made.project.id, path.join(DATA, 'image_01.jpg'), 'image', token)).asset;
  const video = (await upload(made.project.id, path.join(DATA, 'clip_01.mp4'), 'video', token)).asset;
  const audio = (await upload(made.project.id, path.join(DATA, 'voiceover.mp3'), 'audio', token)).asset;
  const project = (await call(`/api/projects/${made.project.id}`, token)).project;
  const transform = { x: 0, y: 0, scale: 1, rotation: 0, fit: 'fill', opacity: 1, crop: { top: 0, right: 0, bottom: 0, left: 0 } };
  project.clips = [
    { id: 'test_image', assetId: image.id, trackId: 'V1', start: 0, duration: 2.5, sourceIn: 0, transform, muted: false, volume: 1 },
    { id: 'test_video', assetId: video.id, trackId: 'V1', start: 2.5, duration: 3.5, sourceIn: 0, transform, muted: true, volume: 1 },
    { id: 'test_audio', assetId: audio.id, trackId: 'A1', start: 0, duration: 6, sourceIn: 0, transform, muted: false, volume: 1 }
  ];
  let saved = await call(`/api/projects/${project.id}/save`, token, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ baseRevision: project.revision, project }) });
  const plan = await call(`/api/projects/${project.id}/automation`, token, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ automation: { presetId: 'cinematic_atmosphere_04', seed: 1447, intensity: 'balanced', backgroundMode: 'auto', framedDensity: 1, transitionDensity: 1, transitionsEnabled: true, motionEnabled: true, text: { enabled: false }, export: { resolution: '1080p', quality: 'fast' } } }) });
  assert(plan.automation.plan.shots.length === 2, 'Automation should create one plan shot per main visual');
  assert(plan.automation.plan.presetId === 'cinematic_atmosphere_04', 'The chosen automation recipe should persist');
  assert(plan.automation.plan.shots.some(x => x.layoutId !== 'fullscreen'), 'Acceptance render must exercise a framed background layout');
  assert(plan.automation.plan.shots.some(x => x.transitionId !== 'hard'), 'Acceptance render must exercise an automated transition');
  const queued = await call(`/api/projects/${project.id}/renders`, token, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ preview: true, previewStart: 0, previewDuration: 6, resolution: '1080p', quality: 'fast', startNow: true }) });
  let job;
  for (let i = 0; i < 240; i++) {
    const state = await call('/api/render-queue', token); job = state.queue.jobs.find(x => x.id === queued.job.id);
    if (job && ['complete', 'failed', 'canceled'].includes(job.status)) break;
    await sleep(500);
  }
  assert(job?.status === 'complete', `Preview render should complete: ${job?.error || job?.stage || 'timeout'}`);
  assert(fs.existsSync(job.output), 'Rendered MP4 should exist');
  const probe = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'stream=width,height:format=duration', '-of', 'json', job.output], { encoding: 'utf8', windowsHide: true });
  assert(probe.status === 0, `ffprobe should read output: ${probe.stderr}`); const meta = JSON.parse(probe.stdout);
  assert(meta.streams[0].width === 1280 && meta.streams[0].height === 720, 'Preview should render at exact 16:9 1280x720');
  assert(Number(meta.format.duration) >= 5.8 && Number(meta.format.duration) <= 6.2, 'Preview duration should remain exact');
  console.log(JSON.stringify({ ok: true, project: project.id, job: job.id, output: job.output, width: meta.streams[0].width, height: meta.streams[0].height, duration: Number(meta.format.duration), preset: plan.automation.plan.presetId }, null, 2));
}

main().catch(error => { console.error(error.stack || error); process.exitCode = 1; }).finally(stop);
