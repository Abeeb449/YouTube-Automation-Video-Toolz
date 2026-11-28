/**
 * Things other than animals in a live 3D shot, built from simple shapes: a cage-diving boat, a rocky island, a shark
 * net, a bed of shark-skin scales, a row of orca teeth, a burst of spray. Each has an id, so labels can be pinned
 * to it, and moves by a formula of time.
 */
import * as THREE from 'three';
import {keyTime, ramp, rnd, V3} from './math';
import type {Env} from './world';

export type PropSpec = {
  kind: 'boat' | 'island' | 'net' | 'denticles' | 'teeth' | 'spray' | 'longline';
  id: string;
  pos?: V3;
  heading?: number;
  scale?: number;
  at?: number; u?: number;
  [k: string]: any;
};

export type Prop = {group: THREE.Group; update: (t: number) => void; points: Record<string, V3>};

const DEG = Math.PI / 180;
const std = (color: string, rough = 0.7, extra: Partial<THREE.MeshStandardMaterialParameters> = {}) => new THREE.MeshStandardMaterial({color: new THREE.Color(color), roughness: rough, ...extra});

/** A small cage-diving boat seen from above or below the water; `cage: true` hangs the steel cage at its side. */
const boat = (s: PropSpec): Prop => {
  const g = new THREE.Group();
  const L = s.length ?? 11;
  const hw = L * 0.155;
  // the hull is lofted from sections: beam, deck height (rising to the bow) and keel depth along its length
  const N = 28;
  const pos: number[] = [];
  const col: number[] = [];
  const idx: number[] = [];
  const white = new THREE.Color(s.color ?? '#eef1f3');
  const stripe = new THREE.Color('#1d3a5c');
  const bottom = new THREE.Color('#5c1f1c');
  const deckC = new THREE.Color('#b9a98a');
  const ring = (u: number) => {
    const x = -L / 2 + L * u;
    const taper = u < 0.55 ? 1 : Math.cos(((u - 0.55) / 0.45) * Math.PI * 0.5);
    const bm = hw * (0.88 + 0.12 * Math.sin(Math.PI * Math.min(1, u / 0.55))) * Math.pow(Math.max(taper, 0), 0.75);
    const deck = 1.05 + 0.75 * Math.pow(u, 2.2);
    const keel = -0.75 + 0.6 * Math.pow(Math.max(0, u - 0.6) / 0.4, 2);
    // port deck edge, port waterline, port chine, keel, starboard chine, waterline, deck edge, deck centre
    return [[x, deck, -bm], [x, 0.22, -bm * 0.97], [x, -0.25, -bm * 0.8], [x + (u > 0.9 ? 0.2 : 0), keel, 0], [x, -0.25, bm * 0.8], [x, 0.22, bm * 0.97], [x, deck, bm], [x, deck - 0.22, 0]];
  };
  const colours = [white, stripe, bottom, bottom, bottom, stripe, white, deckC];
  for (let i = 0; i <= N; i++) {
    ring(i / N).forEach((pt, k) => { pos.push(pt[0], pt[1], pt[2]); col.push(colours[k].r, colours[k].g, colours[k].b); });
  }
  for (let i = 0; i < N; i++) for (let k = 0; k < 8; k++) {
    const a = i * 8 + k, b2 = i * 8 + ((k + 1) % 8), c = (i + 1) * 8 + k, d = (i + 1) * 8 + ((k + 1) % 8);
    idx.push(a, c, b2, b2, c, d);
  }
  // close the stern
  const sc = pos.length / 3;
  pos.push(-L / 2, 0.4, 0); col.push(white.r, white.g, white.b);
  for (let k = 0; k < 8; k++) idx.push(sc, k, (k + 1) % 8);
  const hg = new THREE.BufferGeometry();
  hg.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  hg.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  hg.setIndex(idx);
  hg.computeVertexNormals();
  g.add(new THREE.Mesh(hg, new THREE.MeshStandardMaterial({vertexColors: true, roughness: 0.45, side: THREE.DoubleSide})));
  const cabinGeo = new THREE.BoxGeometry(L * 0.26, 1.55, hw * 1.3);
  const cp = cabinGeo.attributes.position;
  for (let i = 0; i < cp.count; i++) if (cp.getY(i) > 0) cp.setX(i, cp.getX(i) - 0.28 * Math.sign(cp.getX(i)) - 0.12);       // walls lean in toward the roof
  cabinGeo.computeVertexNormals();
  const cabin = new THREE.Mesh(cabinGeo, std('#f4f5f6', 0.5));
  cabin.position.set(L * 0.12, 1.75, 0);
  g.add(cabin);
  const glass = new THREE.Mesh(new THREE.BoxGeometry(L * 0.235, 0.5, hw * 1.32), std('#101c24', 0.15));
  glass.position.set(L * 0.105, 2.05, 0);
  g.add(glass);
  const roof = new THREE.Mesh(new THREE.BoxGeometry(L * 0.3, 0.09, hw * 1.5), std('#dfe3e6', 0.6));
  roof.position.set(L * 0.1, 2.56, 0);
  g.add(roof);
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.04, 1.5, 6), std('#c9ced1', 0.4, {metalness: 0.6}));
  mast.position.set(L * 0.1, 3.3, 0);
  g.add(mast);
  const radar = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.1, 0.16), std('#f4f5f6', 0.5));
  radar.position.set(L * 0.1, 3.75, 0);
  g.add(radar);
  // rail posts and rail round the working deck at the stern
  const railMat = std('#c9ced1', 0.4, {metalness: 0.6});
  for (let i = 0; i <= 6; i++) for (const sd of [-1, 1]) {
    const x = -L / 2 + 0.3 + i * (L * 0.36 / 6);
    const post = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 0.75, 5), railMat);
    post.position.set(x, 1.45, sd * hw * 0.9);
    g.add(post);
  }
  for (const sd of [-1, 1]) {
    const rail = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, L * 0.36, 5), railMat);
    rail.rotation.z = Math.PI / 2;
    rail.position.set(-L / 2 + 0.3 + L * 0.18, 1.82, sd * hw * 0.9);
    g.add(rail);
  }
  // a few people on deck, for scale
  const jackets = ['#e8452c', '#f2c21c', '#2d6fb0', '#e8452c'];
  for (let i = 0; i < (s.crew ?? 4); i++) {
    const person = new THREE.Group();
    const legs = new THREE.Mesh(new THREE.CapsuleGeometry(0.12, 0.5, 4, 8), std('#1f2a33', 0.9));
    legs.position.y = 0.37;
    const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.15, 0.36, 4, 8), std(jackets[i % 4], 0.8));
    body.position.y = 1.0;
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.11, 10, 8), std('#c9a58a', 0.8));
    head.position.y = 1.44;
    person.add(legs, body, head);
    person.position.set(-L / 2 + 0.9 + i * 0.85, 0.95, (i % 2 ? 1 : -1) * hw * (0.25 + 0.3 * rnd(i * 3.1)));
    g.add(person);
  }
  const points: Record<string, V3> = {deck: [0, 1.2, 0], bow: [L / 2, 0.9, 0], cabin: [L * 0.08, 2.4, 0]};
  if (s.cage) {
    const cg = new THREE.Group();
    const w = 3.2, h = 2.2, d = 1.1;
    const barMat = std('#b9c2c8', 0.35, {metalness: 0.75});
    const bar = (len: number) => new THREE.CylinderGeometry(0.03, 0.03, len, 6);
    for (let i = 0; i <= 10; i++) for (const z of [-d / 2, d / 2]) { const b = new THREE.Mesh(bar(h), barMat); b.position.set(-w / 2 + (w * i) / 10, 0, z); cg.add(b); }
    for (let i = 0; i <= 3; i++) for (const x of [-w / 2, w / 2]) { const b = new THREE.Mesh(bar(h), barMat); b.position.set(x, 0, -d / 2 + (d * i) / 3); cg.add(b); }
    for (const y of [-h / 2, 0, h / 2]) {
      for (const z of [-d / 2, d / 2]) { const b = new THREE.Mesh(bar(w), barMat); b.rotation.z = Math.PI / 2; b.position.set(0, y, z); cg.add(b); }
      for (const x of [-w / 2, w / 2]) { const b = new THREE.Mesh(bar(d), barMat); b.rotation.x = Math.PI / 2; b.position.set(x, y, 0); cg.add(b); }
    }
    const fl = new THREE.Mesh(new THREE.BoxGeometry(w, 0.28, 0.28), std('#f2c21c', 0.6));
    for (const z of [-d / 2, d / 2]) { const f = fl.clone(); f.position.set(0, h / 2 - 0.05, z); cg.add(f); }
    cg.position.set(-L * 0.12, -h / 2 + 0.25, hw + d / 2 + 0.15);
    g.add(cg);
    points.cage = [-L * 0.12, -h / 2 + 0.25, hw + d / 2 + 0.15];
  }
  return {group: g, points, update: (t) => { g.position.y = (s.pos?.[1] ?? 0) + Math.sin(t * 0.9 + (s.pos?.[0] ?? 0)) * 0.09; g.rotation.x = Math.sin(t * 0.7) * 0.025; g.rotation.z = Math.sin(t * 0.53 + 1) * 0.02; }};
};

/** A low rocky island (Dyer Island, Seal Island, the Farallones): bare rock, pale on top, surf round its shore. */
const island = (s: PropSpec, env: Env): Prop => {
  const g = new THREE.Group();
  const R = s.radius ?? 60;
  const H = s.height ?? 6;
  const el = s.stretch ?? 1.9;
  const pg = new THREE.PlaneGeometry(R * 2.6, R * 2.6, 180, 180);
  pg.rotateX(-Math.PI / 2);
  const p = pg.attributes.position;
  const n2 = (x: number, z: number) => Math.sin(x * 0.083 + 1.3) * Math.cos(z * 0.097 + 0.4) + 0.5 * Math.sin(x * 0.21 + z * 0.17 + 2.0) + 0.25 * Math.sin(x * 0.47 - z * 0.39);
  const fine = (x: number, z: number) => Math.sin(x * 1.3 + z * 0.9) * Math.cos(z * 1.7 - x * 0.6) + 0.5 * Math.sin(x * 2.9 - z * 2.3);
  const cols = new Float32Array(p.count * 3);
  const rock = new THREE.Color('#4a463f');
  const top = new THREE.Color(s.top ?? '#a39c8b');
  const pale = new THREE.Color('#d8d4c8');
  const c = new THREE.Color();
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), z = p.getZ(i);
    const d = Math.hypot(x / el, z) / (R / el) + 0.10 * n2(x, z);
    const dome = Math.max(0, 1 - d * d);
    const h = H * Math.pow(dome, 0.7) * (0.8 + 0.2 * n2(x * 1.7, z * 1.9)) + 0.18 * fine(x, z) * dome - 2.5 * Math.max(0, d - 0.92);
    p.setY(i, Math.max(-3, h));
    const k = Math.min(1, Math.max(0, h / H));
    c.lerpColors(rock, top, Math.pow(k, 0.8));
    c.lerp(pale, Math.max(0, 0.5 * fine(x * 0.7, z * 0.7)) * k);                 // pale streaks where the birds sit
    if (h < 0.7) c.multiplyScalar(0.55);                                        // wet rock at the waterline
    cols[i * 3] = c.r; cols[i * 3 + 1] = c.g; cols[i * 3 + 2] = c.b;
  }
  pg.computeVertexNormals();
  pg.setAttribute('color', new THREE.BufferAttribute(cols, 3));
  g.add(new THREE.Mesh(pg, new THREE.MeshStandardMaterial({vertexColors: true, roughness: 0.95})));
  // white water breaking round the shore
  const surf = new THREE.Mesh(
    new THREE.RingGeometry(R * 0.80, R * 1.12, 96, 1),
    new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, side: THREE.DoubleSide, uniforms: {uTime: env.shared.uTime},
      vertexShader: `varying vec3 vP; void main(){ vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `uniform float uTime; varying vec3 vP;
        float h(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
        float n(vec2 p){ vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(h(i), h(i + vec2(1.0, 0.0)), f.x), mix(h(i + vec2(0.0, 1.0)), h(i + vec2(1.0, 1.0)), f.x), f.y); }
        void main(){ float a = atan(vP.y, vP.x); float r = length(vP.xy) / ${R.toFixed(1)}; float edge = 0.93 + 0.06 * n(vec2(a * 9.0, uTime * 0.25)) + 0.03 * sin(uTime * 0.7 + a * 5.0);
          float foam = smoothstep(0.10, 0.0, abs(r - edge)) * (0.5 + 0.5 * n(vec2(a * 40.0, r * 30.0 - uTime * 0.6)));
          gl_FragColor = vec4(vec3(0.97), foam * 0.85);
#include <colorspace_fragment>
 }`,
    }),
  );
  surf.rotation.x = -Math.PI / 2;
  surf.scale.set(1, 1 / el, 1);              // the island is longer than it is wide
  surf.position.y = 0.12;
  g.add(surf);
  return {group: g, points: {top: [0, H, 0], shore: [R * 0.9, 0.3, 0]}, update: () => undefined};
};

/** A shark net off a swimming beach: a long curtain of mesh hanging from a line of floats, swaying. */
const net = (s: PropSpec, env: Env): Prop => {
  const g = new THREE.Group();
  const L = s.length ?? 60;
  const D = s.depth ?? 6;
  const mat = new THREE.ShaderMaterial({
    transparent: true, side: THREE.DoubleSide, depthWrite: false,
    uniforms: {uTime: env.shared.uTime, uFog: env.shared.uFogColor, uColor: {value: new THREE.Color(s.color ?? '#c9d6cf')}},
    vertexShader: `uniform float uTime; varying vec2 vUv; varying float vDist; void main(){ vUv = uv; vec3 p = position; float hang = 1.0 - uv.y; p.z += sin(uTime * 0.8 + p.x * 0.25) * 0.5 * hang + sin(uTime * 0.37 + p.x * 0.08) * 0.8 * hang; vec4 mv = modelViewMatrix * vec4(p, 1.0); vDist = -mv.z; gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform vec3 uFog; uniform vec3 uColor; varying vec2 vUv; varying float vDist;
      void main(){ vec2 cell = vec2(vUv.x * ${(L / 0.5).toFixed(1)}, vUv.y * ${(D / 0.5).toFixed(1)}); vec2 a = abs(fract(cell + vec2(cell.y * 0.5, 0.0)) - 0.5); float w = fwidth(cell.x) * 1.2 + 0.06;
        float line = max(smoothstep(0.5 - w, 0.5, a.x), smoothstep(0.5 - w, 0.5, a.y)); float edge = smoothstep(0.985, 1.0, vUv.y);
        float f = 1.0 - exp(-0.0009 * vDist * vDist); gl_FragColor = vec4(mix(uColor, uFog, clamp(f, 0.0, 1.0)), max(line * 0.75, edge) * (1.0 - 0.6 * clamp(f, 0.0, 1.0)));
#include <colorspace_fragment>
 }`,
  });
  const sheet = new THREE.Mesh(new THREE.PlaneGeometry(L, D, 80, 8), mat);
  sheet.position.y = -D / 2 - 0.2;
  sheet.frustumCulled = false;
  g.add(sheet);
  const floats = new THREE.InstancedMesh(new THREE.SphereGeometry(0.28, 12, 10), std('#f28a1c', 0.5), Math.floor(L / 3) + 1);
  const m4 = new THREE.Matrix4();
  for (let i = 0; i < floats.count; i++) { m4.makeTranslation(-L / 2 + i * 3, -0.05, 0); floats.setMatrixAt(i, m4); }
  g.add(floats);
  return {group: g, points: {mid: [0, -D / 2, 0], top: [0, 0, 0]}, update: () => undefined};
};

/** Shark skin under a microscope: rows of tiny tooth-shaped scales with three ridges, overlapping like roof tiles
 * and all pointing toward the tail. */
const denticles = (s: PropSpec): Prop => {
  const g = new THREE.Group();
  const nx = s.nx ?? 30, nz = s.nz ?? 26;
  // one scale: a shield that widens from its root and ends in three points, arched, with three ridges along it
  const geo = new THREE.PlaneGeometry(1, 1, 18, 14);
  const p = geo.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const u = p.getX(i) + 0.5;                      // 0 root → 1 tip (toward the tail)
    const v = p.getY(i) * 2;                        // -1 … 1 across
    const half = 0.50 * Math.sin(Math.PI * Math.min(1, 0.18 + u * 0.72)) * (1 - 0.35 * Math.max(0, u - 0.7) / 0.3);
    const tips = 0.16 * Math.max(0, u - 0.62) * (Math.cos(v * Math.PI * 2) * 0.5 + 0.5);       // three points at the back
    const x = (u + tips) * 1.5 - 0.3;
    const z = v * half;
    const ridge = 0.085 * (Math.cos(v * Math.PI * 2) * 0.5 + 0.5) * Math.sin(Math.PI * Math.min(1, u * 1.15));
    const arch = 0.13 * (1 - v * v) + 0.34 * u;     // rises toward the tip, so each scale lies over the next
    p.setXYZ(i, x, arch + ridge, z);
  }
  geo.computeVertexNormals();
  const mat = std(s.color ?? '#9aabb6', 0.34, {metalness: 0.12, side: THREE.DoubleSide});
  const mesh = new THREE.InstancedMesh(geo, mat, nx * nz);
  const m4 = new THREE.Matrix4();
  const q = new THREE.Quaternion();
  let k = 0;
  for (let ix = 0; ix < nx; ix++) for (let iz = 0; iz < nz; iz++) {
    const x = (ix - nx / 2) * 0.9 + (iz % 2) * 0.45;
    const z = (iz - nz / 2) * 0.56;
    q.setFromEuler(new THREE.Euler(0, (rnd(k * 1.3) - 0.5) * 0.14, (rnd(k * 2.1) - 0.5) * 0.06));
    m4.compose(new THREE.Vector3(x + (rnd(k * 4.7) - 0.5) * 0.06, 0.015 * rnd(k), z), q, new THREE.Vector3(1, 1, 1).multiplyScalar(0.93 + 0.14 * rnd(k * 3.3)));
    mesh.setMatrixAt(k++, m4);
  }
  g.add(mesh);
  const base = new THREE.Mesh(new THREE.PlaneGeometry(nx * 1.2, nz * 0.8), std('#56646d', 0.8));
  base.rotation.x = -Math.PI / 2;
  base.position.y = 0.0;
  g.add(base);
  return {group: g, points: {mid: [0, 0.3, 0], scale: [0.4, 0.45, 0]}, update: () => undefined};
};

/** A row of orca teeth, sharp at first and worn flat when `wear` arrives (teeth that have eaten a lot of shark). */
const teeth = (s: PropSpec, _env: Env, dur: number): Prop => {
  const g = new THREE.Group();
  const n = s.n ?? 9;
  const gum = new THREE.Mesh(new THREE.BoxGeometry(n * 0.95 + 1.2, 0.9, 1.15, 24, 4, 6), std('#8f5b60', 0.5));
  const gp = gum.geometry.attributes.position;
  for (let i = 0; i < gp.count; i++) {
    const x = gp.getX(i), y = gp.getY(i), z = gp.getZ(i);
    const round = 1 - 0.35 * Math.pow(Math.abs(z) / 0.575, 2.2);             // rounded across
    gp.setXYZ(i, x, (y > 0 ? y * round : y) - 0.02 * x * x * 0.2, z);
  }
  gum.geometry.computeVertexNormals();
  gum.position.y = -0.42;
  g.add(gum);
  const mat = std('#efe9d6', 0.35);
  const wearMat = std('#c9b58c', 0.6);
  const items: {tooth: THREE.Mesh; cap: THREE.Mesh}[] = [];
  for (let i = 0; i < n; i++) {
    const geo = new THREE.ConeGeometry(0.3, 1.5, 20, 12);
    geo.translate(0, 0.75, 0);
    const p = geo.attributes.position;
    for (let k = 0; k < p.count; k++) p.setX(k, p.getX(k) - 0.16 * Math.pow(p.getY(k) / 1.5, 2));          // curved back a little
    geo.computeVertexNormals();
    const tooth = new THREE.Mesh(geo, mat);
    tooth.position.set((i - (n - 1) / 2) * 0.95, 0, 0);
    const cap = new THREE.Mesh(new THREE.CircleGeometry(0.3, 20), wearMat);
    cap.rotation.x = -Math.PI / 2;
    cap.position.copy(tooth.position);
    cap.visible = false;
    g.add(tooth, cap);
    items.push({tooth, cap});
  }
  const t0 = s.wear !== undefined ? keyTime(typeof s.wear === 'object' ? s.wear : {at: s.wear}, dur, 0) : 1e9;
  const plane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 1.6);
  mat.clippingPlanes = [plane];
  return {group: g, points: {tip: [0, 1.5, 0], row: [0, 0.4, 0]}, update: (t) => {
    const w = ramp(t, t0, s.wearD ?? 2.2, 'inOut');
    const top = 1.6 - 1.15 * w;                         // worn down to flat stumps
    g.updateMatrixWorld(true);
    const y = g.localToWorld(new THREE.Vector3(0, top, 0)).y;
    plane.constant = y;
    for (const it of items) { it.cap.visible = w > 0.02; it.cap.position.y = top - 0.002; it.cap.scale.setScalar(Math.max(0.05, 1 - top / 1.5) * 1.0 + 0.02); }
  }};
};

/** Spray thrown up where something breaks the surface. */
const spray = (s: PropSpec, _env: Env, dur: number): Prop => {
  const g = new THREE.Group();
  const n = s.n ?? 420;
  const pos = new Float32Array(n * 3);
  const vel = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const a = rnd(i * 1.7) * 6.283;
    const sp = (2 + 7 * rnd(i * 2.9)) * (s.power ?? 1);
    const upv = (4 + 9 * rnd(i * 4.1)) * (s.power ?? 1);
    vel[i * 3] = Math.cos(a) * sp * 0.55; vel[i * 3 + 1] = upv; vel[i * 3 + 2] = Math.sin(a) * sp * 0.55;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.PointsMaterial({color: 0xffffff, size: 0.22, transparent: true, opacity: 0.9, depthWrite: false});
  const pts = new THREE.Points(geo, mat);
  pts.frustumCulled = false;
  g.add(pts);
  const t0 = keyTime(s, dur, 0);
  return {group: g, points: {}, update: (t) => {
    const dt = t - t0;
    pts.visible = dt > 0 && dt < 3.2;
    if (!pts.visible) return;
    for (let i = 0; i < n; i++) {
      const d = Math.max(0, dt - rnd(i * 6.3) * 0.25);
      pos[i * 3] = vel[i * 3] * d; pos[i * 3 + 1] = Math.max(-0.2, vel[i * 3 + 1] * d - 4.9 * d * d); pos[i * 3 + 2] = vel[i * 3 + 2] * d;
    }
    geo.attributes.position.needsUpdate = true;
    mat.opacity = 0.9 * (1 - ramp(t, t0 + 1.6, 1.5, 'soft'));
  }};
};

/** A fishing longline: a main line near the surface with baited hooks hanging from it. */
const longline = (s: PropSpec): Prop => {
  const g = new THREE.Group();
  const L = s.length ?? 80;
  const lineMat = new THREE.MeshBasicMaterial({color: new THREE.Color('#d9e2e6'), transparent: true, opacity: 0.75});
  const main = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, L, 6), lineMat);
  main.rotation.z = Math.PI / 2;
  g.add(main);
  const n = Math.floor(L / 4);
  for (let i = 0; i <= n; i++) {
    const x = -L / 2 + i * 4;
    const len = 2.5 + rnd(i) * 1.5;
    const drop = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, len, 5), lineMat);
    drop.position.set(x, -len / 2, 0);
    const hook = new THREE.Mesh(new THREE.TorusGeometry(0.14, 0.03, 6, 14, Math.PI * 1.4), std('#c9ced1', 0.3, {metalness: 0.8}));
    hook.position.set(x, -len - 0.1, 0);
    const bait = new THREE.Mesh(new THREE.SphereGeometry(0.13, 8, 6), std('#8a3b33', 0.7));
    bait.position.set(x + 0.1, -len - 0.2, 0);
    g.add(drop, hook, bait);
    if (i % 4 === 0) { const fl = new THREE.Mesh(new THREE.SphereGeometry(0.3, 10, 8), std('#f2421c', 0.5)); fl.position.set(x, 0.9, 0); const rope = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.9, 5), lineMat); rope.position.set(x, 0.45, 0); g.add(fl, rope); }
  }
  return {group: g, points: {mid: [0, -2, 0]}, update: () => undefined};
};

export const buildProp = (s: PropSpec, env: Env, dur: number): Prop => {
  const p = s.kind === 'boat' ? boat(s) : s.kind === 'island' ? island(s, env) : s.kind === 'net' ? net(s, env) : s.kind === 'denticles' ? denticles(s)
    : s.kind === 'teeth' ? teeth(s, env, dur) : s.kind === 'longline' ? longline(s) : spray(s, env, dur);
  if (s.pos) p.group.position.set(s.pos[0], s.pos[1], s.pos[2]);
  if (s.heading) p.group.rotation.y = s.heading * DEG;
  if (s.tilt) p.group.rotation.x = s.tilt * DEG;
  if (s.scale) p.group.scale.setScalar(s.scale);
  return p;
};
