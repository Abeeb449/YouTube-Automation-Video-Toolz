/** Small maths for the live 3D stage: easing, repeatable random numbers, smooth curves through keyed points. */
export type V3 = [number, number, number];

export const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const smooth = (t: number) => t * t * (3 - 2 * t);

export const EASE: Record<string, (t: number) => number> = {
  linear: (t) => t,
  in: (t) => t * t * t,
  out: (t) => 1 - Math.pow(1 - t, 3),
  inOut: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  soft: smooth,
  expo: (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t)),
  back: (t) => 1 + 2.2 * Math.pow(t - 1, 3) + 1.2 * Math.pow(t - 1, 2),
};
export const ease = (name: string | undefined, t: number) => (EASE[name ?? 'inOut'] ?? EASE.inOut)(clamp(t));

/** 0→1 between t0 and t0+d, eased. */
export const ramp = (t: number, t0: number, d: number, e = 'out') => ease(e, d <= 0 ? (t >= t0 ? 1 : 0) : (t - t0) / d);

/** The same number for the same seed, every time (frames are drawn out of order on several machines). */
export const rnd = (seed: number) => {
  const x = Math.sin(seed * 127.1 + 311.7) * 43758.5453123;
  return x - Math.floor(x);
};
export const rndRange = (seed: number, a: number, b: number) => a + (b - a) * rnd(seed);

/** Smooth noise in one dimension (for drift and hand-held movement), about -1..1. */
export const noise1 = (x: number, seed = 0) => {
  const i = Math.floor(x);
  const f = x - i;
  const a = rnd(i + seed * 57.3) * 2 - 1;
  const b = rnd(i + 1 + seed * 57.3) * 2 - 1;
  return lerp(a, b, smooth(f));
};

const cr = (p0: number, p1: number, p2: number, p3: number, t: number) => {
  const t2 = t * t;
  const t3 = t2 * t;
  return 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3);
};

export type Key<T> = {t: number; v: T; ease?: string; cut?: boolean};

/** A moment's time: `at` in seconds (a word cue has already been turned into seconds), or `u` as a share of the shot. */
export const keyTime = (k: {at?: number; u?: number}, dur: number, fallback = 0) =>
  typeof k.at === 'number' ? k.at : typeof k.u === 'number' ? k.u * dur : fallback;

/** Value of a keyed track of numbers at time t (smooth through the keys; `cut` jumps). */
export const track = (keys: Key<number[]>[], t: number): number[] => {
  if (!keys.length) return [];
  if (t <= keys[0].t) return keys[0].v;
  const last = keys[keys.length - 1];
  if (t >= last.t) return last.v;
  let i = 0;
  while (i < keys.length - 2 && t >= keys[i + 1].t) i++;
  const a = keys[i];
  const b = keys[i + 1];
  if (b.cut) return a.v;
  const span = Math.max(1e-6, b.t - a.t);
  const u = ease(b.ease ?? 'soft', (t - a.t) / span);
  const before = i > 0 && !a.cut ? keys[i - 1].v : a.v;
  const after = i + 2 < keys.length && !keys[i + 2].cut ? keys[i + 2].v : b.v;
  // eased keys move straight from one to the next; unlabelled keys flow through as one curve
  if (b.ease) return a.v.map((x, k) => lerp(x, b.v[k], u));
  const lin = (t - a.t) / span;
  return a.v.map((x, k) => cr(before[k], x, b.v[k], after[k], lin));
};
