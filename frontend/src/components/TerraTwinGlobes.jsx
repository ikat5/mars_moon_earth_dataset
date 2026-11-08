/**
 * TerraTwin: Planetary Analog Discovery Engine
 *
 * Split-screen mission-control view: an extraterrestrial target globe (Moon / Mars)
 * on the left, its Earth analog twin globe on the right, bridged by live data streams
 * and a pre-rendered hologram video used in three tiers:
 *   A. ambient screen-blended background layer behind both WebGL globes
 *   B. full-screen cinematic "hologram stream" mode with HTML/SVG HUD overlays
 *   C. LIDAR picture-in-picture monitor inside the telemetry card
 */
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import Globe from 'react-globe.gl';
import * as THREE from 'three';
import {
  Activity,
  Box,
  ChevronDown,
  ChevronUp,
  Crosshair,
  Gauge,
  Moon,
  Mountain,
  Orbit,
  Pause,
  Pickaxe,
  Play,
  Radar,
  RotateCcw,
  Satellite,
  ScanLine,
  SlidersHorizontal,
  Snowflake,
  Thermometer,
  Video,
  Wallet,
  Weight,
} from 'lucide-react';

export const HOLOGRAM_VIDEO_URL = '/hologram-bg.mp4';

// ---------------------------------------------------------------------------
// Static mission data
// ---------------------------------------------------------------------------

const TEXTURES = {
  moonSurface:
    'https://raw.githubusercontent.com/vasturiano/globe.gl/master/example/moon-landing-sites/lunar_surface.jpg',
  moonBump:
    'https://raw.githubusercontent.com/vasturiano/globe.gl/master/example/moon-landing-sites/lunar_bumpmap.jpg',
  // OSIRIS_Mars_true_color.jpg is a photo of the planet's disk (2205x2205), not an
  // equirectangular map, so it can't wrap a sphere. This 2:1 Solar System Scope map
  // (CC BY 4.0, same Wikimedia host) can, and doubles as a bump map for relief.
  marsSurface: 'https://upload.wikimedia.org/wikipedia/commons/4/46/Solarsystemscope_texture_2k_mars.jpg',
  earthSurface: '//unpkg.com/three-globe/example/img/earth-blue-marble.jpg',
  earthBump: '//unpkg.com/three-globe/example/img/earth-topology.png',
  starfield: '//unpkg.com/three-globe/example/img/night-sky.png',
};

const normalizeLng = (lng) => ((((lng + 180) % 360) + 360) % 360) - 180;

// Site signatures: slopeDeg (°), roughness (0-1 RMS index), mafic (0 felsic/sedimentary
// to 1 basaltic), tempC (mean surface °C), aridity (0 wet to 1 hyper-arid / ice-free).
const BODIES = {
  moon: {
    id: 'moon',
    label: 'MOON',
    mission: 'Artemis',
    accent: '#fb923c',
    gravity: 0.1654,
    gravityLabel: '0.16 g',
    surface: TEXTURES.moonSurface,
    bump: TEXTURES.moonBump,
    rover: { name: 'VIPER-class rover', massKg: 430 },
    bases: [
      {
        id: 'shackleton',
        name: 'Shackleton Crater Rim',
        lat: -88.81,
        lng: 123.76,
        slopeDeg: 12,
        roughness: 0.55,
        mafic: 0.25,
        tempC: -120,
        aridity: 0.92,
        rockType: 'Anorthositic highland regolith',
      },
      {
        id: 'nobile',
        name: 'Nobile Rim 1',
        lat: -85.46,
        lng: 36.36,
        slopeDeg: 8,
        roughness: 0.45,
        mafic: 0.3,
        tempC: -110,
        aridity: 0.9,
        rockType: 'Highland breccia regolith',
      },
      {
        id: 'marius',
        name: 'Marius Hills Lava Tube',
        lat: 14.09,
        lng: -56.77,
        slopeDeg: 5,
        roughness: 0.35,
        mafic: 0.95,
        tempC: -20,
        aridity: 1,
        rockType: 'Mare basalt (skylight)',
      },
    ],
  },
  mars: {
    id: 'mars',
    label: 'MARS',
    mission: 'MRO',
    accent: '#f87171',
    gravity: 0.3783,
    gravityLabel: '0.38 g',
    surface: TEXTURES.marsSurface,
    bump: TEXTURES.marsSurface,
    rover: { name: 'Perseverance-class rover', massKg: 1025 },
    bases: [
      {
        id: 'jezero',
        name: 'Jezero Crater Delta',
        lat: 18.38,
        lng: 77.58,
        slopeDeg: 6,
        roughness: 0.5,
        mafic: 0.55,
        tempC: -60,
        aridity: 0.95,
        rockType: 'Deltaic clays + carbonates',
      },
      {
        id: 'arcadia',
        name: 'Arcadia Planitia',
        lat: 39.2,
        lng: normalizeLng(-188.0),
        slopeDeg: 2,
        roughness: 0.2,
        mafic: 0.8,
        tempC: -70,
        aridity: 0.75,
        rockType: 'Ice-rich basaltic plains',
      },
    ],
  },
};

// budget: 0 = expensive expedition logistics, 1 = reachable on a local team budget.
const EARTH_ANALOGS = [
  {
    id: 'haughton',
    name: 'Haughton Crater',
    region: 'Devon Island, Canada',
    lat: 75.38,
    lng: -89.68,
    slopeDeg: 9,
    roughness: 0.6,
    mafic: 0.15,
    tempC: -16,
    aridity: 0.8,
    rockType: 'Impact breccia in dolomite',
    budget: 0.15,
  },
  {
    id: 'corona',
    name: 'Corona Lava Tube',
    region: 'Lanzarote, Spain',
    lat: 29.15,
    lng: -13.43,
    slopeDeg: 4,
    roughness: 0.4,
    mafic: 0.95,
    tempC: 19,
    aridity: 0.65,
    rockType: 'Basaltic lava tube',
    budget: 0.55,
  },
  {
    id: 'yungay',
    name: 'Yungay Station',
    region: 'Atacama Desert, Chile',
    lat: -24.09,
    lng: -69.93,
    slopeDeg: 3,
    roughness: 0.3,
    mafic: 0.3,
    tempC: 16,
    aridity: 1,
    rockType: 'Sulfate / nitrate evaporites',
    budget: 0.45,
  },
  {
    id: 'mcmurdo',
    name: 'McMurdo Dry Valleys',
    region: 'Antarctica',
    lat: -77.47,
    lng: 162.52,
    slopeDeg: 10,
    roughness: 0.55,
    mafic: 0.5,
    tempC: -20,
    aridity: 0.95,
    rockType: 'Dolerite + permafrost till',
    budget: 0.05,
  },
  {
    id: 'barind',
    name: 'Barind / Rajmahal Basalt',
    region: 'South Asia · Local Budget Analog',
    lat: 24.8,
    lng: 87.7,
    slopeDeg: 3,
    roughness: 0.35,
    mafic: 0.85,
    tempC: 26,
    aridity: 0.3,
    rockType: 'Rajmahal Trap flood basalt',
    budget: 1,
    isLocal: true,
  },
];

const ANALOG_BY_ID = new Map(EARTH_ANALOGS.map((a) => [a.id, a]));

const FEATURES = [
  { key: 'slopeDeg', label: 'Slope', range: [0, 25] },
  { key: 'roughness', label: 'Roughness', range: [0, 1] },
  { key: 'mafic', label: 'Rock match', range: [0, 1] },
  { key: 'tempC', label: 'Temperature', range: [-150, 40] },
  { key: 'aridity', label: 'Aridity', range: [0, 1] },
];

const WEIGHT_SLIDERS = [
  { key: 'traction', label: 'Rover Traction / Slope', icon: Mountain, accent: '#fb923c', hint: 'Weights slope and surface roughness' },
  { key: 'geochem', label: 'Drilling / Geochemistry', icon: Pickaxe, accent: '#facc15', hint: 'Weights rock and mineralogy match' },
  { key: 'thermal', label: 'Cryogenic / Thermal', icon: Snowflake, accent: '#22d3ee', hint: 'Weights temperature and aridity' },
  { key: 'budget', label: 'Local Budget Priority', icon: Wallet, accent: '#34d399', hint: 'Blends in low-cost, reachable analogs' },
];

const DEFAULT_WEIGHTS = { traction: 60, geochem: 55, thermal: 70, budget: 25 };

const COLORS = {
  cyan: '#22d3ee',
  emerald: '#34d399',
  lime: '#a3e635',
  selected: '#fde68a',
};

const G0 = 9.80665;
const BUDGET_BLEND_MAX = 0.3;
const FLY_MS = 1200;
const IDLE_RESUME_MS = 7000;
const BODY_SWAP_MS = 320;
const PULSE_MS = 900;
const HOLOGRAM_FADE_MS = 700;
const LEFT_PIN_ALT = { selected: 0.1, idle: 0.05 };
const LEFT_SHELL_LAYER = [{ id: 'lidar-shell', altitude: 0.012 }];
const RIGHT_SHELL_LAYER = [{ id: 'earth-shell', altitude: 0.012 }];
const STREAM_BENDS = [0.3, 0.17, -0.14];

const GLASS =
  'backdrop-blur-md bg-slate-900/80 border border-cyan-500/30 shadow-[0_0_32px_-12px_rgba(34,211,238,0.45)]';

// ---------------------------------------------------------------------------
// Analog scoring: weighted cosine similarity over centred 5-D terrain signatures
// ---------------------------------------------------------------------------

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

// Each feature is mapped to [-1, 1] around the middle of its range so the cosine
// measures direction (cold vs warm, steep vs flat) instead of saturating near 1.
const toSignature = (site) =>
  FEATURES.map(({ key, range: [lo, hi] }) => clamp(((site[key] - lo) / (hi - lo)) * 2 - 1, -1, 1));

const ANALOG_SIGNATURES = new Map(EARTH_ANALOGS.map((a) => [a.id, toSignature(a)]));

function weightedCosine(a, b, w) {
  let dot = 0;
  let na = 0;
  let nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += w[i] * a[i] * b[i];
    na += w[i] * a[i] * a[i];
    nb += w[i] * b[i] * b[i];
  }
  return na > 0 && nb > 0 ? dot / Math.sqrt(na * nb) : 0;
}

function featureWeights({ traction, geochem, thermal }) {
  const t = traction / 100;
  const g = geochem / 100;
  const th = thermal / 100;
  // Small floor keeps the vector well-defined when every slider is at zero.
  return [t, t * 0.7, g, th, th * 0.8].map((w) => w + 0.02);
}

export function scoreAnalogs(base, weights) {
  const w = featureWeights(weights);
  const target = toSignature(base);
  const beta = (weights.budget / 100) * BUDGET_BLEND_MAX;
  return EARTH_ANALOGS.map((analog) => {
    const sig = ANALOG_SIGNATURES.get(analog.id);
    const similarity = ((weightedCosine(target, sig, w) + 1) / 2) * 100;
    const score = similarity * (1 - beta) + analog.budget * 100 * beta;
    return {
      analog,
      similarity,
      score,
      budgetDelta: score - similarity,
      features: FEATURES.map((f, i) => ({ key: f.key, label: f.label, match: 1 - Math.abs(target[i] - sig[i]) / 2 })),
    };
  })
    .sort((a, b) => b.score - a.score)
    .map((s, i) => ({ ...s, rank: i + 1 }));
}

const rightPinAltitude = (score) => 0.02 + (score / 100) ** 2 * 0.22;

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

const fmtLat = (lat) => `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? 'N' : 'S'}`;
const fmtLng = (lng) => `${Math.abs(lng).toFixed(2)}°${lng >= 0 ? 'E' : 'W'}`;
const fmtCoords = (lat, lng) => `${fmtLat(lat)} ${fmtLng(lng)}`;
const fmtInt = (n) => Math.round(n).toLocaleString('en-US');

function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`;
}

const fadingRing = (hex, strength = 0.9) => {
  const rgb = hexToRgb(hex);
  return (t) => `rgba(${rgb},${(1 - t) * strength})`;
};

const tooltipHtml = (title, body, color) =>
  `<div class="tt-tip" style="--tt-tip:${color}"><b>${title}</b><br/>${body}</div>`;

function makeGeoTag(d) {
  const el = document.createElement('div');
  el.className = 'tt-geo-tag';
  el.style.setProperty('--tt-tag', d.tagColor);
  const label = document.createElement('div');
  label.textContent = d.tagText;
  el.appendChild(label);
  return el;
}

// ---------------------------------------------------------------------------
// LIDAR scan shell: additive shader sphere hugging the globe surface
// ---------------------------------------------------------------------------

const SHELL_VERTEX = /* glsl */ `
  varying vec2 vUv;
  varying vec3 vNormal;
  varying vec3 vViewDir;
  void main() {
    vUv = uv;
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vViewDir = normalize(-mvPosition.xyz);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const SHELL_FRAGMENT = /* glsl */ `
  uniform float uTime;
  uniform float uPulse;
  uniform float uIntensity;
  uniform float uGrid;
  uniform float uScanSpeed;
  uniform vec3 uColor;
  varying vec2 vUv;
  varying vec3 vNormal;
  varying vec3 vViewDir;

  float gridLine(float coord, float count, float width) {
    float c = coord * count;
    float d = abs(fract(c - 0.5) - 0.5) / max(fwidth(c), 1e-4);
    return 1.0 - min(d / width, 1.0);
  }

  void main() {
    float lat = vUv.y;
    float poleFade = smoothstep(0.0, 0.06, min(lat, 1.0 - lat));
    float major = max(gridLine(vUv.x, uGrid * 2.0, 1.0) * poleFade, gridLine(lat, uGrid, 1.0));
    float minor = max(gridLine(vUv.x, uGrid * 8.0, 0.6) * poleFade, gridLine(lat, uGrid * 4.0, 0.6));

    // LIDAR sweep: bright latitude band travelling pole to pole with a fading wake.
    float scan = fract(uTime * uScanSpeed);
    float dist = lat - scan;
    float band = exp(-pow(dist * 30.0, 2.0));
    float wake = smoothstep(-0.22, 0.0, dist) * (1.0 - step(0.0, dist)) * 0.6;

    // Rotating meridian radar beam.
    float beam = pow(fract(vUv.x + uTime * 0.04), 18.0);

    float fresnel = pow(1.0 - clamp(dot(normalize(vNormal), normalize(vViewDir)), 0.0, 1.0), 3.0);
    float lines = major * 0.3 + minor * 0.1;
    float alpha = lines * (0.35 + band * 2.2 + wake + beam * 0.8) + band * 0.18 + fresnel * 0.45;
    alpha *= uIntensity * (1.0 + uPulse * 2.0);
    gl_FragColor = vec4(uColor, clamp(alpha, 0.0, 1.0));
  }
`;

function createScanShell({ color, intensity, grid, scanSpeed }) {
  const uniforms = {
    uTime: { value: 0 },
    uPulse: { value: 0 },
    uIntensity: { value: intensity },
    uGrid: { value: grid },
    uScanSpeed: { value: scanSpeed },
    uColor: { value: new THREE.Color(color) },
  };
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(1, 96, 64),
    new THREE.ShaderMaterial({
      uniforms,
      vertexShader: SHELL_VERTEX,
      fragmentShader: SHELL_FRAGMENT,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  mesh.raycast = () => {}; // never intercept pin clicks
  return { mesh, uniforms };
}

const updateShell = (obj, d, globeRadius) => obj.scale.setScalar(globeRadius * (1 + d.altitude));

const arcColor = () => ['rgba(52,211,153,0.95)', 'rgba(34,211,238,0.35)'];
const arcStroke = (d) => (d.rank === 2 ? 0.75 : 0.5);

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

function useElementSize() {
  const ref = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const observer = new ResizeObserver(([entry]) => {
      const width = Math.floor(entry.contentRect.width);
      const height = Math.floor(entry.contentRect.height);
      setSize((prev) => (prev.width === width && prev.height === height ? prev : { width, height }));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, size];
}

function useMediaQuery(query) {
  const [matches, setMatches] = useState(() => typeof window !== 'undefined' && window.matchMedia(query).matches);
  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [query]);
  return matches;
}

function useTicker(ms) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), ms);
    return () => clearInterval(id);
  }, [ms]);
  return tick;
}

function useVideoStatus(src) {
  const [state, setState] = useState({ src, status: 'loading' });
  const status = state.src === src ? state.status : 'loading';
  const handlers = useMemo(
    () => ({
      onLoadedData: () => setState({ src, status: 'ready' }),
      onError: () => setState({ src, status: 'error' }),
    }),
    [src],
  );
  return [status, handlers];
}

// Idle auto-rotation that halts while the user drags/zooms and resumes after a quiet
// period. Returns a `hold` callback for programmatic camera moves (fly-to).
function useIdleAutoRotate(globeRef, { ready, enabled, speed = 0.35 }) {
  const holdRef = useRef(() => {});
  useEffect(() => {
    const globe = globeRef.current;
    if (!ready || !globe) return undefined;
    const controls = globe.controls();
    let timer;
    const stop = () => {
      clearTimeout(timer);
      controls.autoRotate = false;
    };
    const scheduleResume = () => {
      clearTimeout(timer);
      if (!enabled) return;
      timer = setTimeout(() => {
        controls.autoRotate = true;
      }, IDLE_RESUME_MS);
    };
    controls.autoRotateSpeed = speed;
    controls.autoRotate = enabled;
    controls.addEventListener('start', stop);
    controls.addEventListener('end', scheduleResume);
    holdRef.current = () => {
      stop();
      scheduleResume();
    };
    return () => {
      clearTimeout(timer);
      controls.removeEventListener('start', stop);
      controls.removeEventListener('end', scheduleResume);
      holdRef.current = () => {};
    };
  }, [globeRef, ready, enabled, speed]);
  return useCallback(() => holdRef.current(), []);
}

// Screen position of a geo point inside the split viewport, plus whether it faces the camera.
function projectAnchor(globe, panel, lat, lng, altitude) {
  const { x, y } = globe.getScreenCoords(lat, lng, altitude);
  const p = globe.getCoords(lat, lng, altitude);
  const cam = globe.camera().position;
  const facing = p.x * (cam.x - p.x) + p.y * (cam.y - p.y) + p.z * (cam.z - p.z) > 0;
  return { x: x + panel.offsetLeft, y: y + panel.offsetTop, facing };
}

function streamPath(a, b, bend) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const dist = Math.hypot(dx, dy) || 1;
  // Left-hand normal: "up" for a left-to-right stream, "right" for a top-to-bottom one.
  const nx = (dy / dist) * dist * bend;
  const ny = (-dx / dist) * dist * bend;
  const c1x = a.x + dx * 0.3 + nx;
  const c1y = a.y + dy * 0.3 + ny;
  const c2x = a.x + dx * 0.7 + nx;
  const c2y = a.y + dy * 0.7 + ny;
  return `M${a.x.toFixed(1)} ${a.y.toFixed(1)} C${c1x.toFixed(1)} ${c1y.toFixed(1)} ${c2x.toFixed(1)} ${c2y.toFixed(1)} ${b.x.toFixed(1)} ${b.y.toFixed(1)}`;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function TerraTwinGlobes({ videoSrc = HOLOGRAM_VIDEO_URL }) {
  const [bodyId, setBodyId] = useState('moon');
  const [selectedBaseId, setSelectedBaseId] = useState(BODIES.moon.bases[0].id);
  const [viewMode, setViewMode] = useState('3d');
  const [autoRotate, setAutoRotate] = useState(true);
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [flyNonce, setFlyNonce] = useState(0);
  const [bodySwapping, setBodySwapping] = useState(false);
  const [leftReady, setLeftReady] = useState(false);
  const [rightReady, setRightReady] = useState(false);
  const [pulseId, setPulseId] = useState(0);
  const [isPulsing, setIsPulsing] = useState(false);
  const isWide = useMediaQuery('(min-width: 768px)');
  const [cardOpen, setCardOpen] = useState(() => typeof window === 'undefined' || window.innerWidth >= 768);

  const leftGlobeRef = useRef();
  const rightGlobeRef = useRef();
  const [leftPanelRef, leftSize] = useElementSize();
  const [rightPanelRef, rightSize] = useElementSize();
  const leftPovRef = useRef(null);
  const rightPovRef = useRef(null);
  const swapTimer = useRef();
  const pulseTimer = useRef();

  const svgRef = useRef(null);
  const gradientRef = useRef(null);
  const streamGroupRefs = useRef([]);
  const streamGlowRefs = useRef([]);
  const streamCoreRefs = useRef([]);
  const packetRefs = useRef([]);
  const anchorRefs = useRef([]);
  const streamStateRef = useRef({ enabled: false });

  const [bgStatus, bgVideoHandlers] = useVideoStatus(videoSrc);

  const body = BODIES[bodyId];
  const selectedBase = body.bases.find((b) => b.id === selectedBaseId) ?? body.bases[0];
  const hologram = viewMode === 'hologram';

  const scores = useMemo(() => scoreAnalogs(selectedBase, weights), [selectedBase, weights]);
  const scoreById = useMemo(() => new Map(scores.map((s) => [s.analog.id, s])), [scores]);
  const topMatch = scores[0];
  const topAnalog = topMatch.analog;
  const top3Key = scores
    .slice(0, 3)
    .map((s) => s.analog.id)
    .join('|');

  const leftShell = useMemo(() => createScanShell({ color: BODIES.moon.accent, intensity: 1, grid: 18, scanSpeed: 0.07 }), []);
  const rightShell = useMemo(() => createScanShell({ color: COLORS.cyan, intensity: 0.4, grid: 12, scanSpeed: 0.045 }), []);
  const leftShellObject = useCallback(() => leftShell.mesh, [leftShell]);
  const rightShellObject = useCallback(() => rightShell.mesh, [rightShell]);

  useEffect(() => {
    leftShell.uniforms.uColor.value.set(body.accent);
  }, [leftShell, body.accent]);

  useEffect(
    () => () => {
      clearTimeout(swapTimer.current);
      clearTimeout(pulseTimer.current);
      for (const { mesh } of [leftShell, rightShell]) {
        mesh.geometry.dispose();
        mesh.material.dispose();
      }
    },
    [leftShell, rightShell],
  );

  // --- camera control ------------------------------------------------------

  const holdLeft = useIdleAutoRotate(leftGlobeRef, { ready: leftReady, enabled: autoRotate });
  const holdRight = useIdleAutoRotate(rightGlobeRef, { ready: rightReady, enabled: autoRotate, speed: 0.3 });

  const flyLeftTo = useCallback(
    (site, altitude) => {
      const globe = leftGlobeRef.current;
      if (!globe) return;
      holdLeft();
      globe.pointOfView({ lat: site.lat, lng: site.lng, altitude }, FLY_MS);
    },
    [holdLeft],
  );

  const flyRightTo = useCallback(
    (site, altitude) => {
      const globe = rightGlobeRef.current;
      if (!globe) return;
      holdRight();
      globe.pointOfView({ lat: site.lat, lng: site.lng, altitude }, FLY_MS);
    },
    [holdRight],
  );

  const triggerPulse = useCallback(() => {
    setPulseId((n) => n + 1);
    setIsPulsing(true);
    clearTimeout(pulseTimer.current);
    pulseTimer.current = setTimeout(() => setIsPulsing(false), PULSE_MS);
    leftShell.uniforms.uPulse.value = 1;
    rightShell.uniforms.uPulse.value = 1;
  }, [leftShell, rightShell]);

  // Frame the first candidate base whenever the target body changes (and on load).
  useEffect(() => {
    if (leftReady) flyLeftTo(BODIES[bodyId].bases[0], 1.9);
  }, [leftReady, bodyId, flyLeftTo]);

  // Earth twin follows the #1 analog: new selection, re-ranking, or slider release.
  useEffect(() => {
    if (rightReady) flyRightTo(topAnalog, 1.8);
  }, [rightReady, topAnalog, flyNonce, flyRightTo]);

  // Stop rendering the hidden globes in cinematic mode.
  useEffect(() => {
    const globes = [leftGlobeRef.current, rightGlobeRef.current].filter(Boolean);
    if (hologram) {
      const timer = setTimeout(() => globes.forEach((g) => g.pauseAnimation()), HOLOGRAM_FADE_MS);
      return () => clearTimeout(timer);
    }
    globes.forEach((g) => g.resumeAnimation());
    return undefined;
  }, [hologram, leftReady, rightReady]);

  const handleSelectBase = useCallback(
    (base) => {
      setSelectedBaseId(base.id);
      setFlyNonce((n) => n + 1);
      flyLeftTo(base, 1.4);
      triggerPulse();
    },
    [flyLeftTo, triggerPulse],
  );

  const switchBody = useCallback(
    (id) => {
      if (id === bodyId) return;
      setBodySwapping(true);
      clearTimeout(swapTimer.current);
      swapTimer.current = setTimeout(() => {
        setBodyId(id);
        setSelectedBaseId(BODIES[id].bases[0].id);
        setBodySwapping(false);
        triggerPulse();
      }, BODY_SWAP_MS);
    },
    [bodyId, triggerPulse],
  );

  const resetCameras = useCallback(() => {
    flyLeftTo(selectedBase, 2.4);
    flyRightTo(topAnalog, 2.4);
  }, [flyLeftTo, flyRightTo, selectedBase, topAnalog]);

  const setWeight = useCallback((key, value) => setWeights((w) => ({ ...w, [key]: value })), []);
  const commitWeights = useCallback(() => setFlyNonce((n) => n + 1), []);

  const focusAnalog = useCallback((analog) => flyRightTo(analog, 1.6), [flyRightTo]);

  const onLeftZoom = useCallback(({ lat, lng, altitude }) => {
    if (leftPovRef.current) leftPovRef.current.textContent = `CAM ${fmtCoords(lat, lng)} · ALT ${altitude.toFixed(2)}`;
  }, []);
  const onRightZoom = useCallback(({ lat, lng, altitude }) => {
    if (rightPovRef.current) rightPovRef.current.textContent = `CAM ${fmtCoords(lat, lng)} · ALT ${altitude.toFixed(2)}`;
  }, []);

  // --- globe layer accessors -----------------------------------------------

  const isSelected = useCallback((d) => d.id === selectedBase.id, [selectedBase.id]);
  const leftPointAltitude = useCallback((d) => (isSelected(d) ? LEFT_PIN_ALT.selected : LEFT_PIN_ALT.idle), [isSelected]);
  const leftPointColor = useCallback((d) => (isSelected(d) ? COLORS.selected : body.accent), [isSelected, body.accent]);
  const leftRingColor = useCallback((d) => fadingRing(isSelected(d) ? COLORS.selected : body.accent), [isSelected, body.accent]);
  const leftRingRadius = useCallback((d) => (isSelected(d) ? 7 : 3.5), [isSelected]);
  const leftRingPeriod = useCallback((d) => (isSelected(d) ? 700 : 1400), [isSelected]);
  const baseLabel = useCallback(
    (d) =>
      tooltipHtml(
        d.name,
        `${fmtCoords(d.lat, d.lng)}<br/>${d.rockType}<br/>Slope ${d.slopeDeg}° · ${d.tempC} °C<br/><i>Click to compute Earth twins</i>`,
        body.accent,
      ),
    [body.accent],
  );

  const analogColor = useCallback(
    (d) => {
      if (scoreById.get(d.id).rank === 1) return COLORS.emerald;
      return d.isLocal ? COLORS.lime : COLORS.cyan;
    },
    [scoreById],
  );
  const rightPointAltitude = useCallback((d) => rightPinAltitude(scoreById.get(d.id).score), [scoreById]);
  const rightPointRadius = useCallback((d) => (d.id === topAnalog.id ? 0.95 : 0.6), [topAnalog.id]);
  const rightRingColor = useCallback((d) => fadingRing(analogColor(d), d.id === topAnalog.id ? 0.95 : 0.6), [analogColor, topAnalog.id]);
  const rightRingRadius = useCallback((d) => (d.id === topAnalog.id ? 6.5 : 3), [topAnalog.id]);
  const rightRingSpeed = useCallback((d) => (d.id === topAnalog.id ? 2.6 : 1.4), [topAnalog.id]);
  const analogLabel = useCallback(
    (d) => {
      const s = scoreById.get(d.id);
      return tooltipHtml(
        `#${s.rank} ${d.name}`,
        `${d.region}<br/>${d.rockType}<br/>Match ${s.score.toFixed(1)}% · ${fmtCoords(d.lat, d.lng)}`,
        analogColor(d),
      );
    },
    [scoreById, analogColor],
  );

  const arcsData = useMemo(() => {
    const [first, ...rest] = top3Key.split('|').map((id) => ANALOG_BY_ID.get(id));
    return rest.map((to, i) => ({
      id: `${first.id}-${to.id}`,
      rank: i + 2,
      startLat: first.lat,
      startLng: first.lng,
      endLat: to.lat,
      endLng: to.lng,
      label: `#1 ${first.name} ⇢ #${i + 2} ${to.name}`,
    }));
  }, [top3Key]);

  const leftTags = useMemo(
    () => [{ ...selectedBase, tagText: selectedBase.name, tagColor: body.accent, tagAlt: LEFT_PIN_ALT.selected }],
    [selectedBase, body.accent],
  );
  const rightTags = useMemo(
    () => [{ ...topAnalog, tagText: `★ ${topAnalog.name}`, tagColor: COLORS.emerald, tagAlt: 0.24 }],
    [topAnalog],
  );

  const leftOffset = useMemo(() => [0, isWide ? -40 : 0], [isWide]);
  const rightOffset = useMemo(() => [cardOpen && isWide ? -150 : 0, isWide ? -40 : 0], [cardOpen, isWide]);

  // --- data streams bridging the two globes (updated per frame, no re-render) ---

  useEffect(() => {
    streamStateRef.current = {
      enabled: !hologram && !bodySwapping && leftReady && rightReady,
      base: selectedBase,
      targets: scores.slice(0, 3).map((s) => ({ lat: s.analog.lat, lng: s.analog.lng, alt: rightPinAltitude(s.score) })),
    };
  });

  useEffect(() => {
    let frame;
    const start = performance.now();
    const opacity = [0, 0, 0];

    const updateStreams = (t) => {
      const svg = svgRef.current;
      const state = streamStateRef.current;
      const lg = leftGlobeRef.current;
      const rg = rightGlobeRef.current;
      const lp = leftPanelRef.current;
      const rp = rightPanelRef.current;
      if (!svg) return;
      if (!state.enabled || !lg || !rg || !lp || !rp) {
        svg.style.opacity = '0';
        return;
      }
      svg.style.opacity = '1';

      const { base, targets } = state;
      const a = projectAnchor(lg, lp, base.lat, base.lng, LEFT_PIN_ALT.selected);
      setPoint(anchorRefs.current[0], a, a.facing ? 1 : 0.2);

      targets.forEach((target, i) => {
        const b = projectAnchor(rg, rp, target.lat, target.lng, target.alt);
        const d = streamPath(a, b, STREAM_BENDS[i]);
        streamGlowRefs.current[i]?.setAttribute('d', d);
        streamCoreRefs.current[i]?.setAttribute('d', d);
        const goal = (a.facing ? 1 : 0.25) * (b.facing ? 1 : 0.25) * (i === 0 ? 1 : 0.55);
        opacity[i] += (goal - opacity[i]) * 0.12;
        const group = streamGroupRefs.current[i];
        if (group) group.style.opacity = opacity[i].toFixed(3);
        if (i === 0) {
          setPoint(anchorRefs.current[1], b, b.facing ? 1 : 0.2);
          const grad = gradientRef.current;
          if (grad) {
            grad.setAttribute('x1', a.x);
            grad.setAttribute('y1', a.y);
            grad.setAttribute('x2', b.x);
            grad.setAttribute('y2', b.y);
          }
        }
      });

      const core = streamCoreRefs.current[0];
      if (!core) return;
      const length = core.getTotalLength();
      packetRefs.current.forEach((packet, k) => {
        if (!packet) return;
        const f = (t * 0.32 + k / packetRefs.current.length) % 1;
        const pt = core.getPointAtLength(f * length);
        packet.setAttribute('cx', pt.x.toFixed(1));
        packet.setAttribute('cy', pt.y.toFixed(1));
        packet.style.opacity = (Math.sin(f * Math.PI) * opacity[0]).toFixed(3);
      });
    };

    const tick = (now) => {
      const t = (now - start) / 1000;
      for (const shell of [leftShell, rightShell]) {
        shell.uniforms.uTime.value = t;
        shell.uniforms.uPulse.value *= 0.95;
      }
      updateStreams(t);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [leftShell, rightShell, leftPanelRef, rightPanelRef]);

  // --- render --------------------------------------------------------------

  return (
    <div className="bg-slate-950 text-slate-100 h-screen w-screen overflow-hidden flex flex-col relative">
      <style>{HUD_STYLES}</style>

      {/* Obsidian starfield */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-cover bg-center opacity-50"
        style={{ backgroundImage: `url(${TEXTURES.starfield})` }}
      />

      {/* TIER A: ambient hologram layer (full opacity in cinematic mode) */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <HologramFallback
          accent={body.accent}
          className={`mix-blend-screen transition-opacity duration-700 ${
            bgStatus === 'ready' ? 'opacity-0' : hologram ? 'opacity-100' : 'opacity-25'
          }`}
        />
        <video
          key={videoSrc}
          src={videoSrc}
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          {...bgVideoHandlers}
          className={`absolute inset-0 h-full w-full object-cover mix-blend-screen transition-[opacity,filter] duration-700 ${
            bgStatus !== 'ready'
              ? 'opacity-0'
              : hologram
                ? 'opacity-100'
                : isPulsing
                  ? 'opacity-60 brightness-150 saturate-150'
                  : 'opacity-20'
          }`}
        />
        {pulseId > 0 && (
          <div
            key={pulseId}
            className="tt-anim absolute inset-0 mix-blend-screen"
            style={{
              animation: `tt-flash ${PULSE_MS}ms ease-out forwards`,
              background: `radial-gradient(ellipse 45% 55% at 28% 50%, rgba(${hexToRgb(body.accent)},0.35), transparent 70%), radial-gradient(ellipse 45% 55% at 72% 50%, rgba(34,211,238,0.35), transparent 70%), linear-gradient(90deg, transparent 20%, rgba(186,230,253,0.18) 50%, transparent 80%)`,
            }}
          />
        )}
        <div
          className="absolute inset-0"
          style={{ background: 'radial-gradient(ellipse at center, transparent 55%, rgba(2,6,23,0.75) 100%)' }}
        />
      </div>

      <TopNav
        bodyId={bodyId}
        onBodyChange={switchBody}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        autoRotate={autoRotate}
        onToggleAutoRotate={() => setAutoRotate((v) => !v)}
        onResetCamera={resetCameras}
      />

      <main className="relative z-10 min-h-0 flex-1">
        {/* MAIN SPLIT VIEWPORT */}
        <div
          className={`absolute inset-0 flex flex-col transition-opacity md:flex-row ${
            hologram ? 'pointer-events-none opacity-0' : 'opacity-100'
          }`}
          style={{ transitionDuration: `${HOLOGRAM_FADE_MS}ms` }}
          aria-hidden={hologram}
        >
          <section
            ref={leftPanelRef}
            aria-label={`${body.label} candidate base globe`}
            className={`relative min-h-0 min-w-0 flex-1 border-b border-cyan-500/10 transition-opacity duration-300 md:border-b-0 md:border-r ${
              bodySwapping ? 'opacity-0' : 'opacity-100'
            }`}
          >
            {leftSize.width > 0 && leftSize.height > 0 && (
              <Globe
                ref={leftGlobeRef}
                width={leftSize.width}
                height={leftSize.height}
                backgroundColor="rgba(0,0,0,0)"
                globeImageUrl={body.surface}
                bumpImageUrl={body.bump}
                showAtmosphere={body.id === 'mars'}
                atmosphereColor={body.accent}
                atmosphereAltitude={0.08}
                globeOffset={leftOffset}
                onGlobeReady={() => setLeftReady(true)}
                onZoom={onLeftZoom}
                pointsData={body.bases}
                pointLat="lat"
                pointLng="lng"
                pointAltitude={leftPointAltitude}
                pointColor={leftPointColor}
                pointRadius={0.8}
                pointResolution={16}
                pointsTransitionDuration={600}
                pointLabel={baseLabel}
                onPointClick={handleSelectBase}
                ringsData={body.bases}
                ringLat="lat"
                ringLng="lng"
                ringColor={leftRingColor}
                ringMaxRadius={leftRingRadius}
                ringPropagationSpeed={2.2}
                ringRepeatPeriod={leftRingPeriod}
                htmlElementsData={leftTags}
                htmlLat="lat"
                htmlLng="lng"
                htmlAltitude="tagAlt"
                htmlElement={makeGeoTag}
                customLayerData={LEFT_SHELL_LAYER}
                customThreeObject={leftShellObject}
                customThreeObjectUpdate={updateShell}
              />
            )}
            <PanelLabel
              kicker={`Target body // ${body.label} · ${body.mission}`}
              title="Candidate Space Bases"
              accent={body.accent}
              povRef={leftPovRef}
            >
              <ul className="pointer-events-auto mt-3 space-y-1">
                {body.bases.map((base) => {
                  const active = base.id === selectedBase.id;
                  return (
                    <li key={base.id}>
                      <button
                        type="button"
                        onClick={() => handleSelectBase(base)}
                        aria-pressed={active}
                        className={`flex w-full items-center gap-2 rounded border px-2 py-1 text-left font-mono text-[10px] uppercase tracking-wider transition-colors ${
                          active
                            ? 'border-amber-200/60 bg-amber-200/10 text-amber-100'
                            : 'border-slate-600/40 bg-slate-950/40 text-slate-300 hover:border-slate-400/60 hover:text-slate-100'
                        }`}
                      >
                        <Crosshair className="h-3 w-3 shrink-0" style={{ color: active ? COLORS.selected : body.accent }} />
                        <span className="truncate">{base.name}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </PanelLabel>
          </section>

          <section ref={rightPanelRef} aria-label="Earth analog twin globe" className="relative min-h-0 min-w-0 flex-1">
            {rightSize.width > 0 && rightSize.height > 0 && (
              <Globe
                ref={rightGlobeRef}
                width={rightSize.width}
                height={rightSize.height}
                backgroundColor="rgba(0,0,0,0)"
                globeImageUrl={TEXTURES.earthSurface}
                bumpImageUrl={TEXTURES.earthBump}
                showAtmosphere
                atmosphereColor="#38bdf8"
                atmosphereAltitude={0.18}
                globeOffset={rightOffset}
                onGlobeReady={() => setRightReady(true)}
                onZoom={onRightZoom}
                pointsData={EARTH_ANALOGS}
                pointLat="lat"
                pointLng="lng"
                pointAltitude={rightPointAltitude}
                pointColor={analogColor}
                pointRadius={rightPointRadius}
                pointResolution={16}
                pointsTransitionDuration={800}
                pointLabel={analogLabel}
                onPointClick={focusAnalog}
                ringsData={EARTH_ANALOGS}
                ringLat="lat"
                ringLng="lng"
                ringColor={rightRingColor}
                ringMaxRadius={rightRingRadius}
                ringPropagationSpeed={rightRingSpeed}
                ringRepeatPeriod={900}
                arcsData={arcsData}
                arcColor={arcColor}
                arcStroke={arcStroke}
                arcDashLength={0.35}
                arcDashGap={0.18}
                arcDashAnimateTime={1600}
                arcAltitudeAutoScale={0.45}
                arcLabel="label"
                arcsTransitionDuration={600}
                htmlElementsData={rightTags}
                htmlLat="lat"
                htmlLng="lng"
                htmlAltitude="tagAlt"
                htmlElement={makeGeoTag}
                customLayerData={RIGHT_SHELL_LAYER}
                customThreeObject={rightShellObject}
                customThreeObjectUpdate={updateShell}
              />
            )}
            <PanelLabel
              kicker="Earth analog twin // 5 field sites"
              title="Terrain Harmonization"
              accent={COLORS.cyan}
              povRef={rightPovRef}
            />
          </section>

          {/* Live data streams: selected base -> top-3 Earth analogs */}
          <svg
            ref={svgRef}
            aria-hidden
            className={`pointer-events-none absolute inset-0 h-full w-full overflow-visible transition-opacity duration-300 ${
              isPulsing ? 'tt-streams--pulse' : ''
            }`}
            style={{ opacity: 0 }}
          >
            <defs>
              <linearGradient ref={gradientRef} id="tt-stream-grad" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor={body.accent} />
                <stop offset="50%" stopColor="#e0f2fe" />
                <stop offset="100%" stopColor={COLORS.cyan} />
              </linearGradient>
              <filter id="tt-stream-blur" filterUnits="userSpaceOnUse" x="0" y="0" width="100%" height="100%">
                <feGaussianBlur stdDeviation="5" />
              </filter>
            </defs>
            {STREAM_BENDS.map((_, i) => (
              <g key={i} ref={(el) => (streamGroupRefs.current[i] = el)} style={{ opacity: 0 }}>
                <path
                  ref={(el) => (streamGlowRefs.current[i] = el)}
                  className="tt-stream-glow"
                  fill="none"
                  stroke="url(#tt-stream-grad)"
                  strokeWidth={i === 0 ? 8 : 5}
                  strokeOpacity={0.45}
                  filter="url(#tt-stream-blur)"
                />
                <path
                  ref={(el) => (streamCoreRefs.current[i] = el)}
                  className="tt-stream-core"
                  fill="none"
                  stroke="url(#tt-stream-grad)"
                  strokeWidth={i === 0 ? 2 : 1.2}
                  strokeLinecap="round"
                  strokeDasharray={i === 0 ? '14 10' : '3 9'}
                  style={{ animationDuration: i === 0 ? '1.1s' : '1.8s' }}
                />
              </g>
            ))}
            {[0, 1, 2].map((k) => (
              <circle key={k} ref={(el) => (packetRefs.current[k] = el)} r={3.2} fill="#f8fafc" filter="url(#tt-stream-blur)" />
            ))}
            {[body.accent, COLORS.emerald].map((color, k) => (
              <circle
                key={k}
                ref={(el) => (anchorRefs.current[k] = el)}
                r={6}
                fill="none"
                stroke={color}
                strokeWidth={1.5}
                className="tt-anchor"
              />
            ))}
          </svg>
        </div>

        {/* TIER B: cinematic hologram HUD */}
        {hologram && (
          <HologramHud body={body} base={selectedBase} topMatch={topMatch} videoStatus={bgStatus} videoSrc={videoSrc} />
        )}

        <ControlDock weights={weights} onChange={setWeight} onCommit={commitWeights} topMatch={topMatch} />

        <TelemetryCard
          open={cardOpen}
          onToggle={() => setCardOpen((v) => !v)}
          body={body}
          base={selectedBase}
          scores={scores}
          onFocusAnalog={focusAnalog}
          videoSrc={videoSrc}
        />
      </main>
    </div>
  );
}

function setPoint(el, p, opacity) {
  if (!el) return;
  el.setAttribute('cx', p.x.toFixed(1));
  el.setAttribute('cy', p.y.toFixed(1));
  el.style.opacity = String(opacity);
}

// ---------------------------------------------------------------------------
// Top navigation
// ---------------------------------------------------------------------------

const BODY_OPTIONS = [
  { value: 'moon', label: 'MOON (Artemis)', icon: Moon, accent: BODIES.moon.accent },
  { value: 'mars', label: 'MARS (MRO)', icon: Satellite, accent: BODIES.mars.accent },
];

const VIEW_OPTIONS = [
  { value: '3d', label: '3D WEBGL ENGINE', title: 'Interactive 3D WebGL', icon: Box, accent: COLORS.cyan },
  { value: 'hologram', label: 'HOLOGRAM VIDEO FEED', title: 'Hologram stream', icon: Video, accent: COLORS.cyan },
];

function TopNav({ bodyId, onBodyChange, viewMode, onViewModeChange, autoRotate, onToggleAutoRotate, onResetCamera }) {
  return (
    <header className="relative z-30 flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-cyan-500/20 bg-slate-950/70 px-4 py-2.5 backdrop-blur-md">
      <div className="mr-auto flex min-w-0 items-center gap-3">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded border border-cyan-400/50 bg-cyan-400/10 shadow-[0_0_14px_rgba(34,211,238,0.45)]">
          <Orbit className="h-4 w-4 text-cyan-300" />
        </span>
        <h1 className="truncate font-display text-xs font-bold tracking-[0.18em] text-slate-50 sm:text-sm">
          TERRATWIN
          <span className="hidden font-medium text-cyan-300/80 xl:inline"> // EXTRATERRESTRIAL-TO-EARTH ANALOG ENGINE</span>
        </h1>
        <LiveClock />
      </div>

      <SegmentedControl label="Planetary body" value={bodyId} options={BODY_OPTIONS} onChange={onBodyChange} />
      <SegmentedControl label="View mode" value={viewMode} options={VIEW_OPTIONS} onChange={onViewModeChange} />

      <div className="flex items-center gap-1.5">
        <NavButton onClick={onResetCamera} icon={RotateCcw} label="Reset Camera" />
        <NavButton
          onClick={onToggleAutoRotate}
          icon={autoRotate ? Pause : Play}
          label={autoRotate ? 'Auto-Rotate On' : 'Auto-Rotate Off'}
          pressed={autoRotate}
        />
      </div>
    </header>
  );
}

function SegmentedControl({ label, value, options, onChange }) {
  return (
    <div role="group" aria-label={label} className="flex rounded-md border border-cyan-500/30 bg-slate-900/70 p-0.5">
      {options.map((opt) => {
        const active = opt.value === value;
        const Icon = opt.icon;
        return (
          <button
            key={opt.value}
            type="button"
            aria-pressed={active}
            aria-label={opt.label}
            title={opt.title ?? opt.label}
            onClick={() => onChange(opt.value)}
            className={`flex items-center gap-1.5 rounded px-2.5 py-1.5 font-mono text-[11px] font-semibold tracking-wider transition-colors ${
              active
                ? 'bg-cyan-400/15 text-cyan-100 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.5)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Icon className="h-3.5 w-3.5" style={active ? { color: opt.accent } : undefined} />
            <span className="hidden lg:inline">{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function NavButton({ onClick, icon: Icon, label, pressed }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-pressed={pressed}
      title={label}
      className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider transition-colors ${
        pressed
          ? 'border-emerald-400/50 bg-emerald-400/10 text-emerald-200'
          : 'border-cyan-500/30 bg-slate-900/70 text-slate-300 hover:border-cyan-400/60 hover:text-cyan-100'
      }`}
    >
      <Icon className="h-3.5 w-3.5" />
      <span className="hidden 2xl:inline">{label}</span>
    </button>
  );
}

function LiveClock() {
  useTicker(1000);
  const now = new Date();
  return (
    <span className="hidden shrink-0 rounded border border-slate-700/60 px-2 py-0.5 font-mono text-[10px] tabular-nums text-slate-400 md:inline">
      UTC {now.toISOString().slice(11, 19)}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Panel chrome
// ---------------------------------------------------------------------------

function PanelLabel({ kicker, title, accent, povRef, children }) {
  return (
    <div className="pointer-events-none absolute left-4 top-4 z-10 w-56 max-w-[calc(100%-2rem)] font-mono">
      <div className="truncate text-[10px] uppercase tracking-[0.22em]" style={{ color: accent }}>
        {kicker}
      </div>
      <div className="font-display text-sm font-bold tracking-[0.12em] text-slate-100">{title}</div>
      <div ref={povRef} className="mt-0.5 text-[10px] tabular-nums text-slate-400">
        CAM —
      </div>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bottom control dock
// ---------------------------------------------------------------------------

function ControlDock({ weights, onChange, onCommit, topMatch }) {
  return (
    <section
      aria-label="Analog weighting controls"
      className={`absolute bottom-4 left-1/2 z-20 w-[min(780px,calc(100%-2rem))] -translate-x-1/2 rounded-lg px-4 pb-3 pt-2.5 ${GLASS}`}
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 font-mono text-[10px] uppercase tracking-[0.18em]">
        <span className="flex items-center gap-1.5 text-cyan-300">
          <SlidersHorizontal className="h-3.5 w-3.5" />
          Analog weighting matrix
        </span>
        <span className="truncate text-slate-400">
          5-D weighted cosine ·{' '}
          <span className="text-emerald-300">
            #1 {topMatch.analog.name} {topMatch.score.toFixed(1)}%
          </span>
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-5 gap-y-2.5 lg:grid-cols-4">
        {WEIGHT_SLIDERS.map((def) => (
          <WeightSlider key={def.key} def={def} value={weights[def.key]} onChange={onChange} onCommit={onCommit} />
        ))}
      </div>
    </section>
  );
}

function WeightSlider({ def, value, onChange, onCommit }) {
  const id = useId();
  const Icon = def.icon;
  return (
    <div title={def.hint}>
      <label
        htmlFor={id}
        className="mb-1.5 flex items-center justify-between gap-2 font-mono text-[10px] uppercase tracking-wider text-slate-300"
      >
        <span className="flex min-w-0 items-center gap-1.5">
          <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: def.accent }} />
          <span className="truncate">{def.label}</span>
        </span>
        <span className="tabular-nums" style={{ color: def.accent }}>
          {value}%
        </span>
      </label>
      <input
        id={id}
        type="range"
        min={0}
        max={100}
        step={1}
        value={value}
        onChange={(e) => onChange(def.key, Number(e.target.value))}
        onPointerUp={onCommit}
        onKeyUp={onCommit}
        className="tt-range"
        style={{ '--tt-accent': def.accent, '--tt-fill': `${value}%` }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Right-side telemetry card
// ---------------------------------------------------------------------------

function TelemetryCard({ open, onToggle, body, base, scores, onFocusAnalog, videoSrc }) {
  const top = scores[0];
  const twin = top.analog;
  const rover = body.rover;
  const earthWeightN = rover.massKg * G0;
  const targetWeightN = earthWeightN * body.gravity;
  const offloadPct = (1 - body.gravity) * 100;

  return (
    <aside
      aria-label="Telemetry"
      className={`absolute right-4 top-4 z-20 flex w-[340px] max-w-[calc(100%-2rem)] flex-col rounded-lg ${GLASS} ${
        open ? 'max-h-[calc(100%-13rem)] lg:max-h-[calc(100%-10.5rem)] 2xl:max-h-[calc(100%-2rem)]' : ''
      }`}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex items-center justify-between gap-2 border-b border-cyan-500/20 px-3.5 py-2 font-mono text-[10px] uppercase tracking-[0.2em] text-cyan-300 hover:text-cyan-100"
      >
        <span className="flex items-center gap-1.5">
          <Radar className="h-3.5 w-3.5" />
          Telemetry // twin lock
        </span>
        <span className="flex items-center gap-2">
          <span className="rounded bg-emerald-400/15 px-1.5 py-0.5 text-emerald-300">{top.score.toFixed(1)}%</span>
          {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </span>
      </button>

      {open && (
        <div className="min-h-0 space-y-3 overflow-y-auto px-3.5 pb-3.5 pt-3">
          {/* TIER C: LIDAR picture-in-picture */}
          <LidarPip src={videoSrc} accent={body.accent} />

          <div className="grid grid-cols-[1fr_auto_1fr] items-start gap-2">
            <SiteColumn kicker={`${body.label} base`} accent={body.accent} site={base} />
            <MatchGauge score={top.score} />
            <SiteColumn kicker="Earth twin" accent={COLORS.emerald} site={twin} />
          </div>

          <MetricTable body={body} base={base} twin={twin} />

          <div>
            <SectionTitle icon={Activity}>Signature match</SectionTitle>
            <div className="space-y-1">
              {top.features.map((f) => (
                <Bar key={f.key} label={f.label} value={f.match * 100} color={COLORS.cyan} />
              ))}
            </div>
            {top.budgetDelta !== 0 && (
              <p className="mt-1 font-mono text-[10px] text-slate-400">
                Cosine {top.similarity.toFixed(1)}% · budget {top.budgetDelta >= 0 ? '+' : ''}
                {top.budgetDelta.toFixed(1)}
              </p>
            )}
          </div>

          <div>
            <SectionTitle icon={ScanLine}>Analog ranking</SectionTitle>
            <ol className="space-y-1">
              {scores.map((s) => (
                <li key={s.analog.id}>
                  <button
                    type="button"
                    onClick={() => onFocusAnalog(s.analog)}
                    className="group w-full rounded px-1.5 py-1 text-left hover:bg-cyan-400/10"
                  >
                    <div className="flex items-center justify-between gap-2 font-mono text-[10px]">
                      <span className={`truncate ${s.rank <= 3 ? 'text-slate-100' : 'text-slate-400'}`}>
                        #{s.rank} {s.analog.name}
                        {s.analog.isLocal && <span className="ml-1 text-lime-300">[LOCAL]</span>}
                      </span>
                      <span className="tabular-nums text-slate-300">{s.score.toFixed(1)}%</span>
                    </div>
                    <div className="mt-0.5 h-1 rounded-full bg-slate-700/60">
                      <div
                        className="h-full rounded-full transition-[width] duration-500"
                        style={{
                          width: `${s.score}%`,
                          background: s.rank === 1 ? COLORS.emerald : s.analog.isLocal ? COLORS.lime : COLORS.cyan,
                          opacity: s.rank <= 3 ? 1 : 0.5,
                        }}
                      />
                    </div>
                  </button>
                </li>
              ))}
            </ol>
          </div>

          <div className="rounded border border-amber-300/25 bg-amber-300/5 p-2.5">
            <SectionTitle icon={Weight}>Rover weight calibration</SectionTitle>
            <div className="font-mono text-[10px] text-slate-300">
              <div className="flex justify-between">
                <span>{rover.name}</span>
                <span className="tabular-nums">{fmtInt(rover.massKg)} kg</span>
              </div>
              <div className="mt-1.5 flex items-center gap-2">
                <span className="text-slate-400">1 g</span>
                <div className="relative h-1.5 flex-1 rounded-full bg-slate-700/70">
                  <div
                    className="absolute inset-y-0 left-0 rounded-full"
                    style={{ width: `${body.gravity * 100}%`, background: body.accent }}
                  />
                </div>
                <span style={{ color: body.accent }}>{body.gravityLabel}</span>
              </div>
              <div className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 tabular-nums">
                <span className="text-slate-400">Earth weight</span>
                <span className="text-right">{fmtInt(earthWeightN)} N</span>
                <span className="text-slate-400">{body.id === 'moon' ? 'Lunar' : 'Martian'} weight</span>
                <span className="text-right">{fmtInt(targetWeightN)} N</span>
                <span className="text-slate-400">Gravity offload rig</span>
                <span className="text-right text-amber-200">{offloadPct.toFixed(1)}%</span>
                <span className="text-slate-400">Equivalent test mass</span>
                <span className="text-right">{fmtInt(rover.massKg * body.gravity)} kg</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}

function SectionTitle({ icon: Icon, children }) {
  return (
    <div className="mb-1.5 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-slate-400">
      <Icon className="h-3 w-3 text-cyan-400" />
      {children}
    </div>
  );
}

function SiteColumn({ kicker, accent, site }) {
  return (
    <div className="min-w-0 font-mono">
      <div className="text-[9px] uppercase tracking-[0.2em]" style={{ color: accent }}>
        {kicker}
      </div>
      <div className="mt-0.5 font-display text-[11px] font-bold leading-tight text-slate-100">{site.name}</div>
      <div className="mt-0.5 text-[9px] tabular-nums text-slate-400">{fmtCoords(site.lat, site.lng)}</div>
    </div>
  );
}

function MatchGauge({ score }) {
  const r = 22;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative grid h-14 w-14 place-items-center" role="img" aria-label={`Overall match ${score.toFixed(1)} percent`}>
      <svg viewBox="0 0 56 56" className="absolute inset-0 -rotate-90">
        <circle cx="28" cy="28" r={r} fill="none" stroke="rgba(51,65,85,0.8)" strokeWidth="4" />
        <circle
          cx="28"
          cy="28"
          r={r}
          fill="none"
          stroke={COLORS.emerald}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - score / 100)}
          style={{ transition: 'stroke-dashoffset 500ms ease', filter: 'drop-shadow(0 0 4px rgba(52,211,153,0.7))' }}
        />
      </svg>
      <div className="text-center font-mono leading-none">
        <div className="text-[12px] font-bold tabular-nums text-emerald-300">{Math.round(score)}%</div>
        <div className="mt-0.5 text-[7px] uppercase tracking-widest text-slate-400">match</div>
      </div>
    </div>
  );
}

function MetricTable({ body, base, twin }) {
  const rows = [
    { icon: Mountain, label: 'Slope', a: `${base.slopeDeg}°`, b: `${twin.slopeDeg}°` },
    { icon: Pickaxe, label: 'Rock', a: base.rockType, b: twin.rockType },
    { icon: Thermometer, label: 'Temp', a: `${base.tempC} °C`, b: `${twin.tempC} °C` },
    { icon: Gauge, label: 'Gravity', a: body.gravityLabel, b: '1.00 g' },
  ];
  return (
    <table className="w-full table-fixed font-mono text-[10px]">
      <thead className="sr-only">
        <tr>
          <th>Metric</th>
          <th>Space base</th>
          <th>Earth twin</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(({ icon: Icon, label, a, b }) => (
          <tr key={label} className="border-t border-slate-700/50 align-top">
            <th scope="row" className="w-16 py-1 text-left font-normal text-slate-400">
              <span className="flex items-center gap-1">
                <Icon className="h-3 w-3 text-cyan-400/80" />
                {label}
              </span>
            </th>
            <td className="py-1 pr-2 text-slate-200">{a}</td>
            <td className="py-1 text-emerald-200">{b}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Bar({ label, value, color }) {
  return (
    <div className="flex items-center gap-2 font-mono text-[10px]">
      <span className="w-20 shrink-0 text-slate-400">{label}</span>
      <div className="h-1 flex-1 rounded-full bg-slate-700/60">
        <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${value}%`, background: color }} />
      </div>
      <span className="w-8 text-right tabular-nums text-slate-300">{Math.round(value)}</span>
    </div>
  );
}

// TIER C: compact LIDAR monitor, panning across the hologram render.
function LidarPip({ src, accent }) {
  const [status, handlers] = useVideoStatus(src);
  const tick = useTicker(500);
  const pointsPerSec = (1.18 + Math.sin(tick * 0.9) * 0.05 + Math.sin(tick * 2.3) * 0.02).toFixed(2);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between font-mono text-[9px] uppercase tracking-[0.18em]">
        <span className="text-cyan-300">Live LIDAR &amp; terrain harmonization feed</span>
        <span className="flex items-center gap-1 text-rose-300">
          <span className="tt-anim h-1.5 w-1.5 rounded-full bg-rose-400" style={{ animation: 'tt-blink 1.2s steps(2) infinite' }} />
          {status === 'ready' ? 'Live' : status === 'error' ? 'Synth' : 'Sync'}
        </span>
      </div>
      <div className="relative h-28 overflow-hidden rounded bg-slate-950/60">
        <HologramFallback accent={accent} className={`transition-opacity duration-500 ${status === 'ready' ? 'opacity-0' : 'opacity-100'}`} />
        <video
          key={src}
          src={src}
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          {...handlers}
          className={`tt-anim h-28 w-full object-cover rounded border border-cyan-500/40 mix-blend-screen transition-opacity duration-500 ${
            status === 'ready' ? 'opacity-100' : 'opacity-0'
          }`}
          style={{ animation: 'tt-pan 16s ease-in-out infinite' }}
        />
        <ScanReticle />
        <div className="pointer-events-none absolute bottom-1 left-1.5 font-mono text-[8px] uppercase tracking-wider text-cyan-200/90">
          {pointsPerSec}M pts/s · ±2 cm
        </div>
        {status === 'error' && (
          <div className="pointer-events-none absolute bottom-1 right-1.5 font-mono text-[8px] uppercase tracking-wider text-amber-200/90">
            procedural feed
          </div>
        )}
      </div>
    </div>
  );
}

function ScanReticle() {
  return (
    <div aria-hidden className="tt-anim pointer-events-none absolute inset-0 rounded border border-cyan-500/40">
      <div
        className="absolute inset-x-0 h-6"
        style={{
          background: 'linear-gradient(to bottom, transparent, rgba(34,211,238,0.35) 85%, rgba(165,243,252,0.9))',
          animation: 'tt-sweep 2.6s linear infinite',
        }}
      />
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full" fill="none">
        <g stroke="rgba(165,243,252,0.85)" strokeWidth="0.8" vectorEffect="non-scaling-stroke">
          <path d="M3 14V3h11M86 3h11v11M97 86v11H86M14 97H3V86" vectorEffect="non-scaling-stroke" />
          <path d="M50 38v8M50 54v8M38 50h8M54 50h8" vectorEffect="non-scaling-stroke" />
        </g>
      </svg>
      <div className="tt-scanlines absolute inset-0" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// TIER B: cinematic hologram HUD
// ---------------------------------------------------------------------------

function HologramHud({ body, base, topMatch, videoStatus, videoSrc }) {
  const tick = useTicker(250);
  const startRef = useRef(Date.now());
  const elapsed = Math.floor((Date.now() - startRef.current) / 1000);
  const met = `${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}`;
  const downlink = (412 + Math.sin(tick * 0.6) * 18 + Math.sin(tick * 1.7) * 6).toFixed(0);
  const lidar = (1.18 + Math.sin(tick * 0.9) * 0.05).toFixed(2);

  return (
    <div aria-hidden className="tt-anim pointer-events-none absolute inset-0 z-20 overflow-hidden">
      <div className="tt-scanlines absolute inset-0" />
      <div
        className="absolute inset-x-0 h-32"
        style={{
          background: 'linear-gradient(to bottom, transparent, rgba(34,211,238,0.08) 80%, rgba(165,243,252,0.18))',
          animation: 'tt-sweep 7s linear infinite',
        }}
      />
      <div className="absolute left-4 top-4 h-10 w-10 border-l-2 border-t-2 border-cyan-400/60" />
      <div className="absolute right-4 top-4 h-10 w-10 border-r-2 border-t-2 border-cyan-400/60" />
      <div className="absolute bottom-4 left-4 h-10 w-10 border-b-2 border-l-2 border-cyan-400/60" />
      <div className="absolute bottom-4 right-4 h-10 w-10 border-b-2 border-r-2 border-cyan-400/60" />

      <Reticle x="27%" y="44%" color={body.accent} label="LIDAR grid lock" sub={base.name} />
      <Reticle x="73%" y="44%" color={COLORS.cyan} label="Analog pin lock" sub={topMatch.analog.name} />

      <div className="absolute left-1/2 top-[18%] -translate-x-1/2 text-center font-mono text-[10px] uppercase tracking-[0.3em]">
        <div className="text-slate-400">Data link // weighted cosine</div>
        <div className="mt-1 font-display text-2xl font-bold tracking-[0.12em] text-emerald-300 drop-shadow-[0_0_12px_rgba(52,211,153,0.6)]">
          {topMatch.score.toFixed(1)}%
        </div>
      </div>

      <div className={`absolute left-8 top-8 w-64 max-w-[calc(100%-4rem)] rounded-md p-3 font-mono text-[10px] ${GLASS}`}>
        <div className="mb-1.5 flex items-center gap-1.5 uppercase tracking-[0.2em] text-cyan-300">
          <Video className="h-3.5 w-3.5" />
          Hologram stream
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 tabular-nums">
          <dt className="text-slate-400">SOURCE</dt>
          <dd className="truncate text-slate-200">{videoStatus === 'error' ? 'procedural fallback' : videoSrc}</dd>
          <dt className="text-slate-400">MET</dt>
          <dd className="text-slate-200">T+{met}</dd>
          <dt className="text-slate-400">TARGET</dt>
          <dd className="truncate" style={{ color: body.accent }}>
            {base.name}
          </dd>
          <dt className="text-slate-400" />
          <dd className="text-slate-400">{fmtCoords(base.lat, base.lng)}</dd>
          <dt className="text-slate-400">TWIN</dt>
          <dd className="truncate text-emerald-300">{topMatch.analog.name}</dd>
          <dt className="text-slate-400" />
          <dd className="text-slate-400">{fmtCoords(topMatch.analog.lat, topMatch.analog.lng)}</dd>
          <dt className="text-slate-400">LIDAR</dt>
          <dd className="text-slate-200">{lidar}M pts/s</dd>
          <dt className="text-slate-400">DOWNLINK</dt>
          <dd className="text-slate-200">{downlink} Mbps</dd>
        </dl>
      </div>
    </div>
  );
}

function Reticle({ x, y, color, label, sub }) {
  return (
    <div className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: x, top: y, color }}>
      <svg viewBox="0 0 200 200" className="h-[min(34vh,260px)] w-[min(34vh,260px)]" fill="none" stroke="currentColor">
        <circle cx="100" cy="100" r="94" strokeOpacity="0.25" />
        <g className="tt-spin" style={{ animationDuration: '18s' }}>
          <circle cx="100" cy="100" r="80" strokeDasharray="4 10" strokeOpacity="0.7" />
        </g>
        <g className="tt-spin" style={{ animationDuration: '9s', animationDirection: 'reverse' }}>
          <path d="M100 14 A86 86 0 0 1 186 100" strokeWidth="2" />
          <path d="M100 186 A86 86 0 0 1 14 100" strokeWidth="2" />
        </g>
        <path d="M100 0v22M100 178v22M0 100h22M178 100h22" strokeWidth="1.5" />
        <circle cx="100" cy="100" r="3" fill="currentColor" />
      </svg>
      <div className="absolute left-1/2 top-full mt-2 -translate-x-1/2 whitespace-nowrap text-center font-mono text-[10px] uppercase tracking-[0.22em]">
        <div>{label}</div>
        <div className="mt-0.5 normal-case tracking-wider text-slate-300/80">{sub}</div>
      </div>
    </div>
  );
}

// Procedural stand-in for the hologram render while the video loads (or if it's missing):
// orange LIDAR-gridded orb, cyan Earth orb, and a dashed data stream between them.
function HologramFallback({ accent, className = '' }) {
  const gradId = `tt-fallback-${useId().replace(/:/g, '')}`;
  const rgb = hexToRgb(accent);
  return (
    <div aria-hidden className={`tt-anim pointer-events-none absolute inset-0 overflow-hidden ${className}`}>
      <div
        className="absolute -inset-x-1/2 -bottom-[10%] h-[55%] origin-bottom"
        style={{
          transform: 'perspective(500px) rotateX(64deg)',
          backgroundImage:
            'linear-gradient(rgba(34,211,238,0.35) 1px, transparent 1px), linear-gradient(90deg, rgba(34,211,238,0.35) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
          animation: 'tt-grid-drift 3s linear infinite',
          maskImage: 'linear-gradient(to top, black, transparent)',
          WebkitMaskImage: 'linear-gradient(to top, black, transparent)',
        }}
      />
      <FallbackOrb x="27%" rgb={rgb} grid />
      <FallbackOrb x="73%" rgb="34,211,238" />
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
        <defs>
          <linearGradient id={gradId} x1="0" x2="1" y1="0" y2="0">
            <stop offset="0.25" stopColor={accent} />
            <stop offset="0.5" stopColor="#e0f2fe" />
            <stop offset="0.75" stopColor={COLORS.cyan} />
          </linearGradient>
        </defs>
        {[22, 30, 38].map((lift, i) => (
          <path
            key={lift}
            d={`M27 46 C 40 ${46 - lift}, 60 ${46 - lift}, 73 46`}
            fill="none"
            stroke={`url(#${gradId})`}
            strokeWidth={i === 0 ? 2 : 1}
            strokeOpacity={i === 0 ? 0.9 : 0.45}
            strokeDasharray="6 8"
            vectorEffect="non-scaling-stroke"
            className="tt-stream-core"
          />
        ))}
      </svg>
    </div>
  );
}

function FallbackOrb({ x, rgb, grid = false }) {
  return (
    <div
      className="absolute top-[46%] aspect-square w-[24%] overflow-hidden rounded-full"
      style={{
        left: x,
        transform: 'translate(-50%, -50%)',
        background: `radial-gradient(circle at 35% 35%, rgba(${rgb},0.55), rgba(${rgb},0.12) 60%, transparent 72%)`,
        boxShadow: `0 0 60px rgba(${rgb},0.35), inset 0 0 30px rgba(${rgb},0.35)`,
        animation: 'tt-orb 4s ease-in-out infinite',
      }}
    >
      {grid && (
        <div
          className="absolute inset-0 rounded-full"
          style={{
            backgroundImage: `repeating-linear-gradient(0deg, rgba(${rgb},0.4) 0 1px, transparent 1px 12%), repeating-linear-gradient(90deg, rgba(${rgb},0.3) 0 1px, transparent 1px 12%)`,
          }}
        />
      )}
      <div
        className="absolute inset-x-0 h-[14%]"
        style={{
          background: `linear-gradient(to bottom, transparent, rgba(${rgb},0.85))`,
          animation: `tt-sweep ${grid ? 2.8 : 4.2}s linear infinite`,
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Scoped styles (keyframes, range inputs, globe tags & tooltips)
// ---------------------------------------------------------------------------

const HUD_STYLES = `
@keyframes tt-dash { to { stroke-dashoffset: -96; } }
@keyframes tt-sweep { from { top: -20%; } to { top: 105%; } }
@keyframes tt-spin { to { transform: rotate(360deg); } }
@keyframes tt-flash { 0% { opacity: 0; } 12% { opacity: 1; } 100% { opacity: 0; } }
@keyframes tt-blink { 50% { opacity: 0.2; } }
@keyframes tt-grid-drift { to { background-position: 0 40px; } }
@keyframes tt-pan { 0%, 100% { object-position: 18% 50%; } 50% { object-position: 82% 50%; } }
@keyframes tt-orb {
  0%, 100% { transform: translate(-50%, -50%) scale(1); }
  50% { transform: translate(-50%, -50%) scale(1.05); }
}
@keyframes tt-anchor { 0%, 100% { r: 5; } 50% { r: 9; } }

.tt-stream-core { animation: tt-dash 1.4s linear infinite; }
.tt-stream-glow { transition: stroke-width 300ms ease; }
.tt-streams--pulse .tt-stream-glow { stroke-width: 16px; stroke-opacity: 0.8; }
.tt-anchor { animation: tt-anchor 1.6s ease-in-out infinite; }
.tt-spin { transform-box: fill-box; transform-origin: center; animation: tt-spin 12s linear infinite; }
.tt-scanlines {
  background-image: repeating-linear-gradient(to bottom, rgba(148, 163, 184, 0.06) 0 1px, transparent 1px 3px);
}

.tt-range {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 4px;
  border-radius: 9999px;
  background: linear-gradient(90deg, var(--tt-accent) var(--tt-fill), rgba(51, 65, 85, 0.9) var(--tt-fill));
  cursor: pointer;
  outline: none;
}
.tt-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #0f172a;
  border: 2px solid var(--tt-accent);
  box-shadow: 0 0 10px var(--tt-accent);
}
.tt-range::-moz-range-thumb {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #0f172a;
  border: 2px solid var(--tt-accent);
  box-shadow: 0 0 10px var(--tt-accent);
}
.tt-range:focus-visible { box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.35); }

.tt-geo-tag { position: relative; width: 0; height: 0; pointer-events: none; }
.tt-geo-tag > div {
  position: absolute;
  left: 0;
  bottom: 14px;
  transform: translateX(-50%);
  white-space: nowrap;
  padding: 3px 7px;
  border: 1px solid var(--tt-tag);
  border-radius: 3px;
  background: rgba(2, 6, 23, 0.8);
  color: var(--tt-tag);
  font: 600 10px/1.2 "JetBrains Mono", ui-monospace, monospace;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  box-shadow: 0 0 14px -2px var(--tt-tag);
}
.tt-geo-tag > div::after {
  content: "";
  position: absolute;
  left: 50%;
  top: 100%;
  width: 1px;
  height: 12px;
  background: var(--tt-tag);
}

.tt-tip { font: 500 11px/1.5 "JetBrains Mono", ui-monospace, monospace; color: #e2e8f0; }
.tt-tip b { font-family: Orbitron, ui-sans-serif, sans-serif; letter-spacing: 0.06em; color: var(--tt-tip, #67e8f9); }
.tt-tip i { color: #94a3b8; }

@media (prefers-reduced-motion: reduce) {
  .tt-anim, .tt-anim *, .tt-stream-core, .tt-spin, .tt-anchor { animation: none !important; }
}
`;
