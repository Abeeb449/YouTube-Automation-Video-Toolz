/**
 * Maps for the live 3D stage, drawn from Natural Earth coastlines (public domain, the world-atlas package):
 *   map    a stretch of coast as a lit table-top model the camera flies over: raised land, a glowing coastline,
 *          moving water, pins, routes that draw themselves, zones, and streams of dots (animals on the move)
 *   globe  the whole Earth, turning, with pins and arcs
 * Places are given as [longitude, latitude]; `env.geo` turns them into points of the 3D scene, so labels and the
 * camera can be pinned to real places.
 */
import * as THREE from 'three';
import {geoEquirectangular, geoMercator, geoPath} from 'd3-geo';
import {feature} from 'topojson-client';
import land10 from 'world-atlas/land-10m.json';
import land50 from 'world-atlas/land-50m.json';
import {clamp, ease, keyTime, ramp, rnd} from './math';
import type {Env, EnvSpec} from './world';
import {NOISE_GLSL} from './world';

type LL = [number, number];
type When = {at?: number; u?: number};
export type Pin = When & {lon: number; lat: number; color?: string; h?: number; pulse?: boolean};
export type Route = When & {points: LL[]; d?: number; color?: string; width?: number; arc?: number; out?: number};
export type Zone = When & {lon: number; lat: number; km: number; color?: string; out?: number; alpha?: number};
export type Flow = When & {from: LL; to: LL; d?: number; n?: number; spread?: number; color?: string; via?: LL[]; loop?: boolean; out?: number};
export type MapSpec = {bbox?: [LL, LL]; pins?: Pin[]; routes?: Route[]; zones?: Zone[]; flows?: Flow[]};

export type GeoEnv = Env & {
  geo: (lon: number, lat: number, h?: number) => THREE.Vector3;
  /** where a camera stands to look at a place: distance, height angle (90 = straight down), compass bearing */
  view: (over: LL, dist: number, tilt: number, bearing: number) => {pos: THREE.Vector3; look: THREE.Vector3};
};

const YELLOW = '#FDE302';
const ORANGE = '#FB9002';
const col = (h: string) => new THREE.Color(h);
const landOf = (topo: any) => feature(topo, topo.objects.land) as any;

const COLOR_OUT = '\n#include <colorspace_fragment>\n';

/* -------------------------------------------------------------------------------------------- shared bits */
const makePins = (pins: Pin[], geo: GeoEnv['geo'], up: (lon: number, lat: number) => THREE.Vector3, size: number, dur: number) => {
  const group = new THREE.Group();
  const items = pins.map((p) => {
    const g = new THREE.Group();
    const c = col(p.color ?? YELLOW);
    const h = (p.h ?? 1) * size * 5;
    const stem = new THREE.Mesh(new THREE.CylinderGeometry(size * 0.06, size * 0.06, h, 8), new THREE.MeshBasicMaterial({color: c, fog: false}));
    stem.position.y = h / 2;
    const head = new THREE.Mesh(new THREE.SphereGeometry(size * 0.42, 20, 14), new THREE.MeshBasicMaterial({color: c, fog: false}));
    head.position.y = h;
    const ringMat = new THREE.MeshBasicMaterial({color: c, transparent: true, opacity: 0.8, side: THREE.DoubleSide, depthWrite: false, fog: false});
    const ring = new THREE.Mesh(new THREE.RingGeometry(size * 0.85, size * 1.0, 48), ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = size * 0.05;
    const dot = new THREE.Mesh(new THREE.CircleGeometry(size * 0.3, 24), new THREE.MeshBasicMaterial({color: c, side: THREE.DoubleSide, fog: false}));
    dot.rotation.x = -Math.PI / 2;
    dot.position.y = size * 0.06;
    g.add(stem, head, ring, dot);
    g.position.copy(geo(p.lon, p.lat, 0));
    g.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), up(p.lon, p.lat));
    group.add(g);
    return {g, stem, head, ring, ringMat, t0: keyTime(p, dur, 0), pulse: p.pulse !== false, h};
  });
  const update = (t: number) => {
    for (const it of items) {
      const p = ramp(t, it.t0, 0.55, 'back');
      it.g.visible = t >= it.t0;
      it.stem.scale.y = Math.max(0.001, p);
      it.stem.position.y = (it.h * p) / 2;
      it.head.position.y = it.h * p;
      it.head.scale.setScalar(0.6 + 0.4 * p);
      const k = ((t - it.t0) * 0.55) % 1;
      it.ring.scale.setScalar(it.pulse ? 1 + 2.4 * k : 1);
      it.ringMat.opacity = it.pulse ? 0.85 * (1 - k) : 0.8;
    }
  };
  return {group, update};
};

const makeRoutes = (routes: Route[], path: (r: Route) => THREE.Vector3[], size: number, dur: number) => {
  const group = new THREE.Group();
  const items = routes.map((r) => {
    const pts = path(r);
    const curve = new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.3);
    const geo_ = new THREE.TubeGeometry(curve, Math.max(40, pts.length * 14), size * 0.085 * (r.width ?? 1), 8, false);
    const mat = new THREE.ShaderMaterial({
      transparent: true, fog: false, depthWrite: false,
      uniforms: {uProg: {value: 0}, uColor: {value: col(r.color ?? YELLOW)}, uTime: {value: 0}, uFade: {value: 1}},
      vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `uniform float uProg; uniform vec3 uColor; uniform float uTime; uniform float uFade; varying vec2 vUv;
        void main(){ if (vUv.x > uProg) discard; float head = smoothstep(0.06, 0.0, uProg - vUv.x); float flow = 0.75 + 0.25 * sin(vUv.x * 90.0 - uTime * 5.0);
        gl_FragColor = vec4(mix(uColor * flow, vec3(1.0), head * 0.7), uFade);${COLOR_OUT}}`,
    });
    const mesh = new THREE.Mesh(geo_, mat);
    mesh.frustumCulled = false;
    mesh.renderOrder = 4;
    group.add(mesh);
    return {mat, t0: keyTime(r, dur, 0), d: r.d ?? 1.6, out: r.out};
  });
  const update = (t: number) => {
    for (const it of items) {
      it.mat.uniforms.uProg.value = ramp(t, it.t0, it.d, 'inOut');
      it.mat.uniforms.uTime.value = t;
      it.mat.uniforms.uFade.value = typeof it.out === 'number' ? 1 - ramp(t, it.out, 0.6, 'soft') : 1;
    }
  };
  return {group, update};
};

/* ------------------------------------------------------------------------------------------- table-top map */
export const buildMap = (spec: EnvSpec & {map?: MapSpec}): GeoEnv => {
  const m = spec.map ?? {};
  const scene = new THREE.Scene();
  const shared = {uTime: {value: 0}, uCaustic: {value: 0}, uCausticColor: {value: col('#ffffff')}, uFogColor: {value: col('#03090f')}};
  scene.background = col('#02070c');
  scene.fog = new THREE.FogExp2(0x02070c, 0.0042);
  const CW = 4096;
  const CH = 2304;
  const PW = 160;
  const PH = (PW * CH) / CW;
  const bbox = m.bbox ?? [[16, -36], [28, -30]];
  const proj = geoMercator();
  const [[w, s], [e, n]] = bbox;
  proj.fitExtent([[0, 0], [CW, CH]], {type: 'MultiPoint', coordinates: [[w, s], [e, s], [e, n], [w, n], [(w + e) / 2, s], [(w + e) / 2, n]]} as any);
  const cv = document.createElement('canvas');
  cv.width = CW;
  cv.height = CH;
  const ctx = cv.getContext('2d')!;
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, CW, CH);
  // The coastline is drawn point by point on the flat picture. (Left to the globe-aware drawing, three shapes of the
  // detailed data that are wound backwards would fill the sea instead of the land.)
  const land = landOf(land10);
  const polys: number[][][][] = [];
  for (const f of (land.features ?? [land])) {
    const gm = f.geometry ?? f;
    if (gm.type === 'Polygon') polys.push(gm.coordinates);
    else if (gm.type === 'MultiPolygon') polys.push(...gm.coordinates);
  }
  const near = polys.filter((poly) => poly[0].some((p) => p[0] > w - 25 && p[0] < e + 25 && p[1] > s - 20 && p[1] < n + 20));
  const trace = () => {
    ctx.beginPath();
    for (const poly of near) for (const ring of poly) {
      let first = true;
      for (const pt of ring) {
        const q = proj([pt[0], Math.max(-84, Math.min(84, pt[1]))]);
        if (!q) continue;
        if (first) { ctx.moveTo(q[0], q[1]); first = false; } else ctx.lineTo(q[0], q[1]);
      }
      ctx.closePath();
    }
  };
  ctx.globalCompositeOperation = 'lighter';
  // blue: how close the shore is (shallow water glows); red: land; green: the coastline itself
  ctx.filter = 'blur(46px)';
  ctx.fillStyle = '#0000ff';
  trace(); ctx.fill('evenodd');
  ctx.filter = 'none';
  ctx.fillStyle = '#ff0000';
  trace(); ctx.fill('evenodd');
  ctx.strokeStyle = '#00ff00';
  ctx.lineWidth = 5;
  ctx.lineJoin = 'round';
  trace(); ctx.stroke();
  const tex = new THREE.CanvasTexture(cv);
  tex.anisotropy = 8;
  tex.colorSpace = THREE.NoColorSpace;

  const geo = (lon: number, lat: number, h = 0) => {
    const p = proj([lon, lat]) ?? [CW / 2, CH / 2];
    return new THREE.Vector3((p[0] / CW - 0.5) * PW, h, (p[1] / CH - 0.5) * PH);
  };
  const kmUnit = geo(w, s - 1).distanceTo(geo(w, s)) / 111.2;       // scene units to a kilometre

  // the sea: dark, moving, brighter over the shallows along the shore
  const seaMat = new THREE.ShaderMaterial({
    uniforms: {uTime: shared.uTime, uMap: {value: tex}, uSize: {value: new THREE.Vector2(PW, PH)}},
    vertexShader: `varying vec3 vW; varying float vDist; void main(){ vec4 wp = modelMatrix * vec4(position, 1.0); vW = wp.xyz; vec4 mv = viewMatrix * wp; vDist = -mv.z; gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform float uTime; uniform sampler2D uMap; uniform vec2 uSize; varying vec3 vW; varying float vDist;
      ${NOISE_GLSL}
      void main(){
        vec2 uv = vW.xz / uSize + 0.5; uv.y = 1.0 - uv.y;
        float inside = step(0.0, uv.x) * step(uv.x, 1.0) * step(0.0, uv.y) * step(uv.y, 1.0);
        float shelf = texture2D(uMap, uv).b * inside;
        float wave = ytNoise(vec2(vW.x * 0.5 + uTime * 0.25, vW.z * 1.4 - uTime * 0.12)) * 0.6 + ytNoise(vec2(vW.x * 1.7 - uTime * 0.3, vW.z * 3.1)) * 0.4;
        vec3 deep = vec3(0.004, 0.022, 0.045); vec3 shallow = vec3(0.012, 0.16, 0.22);
        vec3 c = mix(deep, shallow, smoothstep(0.05, 0.75, shelf));
        c += vec3(0.02, 0.07, 0.09) * smoothstep(0.55, 0.9, wave) * (0.25 + shelf);
        vec2 g = abs(fract(vW.xz / 10.0 - 0.5) - 0.5) / fwidth(vW.xz / 10.0);
        c += vec3(0.05, 0.12, 0.16) * (1.0 - min(min(g.x, g.y), 1.0)) * 0.22;
        float f = 1.0 - exp(-0.00005 * vDist * vDist);
        vec2 q = clamp(uv, 0.0, 1.0);
        float edge = smoothstep(0.0, 0.14, min(min(q.x, 1.0 - q.x), min(q.y, 1.0 - q.y)));
        c = mix(vec3(0.0015, 0.006, 0.011), c, 0.12 + 0.88 * edge);
        gl_FragColor = vec4(mix(c, vec3(0.0015, 0.006, 0.011), clamp(f, 0.0, 1.0)), 1.0);${COLOR_OUT}}`,
  });
  const sea = new THREE.Mesh(new THREE.PlaneGeometry(900, 900), seaMat);
  sea.rotation.x = -Math.PI / 2;
  sea.frustumCulled = false;
  scene.add(sea);
  // the land: a slab with a lit top and a bright edge where it meets the sea
  const TOP = 0.9;
  const landMat = (side: number) => new THREE.ShaderMaterial({
    transparent: true,
    uniforms: {uMap: {value: tex}, uSide: {value: side}, uTime: shared.uTime},
    vertexShader: `varying vec2 vUv; varying vec3 vW; varying float vDist; void main(){ vUv = uv; vec4 wp = modelMatrix * vec4(position, 1.0); vW = wp.xyz; vec4 mv = viewMatrix * wp; vDist = -mv.z; gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform sampler2D uMap; uniform float uSide; uniform float uTime; varying vec2 vUv; varying vec3 vW; varying float vDist;
      ${NOISE_GLSL}
      void main(){
        vec4 m = texture2D(uMap, vUv);
        if (m.r < 0.5) discard;
        vec3 c;
        if (uSide > 0.5) { c = vec3(0.012, 0.022, 0.03); }
        else {
          float h = ytFbm(vW.xz * 0.5); float h2 = ytFbm(vW.xz * 0.5 + vec2(0.07, 0.05));
          float shade = clamp(0.5 + (h - h2) * 5.0, 0.0, 1.0);
          c = mix(vec3(0.020, 0.034, 0.042), vec3(0.046, 0.070, 0.082), shade);
          c += vec3(0.75, 0.95, 1.0) * smoothstep(0.25, 0.9, m.g) * 0.85;
        }
        float f = 1.0 - exp(-0.00005 * vDist * vDist);
        float edge = smoothstep(0.0, 0.14, min(min(vUv.x, 1.0 - vUv.x), min(vUv.y, 1.0 - vUv.y)));
        c = mix(vec3(0.0015, 0.006, 0.011), c, 0.12 + 0.88 * edge);
        gl_FragColor = vec4(mix(c, vec3(0.0015, 0.006, 0.011), clamp(f, 0.0, 1.0)), 1.0);${COLOR_OUT}}`,
  });
  const plane = new THREE.PlaneGeometry(PW, PH);
  for (let i = 0; i <= 6; i++) {
    const layer = new THREE.Mesh(plane, landMat(i < 6 ? 1 : 0));
    layer.rotation.x = -Math.PI / 2;
    layer.position.y = (TOP * i) / 6;
    layer.renderOrder = 1;
    scene.add(layer);
  }
  const up = () => new THREE.Vector3(0, 1, 0);
  const dur = (spec as any).__dur ?? 10;
  const size = (spec as any).__size ?? 1;
  const pins = makePins(m.pins ?? [], (lo, la) => geo(lo, la, TOP), up, size, dur);
  scene.add(pins.group);
  const routes = makeRoutes(m.routes ?? [], (r) => r.points.map((p, i) => geo(p[0], p[1], TOP + 0.35 + (r.arc ?? 0) * size * Math.sin((Math.PI * i) / Math.max(1, r.points.length - 1)))), size, dur);
  scene.add(routes.group);
  // zones: a soft disc with a ring that breathes
  const zones = (m.zones ?? []).map((z) => {
    const r = z.km * kmUnit;
    const mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, fog: false, side: THREE.DoubleSide,
      uniforms: {uColor: {value: col(z.color ?? ORANGE)}, uTime: shared.uTime, uOn: {value: 0}},
      vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `uniform vec3 uColor; uniform float uTime; uniform float uOn; varying vec2 vUv;
        void main(){ float d = length(vUv - 0.5) * 2.0; if (d > 1.0) discard; float ring = smoothstep(0.9, 0.97, d) * smoothstep(1.0, 0.985, d); float wave = smoothstep(0.03, 0.0, abs(d - fract(uTime * 0.35)));
        gl_FragColor = vec4(uColor, (0.16 * (1.0 - d * 0.5) + ring * 0.9 + wave * 0.35 * (1.0 - d)) * uOn);${COLOR_OUT}}`,
    });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(r * 2, r * 2), mat);
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.copy(geo(z.lon, z.lat, TOP + 0.12));
    mesh.renderOrder = 3;
    scene.add(mesh);
    return {mat, mesh, t0: keyTime(z, dur, 0), out: z.out, alpha: z.alpha ?? 1};
  });
  // flows: animals on the move, as a stream of glowing dots
  const dotGeo = new THREE.SphereGeometry(size * 0.2, 10, 8);
  const flows = (m.flows ?? []).map((f, fi) => {
    const nDots = f.n ?? 30;
    const mesh = new THREE.InstancedMesh(dotGeo, new THREE.MeshBasicMaterial({color: col(f.color ?? '#F7F7F8'), fog: false, transparent: true}), nDots);
    mesh.frustumCulled = false;
    mesh.renderOrder = 5;
    scene.add(mesh);
    const pts = [f.from, ...(f.via ?? []), f.to].map((p) => geo(p[0], p[1], TOP + 0.3));
    const curve = pts.length > 2 ? new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.4) : new THREE.LineCurve3(pts[0], pts[1]);
    return {mesh, curve, n: nDots, t0: keyTime(f, dur, 0), d: f.d ?? 4, spread: (f.spread ?? 12) * kmUnit, fi, loop: !!f.loop, out: f.out};
  });
  const m4 = new THREE.Matrix4();
  const tmp = new THREE.Vector3();
  const env: GeoEnv = {
    scene, shared, exposure: spec.exposure ?? 1.0, underwater: false,
    geo: (lo, la, h = 0) => geo(lo, la, TOP + h),
    view: (over, dist, tilt, bearing) => {
      const look = geo(over[0], over[1], TOP);
      const el = (tilt * Math.PI) / 180;
      const b = (bearing * Math.PI) / 180;
      return {look, pos: look.clone().add(new THREE.Vector3(Math.cos(el) * Math.sin(b) * dist, Math.sin(el) * dist, Math.cos(el) * Math.cos(b) * dist))};
    },
    update: (t, cam) => {
      shared.uTime.value = t;
      sea.position.set(Math.round(cam.position.x / 10) * 10, 0, Math.round(cam.position.z / 10) * 10);
      pins.update(t);
      routes.update(t);
      for (const z of zones) {
        z.mat.uniforms.uOn.value = z.alpha * ramp(t, z.t0, 0.7, 'out') * (typeof z.out === 'number' ? 1 - ramp(t, z.out, 0.6, 'soft') : 1);
        z.mesh.scale.setScalar(0.6 + 0.4 * ramp(t, z.t0, 0.7, 'back'));
        z.mesh.visible = t >= z.t0;
      }
      for (const f of flows) {
        for (let i = 0; i < f.n; i++) {
          const start = f.t0 + (i / f.n) * f.d * 0.6;
          let u = (t - start) / (f.d * 0.55);
          if (f.loop) u = ((u % 1) + 1) % 1;
          const k = clamp(u);
          f.curve.getPoint(ease('inOut', k), tmp);
          const side = (rnd(i * 3.7 + f.fi * 11) - 0.5) * f.spread * Math.sin(Math.PI * k);
          const along = (rnd(i * 5.3 + f.fi * 7) - 0.5) * f.spread * 0.6;
          tmp.x += along; tmp.z += side;
          const on = t >= start && !(typeof f.out === 'number' && t >= f.out) ? 1 : 0;
          m4.makeScale(on, on, on);
          m4.setPosition(tmp);
          f.mesh.setMatrixAt(i, m4);
        }
        f.mesh.instanceMatrix.needsUpdate = true;
      }
    },
  };
  scene.add(new THREE.AmbientLight(0xffffff, 1));
  return env;
};

/* ---------------------------------------------------------------------------------------------- the globe */
export const buildGlobe = (spec: EnvSpec & {map?: MapSpec}): GeoEnv => {
  const m = spec.map ?? {};
  const scene = new THREE.Scene();
  const shared = {uTime: {value: 0}, uCaustic: {value: 0}, uCausticColor: {value: col('#ffffff')}, uFogColor: {value: col('#02060a')}};
  scene.background = col('#010408');
  const R = 40;
  const CW = 4096;
  const CH = 2048;
  const cv = document.createElement('canvas');
  cv.width = CW;
  cv.height = CH;
  const ctx = cv.getContext('2d')!;
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, CW, CH);
  const proj = geoEquirectangular().scale(CW / (2 * Math.PI)).translate([CW / 2, CH / 2]);
  const land = landOf(land50);
  const gp = geoPath(proj, ctx);
  ctx.globalCompositeOperation = 'lighter';
  ctx.filter = 'blur(14px)';
  ctx.fillStyle = '#0000ff';
  ctx.beginPath(); gp(land); ctx.fill();
  ctx.filter = 'none';
  ctx.fillStyle = '#ff0000';
  ctx.beginPath(); gp(land); ctx.fill();
  ctx.strokeStyle = '#00ff00';
  ctx.lineWidth = 2.2;
  ctx.beginPath(); gp(land); ctx.stroke();
  const tex = new THREE.CanvasTexture(cv);
  tex.anisotropy = 8;
  tex.colorSpace = THREE.NoColorSpace;
  tex.wrapS = THREE.RepeatWrapping;
  const normal = (lon: number, lat: number) => {
    const lo = (lon * Math.PI) / 180;
    const la = (lat * Math.PI) / 180;
    return new THREE.Vector3(Math.cos(la) * Math.sin(lo), Math.sin(la), Math.cos(la) * Math.cos(lo));
  };
  const geo = (lon: number, lat: number, h = 0) => normal(lon, lat).multiplyScalar(R + h);
  const ball = new THREE.Mesh(
    new THREE.SphereGeometry(R, 128, 96),
    new THREE.ShaderMaterial({
      uniforms: {uMap: {value: tex}, uTime: shared.uTime, uLight: {value: new THREE.Vector3(-0.5, 0.45, 0.75).normalize()}},
      vertexShader: `varying vec3 vN; varying vec3 vP; varying vec3 vVN; varying vec3 vView; void main(){ vN = normalize(position); vP = position; vec4 mv = modelViewMatrix * vec4(position, 1.0); vVN = normalize(normalMatrix * normal); vView = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `uniform sampler2D uMap; uniform float uTime; uniform vec3 uLight; varying vec3 vN; varying vec3 vP; varying vec3 vVN; varying vec3 vView;
        ${NOISE_GLSL}
        void main(){
          vec3 n = normalize(vN);
          float lon = atan(n.x, n.z); float lat = asin(clamp(n.y, -1.0, 1.0));
          vec2 uv = vec2(lon / 6.28318530718 + 0.5, lat / 3.14159265359 + 0.5);
          vec4 m = texture2D(uMap, uv);
          float lit = 0.35 + 0.65 * clamp(dot(normalize(vVN), normalize(viewMatrix * vec4(uLight, 0.0)).xyz) * 0.9 + 0.35, 0.0, 1.0);
          vec3 seaC = mix(vec3(0.004, 0.028, 0.06), vec3(0.012, 0.13, 0.19), smoothstep(0.05, 0.8, m.b));
          vec3 landC = mix(vec3(0.045, 0.075, 0.09), vec3(0.10, 0.15, 0.17), ytFbm(uv * vec2(180.0, 90.0)));
          vec3 c = mix(seaC, landC, step(0.5, m.r)) * lit;
          c += vec3(0.7, 0.92, 1.0) * smoothstep(0.3, 0.9, m.g) * 0.55;
          vec2 gr = abs(fract(vec2(lon, lat) * 57.2958 / 15.0 - 0.5) - 0.5) / fwidth(vec2(lon, lat) * 57.2958 / 15.0);
          c += vec3(0.08, 0.2, 0.26) * (1.0 - min(min(gr.x, gr.y), 1.0)) * 0.3;
          float rim = pow(1.0 - max(dot(normalize(vVN), normalize(vView)), 0.0), 3.0);
          c += vec3(0.10, 0.45, 0.65) * rim * 0.9;
          gl_FragColor = vec4(c, 1.0);${COLOR_OUT}}`,
    }),
  );
  scene.add(ball);
  const halo = new THREE.Mesh(
    new THREE.SphereGeometry(R * 1.045, 64, 48),
    new THREE.ShaderMaterial({
      side: THREE.BackSide, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: `varying vec3 vVN; varying vec3 vView; void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); vVN = normalize(normalMatrix * normal); vView = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `varying vec3 vVN; varying vec3 vView; void main(){ float f = pow(clamp(dot(normalize(vVN), -normalize(vView)) + 0.25, 0.0, 1.0), 2.6); gl_FragColor = vec4(vec3(0.16, 0.6, 0.85), f * 0.9);${COLOR_OUT}}`,
    }),
  );
  scene.add(halo);
  const nStar = 900;
  const sp = new Float32Array(nStar * 3);
  for (let i = 0; i < nStar; i++) {
    const a = rnd(i * 1.3) * 6.283;
    const b = Math.acos(2 * rnd(i * 2.7 + 3) - 1);
    sp[i * 3] = 700 * Math.sin(b) * Math.cos(a); sp[i * 3 + 1] = 700 * Math.cos(b); sp[i * 3 + 2] = 700 * Math.sin(b) * Math.sin(a);
  }
  const sg = new THREE.BufferGeometry();
  sg.setAttribute('position', new THREE.BufferAttribute(sp, 3));
  scene.add(new THREE.Points(sg, new THREE.PointsMaterial({color: 0x9fc4dd, size: 1.6, sizeAttenuation: false, transparent: true, opacity: 0.7})));
  const dur = (spec as any).__dur ?? 10;
  const size = (spec as any).__size ?? 1;
  const pins = makePins(m.pins ?? [], geo, normal, size, dur);
  scene.add(pins.group);
  const routes = makeRoutes(m.routes ?? [], (r) => {
    const out: THREE.Vector3[] = [];
    for (let i = 0; i < r.points.length - 1; i++) {
      const a = normal(r.points[i][0], r.points[i][1]);
      const b = normal(r.points[i + 1][0], r.points[i + 1][1]);
      const steps = 24;
      for (let k = i === 0 ? 0 : 1; k <= steps; k++) {
        const u = k / steps;
        const p = a.clone().lerp(b, u).normalize();
        out.push(p.multiplyScalar(R + 0.3 + (r.arc ?? 0) * size * Math.sin(Math.PI * u)));
      }
    }
    return out;
  }, size, dur);
  scene.add(routes.group);
  return {
    scene, shared, exposure: spec.exposure ?? 1.0, underwater: false, geo,
    view: (over, dist, tilt, bearing) => {
      const nrm = normal(over[0], over[1]);
      const look = nrm.clone().multiplyScalar(R);
      // tilt 90 = straight above the place; lower = looking across the surface toward the horizon from `bearing`
      const east = new THREE.Vector3(0, 1, 0).cross(nrm).normalize();
      const north = nrm.clone().cross(east).normalize();
      const el = (tilt * Math.PI) / 180;
      const b = (bearing * Math.PI) / 180;
      const off = nrm.clone().multiplyScalar(Math.sin(el)).addScaledVector(north, -Math.cos(el) * Math.cos(b)).addScaledVector(east, Math.cos(el) * Math.sin(b));
      return {look, pos: look.clone().addScaledVector(off, dist)};
    },
    update: (t) => { shared.uTime.value = t; pins.update(t); routes.update(t); },
  };
};
