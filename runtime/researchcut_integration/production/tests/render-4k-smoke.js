'use strict';

const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const { spawnSync } = require('child_process');
const { renderProject, scanBackgrounds } = require('../renderer');

const ROOT = path.resolve(__dirname, '..');
const DATA = process.env.RCE_TEST_MEDIA || 'C:\\Users\\Dell\\Desktop\\Data';
const PROJECT_DIR = path.join(__dirname, '.4k-store', 'projects', 'p_4k_acceptance');

function assert(value, message) { if (!value) throw new Error(message); }
async function main() {
  const assetDir = path.join(PROJECT_DIR, 'assets'); await fsp.mkdir(assetDir, { recursive: true });
  const source = path.join(DATA, 'image_01.jpg'), storedName = 'a_4k_image.jpg'; await fsp.copyFile(source, path.join(assetDir, storedName));
  const project = {
    id: 'p_4k_acceptance', name: '4K smoke acceptance', settings: { width: 1920, height: 1080, fps: 30 },
    tracks: [{ id: 'V1', name: 'Main video', muted: true, locked: false, magnetic: true }],
    assets: [{ id: 'a_4k_image', name: 'image_01.jpg', storedName, kind: 'image', width: 3840, height: 2160, duration: 0, hasAudio: false }],
    clips: [{ id: 'c_4k_image', assetId: 'a_4k_image', trackId: 'V1', start: 0, duration: 1, sourceIn: 0, transform: { x: 0, y: 0, scale: 1, rotation: 0, fit: 'fill', opacity: 1, crop: { top: 0, right: 0, bottom: 0, left: 0 } }, muted: true, volume: 1 }],
    automation: { text: { enabled: false } }
  };
  const backgrounds = await scanBackgrounds();
  const plan = { presetId: '4k-smoke', seed: 1, settings: { solidColor: '#0b1011', text: { enabled: false } }, shots: [{ clipId: 'c_4k_image', index: 0, start: 0, duration: 1, trackId: 'V1', layoutId: 'frame82', motionId: 'zoom_in', transitionId: 'hard', transitionDuration: .25, backgroundMode: 'builtin', backgroundId: backgrounds[0].id, accent: '#18c9b8', energy: .7 }] };
  const manifest = await renderProject({ project, projectDir: PROJECT_DIR, jobId: 'r_4k_smoke', plan, resolution: '4k', quality: 'fast', preview: false });
  assert(fs.existsSync(manifest.output), '4K renderer output should exist');
  const probe = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'stream=width,height:format=duration', '-of', 'json', manifest.output], { encoding: 'utf8', windowsHide: true });
  assert(probe.status === 0, 'ffprobe should read 4K output: ' + probe.stderr); const meta = JSON.parse(probe.stdout);
  assert(meta.streams[0].width === 3840 && meta.streams[0].height === 2160, 'Full export must be exact 3840x2160 UHD');
  assert(Number(meta.format.duration) >= .95 && Number(meta.format.duration) <= 1.05, '4K smoke duration must remain exact');
  console.log(JSON.stringify({ ok: true, width: meta.streams[0].width, height: meta.streams[0].height, duration: Number(meta.format.duration), output: manifest.output }, null, 2));
}

main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
