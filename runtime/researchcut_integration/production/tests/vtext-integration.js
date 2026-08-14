'use strict';

const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const { spawn, spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const SOURCE = process.env.RCE_AKATSUKI_SOURCE || 'D:\\Anime\\VIDEOS\\Why Did the Akatsuki Wait So Long to Capture the Jinchuriki';
const STORE = path.join(__dirname, '.vtext-store');
const PORT = 43319;
let child;

function assert(value, message) { if (!value) throw new Error(message); }
async function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
async function start() {
  child = spawn(process.execPath, ['server.js', '--no-open'], { cwd: ROOT, env: { ...process.env, RCE_DATA_DIR: STORE, RCE_PORT: String(PORT) }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  child.stderr.on('data', d => process.stderr.write(d));
  for (let i = 0; i < 100; i++) { try { const r = await fetch('http://127.0.0.1:' + PORT + '/api/config'); if (r.ok) return r.json(); } catch {} await sleep(100); }
  throw new Error('Server did not start');
}
async function stop() { if (!child) return; child.kill(); await sleep(300); child = null; }
async function call(route, token, options = {}) {
  const response = await fetch('http://127.0.0.1:' + PORT + route, { ...options, headers: { ...(options.headers || {}), 'x-editor-token': token } });
  const type = response.headers.get('content-type') || ''; const value = type.includes('json') ? await response.json() : await response.text();
  if (!response.ok) throw new Error(response.status + ' ' + (value.message || value)); return value;
}
async function upload(projectId, file, kind, token) {
  return call('/api/projects/' + projectId + '/assets', token, { method: 'POST', headers: { 'x-file-name': encodeURIComponent(path.basename(file)), 'x-media-kind': kind, 'content-type': 'application/octet-stream' }, body: await fsp.readFile(file) });
}
async function main() {
  assert(fs.existsSync(SOURCE), 'Akatsuki test source is missing: ' + SOURCE);
  await fsp.mkdir(STORE, { recursive: true }); const cfg = await start(), token = cfg.token;
  const made = await call('/api/projects', token, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name: 'Integrated one-file VText acceptance' }) });
  const projectId = made.project.id;
  const imageFile = path.join(SOURCE, 'DATA', 'scene_004', 'image_01.jpg');
  const audioFile = path.join(SOURCE, 'Audio.mp3');
  const instructionFile = path.join(__dirname, 'fixtures', 'vtext-akatsuki-first-3.txt');
  const image = (await upload(projectId, imageFile, 'image', token)).asset;
  const audio = (await upload(projectId, audioFile, 'audio', token)).asset;
  const project = (await call('/api/projects/' + projectId, token)).project;
  const transform = { x: 0, y: 0, scale: 1, rotation: 0, fit: 'fill', opacity: 1, crop: { top: 0, right: 0, bottom: 0, left: 0 } };
  project.clips = [
    { id: 'akatsuki_visual', assetId: image.id, trackId: 'V1', start: 0, duration: 12, sourceIn: 0, transform, muted: true, volume: 1 },
    { id: 'akatsuki_voice', assetId: audio.id, trackId: 'A1', start: 0, duration: 12, sourceIn: 0, transform, muted: false, volume: 1 }
  ];
  await call('/api/projects/' + projectId + '/save', token, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ baseRevision: project.revision, project }) });
  const instructionText = await fsp.readFile(instructionFile, 'utf8');
  const uploaded = await call('/api/projects/' + projectId + '/automation/text', token, { method: 'POST', headers: { 'x-file-name': encodeURIComponent(path.basename(instructionFile)), 'x-text-kind': 'instruction', 'content-type': 'text/plain' }, body: instructionText });
  assert(uploaded.text.eventCount === 3, 'Integrated upload should parse all three VText events');
  const automated = await call('/api/projects/' + projectId + '/automation', token, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ automation: { presetId: 'bold_explainer_04', seed: 77, backgroundMode: 'blur', transitionsEnabled: true, motionEnabled: true, text: { enabled: true, energy: 3, scale: 'auto', density: 'file' }, export: { resolution: '1080p', quality: 'fast' } } }) });
  assert(automated.automation.text.instructionFile && !automated.automation.text.scriptFile, 'One-file mode must preserve instructions without requiring a clean script');
  const queued = await call('/api/projects/' + projectId + '/renders', token, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ preview: true, previewStart: 0, previewDuration: 12, resolution: '1080p', quality: 'fast', startNow: true }) });
  let job;
  for (let i = 0; i < 600; i++) {
    const state = await call('/api/render-queue', token); job = state.queue.jobs.find(x => x.id === queued.job.id);
    if (job && ['complete', 'failed', 'canceled'].includes(job.status)) break;
    await sleep(500);
  }
  assert(job && job.status === 'complete', 'Integrated VText render should complete: ' + ((job && (job.error || job.stage)) || 'timeout'));
  assert(fs.existsSync(job.output), 'Integrated VText MP4 should exist');
  const reportPath = job.output.replace(/\.mp4$/i, '.report.json');
  assert(fs.existsSync(reportPath), 'VText should write its timing/quality report beside the MP4');
  const report = JSON.parse(await fsp.readFile(reportPath, 'utf8'));
  assert(report.events_total === 3 && report.events_rendered === 3, 'All three supplied VText events should render');
  assert(report.script_audio_match >= .75, 'The supplied narration cues should match the Akatsuki voiceover');
  const probe = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'stream=width,height:format=duration', '-of', 'json', job.output], { encoding: 'utf8', windowsHide: true });
  assert(probe.status === 0, 'ffprobe should read integrated output: ' + probe.stderr); const meta = JSON.parse(probe.stdout);
  assert(meta.streams[0].width === 1280 && meta.streams[0].height === 720, 'Integrated VText preview should stay exact 16:9');
  console.log(JSON.stringify({ ok: true, project: projectId, job: job.id, output: job.output, eventsRendered: report.events_rendered, audioMatch: report.script_audio_match, duration: Number(meta.format.duration), oneFileMode: true }, null, 2));
}

main().catch(error => { console.error(error.stack || error); process.exitCode = 1; }).finally(stop);
