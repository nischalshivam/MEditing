'use strict';

const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const { spawn } = require('child_process');

const APP_DIR = __dirname;
const BUILTIN_BG_DIR = path.join(APP_DIR, 'backgrounds');
const VTEXT_DIR = path.join(APP_DIR, 'tools', 'vtext');

const VIDEO_EXT = new Set(['.mp4', '.mov', '.mkv', '.webm', '.m4v']);
const IMAGE_EXT = new Set(['.jpg', '.jpeg', '.png', '.webp', '.bmp']);
function trackZ(id) { return id?.startsWith('V') ? Number(id.slice(1)) || 0 : 0; }

function clamp(v, lo, hi) { v = Number(v); return Number.isFinite(v) ? Math.max(lo, Math.min(hi, v)) : lo; }
function ff(value) { return Number(value).toFixed(4).replace(/0+$/, '').replace(/\.$/, ''); }
function safeFile(value) { return String(value || 'render').replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').trim().slice(0, 120) || 'render'; }
function escConcat(p) { return String(p).replace(/'/g, "'\\''").replace(/\\/g, '/'); }
function assetPath(projectDir, asset) { return asset.externalPath || path.join(projectDir, 'assets', asset.storedName); }
function durationOf(project) { return Math.max(0, ...project.clips.map(c => c.start + c.duration)); }

async function scanBackgrounds() {
  const out = [];
  for (const folder of ['Images', 'Videos']) {
    const dir = path.join(BUILTIN_BG_DIR, folder); let names = [];
    try { names = await fsp.readdir(dir); } catch {}
    for (const name of names.sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))) {
      const ext = path.extname(name).toLowerCase(); const kind = IMAGE_EXT.has(ext) ? 'image' : VIDEO_EXT.has(ext) ? 'video' : null;
      if (!kind) continue;
      out.push({ id: `builtin:${folder}:${name}`, kind, name: `${folder.slice(0, -1)} ${path.basename(name, ext)}`, file: path.join(dir, name), folder, storedName: name });
    }
  }
  return out;
}

function resolveBackground(project, projectDir, planShot, backgrounds) {
  if (planShot.backgroundMode === 'project' && planShot.backgroundId) {
    const a = project.assets.find(x => x.id === planShot.backgroundId && x.kind !== 'audio');
    if (a) return { kind: a.kind, file: assetPath(projectDir, a), id: a.id };
  }
  if ((planShot.backgroundMode === 'builtin' || planShot.backgroundMode === 'auto') && planShot.backgroundId) {
    const bg = backgrounds.find(x => x.id === planShot.backgroundId); if (bg) return bg;
  }
  return null;
}

function addMediaInput(args, asset, file, sourceIn, duration, fps, loopVideo = false) {
  if (asset.kind === 'image') args.push('-loop', '1', '-framerate', String(fps), '-t', ff(duration), '-i', file);
  else {
    if (loopVideo) args.push('-stream_loop', '-1');
    if (!loopVideo && sourceIn > 0) args.push('-ss', ff(sourceIn));
    args.push('-t', ff(duration), '-i', file);
  }
}

function cropFilter(c) {
  const p = c.transform?.crop || {}; const l = clamp(p.left, 0, 45), r = clamp(p.right, 0, 45), t = clamp(p.top, 0, 45), b = clamp(p.bottom, 0, 45);
  if (l + r < .01 && t + b < .01) return '';
  return `crop=iw*${ff(1 - (l + r) / 100)}:ih*${ff(1 - (t + b) / 100)}:iw*${ff(l / 100)}:ih*${ff(t / 100)},`;
}

function normalizeFilter(c, W, H, fps, duration, labelIn, labelOut, transparent = false) {
  const fit = c.transform?.fit === 'fit'; const color = transparent ? 'black@0' : 'black';
  const size = fit
    ? `scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=${color}`
    : `scale=${W}:${H}:force_original_aspect_ratio=increase,crop=${W}:${H}`;
  return `[${labelIn}]trim=duration=${ff(duration)},setpts=PTS-STARTPTS,fps=${fps},${cropFilter(c)}${size},setsar=1[${labelOut}]`;
}

function motionFilter(motion, W, H, fps, duration, energy, input, output) {
  if (!motion || motion === 'none') return `[${input}]null[${output}]`;
  const frames = Math.max(2, Math.round(duration * fps)), den = Math.max(1, frames - 1), e = clamp(energy, .3, 1.8);
  let z0 = 1, z1 = 1, x0 = .5, x1 = .5, y0 = .5, y1 = .5;
  if (motion === 'zoom_in') z1 = 1 + .09 * e;
  if (motion === 'zoom_out') { z0 = 1 + .09 * e; z1 = 1; }
  if (motion === 'push_in') z1 = 1 + .16 * e;
  if (motion === 'pan_left') { z0 = z1 = 1.08; x0 = 1; x1 = 0; }
  if (motion === 'pan_right') { z0 = z1 = 1.08; x0 = 0; x1 = 1; }
  if (motion === 'drift') { z0 = 1.04; z1 = 1.1; x0 = .15; x1 = .85; y0 = .35; y1 = .65; }
  const p = `min(on/${den}\\,1)`, z = `${ff(z0)}+(${ff(z1 - z0)})*${p}`;
  const x = `(iw-iw/zoom)*(${ff(x0)}+(${ff(x1 - x0)})*${p})`, y = `(ih-ih/zoom)*(${ff(y0)}+(${ff(y1 - y0)})*${p})`;
  return `[${input}]scale=${Math.round(W * 1.18 / 2) * 2}:-2,zoompan=z='${z}':x='${x}':y='${y}':d=1:s=${W}x${H}:fps=${fps}[${output}]`;
}

function transitionFilters(input, output, transitionIn, transitionOut, d, duration) {
  const filters = []; const add = (name, side) => {
    if (!name || name === 'hard') return;
    const head = side === 'in', start = head ? 0 : Math.max(0, duration - d);
    if (name === 'blur') filters.push(`gblur=sigma=8:enable='between(t,${ff(start)},${ff(head ? d : duration)})'`);
    else {
      const color = name === 'dip_white' || name === 'flash' ? 'white' : name === 'dip_warm' ? '0x160c04' : 'black';
      const scale = name === 'flash' ? .28 : name === 'soft_cut' ? .5 : 1;
      const dd = Math.max(.04, d * scale), st = head ? 0 : Math.max(0, duration - dd);
      filters.push(`fade=t=${head ? 'in' : 'out'}:st=${ff(st)}:d=${ff(dd)}:color=${color}`);
    }
  };
  add(transitionIn, 'in'); add(transitionOut, 'out');
  return filters.length ? `[${input}]${filters.join(',')}[${output}]` : `[${input}]null[${output}]`;
}

function frameGeometry(layout, W, H) {
  let scale = .88, xRatio = .5, yRatio = .5;
  if (layout === 'hero_center') scale = .84;
  if (layout === 'frame82') scale = .8;
  if (layout === 'frame74') scale = .72;
  if (layout === 'screen_left') { scale = .72; xRatio = .06; }
  if (layout === 'screen_right') { scale = .72; xRatio = .94; }
  if (layout === 'focus_left') { scale = .64; xRatio = .06; }
  if (layout === 'focus_right') { scale = .64; xRatio = .94; }
  if (layout === 'card_left') { scale = .68; xRatio = .12; yRatio = .48; }
  if (layout === 'card_right') { scale = .68; xRatio = .88; yRatio = .52; }
  if (layout === 'float_top_left') { scale = .52; xRatio = .055; yRatio = .29; }
  if (layout === 'float_top_right') { scale = .52; xRatio = .945; yRatio = .29; }
  if (layout === 'float_bottom_left') { scale = .52; xRatio = .055; yRatio = .71; }
  if (layout === 'float_bottom_right') { scale = .52; xRatio = .945; yRatio = .71; }
  const fw = Math.round(W * scale / 2) * 2, fh = Math.round(fw * 9 / 16 / 2) * 2;
  const x = xRatio <= .2 ? Math.round(W * xRatio) : xRatio >= .8 ? Math.round(W * xRatio - fw) : Math.round((W - fw) / 2);
  const y = Math.max(0, Math.round(H * yRatio - fh / 2)); return { fw, fh: Math.min(H - 30, fh), x, y };
}

function premiumFrameFilters(input, output, geo, shot, W, H, duration) {
  const style = shot.edgeStyle || 'clean', accent = String(shot.accent || '#18c9b8').replace('#', '0x');
  const specs = {
    clean: { pad: 5, color: accent, radius: 15 }, soft_glass: { pad: 13, color: 'white@0.34', radius: 28 },
    neon: { pad: 15, color: `${accent}@0.30`, radius: 22 }, double_line: { pad: 13, color: '0x07100f', radius: 18 },
    cinema: { pad: 18, color: '0x050706', radius: 13 }, paper: { pad: 19, color: '0xeee8dc', radius: 8 },
    shadow: { pad: 8, color: 'white@0.88', radius: 25 }
  };
  const spec = specs[style] || specs.clean, pw = geo.fw + spec.pad * 2, ph = geo.fh + spec.pad * 2;
  const pieces = [`[${input}]scale=${geo.fw}:${geo.fh}:force_original_aspect_ratio=increase,crop=${geo.fw}:${geo.fh},pad=${pw}:${ph}:${spec.pad}:${spec.pad}:color=${spec.color},format=rgba`];
  if (style === 'neon') pieces[0] += `,drawbox=x=5:y=5:w=iw-10:h=ih-10:color=${accent}:t=3`;
  if (style === 'double_line') pieces[0] += `,drawbox=x=2:y=2:w=iw-4:h=ih-4:color=${accent}:t=3,drawbox=x=8:y=8:w=iw-16:h=ih-16:color=white@0.72:t=2`;
  if (style === 'cinema') pieces[0] += `,drawbox=x=5:y=5:w=iw-10:h=ih-10:color=${accent}@0.75:t=2,drawbox=x=0:y=0:w=iw:h=10:color=black:t=fill,drawbox=x=0:y=ih-10:w=iw:h=10:color=black:t=fill`;
  if (style === 'paper') pieces[0] += ',rotate=-0.012:c=black@0:ow=rotw(iw):oh=roth(ih)';
  const radius = Math.min(spec.radius, Math.floor(Math.min(pw, ph) / 5));
  pieces[0] += `,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(gt(abs(W/2-X),W/2-${radius})*gt(abs(H/2-Y),H/2-${radius}),if(lte(hypot(${radius}-(W/2-abs(W/2-X)),${radius}-(H/2-abs(H/2-Y))),${radius}),255,0),255)'`;
  if (shot.entranceId === 'scale_pop') pieces[0] += `,fade=t=in:st=0:d=${ff(Math.min(.28, duration / 3))}:alpha=1`;
  pieces[0] += `[${output}]`;
  return { filters: pieces, pad: spec.pad, width: pw, height: ph };
}

function entranceOverlay(entrance, x, y, W, H) {
  const d = .52, ease = `sin(min(t/${d}\,1)*PI/2)`; let ex = String(x), ey = String(y);
  if (entrance === 'slide_left') ex = `-w+(${x}+w)*${ease}`;
  if (entrance === 'slide_right') ex = `${W}-(${W}-${x})*${ease}`;
  if (entrance === 'slide_up') ey = `-h+(${y}+h)*${ease}`;
  if (entrance === 'slide_down') ey = `${H}-(${H}-${y})*${ease}`;
  return { x: ex, y: ey };
}

function makeSlices(project, plan, startAt = 0, maxDuration = null) {
  const total = durationOf(project), endAt = maxDuration == null ? total : Math.min(total, startAt + maxDuration);
  const cuts = new Set([startAt, endAt]);
  for (const c of project.clips.filter(c => c.trackId.startsWith('V'))) {
    if (c.start > startAt && c.start < endAt) cuts.add(c.start);
    const end = c.start + c.duration; if (end > startAt && end < endAt) cuts.add(end);
  }
  const points = [...cuts].sort((a, b) => a - b), slices = [];
  for (let i = 0; i < points.length - 1; i++) {
    const start = points[i], end = points[i + 1]; if (end - start < .02) continue; const mid = start + (end - start) / 2;
    const active = project.clips.filter(c => c.trackId.startsWith('V') && mid >= c.start && mid < c.start + c.duration).sort((a, b) => trackZ(a.trackId) - trackZ(b.trackId));
    slices.push({ index: slices.length, start, end, duration: end - start, active, primary: active[0] || null });
  }
  const shotMap = new Map((plan.shots || []).map(s => [s.clipId, s]));
  for (let i = 0; i < slices.length; i++) {
    const current = slices[i], next = slices[i + 1], shot = current.primary ? shotMap.get(current.primary.id) : null;
    const changed = next && current.primary?.id !== next.primary?.id;
    current.transitionOut = changed && shot ? shot.transitionId : 'hard';
    current.transitionIn = i > 0 ? slices[i - 1].transitionOut : 'hard';
  }
  return { slices, startAt, endAt, duration: endAt - startAt, total };
}

async function runProcess(bin, args, options = {}) {
  await fsp.mkdir(options.cwd || APP_DIR, { recursive: true });
  return new Promise((resolve, reject) => {
    const child = spawn(bin, args, { cwd: options.cwd || APP_DIR, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let output = '', error = '', canceled = false;
    const collect = (chunk, isErr) => {
      const text = chunk.toString(); if (isErr) error = (error + text).slice(-30000); else output = (output + text).slice(-30000);
      options.onData?.(text, isErr);
    };
    child.stdout.on('data', d => collect(d, false)); child.stderr.on('data', d => collect(d, true));
    const timer = setInterval(() => { if (options.shouldCancel?.()) { canceled = true; child.kill(); } }, 400);
    child.on('error', err => { clearInterval(timer); reject(err); });
    child.on('close', code => { clearInterval(timer); if (canceled) return reject(Object.assign(new Error('Render canceled'), { canceled: true })); if (code !== 0) return reject(new Error(`${path.basename(bin)} exited ${code}: ${error.slice(-1500)}`)); resolve({ output, error }); });
  });
}

async function renderSlice({ project, projectDir, slice, plan, output, W, H, fps, quality, backgrounds, shouldCancel }) {
  const args = ['-hide_banner', '-loglevel', 'error', '-y']; const filters = []; const shotMap = new Map((plan.shots || []).map(s => [s.clipId, s]));
  if (!slice.primary) {
    args.push('-f', 'lavfi', '-i', `color=c=0x050808:s=${W}x${H}:r=${fps}:d=${ff(slice.duration)}`);
    filters.push(`[0:v]format=yuv420p[outv]`);
  } else {
    const primary = slice.primary, asset = project.assets.find(a => a.id === primary.assetId), file = assetPath(projectDir, asset), sourceIn = primary.sourceIn + Math.max(0, slice.start - primary.start);
    addMediaInput(args, asset, file, sourceIn, slice.duration, fps); let inputCount = 1;
    const shot = shotMap.get(primary.id) || { layoutId: 'fullscreen', motionId: 'none', backgroundMode: 'none', transitionDuration: .3, accent: '#18c9b8', energy: 1 };
    filters.push(normalizeFilter(primary, W, H, fps, slice.duration, '0:v', 'base0'));
    filters.push(motionFilter(shot.motionId, W, H, fps, slice.duration, shot.energy, 'base0', 'base1'));
    filters.push(transitionFilters('base1', 'base2', slice.transitionIn, slice.transitionOut, shot.transitionDuration || .3, slice.duration));
    let current = 'base2';
    if (shot.layoutId !== 'fullscreen') {
      const geo = frameGeometry(shot.layoutId, W, H), bg = resolveBackground(project, projectDir, shot, backgrounds); let bgLabel = 'bg0';
      if (bg) {
        const bgAsset = { kind: bg.kind }; addMediaInput(args, bgAsset, bg.file, 0, slice.duration, fps, bg.kind === 'video'); const bgInput = inputCount++;
        filters.push(`[${bgInput}:v]trim=duration=${ff(slice.duration)},setpts=PTS-STARTPTS,fps=${fps},scale=${W}:${H}:force_original_aspect_ratio=increase,crop=${W}:${H},setsar=1[${bgLabel}]`);
      } else if (shot.backgroundMode === 'solid' || shot.backgroundMode === 'none') {
        filters.push(`color=c=${shot.backgroundMode === 'solid' ? (plan.settings?.solidColor || '#0b1011').replace('#', '0x') : '0x050808'}:s=${W}x${H}:r=${fps}:d=${ff(slice.duration)}[${bgLabel}]`);
      } else {
        filters.push(`[${current}]split[blurcopy][framecopy]`); filters.push(`[blurcopy]gblur=sigma=28,eq=brightness=-0.08[${bgLabel}]`); current = 'framecopy';
      }
      const framed = premiumFrameFilters(current, 'frame', geo, shot, W, H, slice.duration); filters.push(...framed.filters);
      const frameX = geo.x - framed.pad, frameY = geo.y - framed.pad, shadowX = frameX + Math.round(W * .012), shadowY = frameY + Math.round(H * .018);
      filters.push(`[${bgLabel}]drawbox=x=${shadowX}:y=${shadowY}:w=${framed.width}:h=${framed.height}:color=black@0.52:t=fill[bgshadow]`);
      const entry = entranceOverlay(shot.entranceId, frameX, frameY, W, H);
      filters.push(`[bgshadow][frame]overlay=x='${entry.x}':y='${entry.y}':shortest=1[layout]`); current = 'layout';
    }
    const overlays = slice.active.slice(1);
    for (let i = 0; i < overlays.length; i++) {
      const c = overlays[i], a = project.assets.find(x => x.id === c.assetId); if (!a) continue; const file2 = assetPath(projectDir, a), offset = c.sourceIn + Math.max(0, slice.start - c.start);
      addMediaInput(args, a, file2, offset, slice.duration, fps); const idx = inputCount++;
      const scale = clamp(c.transform?.scale, .05, 4), ow = Math.max(8, Math.round(W * scale / 2) * 2), oh = Math.max(8, Math.round(H * scale / 2) * 2);
      const x = Math.round((W - ow) / 2 + clamp(c.transform?.x, -200, 200) / 100 * W), y = Math.round((H - oh) / 2 + clamp(c.transform?.y, -200, 200) / 100 * H);
      const fit = c.transform?.fit === 'fit', sizing = fit ? `scale=${ow}:${oh}:force_original_aspect_ratio=decrease,pad=${ow}:${oh}:(ow-iw)/2:(oh-ih)/2:color=black@0` : `scale=${ow}:${oh}:force_original_aspect_ratio=increase,crop=${ow}:${oh}`;
      filters.push(`[${idx}:v]trim=duration=${ff(slice.duration)},setpts=PTS-STARTPTS,fps=${fps},${cropFilter(c)}${sizing},format=rgba,colorchannelmixer=aa=${ff(clamp(c.transform?.opacity, 0, 1))}[ov${i}]`);
      filters.push(`[${current}][ov${i}]overlay=x=${x}:y=${y}:shortest=1[lay${i}]`); current = `lay${i}`;
    }
    filters.push(`[${current}]format=yuv420p[outv]`);
  }
  const preset = quality === 'fast' ? 'veryfast' : quality === 'quality' ? 'slow' : 'medium', crf = quality === 'quality' ? '17' : quality === 'fast' ? '22' : '19';
  args.push('-filter_complex', filters.join(';'), '-map', '[outv]', '-an', '-r', String(fps), '-c:v', 'libx264', '-preset', preset, '-crf', crf, '-pix_fmt', 'yuv420p', '-movflags', '+faststart', output);
  await runProcess('ffmpeg', args, { shouldCancel });
}

async function concatSegments(files, output, workDir, shouldCancel) {
  const list = path.join(workDir, 'concat.txt'); await fsp.writeFile(list, files.map(f => `file '${escConcat(f)}'`).join('\n'), 'utf8');
  await runProcess('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', list, '-c', 'copy', '-movflags', '+faststart', output], { shouldCancel });
}

async function muxAudio(project, projectDir, video, output, renderDuration, renderStart, shouldCancel) {
  const args = ['-hide_banner', '-loglevel', 'error', '-y', '-i', video], filters = [], labels = []; let idx = 1;
  const tracks = new Map(project.tracks.map(t => [t.id, t]));
  const audioClips = project.clips.filter(c => {
    const a = project.assets.find(x => x.id === c.assetId), tr = tracks.get(c.trackId); if (!a || tr?.muted || c.muted) return false;
    return c.trackId.startsWith('A') ? a.kind === 'audio' || a.hasAudio : c.trackId.startsWith('V') && a.kind === 'video' && a.hasAudio;
  });
  const renderEnd = renderStart + renderDuration;
  for (const c of audioClips) {
    const clipStart = Math.max(c.start, renderStart), clipEnd = Math.min(c.start + c.duration, renderEnd); if (clipEnd - clipStart < .02) continue;
    const a = project.assets.find(x => x.id === c.assetId), file = assetPath(projectDir, a), sourceIn = c.sourceIn + (clipStart - c.start), localStart = clipStart - renderStart, dur = clipEnd - clipStart;
    args.push('-i', file); const label = `a${idx}`; labels.push(`[${label}]`);
    filters.push(`[${idx}:a]atrim=start=${ff(sourceIn)}:duration=${ff(dur)},asetpts=PTS-STARTPTS,volume=${ff(clamp(c.volume, 0, 2))},adelay=${Math.round(localStart * 1000)}:all=1[${label}]`); idx++;
  }
  if (!labels.length) { await fsp.copyFile(video, output); return; }
  filters.push(`${labels.join('')}amix=inputs=${labels.length}:duration=longest:dropout_transition=0,alimiter=limit=0.95[aout]`);
  args.push('-filter_complex', filters.join(';'), '-map', '0:v:0', '-map', '[aout]', '-t', ff(renderDuration), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart', output);
  await runProcess('ffmpeg', args, { shouldCancel });
}

function deriveScript(instructionText) {
  const cues = []; const rx = /^\s*NARRATION_CUE\s*:\s*(.+?)\s*$/gmi; let match;
  while ((match = rx.exec(instructionText))) cues.push(match[1].replace(/^"|"$/g, '').trim());
  return cues.join('\n');
}

async function applyVText({ projectDir, automation, input, output, workDir, onProgress, shouldCancel }) {
  const instruction = automation.text?.instructionFile ? path.join(projectDir, 'automation', automation.text.instructionFile) : null;
  if (!instruction || !fs.existsSync(instruction)) throw new Error('Text is enabled but the VText instruction .txt file is missing.');
  let script = automation.text?.scriptFile ? path.join(projectDir, 'automation', automation.text.scriptFile) : null;
  if (!script || !fs.existsSync(script)) {
    const text = await fsp.readFile(instruction, 'utf8'), derived = deriveScript(text); if (!derived) throw new Error('No NARRATION_CUE lines found in the VText instruction file.');
    script = path.join(workDir, 'derived-narration-cues.txt'); await fsp.writeFile(script, derived, 'utf8');
  }
  const python = process.env.RCE_PYTHON || 'python', args = [path.join(VTEXT_DIR, 'vtext.py'), '--video', input, '--script', script, '--instructions', instruction, '--out', output,
    '--energy', String(automation.text.energy || 3), '--text-scale', automation.text.scale || 'auto', '--density', automation.text.density || 'file', '--crf', '18', '--preset', 'medium'];
  if (automation.text.niche && automation.text.niche !== 'auto') args.push('--niche', automation.text.niche);
  if (automation.text.pack && automation.text.pack !== 'auto') args.push('--pack', automation.text.pack);
  if (/^#[0-9a-f]{6}$/i.test(automation.text.accent || '')) args.push('--accent', automation.text.accent);
  await runProcess(python, args, { cwd: VTEXT_DIR, shouldCancel, onData: text => { const matches = [...text.matchAll(/([0-9]{1,3}(?:\.[0-9]+)?)%/g)]; if (matches.length) onProgress?.(.76 + Math.min(1, Number(matches.at(-1)[1]) / 100) * .23, 'Applying narration-synced text'); } });
}

async function renderProject(options) {
  const { project, projectDir, jobId, plan, resolution = '1080p', quality = 'balanced', preview = false, previewStart = 0, previewDuration = 12, onProgress = () => {}, shouldCancel = () => false } = options;
  const W = preview ? 1280 : resolution === '4k' ? 3840 : 1920, H = Math.round(W * 9 / 16), fps = 30;
  const renderDir = path.join(projectDir, 'renders', jobId), workDir = path.join(renderDir, 'work'); await fsp.mkdir(workDir, { recursive: true });
  const backgrounds = await scanBackgrounds(), timeline = makeSlices(project, plan, preview ? previewStart : 0, preview ? previewDuration : null);
  if (!timeline.slices.length) throw new Error('No visual timeline content is available to render.');
  const files = [];
  for (let i = 0; i < timeline.slices.length; i++) {
    if (shouldCancel()) throw Object.assign(new Error('Render canceled'), { canceled: true });
    const output = path.join(workDir, `segment-${String(i).padStart(5, '0')}.mp4`); files.push(output);
    if (!fs.existsSync(output)) await renderSlice({ project, projectDir, slice: timeline.slices[i], plan, output, W, H, fps, quality: preview ? 'fast' : quality, backgrounds, shouldCancel });
    onProgress(.04 + (i + 1) / timeline.slices.length * .58, `Rendering visual ${i + 1}/${timeline.slices.length}`);
  }
  const silent = path.join(workDir, 'visual-master.mp4'); await concatSegments(files, silent, workDir, shouldCancel); onProgress(.66, 'Joining styled visuals');
  const based = path.join(workDir, 'base-with-audio.mp4'); await muxAudio(project, projectDir, silent, based, timeline.duration, timeline.startAt, shouldCancel); onProgress(.75, 'Mixing voiceover, music and clip audio');
  const outputName = `${safeFile(project.name)}-${preview ? 'preview' : resolution}-${jobId.slice(-6)}.mp4`, final = path.join(renderDir, outputName);
  if (plan.settings?.text?.enabled || project.automation?.text?.enabled) await applyVText({ projectDir, automation: project.automation || plan.settings, input: based, output: final, workDir, onProgress, shouldCancel });
  else await fsp.copyFile(based, final);
  const manifest = { schema: 'researchcut-render-v1', jobId, createdAt: new Date().toISOString(), projectId: project.id, projectName: project.name, resolution: preview ? '720p-preview' : resolution, width: W, height: H, fps, duration: timeline.duration, preview, output: final, outputName, presetId: plan.presetId, seed: plan.seed, shots: plan.shots, text: { enabled: !!project.automation?.text?.enabled, instructionFile: project.automation?.text?.instructionFile || null } };
  await fsp.writeFile(path.join(renderDir, 'render-manifest.json'), JSON.stringify(manifest, null, 2), 'utf8'); onProgress(1, 'Render complete');
  return manifest;
}

module.exports = { scanBackgrounds, renderProject, durationOf, safeFile, deriveScript };
