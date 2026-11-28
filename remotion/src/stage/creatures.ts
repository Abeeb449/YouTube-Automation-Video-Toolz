/**
 * Animals in the live 3D stage. Each is a real 3D model (exported from Blender by blender/export_glb.py) that swims by
 * bending its own body: a wave runs from head to tail (side to side for a shark, up and down for a whale), the body
 * curves into its turns and leans into them, and the tail beats faster the faster it travels.
 */
import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {clamp, keyTime, Key, noise1, ramp, track, V3} from './math';
import {CAUSTIC_GLSL, Env} from './world';

export type ModelMeta = {creature: string; tail: number; nose: number; swim: 'yaw' | 'pitch'; points: Record<string, V3>; parts: string[]};
export type ModelRef = {glb: string; meta: ModelMeta};
export type Loaded = {root: THREE.Object3D; meta: ModelMeta};

export type ActorSpec = {
  id: string;
  model: string;
  /** real length in metres, nose to tail */
  length: number;
  /** where it swims: points in metres with their moments (`at` seconds, or `u` as a share of the shot) */
  path?: {at?: number; u?: number; p: V3; ease?: string}[];
  /** a fixed place and attitude (a carcass, a model on show): degrees */
  pos?: V3;
  heading?: number;
  pitch?: number;
  roll?: number;
  /** turning on the spot, degrees per second (studio) */
  spin?: number;
  pose?: 'swim' | 'still' | 'limp';
  /** tail beat: 1 = natural for its speed */
  beat?: number;
  amp?: number;
  /** show the inside: the skin turns to glass at this moment */
  xray?: {at?: number; u?: number; d?: number; back?: number} | boolean;
  /** separate parts by name (liver, bladder): when they appear and go */
  parts?: Record<string, {at?: number; u?: number; out?: number; outU?: number; glow?: number; color?: string}>;
  /** a wound drawn on the skin: "chest" */
  wound?: string;
  /** when the whole animal appears / goes (seconds) */
  at?: number;
  out?: number;
  /** a dark shape only (0..1): the animal before it is recognised */
  shadow?: number | {from: number; to: number; at?: number; u?: number; d?: number};
  bob?: number;
};

export const loadModels = async (models: Record<string, ModelRef>, url: (p: string) => string): Promise<Record<string, Loaded>> => {
  const loader = new GLTFLoader();
  const out: Record<string, Loaded> = {};
  await Promise.all(Object.entries(models).map(async ([key, ref]) => {
    const gltf = await loader.loadAsync(url(ref.glb));
    gltf.scene.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        const mat = m.material as THREE.MeshStandardMaterial;
        if (mat.map) { mat.map.anisotropy = 8; mat.map.colorSpace = THREE.SRGBColorSpace; }
      }
    });
    out[key] = {root: gltf.scene, meta: ref.meta};
  }));
  return out;
};

const SWIM_GLSL = /* glsl */ `
uniform float uPhase; uniform float uAmp; uniform float uBend; uniform vec2 uExtent; uniform float uAxis; uniform float uWave; uniform float uSag;
vec3 ytSwim(vec3 p) {
  float s = clamp((uExtent.y - p.x) / (uExtent.y - uExtent.x), 0.0, 1.0);
  float env = 0.035 + 0.965 * pow(s, 2.1);
  float w = uAmp * (env * sin(uPhase - uWave * s) - 0.06 * (1.0 - s) * sin(uPhase - 0.6));
  if (uAxis < 0.5) p.z += w; else p.y += w;
  float dx = p.x - mix(uExtent.x, uExtent.y, 0.56);
  p.z += uBend * dx * dx;
  p.y -= uSag * dx * dx;
  return p;
}
`;

type ActorUniforms = {
  uPhase: {value: number}; uAmp: {value: number}; uBend: {value: number}; uExtent: {value: THREE.Vector2}; uAxis: {value: number}; uWave: {value: number};
  uSag: {value: number}; uWound: {value: number}; uShadow: {value: number}; uGhost: {value: number};
};

const patchSkin = (src: THREE.MeshStandardMaterial, u: ActorUniforms, env: Env) => {
  const mat = src.clone();
  mat.roughness = env.underwater ? 0.62 : 0.34;
  mat.metalness = 0.0;
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, u, {uTime: env.shared.uTime, uCaustic: env.shared.uCaustic, uCausticColor: env.shared.uCausticColor, uFogCol: env.shared.uFogColor, uRim: {value: env.underwater ? 1.5 : 0.0}});
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', `#include <common>\n${SWIM_GLSL}\nvarying vec3 vWPos; varying vec3 vWNor; varying vec3 vOPos;`)
      .replace('#include <begin_vertex>', `#include <begin_vertex>\nvOPos = position; transformed = ytSwim(transformed);\nvWPos = (modelMatrix * vec4(transformed, 1.0)).xyz; vWNor = normalize(mat3(modelMatrix) * objectNormal);`);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', `#include <common>\n${CAUSTIC_GLSL}\nuniform float uTime; uniform float uCaustic; uniform vec3 uCausticColor; uniform vec3 uFogCol; uniform float uWound; uniform float uShadow; uniform float uRim;\nvarying vec3 vWPos; varying vec3 vWNor; varying vec3 vOPos;`)
      .replace('#include <map_fragment>', `#include <map_fragment>
        if (uWound > 0.5) {
          // one clean tear across the chest, on the underside between the pectoral fins
          float line = 0.74 + 0.05 * sin(vOPos.z * 9.0);
          float d = abs(vOPos.x - line);
          float m = smoothstep(-0.19, -0.29, vOPos.y) * smoothstep(0.25, 0.17, abs(vOPos.z));
          diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.52, 0.30, 0.28), smoothstep(0.034, 0.014, d) * m * 0.55);
          diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.10, 0.02, 0.02), smoothstep(0.015, 0.005, d) * m);
        }`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        float ytTop = clamp(vWNor.y * 0.7 + 0.45, 0.0, 1.0);
        float ytC = ytCaustic(vWPos.xz * 0.36 + vWPos.y * 0.05, uTime * 0.55) + 0.5 * ytCaustic(vWPos.xz * 0.17 + 2.0, uTime * 0.4);
        totalEmissiveRadiance += uCausticColor * ytC * ytTop * ytTop * uCaustic * (0.16 + 0.95 * diffuseColor.rgb) * 1.5;
        // light scattered by the water wraps round the edge of the body
        float ytRim = pow(1.0 - max(dot(normalize(vViewPosition), normal), 0.0), 3.2);
        totalEmissiveRadiance += uFogCol * ytRim * uRim * (0.5 + 0.5 * ytTop);`)
      .replace('#include <fog_fragment>', `gl_FragColor.rgb = mix(gl_FragColor.rgb, uFogCol * 0.12, uShadow);\n#include <fog_fragment>`);
  };
  return mat;
};

const ghostMaterial = (u: ActorUniforms) =>
  new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false,
    uniforms: {...u},
    vertexShader: `${SWIM_GLSL}\nvarying vec3 vN; varying vec3 vV; void main(){ vec3 p = ytSwim(position); vec4 mv = modelViewMatrix * vec4(p, 1.0); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform float uGhost; varying vec3 vN; varying vec3 vV; void main(){ float f = 1.0 - abs(dot(normalize(vN), normalize(vV))); float a = (pow(f, 2.2) * 0.85 + 0.03) * uGhost; vec3 c = mix(vec3(0.30, 0.72, 1.0), vec3(0.88, 0.97, 1.0), pow(f, 3.0)); gl_FragColor = vec4(c, a);
#include <colorspace_fragment>
 }`,
  });

const partMaterial = (u: ActorUniforms, color: string) => {
  const mat = new THREE.MeshStandardMaterial({color: new THREE.Color(color), emissive: new THREE.Color(color), emissiveIntensity: 0.9, roughness: 0.4, transparent: true});
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, u);
    sh.vertexShader = sh.vertexShader.replace('#include <common>', `#include <common>\n${SWIM_GLSL}`).replace('#include <begin_vertex>', `#include <begin_vertex>\ntransformed = ytSwim(transformed);`);
  };
  return mat;
};

const DEG = Math.PI / 180;

export class Actor {
  group = new THREE.Group();
  spec: ActorSpec;
  meta: ModelMeta;
  scale: number;
  u: ActorUniforms;
  private keys: Key<number[]>[] = [];
  private dist: number[] = [];
  private skins: THREE.MeshStandardMaterial[] = [];
  private ghost: THREE.Mesh[] = [];
  private parts: Record<string, {mesh: THREE.Mesh; mat: THREE.MeshStandardMaterial}> = {};
  private dur: number;
  private mid: number;

  constructor(spec: ActorSpec, model: Loaded, env: Env, dur: number) {
    this.spec = spec;
    this.meta = model.meta;
    this.dur = dur;
    this.scale = spec.length / (model.meta.nose - model.meta.tail);
    this.mid = (model.meta.nose + model.meta.tail) / 2;
    this.u = {
      uPhase: {value: 0}, uAmp: {value: 0}, uBend: {value: 0}, uExtent: {value: new THREE.Vector2(model.meta.tail, model.meta.nose)},
      uAxis: {value: model.meta.swim === 'pitch' ? 1 : 0}, uWave: {value: model.meta.swim === 'pitch' ? 4.2 : 5.6}, uSag: {value: 0},
      uWound: {value: spec.wound ? 1 : 0}, uShadow: {value: 0}, uGhost: {value: 0},
    };
    const inner = model.root.clone(true);
    inner.scale.setScalar(this.scale);
    inner.position.x = -this.mid * this.scale;          // the animal turns about its middle
    const ghostMat = ghostMaterial(this.u);
    const adds: THREE.Mesh[] = [];
    inner.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      m.frustumCulled = false;
      const part = model.meta.parts.find((p) => m.name.startsWith(p) || (m.parent?.name ?? '').startsWith(p));
      if (part) {
        const mat = partMaterial(this.u, spec.parts?.[part]?.color ?? (part === 'liver' ? '#f08a1e' : '#e6f6ff'));
        m.material = mat;
        m.visible = false;
        m.renderOrder = 2;
        this.parts[part] = {mesh: m, mat};
      } else {
        const mat = patchSkin(m.material as THREE.MeshStandardMaterial, this.u, env);
        m.material = mat;
        this.skins.push(mat);
        if (spec.xray) {
          const g = new THREE.Mesh(m.geometry, ghostMat);
          g.frustumCulled = false;
          g.renderOrder = 3;
          g.visible = false;
          adds.push(g);
          (g as any).__parent = m.parent;
        }
      }
    });
    for (const g of adds) { ((g as any).__parent as THREE.Object3D).add(g); this.ghost.push(g); }
    this.group.add(inner);
    if (spec.path?.length) {
      this.keys = spec.path.map((k, i) => ({t: keyTime(k, dur, (i / Math.max(1, spec.path!.length - 1)) * dur), v: k.p as number[], ease: k.ease})).sort((a, b) => a.t - b.t);
      // how far it has swum by each tenth of a second: the tail keeps time with the distance covered
      let d = 0;
      let prev = this.posAt(0);
      const n = Math.ceil((dur + 2) * 10);
      for (let i = 0; i <= n; i++) {
        const p = this.posAt(i / 10);
        d += p.distanceTo(prev);
        this.dist.push(d);
        prev = p;
      }
    }
  }

  private posAt(t: number) {
    if (!this.keys.length) {
      const p = this.spec.pos ?? [0, 0, 0];
      return new THREE.Vector3(p[0], p[1], p[2]);
    }
    // before the first and after the last key it keeps going in the same direction: nothing ever stands frozen
    const k0 = this.keys[0];
    const k1 = this.keys[this.keys.length - 1];
    const v = track(this.keys, clamp(t, k0.t, k1.t));
    const p = new THREE.Vector3(v[0], v[1], v[2]);
    if (this.keys.length > 1 && (t < k0.t || t > k1.t)) {
      const e = t < k0.t ? k0.t : k1.t;
      const a = track(this.keys, e + (t < k0.t ? 0.2 : -0.2));
      const sign = t < k0.t ? -1 : 1;
      const vel = new THREE.Vector3(v[0] - a[0], v[1] - a[1], v[2] - a[2]).multiplyScalar(sign / 0.2);
      p.addScaledVector(vel, t - e);
    }
    return p;
  }

  update(t: number) {
    const s = this.spec;
    const g = this.group;
    let amp = 0;
    let bend = 0;
    let phase = 0;
    if (this.keys.length > 1) {
      const p = this.posAt(t);
      const a = this.posAt(t - 0.12);
      const b = this.posAt(t + 0.12);
      const f1 = p.clone().sub(a);
      const f2 = b.clone().sub(p);
      const f = b.clone().sub(a);
      const speed = f.length() / 0.24;
      if (f.lengthSq() < 1e-8) f.set(1, 0, 0);
      f.normalize();
      const yaw = Math.atan2(-f.z, f.x);
      const pitch = Math.asin(clamp(f.y, -1, 1));
      let dyaw = Math.atan2(-f2.z, f2.x) - Math.atan2(-f1.z, f1.x);
      if (dyaw > Math.PI) dyaw -= 2 * Math.PI;
      if (dyaw < -Math.PI) dyaw += 2 * Math.PI;
      const yawRate = f1.lengthSq() > 1e-8 && f2.lengthSq() > 1e-8 ? dyaw / 0.12 : 0;
      const bob = (s.bob ?? 1) * 0.02 * s.length;
      g.position.set(p.x + noise1(t * 0.31, 3 + s.length) * bob, p.y + noise1(t * 0.4, 11 + s.length) * bob * 1.6, p.z + noise1(t * 0.27, 23 + s.length) * bob);
      const roll = clamp(-yawRate * 0.55, -0.6, 0.6) + (s.roll ?? 0) * DEG + noise1(t * 0.22, 41 + s.length) * 0.035;
      g.rotation.set(roll, yaw + (s.heading ?? 0) * DEG, pitch + (s.pitch ?? 0) * DEG, 'YZX');
      const curv = speed > 0.05 ? yawRate / speed : 0;
      bend = clamp(-0.5 * curv * this.scale * 1.15, -0.085, 0.085);
      const i = clamp(t * 10, 0, this.dist.length - 1);
      const i0 = Math.floor(i);
      const d = this.dist[i0] + (this.dist[Math.min(this.dist.length - 1, i0 + 1)] - this.dist[i0]) * (i - i0);
      const stride = (this.meta.swim === 'pitch' ? 0.78 : 0.62) * s.length;
      phase = 2 * Math.PI * ((d / stride) * (s.beat ?? 1) + 0.07 * t) + s.length * 1.7;
      const bl = speed / s.length;                                     // body lengths a second
      amp = (s.amp ?? 1) * (this.meta.swim === 'pitch' ? 0.24 : 0.2) * (0.42 + 0.58 * clamp(bl / 0.45));
    } else {
      const p = this.posAt(0);
      g.position.copy(p);
      const spin = (s.spin ?? 0) * DEG * t;
      g.rotation.set((s.roll ?? 0) * DEG, (s.heading ?? 0) * DEG + spin, (s.pitch ?? 0) * DEG, 'YZX');
      if ((s.pose ?? 'still') === 'swim') {                           // swimming on the spot (shown in the studio)
        phase = 2 * Math.PI * 0.32 * (s.beat ?? 1) * t;
        amp = (s.amp ?? 1) * (this.meta.swim === 'pitch' ? 0.2 : 0.17);
        g.position.y += Math.sin(t * 0.5) * 0.02 * s.length;
      }
    }
    this.u.uPhase.value = phase;
    this.u.uAmp.value = s.pose === 'limp' || s.pose === 'still' ? 0 : amp;
    this.u.uBend.value = s.pose === 'limp' ? 0.012 : bend;
    this.u.uSag.value = s.pose === 'limp' ? 0.006 : 0;

    // appear / go
    let op = 1;
    if (typeof s.at === 'number') op *= ramp(t, s.at, 0.6, 'soft');
    if (typeof s.out === 'number') op *= 1 - ramp(t, s.out, 0.6, 'soft');
    // a dark shape before it is recognised
    let shadow = 0;
    if (typeof s.shadow === 'number') shadow = s.shadow;
    else if (s.shadow) shadow = s.shadow.from + (s.shadow.to - s.shadow.from) * ramp(t, keyTime(s.shadow, this.dur, 0), s.shadow.d ?? 1.5, 'soft');
    this.u.uShadow.value = shadow;
    // glass skin
    let ghost = 0;
    if (s.xray) {
      const x = s.xray === true ? {at: 0, d: 0.01} : s.xray;
      ghost = ramp(t, keyTime(x, this.dur, 0), x.d ?? 1.0, 'soft');
      if (typeof x.back === 'number') ghost *= 1 - ramp(t, x.back, x.d ?? 1.0, 'soft');
    }
    this.u.uGhost.value = ghost * op;
    for (const m of this.ghost) m.visible = ghost > 0.002;
    const solid = op * (1 - ghost);
    for (const m of this.skins) {
      m.transparent = solid < 0.999;
      m.opacity = solid;
      m.depthWrite = solid > 0.5;
      m.visible = solid > 0.003;
    }
    for (const [name, part] of Object.entries(this.parts)) {
      const ps = s.parts?.[name];
      let a = ps ? ramp(t, keyTime(ps, this.dur, 0), 0.7, 'soft') : ghost;
      if (ps && (typeof ps.out === 'number' || typeof ps.outU === 'number')) a *= 1 - ramp(t, typeof ps.out === 'number' ? ps.out : ps.outU! * this.dur, 0.45, 'soft');
      part.mesh.visible = a > 0.003 && op > 0.003;
      part.mat.opacity = a * op;
      part.mat.emissiveIntensity = (ps?.glow ?? 0.85) * (0.85 + 0.15 * Math.sin(t * 2.2));
    }
    g.visible = op > 0.003;
    g.updateMatrixWorld(true);
  }

  /** Where a named point of the animal is in the world right now (for labels pinned to it). */
  point(name: string | V3 | undefined): THREE.Vector3 {
    const raw = Array.isArray(name) ? name : (name && this.meta.points[name]) || [this.mid, 0, 0];
    const p = new THREE.Vector3(raw[0], raw[1], raw[2]);
    const e = this.u.uExtent.value;
    const sN = clamp((e.y - p.x) / (e.y - e.x));
    const env = 0.035 + 0.965 * Math.pow(sN, 2.1);
    const w = this.u.uAmp.value * (env * Math.sin(this.u.uPhase.value - this.u.uWave.value * sN) - 0.06 * (1 - sN) * Math.sin(this.u.uPhase.value - 0.6));
    if (this.u.uAxis.value < 0.5) p.z += w; else p.y += w;
    const dx = p.x - (e.x + (e.y - e.x) * 0.56);
    p.z += this.u.uBend.value * dx * dx;
    p.y -= this.u.uSag.value * dx * dx;
    p.x -= this.mid;
    p.multiplyScalar(this.scale);
    return p.applyMatrix4(this.group.matrixWorld);
  }

  /** A soft shadow on the ground under it: [x, z, half-length, half-width]. */
  footprint(): number[] {
    const p = this.group.position;
    const yaw = this.group.rotation.y;
    const l = this.spec.length * 0.5;
    const w = this.spec.length * 0.16;
    return [p.x, p.z, Math.abs(Math.cos(yaw)) * l + Math.abs(Math.sin(yaw)) * w, Math.abs(Math.sin(yaw)) * l + Math.abs(Math.cos(yaw)) * w];
  }
}
