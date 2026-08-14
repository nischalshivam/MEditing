'use strict';

const PACKS = [
  { id: 'clean_documentary', name: 'Clean Documentary', description: 'Balanced frames, restrained motion and clean cuts.', accent: '#18c9b8', layouts: ['fullscreen', 'hero_center', 'frame90', 'focus_left', 'focus_right'], motions: ['zoom_in', 'zoom_out', 'pan_left', 'pan_right'], transitions: ['hard', 'soft_cut', 'dip_black'] },
  { id: 'dark_research', name: 'Dark Research', description: 'Deep backgrounds, sharp frames and cinematic dips.', accent: '#5ce1d3', layouts: ['fullscreen', 'hero_center', 'frame82', 'focus_left', 'float_bottom_right'], motions: ['zoom_in', 'pan_left', 'pan_right'], transitions: ['hard', 'dip_black', 'blur'] },
  { id: 'editorial_paper', name: 'Editorial Paper', description: 'Paper-like light framing for research and history.', accent: '#d8a84e', layouts: ['hero_center', 'frame82', 'card_left', 'card_right', 'float_top_left', 'float_bottom_right'], motions: ['zoom_in', 'zoom_out', 'drift'], transitions: ['hard', 'dip_warm', 'soft_cut'] },
  { id: 'archive_polaroid', name: 'Archive Polaroid', description: 'Card layouts, small rotations and archival pacing.', accent: '#e7c98a', layouts: ['card_left', 'card_right', 'frame74', 'float_top_right', 'float_bottom_left'], motions: ['zoom_in', 'drift', 'none'], transitions: ['hard', 'dip_warm', 'flash'] },
  { id: 'cyan_technology', name: 'Cyan Technology', description: 'Cyan borders, screen layouts and quick blur handoffs.', accent: '#38dbea', layouts: ['fullscreen', 'screen_left', 'screen_right', 'focus_left', 'focus_right', 'float_top_right'], motions: ['push_in', 'pan_left', 'pan_right'], transitions: ['hard', 'blur', 'flash'] },
  { id: 'green_data', name: 'Green Data Grid', description: 'CapCut-green tech framing with energetic movement.', accent: '#62e68b', layouts: ['hero_center', 'screen_left', 'screen_right', 'float_top_left', 'float_bottom_right'], motions: ['push_in', 'zoom_in', 'drift'], transitions: ['hard', 'soft_cut', 'flash'] },
  { id: 'cinematic_atmosphere', name: 'Cinematic Atmosphere', description: 'Slow motion, large frames and gentle black dips.', accent: '#c6a36b', layouts: ['fullscreen', 'hero_center', 'frame90', 'focus_left', 'focus_right'], motions: ['zoom_in', 'zoom_out', 'pan_right'], transitions: ['hard', 'dip_black', 'blur'] },
  { id: 'minimal_monochrome', name: 'Minimal Monochrome', description: 'Quiet black/white treatment with minimal effects.', accent: '#f1f6f5', layouts: ['fullscreen', 'hero_center', 'frame90', 'float_bottom_left'], motions: ['zoom_in', 'none'], transitions: ['hard', 'soft_cut'] },
  { id: 'bold_explainer', name: 'Bold Explainer', description: 'Punchy movement and high-contrast framed moments.', accent: '#ffd24a', layouts: ['fullscreen', 'hero_center', 'focus_left', 'focus_right', 'float_top_left', 'float_bottom_right'], motions: ['push_in', 'zoom_in', 'pan_left'], transitions: ['hard', 'flash', 'dip_white'] },
  { id: 'soft_modern', name: 'Soft Modern', description: 'Rounded modern framing with smooth blur transitions.', accent: '#8fe4dc', layouts: ['hero_center', 'frame82', 'fullscreen', 'focus_left', 'focus_right', 'float_top_right'], motions: ['zoom_in', 'zoom_out', 'drift'], transitions: ['hard', 'blur', 'soft_cut'] }
];

const EDGE_STYLES = ['clean', 'soft_glass', 'neon', 'double_line', 'cinema', 'paper', 'shadow'];
const ENTRANCES = ['none', 'slide_left', 'slide_right', 'slide_up', 'slide_down', 'scale_pop'];

const VARIANTS = [
  { id: '01', label: 'Balanced', framedDensity: .32, transitionDensity: .34, energy: .8 },
  { id: '02', label: 'Framed', framedDensity: .52, transitionDensity: .38, energy: .85 },
  { id: '03', label: 'Motion', framedDensity: .26, transitionDensity: .28, energy: 1.15 },
  { id: '04', label: 'Subtle', framedDensity: .2, transitionDensity: .22, energy: .55 },
  { id: '05', label: 'Dynamic', framedDensity: .42, transitionDensity: .52, energy: 1.3 },
  { id: '06', label: 'Editorial', framedDensity: .62, transitionDensity: .3, energy: .7 }
];

const PRESETS = PACKS.flatMap(pack => VARIANTS.map(variant => ({
  id: `${pack.id}_${variant.id}`, packId: pack.id, name: `${pack.name} · ${variant.label}`,
  description: pack.description, accent: pack.accent, layouts: pack.layouts, motions: pack.motions,
  transitions: pack.transitions, framedDensity: variant.framedDensity,
  transitionDensity: variant.transitionDensity, energy: variant.energy
})));

const DEFAULT_AUTOMATION = {
  enabled: true, presetId: 'clean_documentary_01', seed: 812930, intensity: 'balanced',
  transitionsEnabled: true, motionEnabled: true, backgroundMode: 'auto', backgroundId: null,
  solidColor: '#0b1011', framedDensity: null, transitionDensity: null,
  text: { enabled: false, instructionFile: null, scriptFile: null, eventCount: 0, samples: [], niche: 'auto', pack: 'auto', accent: '', energy: 3, scale: 'auto', density: 'file' },
  export: { resolution: '1080p', quality: 'balanced' }, overrides: {}, plan: null
};

function clamp(value, min, max) { value = Number(value); return Number.isFinite(value) ? Math.max(min, Math.min(max, value)) : min; }
function normalizeAutomation(value = {}) {
  const presetId = PRESETS.some(p => p.id === value.presetId) ? value.presetId : DEFAULT_AUTOMATION.presetId;
  const text = { ...DEFAULT_AUTOMATION.text, ...(value.text || {}) };
  const exp = { ...DEFAULT_AUTOMATION.export, ...(value.export || {}) };
  return {
    ...DEFAULT_AUTOMATION, ...value, presetId,
    seed: Math.max(1, Math.floor(Number(value.seed) || DEFAULT_AUTOMATION.seed)),
    intensity: ['subtle', 'balanced', 'energetic'].includes(value.intensity) ? value.intensity : 'balanced',
    backgroundMode: ['auto', 'blur', 'builtin', 'project', 'solid', 'none'].includes(value.backgroundMode) ? value.backgroundMode : 'auto',
    solidColor: /^#[0-9a-f]{6}$/i.test(value.solidColor || '') ? value.solidColor : '#0b1011',
    framedDensity: value.framedDensity == null ? null : clamp(value.framedDensity, 0, 1),
    transitionDensity: value.transitionDensity == null ? null : clamp(value.transitionDensity, 0, 1),
    text: {
      ...text, enabled: !!text.enabled, energy: clamp(text.energy, 1, 5),
      density: ['file', 'medium', 'light'].includes(text.density) ? text.density : 'file',
      scale: ['auto', 'small', 'balanced', 'large'].includes(text.scale) ? text.scale : 'auto'
    },
    export: {
      ...exp, resolution: ['1080p', '4k'].includes(exp.resolution) ? exp.resolution : '1080p',
      quality: ['fast', 'balanced', 'quality'].includes(exp.quality) ? exp.quality : 'balanced'
    },
    overrides: value.overrides && typeof value.overrides === 'object' ? value.overrides : {},
    plan: value.plan && typeof value.plan === 'object' ? value.plan : null
  };
}

function mulberry32(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function pickDifferent(list, random, previous) {
  if (!list.length) return 'none'; if (list.length === 1) return list[0];
  let selected = list[Math.floor(random() * list.length)], guard = 0;
  while (selected === previous && guard++ < 6) selected = list[Math.floor(random() * list.length)];
  return selected;
}

function buildPlan(project, automation, backgrounds = []) {
  const settings = normalizeAutomation(automation); const preset = PRESETS.find(p => p.id === settings.presetId) || PRESETS[0];
  const random = mulberry32(settings.seed); const visual = project.clips.filter(c => c.trackId.startsWith('V')).sort((a, b) => a.start - b.start || a.trackId.localeCompare(b.trackId));
  const density = settings.framedDensity == null ? preset.framedDensity : settings.framedDensity;
  const transitionDensity = settings.transitionDensity == null ? preset.transitionDensity : settings.transitionDensity;
  const intensityFactor = settings.intensity === 'subtle' ? .62 : settings.intensity === 'energetic' ? 1.28 : 1;
  let lastLayout = null, lastMotion = null, lastTransition = null, lastFramed = false, bgIndex = Math.floor(random() * Math.max(1, backgrounds.length));
  const shots = visual.map((clip, index) => {
    const override = settings.overrides[clip.id] || {}; const useFrame = !lastFramed && random() < density;
    const layoutPool = useFrame ? preset.layouts.filter(x => x !== 'fullscreen') : ['fullscreen'];
    const layoutId = override.layoutId || pickDifferent(layoutPool.length ? layoutPool : ['frame90'], random, lastLayout);
    const motionId = override.motionId || (settings.motionEnabled ? pickDifferent(preset.motions, random, lastMotion) : 'none');
    const edgeStyle = override.edgeStyle || EDGE_STYLES[(index + Math.floor(random() * EDGE_STYLES.length)) % EDGE_STYLES.length];
    const entranceId = override.entranceId || (layoutId === 'fullscreen' ? 'none' : ENTRANCES[1 + Math.floor(random() * (ENTRANCES.length - 1))]);
    let transitionId = 'hard';
    if (settings.transitionsEnabled && index < visual.length - 1 && random() < transitionDensity) transitionId = pickDifferent(preset.transitions.filter(x => x !== 'hard'), random, lastTransition) || 'hard';
    if (override.transitionId) transitionId = override.transitionId;
    let backgroundId = override.backgroundId || settings.backgroundId || null;
    if (!backgroundId && backgrounds.length) { backgroundId = backgrounds[bgIndex % backgrounds.length].id; if (layoutId !== 'fullscreen') bgIndex++; }
    lastLayout = layoutId; lastMotion = motionId; lastTransition = transitionId; lastFramed = layoutId !== 'fullscreen';
    return {
      clipId: clip.id, index, start: clip.start, duration: clip.duration, trackId: clip.trackId,
      layoutId, motionId, edgeStyle, entranceId, transitionId, transitionDuration: +(Math.min(.58, Math.max(.16, .34 * preset.energy * intensityFactor))).toFixed(3),
      backgroundMode: override.backgroundMode || settings.backgroundMode, backgroundId,
      accent: override.accent || preset.accent, energy: +(preset.energy * intensityFactor).toFixed(2), overridden: Object.keys(override).length > 0
    };
  });
  return { version: 1, generatedAt: new Date().toISOString(), projectId: project.id, presetId: preset.id, presetName: preset.name, seed: settings.seed, settings: { ...settings, plan: undefined }, shots };
}

function catalog() {
  return {
    presets: PRESETS,
    layouts: ['fullscreen', 'hero_center', 'frame90', 'frame82', 'frame74', 'screen_left', 'screen_right', 'focus_left', 'focus_right', 'card_left', 'card_right', 'float_top_left', 'float_top_right', 'float_bottom_left', 'float_bottom_right'],
    motions: ['none', 'zoom_in', 'zoom_out', 'push_in', 'pan_left', 'pan_right', 'drift'],
    transitions: ['hard', 'soft_cut', 'dip_black', 'dip_white', 'dip_warm', 'flash', 'blur'],
    edgeStyles: EDGE_STYLES,
    entrances: ENTRANCES
  };
}

module.exports = { PACKS, VARIANTS, PRESETS, DEFAULT_AUTOMATION, normalizeAutomation, buildPlan, catalog };
