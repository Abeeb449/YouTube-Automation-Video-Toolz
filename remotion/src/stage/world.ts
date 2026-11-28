/**
 * The places a live 3D shot can happen in: under water, at the surface, on a beach, a dark studio (for looking inside
 * an animal) and from the air. Every place is a real lit 3D space; nothing in it is a still picture. All motion is a
 * formula of time, so any frame can be drawn on its own.
 */
import * as THREE from 'three';
import {rnd} from './math';

export const CAUSTIC_GLSL = /* glsl */ `
float ytCaustic(vec2 uv, float t) {
  const float TAU = 6.28318530718;
  vec2 p = mod(uv * TAU, TAU) - 250.0;
  vec2 i = p;
  float c = 1.0;
  const float inten = 0.005;
  for (int n = 0; n < 4; n++) {
    float tt = t * (1.0 - (3.5 / float(n + 1)));
    i = p + vec2(cos(tt - i.x) + sin(tt + i.y), sin(tt - i.y) + cos(tt + i.x));
    c += 1.0 / length(vec2(p.x / (sin(i.x + tt) / inten), p.y / (cos(i.y + tt) / inten)));
  }
  c /= 4.0;
  c = 1.17 - pow(c, 1.4);
  return pow(abs(c), 8.0);
}
`;

export const NOISE_GLSL = /* glsl */ `
float ytHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float ytNoise(vec2 p) {
  vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(ytHash(i), ytHash(i + vec2(1.0, 0.0)), f.x), mix(ytHash(i + vec2(0.0, 1.0)), ytHash(i + vec2(1.0, 1.0)), f.x), f.y);
}
float ytFbm(vec2 p) { float a = 0.5; float s = 0.0; for (int i = 0; i < 4; i++) { s += a * ytNoise(p); p *= 2.03; a *= 0.5; } return s; }
`;

export type EnvSpec = {
  kind?: 'sea' | 'surface' | 'beach' | 'studio' | 'aerial' | 'map' | 'globe';
  /** sea: 0 = just under the surface, bright · 1 = deep and dark */
  depth?: number;
  /** water colour: blue (open sea) · green (cold coastal water) · teal */
  water?: 'blue' | 'green' | 'teal';
  /** sky and light above water: day · overcast · dusk · dawn · night */
  sky?: 'day' | 'overcast' | 'dusk' | 'dawn' | 'night';
  /** sea: metres from the surface to the sea floor (none = open water) */
  floor?: number;
  kelp?: boolean;
  rays?: number;
  snow?: number;
  /** where the sun stands above water: a direction [x, y, z] (y up; the sea of a beach is toward -z) */
  sun?: [number, number, number];
  /** wave height at the surface, 0..1 */
  swell?: number;
  exposure?: number;
};

export type Env = {
  scene: THREE.Scene;
  shared: {uTime: {value: number}; uCaustic: {value: number}; uCausticColor: {value: THREE.Color}; uFogColor: {value: THREE.Color}};
  update: (t: number, cam: THREE.PerspectiveCamera) => void;
  exposure: number;
  underwater: boolean;
};

const col = (h: string) => new THREE.Color(h);

const WATER = {
  blue: {top: '#3fa6d6', mid: '#0c4f7c', deep: '#031a2c', glow: '#bfeaff'},
  teal: {top: '#49b6c0', mid: '#0b5a6a', deep: '#03202a', glow: '#c9f5ee'},
  green: {top: '#5fae8f', mid: '#16594f', deep: '#06211f', glow: '#d6f2c9'},
};

const SKY = {
  day: {zenith: '#2f6fb8', horizon: '#bcd9ee', sun: '#fff4dc', sunDir: [0.35, 0.62, -0.7], light: 2.6, amb: '#9fc3e6', water: '#0c3b5c', haze: '#cfe1ee', cloud: 0.35},
  overcast: {zenith: '#7c8a96', horizon: '#c9d0d4', sun: '#f2f2ee', sunDir: [0.2, 0.75, -0.6], light: 1.7, amb: '#b9c2c9', water: '#2b4756', haze: '#c5ccd0', cloud: 0.85},
  dusk: {zenith: '#33426a', horizon: '#efb083', sun: '#ffd6a6', sunDir: [0.55, 0.16, -0.82], light: 2.1, amb: '#a79c9c', water: '#1f3852', haze: '#dfae8c', cloud: 0.45},
  dawn: {zenith: '#51667f', horizon: '#eccfb4', sun: '#ffe6c4', sunDir: [-0.42, 0.3, -0.86], light: 2.3, amb: '#b4b9c2', water: '#27485c', haze: '#d6c8bd', cloud: 0.5},
  night: {zenith: '#060b16', horizon: '#16233a', sun: '#b8c8e8', sunDir: [0.3, 0.5, -0.8], light: 0.55, amb: '#3a4a66', water: '#050d18', haze: '#0f1a2c', cloud: 0.3},
};

/** Specks hanging in the water (or dust in still air): large and soft when close to the lens, repeating around it. */
const makeSnow = (color: THREE.Color, count: number, box: number, shared: Env['shared'], gain = 1) => {
  const pos = new Float32Array(count * 3);
  const seed = new Float32Array(count * 4);
  for (let i = 0; i < count; i++) {
    pos[i * 3] = rnd(i * 1.7) * box; pos[i * 3 + 1] = rnd(i * 2.3 + 5) * box; pos[i * 3 + 2] = rnd(i * 3.1 + 9) * box;
    seed[i * 4] = rnd(i * 4.3); seed[i * 4 + 1] = rnd(i * 5.9); seed[i * 4 + 2] = rnd(i * 6.7); seed[i * 4 + 3] = 0.4 + rnd(i * 8.1);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('aSeed', new THREE.BufferAttribute(seed, 4));
  const mat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false,
    uniforms: {uTime: shared.uTime, uCam: {value: new THREE.Vector3()}, uBox: {value: box}, uColor: {value: color}, uPx: {value: 1080}, uGain: {value: gain}},
    vertexShader: `
      uniform float uTime; uniform vec3 uCam; uniform float uBox; uniform float uPx; attribute vec4 aSeed; varying float vA;
      void main(){
        vec3 p = position + vec3(sin(uTime * 0.31 + aSeed.x * 6.28) * 0.5 + uTime * 0.12, -uTime * 0.07 * (0.4 + aSeed.y), cos(uTime * 0.23 + aSeed.z * 6.28) * 0.5);
        p = mod(p - uCam + uBox * 0.5, uBox) - uBox * 0.5 + uCam;
        vec4 mv = viewMatrix * vec4(p, 1.0);
        float z = max(-mv.z, 0.05);
        float size = aSeed.w * uPx * 0.028 / z;
        gl_PointSize = clamp(size, 1.5, uPx * 0.035);
        vA = smoothstep(uBox * 0.5, uBox * 0.3, length(p - uCam)) * smoothstep(0.3, 1.4, z) * (0.3 + 0.7 * aSeed.x) * clamp(7.0 / size, 0.14, 1.0);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `uniform vec3 uColor; uniform float uGain; varying float vA; void main(){ float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.08, d); gl_FragColor = vec4(uColor, a * vA * 0.5 * uGain);
#include <colorspace_fragment>
 }`,
  });
  const points = new THREE.Points(geo, mat);
  points.frustumCulled = false;
  points.renderOrder = 6;
  return {points, mat};
};

/* ------------------------------------------------------------------------------------------- under water */
export const buildSea = (spec: EnvSpec): Env => {
  const scene = new THREE.Scene();
  const depth = spec.depth ?? 0.35;
  const pal = WATER[spec.water ?? 'blue'];
  const dim = 1 - 0.72 * depth;
  const top = col(pal.top).multiplyScalar(dim);
  const mid = col(pal.mid).multiplyScalar((0.35 + 0.65 * dim) * 1.0);
  const deep = col(pal.deep).lerp(col(pal.mid), 0.22).multiplyScalar(0.55 + 0.45 * dim);
  const shared = {uTime: {value: 0}, uCaustic: {value: 0.55 * (1 - depth) + 0.05}, uCausticColor: {value: col(pal.glow)}, uFogColor: {value: mid.clone()}};
  const sunDir = new THREE.Vector3(0.25, 1, -0.2).normalize();

  scene.fog = new THREE.FogExp2(mid.getHex(), 0.022 + 0.02 * depth);
  scene.background = mid.clone();

  // the water all around: bright toward the surface, dark below
  const dome = new THREE.Mesh(
    new THREE.SphereGeometry(400, 48, 32),
    new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false,
      uniforms: {uTop: {value: top}, uMid: {value: mid}, uDeep: {value: deep}, uSun: {value: sunDir}, uGlow: {value: col(pal.glow).multiplyScalar(0.55 * (1 - depth))}, uTime: shared.uTime},
      vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `
        uniform vec3 uTop; uniform vec3 uMid; uniform vec3 uDeep; uniform vec3 uSun; uniform vec3 uGlow; uniform float uTime; varying vec3 vDir;
        ${NOISE_GLSL}
        void main(){
          vec3 d = normalize(vDir);
          vec3 c = mix(uMid, uTop, smoothstep(0.0, 0.8, d.y));
          c = mix(c, uDeep, smoothstep(-0.04, -0.95, d.y));
          float s = max(dot(d, uSun), 0.0);
          float shimmer = 0.75 + 0.25 * ytNoise(d.xz * 9.0 / max(d.y, 0.15) + uTime * 0.25);
          c += uGlow * (pow(s, 5.0) * 0.9 * shimmer + pow(s, 40.0) * 1.4);
          gl_FragColor = vec4(c, 1.0);
#include <colorspace_fragment>

        }`,
    }),
  );
  dome.renderOrder = -10;
  dome.frustumCulled = false;
  scene.add(dome);

  // light: the sun through the water, the bright water above, the dark water below
  const sun = new THREE.DirectionalLight(col(pal.glow), 2.6 * (1 - 0.6 * depth));
  sun.position.copy(sunDir).multiplyScalar(60);
  scene.add(sun);
  scene.add(new THREE.HemisphereLight(top.clone().lerp(col('#ffffff'), 0.25), deep.clone(), 2.3 * (0.45 + 0.55 * dim)));
  const fill = new THREE.DirectionalLight(mid.clone().lerp(col('#ffffff'), 0.5), 0.5);
  scene.add(fill);

  // shafts of light slanting down from the surface
  const nRays = Math.round((spec.rays ?? 1) * 22 * (1 - 0.8 * depth));
  const rayGeo = new THREE.PlaneGeometry(1, 1);
  rayGeo.translate(0, -0.5, 0);
  const rays: {mesh: THREE.Mesh; base: THREE.Vector3; w: number; len: number; ph: number}[] = [];
  const rayDir = new THREE.Vector3(-0.22, -1, 0.12).normalize();
  for (let i = 0; i < nRays; i++) {
    const mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, fog: false,
      uniforms: {uColor: {value: col(pal.glow)}, uTime: shared.uTime, uPhase: {value: rnd(i * 3.1) * 6.28}, uPower: {value: (0.13 + 0.2 * rnd(i * 7.7)) * (1 - 0.7 * depth)}, uFar: {value: 1}},
      vertexShader: `varying vec2 vUv; varying float vDist; void main(){ vUv = uv; vec4 mv = modelViewMatrix * vec4(position, 1.0); vDist = -mv.z; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `
        uniform vec3 uColor; uniform float uTime; uniform float uPhase; uniform float uPower; varying vec2 vUv; varying float vDist;
        void main(){
          float x = vUv.x * 2.0 - 1.0;
          float across = exp(-x * x * 5.0);
          float along = smoothstep(0.0, 0.08, 1.0 - vUv.y) * pow(vUv.y, 1.6);
          float flick = 0.65 + 0.35 * sin(uTime * 0.7 + uPhase) * sin(uTime * 0.31 + uPhase * 2.3);
          float fade = smoothstep(3.0, 9.0, vDist) * smoothstep(90.0, 30.0, vDist);
          gl_FragColor = vec4(uColor, across * along * flick * uPower * fade);
#include <colorspace_fragment>

        }`,
    });
    const mesh = new THREE.Mesh(rayGeo, mat);
    mesh.frustumCulled = false;
    mesh.matrixAutoUpdate = false;
    mesh.renderOrder = 5;
    scene.add(mesh);
    rays.push({mesh, base: new THREE.Vector3(rnd(i * 1.3) * 80, 0, rnd(i * 2.9) * 80), w: 1.6 + 6.5 * rnd(i * 5.3), len: 30 + 34 * rnd(i * 4.1), ph: rnd(i) * 6.28});
  }

  const {points: snow, mat: snowMat} = makeSnow(col(pal.glow), Math.round((spec.snow ?? 1) * 1000), 46, shared);
  scene.add(snow);

  // the surface seen from below
  const surfMat = new THREE.ShaderMaterial({
    side: THREE.DoubleSide, transparent: true, depthWrite: false, fog: false,
    uniforms: {uTime: shared.uTime, uCam: {value: new THREE.Vector3()}, uColor: {value: col(pal.glow)}, uTop: {value: top}, uMid: {value: mid}},
    vertexShader: `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
    fragmentShader: `
      uniform float uTime; uniform vec3 uCam; uniform vec3 uColor; uniform vec3 uTop; uniform vec3 uMid; varying vec3 vW;
      ${CAUSTIC_GLSL}
      void main(){
        float d = length(vW.xz - uCam.xz);
        float h = max(vW.y - uCam.y, 0.5);
        float c = ytCaustic(vW.xz * 0.045, uTime * 0.5) + 0.6 * ytCaustic(vW.xz * 0.11 + 3.0, uTime * 0.7);
        float window = smoothstep(h * 2.2, h * 0.3, d);
        float far = 1.0 - exp(-pow(d / (h * 4.0 + 16.0), 2.0));
        vec3 colr = mix(uTop * 1.25, uColor, clamp(c * 0.9 + window * 0.45, 0.0, 1.0));
        colr = mix(colr, uMid, far);
        gl_FragColor = vec4(colr, mix(clamp(0.35 + 0.55 * window + 0.5 * c, 0.0, 1.0), 1.0, far));
#include <colorspace_fragment>

      }`,
  });
  const surface = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), surfMat);
  surface.rotation.x = -Math.PI / 2;
  surface.renderOrder = -5;
  surface.frustumCulled = false;
  scene.add(surface);

  // the sea floor, when the water is shallow enough to see it
  let floorMat: THREE.ShaderMaterial | null = null;
  if (spec.floor) {
    const y = -spec.floor;
    floorMat = new THREE.ShaderMaterial({
      uniforms: {uTime: shared.uTime, uFog: {value: mid}, uSand: {value: col(spec.water === 'green' ? '#8d8a6a' : '#a59c7c').multiplyScalar(0.55 + 0.45 * dim)}, uGlow: {value: col(pal.glow)}, uCaustic: shared.uCaustic, uDensity: {value: 0.022 + 0.02 * depth}},
      vertexShader: `varying vec3 vW; varying float vDist; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; vec4 mv = viewMatrix * w; vDist = -mv.z; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `
        uniform float uTime; uniform vec3 uFog; uniform vec3 uSand; uniform vec3 uGlow; uniform float uCaustic; uniform float uDensity; varying vec3 vW; varying float vDist;
        ${NOISE_GLSL}
        ${CAUSTIC_GLSL}
        void main(){
          float ripple = ytNoise(vec2(vW.x * 0.35 + ytNoise(vW.xz * 0.2) * 2.0, vW.z * 2.2));
          float patches = ytFbm(vW.xz * 0.12);
          vec3 c = uSand * (0.72 + 0.22 * ripple + 0.25 * patches);
          c = mix(c, c * vec3(0.35, 0.45, 0.4), smoothstep(0.55, 0.75, ytFbm(vW.xz * 0.05 + 7.0)));
          c += uGlow * ytCaustic(vW.xz * 0.16, uTime * 0.55) * uCaustic * 0.55;
          float f = 1.0 - exp(-uDensity * uDensity * vDist * vDist);
          gl_FragColor = vec4(mix(c, uFog, clamp(f, 0.0, 1.0)), 1.0);
#include <colorspace_fragment>

        }`,
    });
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(600, 600), floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = y;
    floor.frustumCulled = false;
    scene.add(floor);
    // rocks on the floor
    const rockGeo = new THREE.IcosahedronGeometry(1, 2);
    const rp = rockGeo.attributes.position;
    for (let i = 0; i < rp.count; i++) {
      // every corner that shares a place moves the same way, so the rock stays one solid lump
      const x = rp.getX(i), y0 = rp.getY(i), z = rp.getZ(i);
      const k = 1 + 0.22 * Math.sin(x * 4.3 + z * 2.1) * Math.cos(y0 * 3.7 + x * 1.3) + 0.16 * Math.sin(x * 3.1 + z * 2.3 + y0 * 5.1);
      rp.setXYZ(i, x * k, y0 * k * 0.7, z * k);
    }
    rockGeo.computeVertexNormals();
    const rockMat = new THREE.MeshStandardMaterial({color: col(spec.water === 'green' ? '#4a4a3c' : '#4c4a44'), roughness: 0.95});
    const rocks = new THREE.InstancedMesh(rockGeo, rockMat, 46);
    const m4 = new THREE.Matrix4();
    for (let i = 0; i < 46; i++) {
      const a = rnd(i * 2.1) * 6.28;
      const r = 6 + rnd(i * 3.7) * 55;
      const s = 0.5 + rnd(i * 5.1) * 2.6;
      m4.compose(new THREE.Vector3(Math.cos(a) * r, y + s * 0.15, Math.sin(a) * r), new THREE.Quaternion().setFromEuler(new THREE.Euler(rnd(i) * 0.6, rnd(i * 7) * 6.28, rnd(i * 3) * 0.6)), new THREE.Vector3(s * (0.8 + rnd(i * 11)), s * 0.7, s));
      rocks.setMatrixAt(i, m4);
    }
    scene.add(rocks);
    if (spec.kelp) scene.add(buildKelp(y, shared, spec.floor));
  }

  const tmpA = new THREE.Vector3();
  const tmpB = new THREE.Vector3();
  const tmpC = new THREE.Vector3();
  return {
    scene, shared, exposure: spec.exposure ?? 1.0, underwater: true,
    update: (t, cam) => {
      shared.uTime.value = t;
      dome.position.copy(cam.position);
      fill.position.copy(cam.position);
      snowMat.uniforms.uCam.value.copy(cam.position);
      surfMat.uniforms.uCam.value.copy(cam.position);
      surface.position.set(cam.position.x, 0, cam.position.z);
      for (const r of rays) {
        // each shaft keeps its place in the world, repeating so there are always some near the lens
        const span = 80;
        const bx = ((r.base.x - cam.position.x) % span + span * 1.5) % span - span / 2 + cam.position.x;
        const bz = ((r.base.z - cam.position.z) % span + span * 1.5) % span - span / 2 + cam.position.z;
        tmpA.set(bx, 0.5, bz);
        tmpB.copy(cam.position).sub(tmpA);
        const side = tmpC.crossVectors(rayDir, tmpB).normalize();
        const normal = tmpB.crossVectors(side, rayDir).normalize();
        const m = r.mesh.matrix;
        const up = rayDir.clone().multiplyScalar(-r.len);
        m.set(side.x * r.w, up.x, normal.x, tmpA.x, side.y * r.w, up.y, normal.y, tmpA.y, side.z * r.w, up.z, normal.z, tmpA.z, 0, 0, 0, 1);
        r.mesh.matrixWorldNeedsUpdate = true;
      }
    },
  };
};

/** Kelp: tall ribbons that sway with the swell (the cold-water forests of the Cape coast). */
const buildKelp = (y: number, shared: Env['shared'], height: number) => {
  const n = 150;
  const seg = 14;
  const geo = new THREE.PlaneGeometry(0.5, 1, 1, seg);
  geo.translate(0, 0.5, 0);
  const mat = new THREE.ShaderMaterial({
    side: THREE.DoubleSide,
    uniforms: {uTime: shared.uTime, uFog: shared.uFogColor, uA: {value: new THREE.Color('#31461f')}, uB: {value: new THREE.Color('#8b7a2e')}},
    vertexShader: `
      uniform float uTime; attribute vec4 aK; varying float vH; varying float vDist; varying float vShade;
      void main(){
        float h = position.y; vH = h;
        vec3 p = position;
        p.y *= aK.z;
        float sway = sin(uTime * 0.9 + aK.w * 6.28 + h * 2.4) * 0.9 + sin(uTime * 0.37 + aK.w * 11.0) * 1.4;
        p.x += sway * h * h * 1.6 + sin(h * 9.0 + aK.w * 20.0) * 0.12;
        p.z += cos(uTime * 0.6 + aK.w * 3.0 + h * 1.7) * h * 0.8;
        float a = aK.w * 6.28; float cs = cos(a); float sn = sin(a);
        p.xz = vec2(p.x * cs - p.z * sn * 0.2, p.x * sn + p.z * cs);
        vec4 w = vec4(p + vec3(aK.x, ${y.toFixed(2)}, aK.y), 1.0);
        vec4 mv = viewMatrix * w; vDist = -mv.z; vShade = 0.6 + 0.4 * sin(aK.w * 40.0);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `
      uniform vec3 uFog; uniform vec3 uA; uniform vec3 uB; varying float vH; varying float vDist; varying float vShade;
      void main(){
        vec3 c = mix(uA, uB, vH * vH) * vShade * (0.55 + 0.6 * vH);
        float f = 1.0 - exp(-0.0011 * vDist * vDist);
        gl_FragColor = vec4(mix(c, uFog, clamp(f, 0.0, 1.0)), 1.0);
#include <colorspace_fragment>

      }`,
  });
  const mesh = new THREE.InstancedMesh(geo, mat, n);
  const k = new Float32Array(n * 4);
  const m4 = new THREE.Matrix4();
  for (let i = 0; i < n; i++) {
    const a = rnd(i * 1.9) * 6.28;
    const r = 7 + rnd(i * 2.7) * 42;
    k[i * 4] = Math.cos(a) * r; k[i * 4 + 1] = Math.sin(a) * r; k[i * 4 + 2] = height * (0.45 + 0.5 * rnd(i * 3.3)); k[i * 4 + 3] = rnd(i * 4.7);
    mesh.setMatrixAt(i, m4);
  }
  geo.setAttribute('aK', new THREE.InstancedBufferAttribute(k, 4));
  mesh.frustumCulled = false;
  return mesh;
};

/* ------------------------------------------------------------------------------------- sky and open water */
const skyDome = (sk: (typeof SKY)['day'], shared: Env['shared'], sunAt?: [number, number, number]) => {
  const sunDir = new THREE.Vector3(...((sunAt ?? sk.sunDir) as [number, number, number])).normalize();
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(900, 48, 32),
    new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false,
      uniforms: {uZen: {value: col(sk.zenith)}, uHor: {value: col(sk.horizon)}, uSunCol: {value: col(sk.sun)}, uSun: {value: sunDir}, uTime: shared.uTime, uCloud: {value: sk.cloud}},
      vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `
        uniform vec3 uZen; uniform vec3 uHor; uniform vec3 uSunCol; uniform vec3 uSun; uniform float uTime; uniform float uCloud; varying vec3 vDir;
        ${NOISE_GLSL}
        void main(){
          vec3 d = normalize(vDir);
          float h = clamp(d.y, -0.2, 1.0);
          vec3 c = mix(uHor, uZen, pow(smoothstep(-0.02, 0.75, h), 0.6));
          float s = max(dot(d, uSun), 0.0);
          c += uSunCol * (pow(s, 8.0) * 0.35 + pow(s, 180.0) * 1.2);
          vec2 cp = d.xz / max(d.y + 0.12, 0.05) * 1.3 + vec2(uTime * 0.012, uTime * 0.004);
          float cl = smoothstep(1.0 - uCloud, 1.25 - uCloud * 0.6, ytFbm(cp) + 0.35 * ytFbm(cp * 2.7 + 4.0));
          vec3 cloudCol = mix(uHor * 1.05, uSunCol, 0.35 + 0.4 * pow(s, 3.0));
          c = mix(c, cloudCol, cl * smoothstep(0.0, 0.25, d.y) * 0.8);
          gl_FragColor = vec4(c, 1.0);
#include <colorspace_fragment>

        }`,
    }),
  );
  mesh.renderOrder = -10;
  mesh.frustumCulled = false;
  return {mesh, sunDir};
};

const WAVES_GLSL = /* glsl */ `
uniform float uTime; uniform float uSwell;
vec3 ytWave(vec2 p, vec2 dir, float len, float amp, float speed, inout vec3 tangent, inout vec3 binormal) {
  float k = 6.28318 / len; float f = k * (dot(dir, p) - speed * uTime); float a = amp * uSwell;
  tangent += vec3(-dir.x * dir.x * a * k * sin(f), dir.x * a * k * cos(f), -dir.x * dir.y * a * k * sin(f));
  binormal += vec3(-dir.x * dir.y * a * k * sin(f), dir.y * a * k * cos(f), -dir.y * dir.y * a * k * sin(f));
  return vec3(dir.x * a * cos(f), a * sin(f), dir.y * a * cos(f));
}
vec3 ytSea(vec2 p, out vec3 n) {
  vec3 t = vec3(1.0, 0.0, 0.0); vec3 b = vec3(0.0, 0.0, 1.0); vec3 o = vec3(0.0);
  o += ytWave(p, normalize(vec2(1.0, 0.35)), 38.0, 0.55, 3.2, t, b);
  o += ytWave(p, normalize(vec2(0.7, -0.6)), 21.0, 0.30, 2.6, t, b);
  o += ytWave(p, normalize(vec2(-0.2, 1.0)), 11.0, 0.16, 2.1, t, b);
  o += ytWave(p, normalize(vec2(0.9, 0.8)), 5.5, 0.07, 1.7, t, b);
  o += ytWave(p, normalize(vec2(-0.6, 0.4)), 2.7, 0.03, 1.3, t, b);
  n = normalize(cross(b, t));
  return o;
}
`;

const seaSurface = (sk: (typeof SKY)['day'], shared: Env['shared'], sunDir: THREE.Vector3, swell: number, size = 900, segs = 220) => {
  const mat = new THREE.ShaderMaterial({
    uniforms: {uTime: shared.uTime, uSwell: {value: swell}, uDeep: {value: col(sk.water)}, uSky: {value: col(sk.horizon)}, uZen: {value: col(sk.zenith)}, uSunCol: {value: col(sk.sun)}, uSun: {value: sunDir},
      uCam: {value: new THREE.Vector3()}, uHaze: {value: col(sk.haze)}, uShore: {value: -9999}},
    vertexShader: `
      ${WAVES_GLSL}
      varying vec3 vW; varying vec3 vN; varying float vDist;
      void main(){
        vec4 w = modelMatrix * vec4(position, 1.0);
        vec3 n; vec3 o = ytSea(w.xz, n);
        w.xyz += o; vW = w.xyz; vN = n;
        vec4 mv = viewMatrix * w; vDist = -mv.z;
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `
      uniform vec3 uDeep; uniform vec3 uSky; uniform vec3 uZen; uniform vec3 uSunCol; uniform vec3 uSun; uniform vec3 uCam; uniform vec3 uHaze; uniform float uTime;
      varying vec3 vW; varying vec3 vN; varying float vDist;
      ${NOISE_GLSL}
      void main(){
        vec3 v = normalize(uCam - vW);
        vec2 q = vW.xz;
        float fine = exp(-vDist / 45.0);
        vec3 n = normalize(vN + 0.10 * fine * vec3(ytNoise(q * 1.7 + uTime * 0.9) - 0.5, 0.0, ytNoise(q * 1.9 - uTime * 0.8) - 0.5) + 0.05 * fine * fine * vec3(ytNoise(q * 6.0 + uTime * 1.6) - 0.5, 0.0, ytNoise(q * 6.5 - uTime * 1.4) - 0.5));
        float fres = 0.03 + 0.97 * pow(1.0 - max(dot(n, v), 0.0), 5.0);
        vec3 r = reflect(-v, n);
        vec3 sky = mix(uSky, uZen, pow(clamp(r.y, 0.0, 1.0), 0.6));
        vec3 c = mix(uDeep * (0.75 + 0.5 * max(n.y - 0.9, 0.0) * 6.0), sky, fres);
        float sp = pow(max(dot(r, uSun), 0.0), 220.0);
        c += uSunCol * sp * 1.6 + uSunCol * pow(max(dot(r, uSun), 0.0), 18.0) * 0.12;
        float haze = 1.0 - exp(-0.000012 * vDist * vDist);
        gl_FragColor = vec4(mix(c, uHaze, clamp(haze, 0.0, 1.0)), 1.0);
#include <colorspace_fragment>

      }`,
  });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(size, size, segs, segs), mat);
  mesh.rotation.x = -Math.PI / 2;
  mesh.frustumCulled = false;
  return {mesh, mat};
};

export const buildSurface = (spec: EnvSpec): Env => {
  const scene = new THREE.Scene();
  const sk = SKY[spec.sky ?? 'day'];
  const shared = {uTime: {value: 0}, uCaustic: {value: 0}, uCausticColor: {value: col('#ffffff')}, uFogColor: {value: col(sk.haze)}};
  scene.fog = new THREE.FogExp2(col(sk.haze).getHex(), 0.0032);
  const {mesh: dome, sunDir} = skyDome(sk, shared, spec.sun);
  scene.add(dome);
  const {mesh: sea, mat: seaMat} = seaSurface(sk, shared, sunDir, 0.35 + 0.9 * (spec.swell ?? 0.4));
  scene.add(sea);
  const sun = new THREE.DirectionalLight(col(sk.sun), sk.light);
  sun.position.copy(sunDir).multiplyScalar(100);
  scene.add(sun);
  scene.add(new THREE.HemisphereLight(col(sk.amb), col(sk.water), 1.5));
  return {
    scene, shared, exposure: spec.exposure ?? 1.0, underwater: false,
    update: (t, cam) => {
      shared.uTime.value = t;
      dome.position.copy(cam.position);
      // the water sheet follows the lens in whole steps, so the waves stay where they are in the world
      const step = 900 / 220;
      sea.position.set(Math.round(cam.position.x / step) * step, 0, Math.round(cam.position.z / step) * step);
      seaMat.uniforms.uCam.value.copy(cam.position);
    },
  };
};

/* ---------------------------------------------------------------------------------------------- the beach */
/** A beach at the water's edge. The sea is toward -z, the land toward +z; sand level is y = 0 at z = 0. */
export const beachHeight = (x: number, z: number) => Math.max(-1.2, z * 0.035) + 0.018 * Math.sin(x * 0.21 + z * 0.13) + 0.006 * Math.sin(x * 0.8 - z * 0.5);

export const buildBeach = (spec: EnvSpec): Env => {
  const scene = new THREE.Scene();
  const sk = SKY[spec.sky ?? 'overcast'];
  const shared = {uTime: {value: 0}, uCaustic: {value: 0}, uCausticColor: {value: col('#ffffff')}, uFogColor: {value: col(sk.haze)}};
  scene.fog = new THREE.FogExp2(col(sk.haze).getHex(), 0.006);
  const {mesh: dome, sunDir} = skyDome(sk, shared, spec.sun);
  scene.add(dome);
  const {mesh: sea, mat: seaMat} = seaSurface(sk, shared, sunDir, 0.22 + 0.5 * (spec.swell ?? 0.3), 900, 200);
  sea.position.set(0, -0.32, -430);
  scene.add(sea);

  const sandGeo = new THREE.PlaneGeometry(700, 320, 260, 150);
  sandGeo.rotateX(-Math.PI / 2);
  sandGeo.translate(0, 0, 130);
  const sp = sandGeo.attributes.position;
  for (let i = 0; i < sp.count; i++) sp.setY(i, beachHeight(sp.getX(i), sp.getZ(i)));
  sandGeo.computeVertexNormals();
  const sandMat = new THREE.ShaderMaterial({
    uniforms: {uTime: shared.uTime, uSun: {value: sunDir}, uSunCol: {value: col(sk.sun).multiplyScalar(sk.light * 0.36)}, uAmb: {value: col(sk.amb).multiplyScalar(0.74)}, uSky: {value: col(sk.horizon)},
      uHaze: {value: col(sk.haze)}, uCam: {value: new THREE.Vector3()}, uShadow: {value: new Float32Array(4 * 12)}, uShadowN: {value: 0}},
    vertexShader: `varying vec3 vW; varying vec3 vN; varying float vDist; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; vN = normal; vec4 mv = viewMatrix * w; vDist = -mv.z; gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `
      uniform float uTime; uniform vec3 uSun; uniform vec3 uSunCol; uniform vec3 uAmb; uniform vec3 uSky; uniform vec3 uHaze; uniform vec3 uCam; uniform vec4 uShadow[12]; uniform int uShadowN;
      varying vec3 vW; varying vec3 vN; varying float vDist;
      ${NOISE_GLSL}
      // where the last wave reached and where the water is now
      float swash(float x, float t){ return -1.6 + 2.6 * sin(t * 0.42 + ytNoise(vec2(x * 0.06, 2.0)) * 3.0) + 1.2 * ytNoise(vec2(x * 0.12, t * 0.2)) + 0.5 * ytNoise(vec2(x * 0.6, t * 0.5)); }
      void main(){
        vec2 q = vW.xz;
        float grain = ytNoise(q * 38.0) * 0.5 + ytNoise(q * 90.0) * 0.5;
        float ripple = sin(q.y * 7.5 + ytNoise(q * 0.7) * 5.0 + q.x * 0.6) * 0.5 + 0.5;
        float near = smoothstep(26.0, 3.0, vDist);
        vec3 dry = vec3(0.83, 0.75, 0.60) * (0.90 + 0.12 * grain * near) * (0.97 + 0.03 * ripple * near);
        dry = mix(dry, dry * vec3(0.93, 0.90, 0.85), ytFbm(q * 0.3));
        vec3 wet = vec3(0.46, 0.40, 0.33) * (0.92 + 0.08 * grain * near);
        float edge = swash(q.x, uTime);
        float reach = 1.3 + 1.2 * ytNoise(vec2(q.x * 0.05, 9.0));
        float wetness = smoothstep(reach + 1.6, reach - 0.6, q.y);
        vec3 base = mix(dry, wet, wetness);
        vec3 n = normalize(vN + vec3(0.0, 0.0, (ripple - 0.5) * 0.10 * (1.0 - wetness) * near));
        float diff = max(dot(n, uSun), 0.0);
        vec3 c = base * (uAmb + uSunCol * diff);
        // wet sand mirrors the sky
        vec3 v = normalize(uCam - vW);
        float fres = pow(1.0 - max(dot(n, v), 0.0), 4.0);
        c = mix(c, uSky, wetness * (0.12 + 0.6 * fres));
        // the thin sheet of water running up and back, with its foam line
        float water = smoothstep(edge + 0.25, edge - 0.5, q.y);
        c = mix(c, mix(vec3(0.34, 0.46, 0.50), uSky, 0.35 + 0.5 * fres), water * 0.75);
        float foam = smoothstep(0.55, 0.0, abs(q.y - edge)) * (0.55 + 0.45 * ytNoise(q * 3.0 + uTime * 0.6));
        foam += smoothstep(edge, edge - 6.0, q.y) * smoothstep(0.62, 0.8, ytNoise(q * 1.4 + vec2(0.0, uTime * 0.5))) * 0.5;
        c = mix(c, vec3(0.97), clamp(foam, 0.0, 1.0) * 0.9);
        // soft shadows under whatever lies on the sand
        float sh = 0.0;
        for (int i = 0; i < 12; i++) { if (i >= uShadowN) break; vec4 s = uShadow[i]; vec2 d = (q - s.xy) / vec2(s.z, s.w); sh = max(sh, smoothstep(1.25, 0.25, length(d))); }
        c *= 1.0 - 0.5 * sh;
        float haze = 1.0 - exp(-0.00004 * vDist * vDist);
        gl_FragColor = vec4(mix(c, uHaze, clamp(haze, 0.0, 1.0)), 1.0);
#include <colorspace_fragment>

      }`,
  });
  const sand = new THREE.Mesh(sandGeo, sandMat);
  sand.frustumCulled = false;
  scene.add(sand);

  // dunes far behind, so the land does not end in a line
  const duneGeo = new THREE.PlaneGeometry(900, 60, 120, 1);
  const dp = duneGeo.attributes.position;
  for (let i = 0; i < dp.count; i++) if (dp.getY(i) > 0) dp.setY(i, 6 + 9 * (0.5 + 0.5 * Math.sin(dp.getX(i) * 0.021 + 1.3)) + 5 * Math.sin(dp.getX(i) * 0.057));
  const dune = new THREE.Mesh(duneGeo, new THREE.MeshBasicMaterial({color: col(sk.haze).lerp(col('#6f6a55'), 0.55), fog: true}));
  dune.position.set(0, 4, 250);
  dune.rotation.y = Math.PI;
  scene.add(dune);

  const sun = new THREE.DirectionalLight(col(sk.sun), sk.light);
  sun.position.copy(sunDir).multiplyScalar(100);
  scene.add(sun);
  scene.add(new THREE.HemisphereLight(col(sk.amb), col('#8a7a5c'), 1.6));
  const env: Env & {shadows?: (list: number[][]) => void} = {
    scene, shared, exposure: spec.exposure ?? 1.0, underwater: false,
    update: (t, cam) => {
      shared.uTime.value = t;
      dome.position.copy(cam.position);
      seaMat.uniforms.uCam.value.copy(cam.position);
      sandMat.uniforms.uCam.value.copy(cam.position);
    },
  };
  env.shadows = (list) => {
    const arr = sandMat.uniforms.uShadow.value as Float32Array;
    list.slice(0, 12).forEach((s, i) => arr.set(s, i * 4));
    sandMat.uniforms.uShadowN.value = Math.min(12, list.length);
  };
  return env;
};

/* --------------------------------------------------------------------------------------------- the studio */
/** A dark, quiet space for looking at one animal closely or inside it. */
export const buildStudio = (spec: EnvSpec): Env => {
  const scene = new THREE.Scene();
  const shared = {uTime: {value: 0}, uCaustic: {value: 0.0}, uCausticColor: {value: col('#bfeaff')}, uFogColor: {value: col('#05090d')}};
  scene.fog = new THREE.FogExp2(0x030608, 0.012);
  const dome = new THREE.Mesh(
    new THREE.SphereGeometry(300, 32, 24),
    new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false, uniforms: {uTime: shared.uTime},
      vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `varying vec3 vDir; void main(){ vec3 d = normalize(vDir); vec3 c = mix(vec3(0.0016, 0.0032, 0.0052), vec3(0.0075, 0.019, 0.030), smoothstep(-0.5, 0.6, d.y)); c += vec3(0.004, 0.012, 0.018) * pow(max(d.y, 0.0), 3.0); gl_FragColor = vec4(c, 1.0);
#include <colorspace_fragment>
 }`,
    }),
  );
  dome.frustumCulled = false;
  dome.renderOrder = -10;
  scene.add(dome);
  // a faint measuring grid far below, drifting with the camera: depth without a "floor"
  const grid = new THREE.Mesh(
    new THREE.PlaneGeometry(400, 400),
    new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, fog: false, uniforms: {uTime: shared.uTime},
      vertexShader: `varying vec3 vW; varying float vDist; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; vec4 mv = viewMatrix * w; vDist = -mv.z; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `varying vec3 vW; varying float vDist; void main(){ vec2 g = abs(fract(vW.xz / 2.0 - 0.5) - 0.5) / fwidth(vW.xz / 2.0); float l = 1.0 - min(min(g.x, g.y), 1.0); float a = l * 0.16 * smoothstep(70.0, 8.0, vDist); gl_FragColor = vec4(0.45, 0.8, 0.95, a);
#include <colorspace_fragment>
 }`,
    }),
  );
  grid.rotation.x = -Math.PI / 2;
  grid.position.y = -3.2;
  scene.add(grid);
  const key = new THREE.DirectionalLight(0xdfefff, 2.4);
  key.position.set(4, 9, 7);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x6fd0ff, 2.0);
  rim.position.set(-6, 3, -8);
  scene.add(rim);
  scene.add(new THREE.HemisphereLight(0x9fc8e6, 0x05121c, 0.9));
  // a soft light from where the camera stands, so whatever side it looks at is never left in the dark
  const front = new THREE.DirectionalLight(0xcfe6ff, 0.85);
  scene.add(front);
  const {points: dust, mat: dustMat} = makeSnow(col('#9fd8ff'), 260, 24, shared, 0.55);
  scene.add(dust);
  return {scene, shared, exposure: spec.exposure ?? 1.0, underwater: false, update: (t, cam) => { shared.uTime.value = t; dome.position.copy(cam.position); front.position.copy(cam.position); dustMat.uniforms.uCam.value.copy(cam.position); grid.position.x = Math.round(cam.position.x / 2) * 2; grid.position.z = Math.round(cam.position.z / 2) * 2; }};
};

/* ------------------------------------------------------------------------------------------- from the air */
/** Looking down into the sea from the air (a drone's view): animals are dark shapes under a moving, glinting skin. */
export const buildAerial = (spec: EnvSpec): Env => {
  const scene = new THREE.Scene();
  const pal = WATER[spec.water ?? 'teal'];
  const mid = col(pal.mid).lerp(col(pal.top), 0.35);
  const shared = {uTime: {value: 0}, uCaustic: {value: 0.5}, uCausticColor: {value: col(pal.glow)}, uFogColor: {value: mid.clone()}};
  scene.background = mid.clone();
  // water gets murkier with depth: what is deeper is dimmer
  scene.fog = new THREE.FogExp2(mid.getHex(), 0.006);
  const bedMat = new THREE.ShaderMaterial({
    uniforms: {uTime: shared.uTime, uA: {value: mid}, uB: {value: col(pal.top)}, uGlow: {value: col(pal.glow)}},
    vertexShader: `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
    fragmentShader: `
      uniform float uTime; uniform vec3 uA; uniform vec3 uB; uniform vec3 uGlow; varying vec3 vW;
      ${NOISE_GLSL}
      ${CAUSTIC_GLSL}
      void main(){
        float patch_ = ytFbm(vW.xz * 0.035);
        vec3 c = mix(uA * 0.8, uB * 0.9, smoothstep(0.3, 0.75, patch_));
        c += uGlow * ytCaustic(vW.xz * 0.05, uTime * 0.4) * 0.12;
        gl_FragColor = vec4(c, 1.0);
#include <colorspace_fragment>

      }`,
  });
  const bed = new THREE.Mesh(new THREE.PlaneGeometry(900, 900), bedMat);
  bed.rotation.x = -Math.PI / 2;
  bed.position.y = -(spec.floor ?? 14);
  bed.frustumCulled = false;
  scene.add(bed);
  // the skin of the sea: ripples and glints, see-through
  const skinMat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, fog: false,
    uniforms: {uTime: shared.uTime, uGlow: {value: col(pal.glow)}, uSwell: {value: 0.4 + (spec.swell ?? 0.4)}},
    vertexShader: `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
    fragmentShader: `
      uniform float uTime; uniform vec3 uGlow; uniform float uSwell; varying vec3 vW;
      ${NOISE_GLSL}
      void main(){
        vec2 q = vW.xz;
        float w1 = ytNoise(vec2(q.x * 0.22 + uTime * 0.5, q.y * 0.9 - uTime * 0.2));
        float w2 = ytNoise(vec2(q.x * 0.9 - uTime * 0.7, q.y * 2.6 + uTime * 0.4));
        float glint = smoothstep(0.84, 0.99, w1 * 0.6 + w2 * 0.5) * uSwell * 0.5;
        float sheen = 0.03 + 0.05 * w1;
        gl_FragColor = vec4(uGlow, clamp(sheen + glint * 0.85, 0.0, 1.0));
#include <colorspace_fragment>

      }`,
  });
  const skin = new THREE.Mesh(new THREE.PlaneGeometry(900, 900), skinMat);
  skin.rotation.x = -Math.PI / 2;
  skin.frustumCulled = false;
  skin.renderOrder = 8;
  scene.add(skin);
  const sun = new THREE.DirectionalLight(0xffffff, 2.4);
  sun.position.set(20, 80, 10);
  scene.add(sun);
  scene.add(new THREE.HemisphereLight(col(pal.glow), mid, 1.6));
  return {scene, shared, exposure: spec.exposure ?? 1.0, underwater: true, update: (t) => { shared.uTime.value = t; }};
};

export const buildEnv = (spec: EnvSpec): Env =>
  spec.kind === 'surface' ? buildSurface(spec) : spec.kind === 'beach' ? buildBeach(spec) : spec.kind === 'studio' ? buildStudio(spec) : spec.kind === 'aerial' ? buildAerial(spec) : buildSea(spec);
