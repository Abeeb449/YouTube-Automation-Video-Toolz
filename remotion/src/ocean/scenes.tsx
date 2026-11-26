import React, {useEffect, useState} from 'react';
import {AbsoluteFill, continueRender, delayRender, Easing, Img, interpolate, OffthreadVideo, staticFile} from 'remotion';
import {Lottie, LottieAnimationData} from '@remotion/lottie';
import {C, DocuFrame, DocuProps, F, fmtNum, prog, Reveal, stagger, useT} from '../docu/kit';
import {OceanBackdrop} from './OceanBackdrop';
import {CREATURES, EXTENTS} from './creatures';

type XY = [number, number];

export type Actor = {
  /** Built-in creature: spermWhale, giantSquid, orca, shark, anglerfish, jellyfish, diver, fishSchool, octopus */
  creature?: string;
  /** Or your own cut-out image (PNG/SVG with transparency), path relative to the project. */
  image?: string;
  /** Or a Lottie animation (.json, e.g. a free animal from lottiefiles.com), path relative to the project. */
  lottie?: string;
  /** Position as fractions of the frame (0..1). `to` moves it over the scene. */
  x?: number; y?: number; to?: XY;
  /** 1 = about a third of the frame wide. Small values are raised to a readable minimum unless allowTiny. */
  scale?: number; scaleTo?: number; allowTiny?: boolean;
  /** Gentle idle motion when the actor has no `to` (default true). */
  idle?: boolean;
  /** 3D sprite camera view: side (default) | three_quarter. Land animals (detail.rest) use the rest pose. */
  view?: string;
  /** Force the flat drawing even when a 3D sprite exists. */
  flat?: boolean;
  flip?: boolean; rotate?: number;
  /** Turn toward another actor (its index in `actors`, or its creature name) or 'left' / 'right'. A hunter that
   *  waits should look at what it hunts. Actors that travel always face where they are going. */
  lookAt?: number | string;
  /** Keep `flip` exactly as written even while travelling the other way (an animal backing off). */
  keepFacing?: boolean;
  at?: number;
  enter?: 'fade' | 'left' | 'right' | 'none';
  /** Draw as a flat silhouette (e.g. "#000" for a looming shape, "#39ff88" for sonar). */
  silhouette?: string;
  opacity?: number;
  blur?: number;
  color?: string;
  detail?: Record<string, unknown>;
  label?: {text: string; at?: number; color?: string; dy?: number};
  /** Red lock-on brackets around the actor. */
  target?: {at?: number};
  /** Expanding sound-wave arcs in front of the actor (echolocation). */
  waves?: {at?: number; color?: string};
  /** Spotlight ring: around the actor, or at x/y (frame fractions) with radius r (fraction of frame width). */
  ring?: {at?: number; x?: number; y?: number; r?: number; local?: [number, number]};
};

export type SpriteMeta = {frames: number; w: number; h: number; bbox: [number, number, number, number]; fps: number; loop?: boolean;
  /** Cross-fade neighbouring frames (slow turning 3D models rendered at a low frame rate). */
  blend?: boolean};
export type SpriteManifest = Record<string, Record<string, SpriteMeta>>;

export type OceanSceneProps = DocuProps & {
  /** 3D creature sprites rendered by Blender (injected by ytauto). */
  sprites?: SpriteManifest;
  depth?: number; depthTo?: number; surface?: boolean; rays?: boolean;
  /** Above/below the waterline: sky + ice or rocky shore on top, ocean below. y = waterline (0..1). */
  split?: {y?: number; land?: 'ice' | 'rocks' | 'none'; landWidth?: number; sky?: 'polar' | 'dusk' | 'storm'; floes?: boolean};
  /** Real B-roll behind everything: a video file or "pexels:sperm whale" (resolved by ytauto). */
  footage?: string; footageStart?: number; footageDim?: number;
  actors?: Actor[];
  /** Camera: zoom from → to, centred on focus (fractions). */
  zoom?: XY; focus?: XY;
  title?: string; titleColor?: 'white' | 'red'; titleAt?: number;
  bigText?: string; bigAt?: number; bigColor?: string;
  facts?: {text: string; at?: number; red?: boolean}[];
  check?: {text: string; at?: number; ok?: boolean};
  scaleBar?: {x1: number; x2: number; y: number; label: string; at?: number};
  depthMeter?: {from: number; to: number; unit?: string; max?: number};
  timer?: {from?: number; label?: string};
};

const UNIT = 600; // creature drawing length in local units

/** Smallest on-screen scale per creature so nothing ever reads as a speck (opt out with allowTiny). */
const MIN_SCALE: Record<string, number> = {
  spermWhale: 0.7, giantSquid: 0.6, orca: 0.6, shark: 0.55, anglerfish: 0.32, jellyfish: 0.3, diver: 0.38,
  fishSchool: 0.45, octopus: 0.3, leopardSeal: 0.62, seaLion: 0.42, furSeal: 0.42, penguin: 0.22, krill: 0.4,
};
const PUP_MIN = 0.32;
const STAND_PENGUIN_MIN = 0.16;

/** Height of the land surface (px) at x for a split shot, or null over open water. Mirrors SplitSurface. */
export const terrainY = (cfg: NonNullable<OceanSceneProps['split']>, x: number, width: number, height: number, s: number): number | null => {
  const wy = (cfg.y ?? 0.34) * height;
  const lw = (cfg.landWidth ?? 0.4) * width;
  if (cfg.land === 'ice') {
    if (x > lw * 0.92) return x < lw ? wy - 74 * s + ((x - lw * 0.92) / (lw * 0.08)) * 44 * s : null;
    return wy - 74 * s - (x / (lw * 0.92)) * -6 * s - 6 * s;
  }
  if (cfg.land === 'rocks') {
    const pts: [number, number][] = [[0, -70], [0.15, -95], [0.32, -60], [0.5, -85], [0.7, -40], [0.86, -22], [1, 6]];
    const f = x / lw;
    if (f > 1) return null;
    for (let i = 0; i < pts.length - 1; i++) {
      const [x0, y0] = pts[i], [x1, y1] = pts[i + 1];
      if (f >= x0 && f <= x1) return wy + (y0 + ((f - x0) / (x1 - x0)) * (y1 - y0)) * s;
    }
  }
  return null;
};

/** The surface world for split shots: sky, waterline, drifting ice floes, an ice shelf or a rocky shore. */
const SplitSurface: React.FC<{cfg: NonNullable<OceanSceneProps['split']>}> = ({cfg}) => {
  const {t, s, width, height} = useT();
  const wy = (cfg.y ?? 0.34) * height;
  const sky = cfg.sky === 'dusk' ? ['#2e3242', '#b98a6e'] : cfg.sky === 'storm' ? ['#4a535b', '#8d979e'] : ['#9fb7c7', '#dfe8ee'];
  const lw = (cfg.landWidth ?? 0.4) * width;
  const swell = (x: number) => Math.sin(x / (120 * s) + t * 1.2) * 4 * s;
  const surf = Array.from({length: 49}).map((_, i) => `${(i / 48) * width},${wy + swell((i / 48) * width)}`).join(' ');
  return (
    <svg width={width} height={height} style={{position: 'absolute'}}>
      <defs>
        <linearGradient id="sp-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={sky[0]} /><stop offset="100%" stopColor={sky[1]} /></linearGradient>
        <linearGradient id="sp-ice" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#ffffff" /><stop offset="100%" stopColor="#cfe3ee" /></linearGradient>
        <linearGradient id="sp-under" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#a9d4e6" stopOpacity={0.75} /><stop offset="100%" stopColor="#3f7d9c" stopOpacity={0.15} /></linearGradient>
        <linearGradient id="sp-rock" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3b3a38" /><stop offset="100%" stopColor="#1d1d1c" /></linearGradient>
      </defs>
      <polygon points={`0,0 ${width},0 ${width},${wy} ${surf.split(' ').reverse().join(' ')} 0,${wy}`} fill="url(#sp-sky)" />
      {cfg.land === 'rocks' ? (
        <>
          <path d={`M0,${wy - 70 * s} L${lw * 0.15},${wy - 95 * s} L${lw * 0.32},${wy - 60 * s} L${lw * 0.5},${wy - 85 * s} L${lw * 0.7},${wy - 40 * s} L${lw * 0.86},${wy - 22 * s} L${lw},${wy + 6 * s} L0,${wy + 6 * s} Z`} fill="url(#sp-rock)" />
          <path d={`M0,${wy} L${lw * 1.02},${wy} L${lw * 0.8},${wy + 140 * s} L${lw * 0.3},${wy + 260 * s} L0,${wy + 300 * s} Z`} fill="#121516" opacity={0.85} />
        </>
      ) : cfg.land === 'ice' ? (
        <>
          <path d={`M0,${wy - 80 * s} L${lw * 0.92},${wy - 74 * s} L${lw},${wy - 30 * s} L${lw * 0.97},${wy + 2 * s} L0,${wy + 2 * s} Z`} fill="url(#sp-ice)" />
          <path d={`M${lw * 0.92},${wy - 74 * s} L${lw},${wy - 30 * s} L${lw * 0.97},${wy + 2 * s} L${lw * 0.88},${wy + 2 * s} Z`} fill="#b9d6e4" />
          <path d={`M0,${wy} L${lw * 0.97},${wy} L${lw * 0.9},${wy + 150 * s} L${lw * 0.55},${wy + 230 * s} L0,${wy + 260 * s} Z`} fill="url(#sp-under)" />
        </>
      ) : null}
      {cfg.floes !== false
        ? Array.from({length: 5}).map((_, i) => {
            const fw = (90 + ((i * 53) % 120)) * s;
            const x0 = (lw + 60 * s) + i * ((width - lw) / 5) + Math.sin(t * 0.2 + i) * 30 * s;
            const top = wy - (8 + (i % 3) * 6) * s;
            return (
              <g key={i}>
                <path d={`M${x0},${wy} L${x0 + fw * 0.1},${top} L${x0 + fw * 0.85},${top + 2 * s} L${x0 + fw},${wy} Z`} fill="url(#sp-ice)" />
                <path d={`M${x0},${wy} L${x0 + fw},${wy} L${x0 + fw * 0.8},${wy + fw * 0.45} L${x0 + fw * 0.2},${wy + fw * 0.5} Z`} fill="url(#sp-under)" />
              </g>
            );
          })
        : null}
      <polyline points={surf} fill="none" stroke="#e8f6ff" strokeOpacity={0.75} strokeWidth={2.5 * s} />
      <rect x={0} y={wy} width={width} height={40 * s} fill="url(#sp-under)" opacity={0.35} />
    </svg>
  );
};

/** Lottie animation loaded from remotion/public (ytauto stages project files there). */
const LottieAsset: React.FC<{src: string; style: React.CSSProperties}> = ({src, style}) => {
  const [data, setData] = useState<LottieAnimationData | null>(null);
  const [handle] = useState(() => delayRender(`lottie ${src}`));
  useEffect(() => {
    fetch(staticFile(src))
      .then((r) => r.json())
      .then((j) => { setData(j); continueRender(handle); })
      .catch((e) => { console.error(e); continueRender(handle); });
  }, [handle, src]);
  return data ? <div style={style}><Lottie animationData={data} loop /></div> : null;
};

/** Full-frame background footage (B-roll), cover-cropped and slightly darkened so overlays stay readable. */
export const Footage: React.FC<{src: string; startFrom?: number; dim?: number}> = ({src, startFrom = 0, dim = 0.25}) => {
  const {fps} = useT();
  return (
    <AbsoluteFill>
      <OffthreadVideo src={staticFile(src)} muted startFrom={Math.round(startFrom * fps)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      <AbsoluteFill style={{background: `rgba(2,8,14,${dim})`}} />
    </AbsoluteFill>
  );
};

/** Frame number of a sprite at time t: loops cycle (offset per actor); one-shot sets play once and hold. */
export const spriteFrame = (meta: SpriteMeta, t: number, i = 0): number => {
  if (meta.frames <= 1) return 1;
  if (meta.loop === false) return Math.min(meta.frames, Math.max(1, Math.floor(Math.max(0, t) * meta.fps) + 1));
  return (Math.floor((t + i * 0.37) * meta.fps) % meta.frames + meta.frames) % meta.frames + 1;
};

const spriteFor = (a: Actor, man?: SpriteManifest): {key: string; view: string; meta: SpriteMeta} | null => {
  if (!man || a.flat || !a.creature) return null;
  const pup = !!a.detail?.pup;
  let key = (a.creature === 'seaLion' || a.creature === 'furSeal') ? (pup ? 'seaLionPup' : 'seaLion') : a.creature;
  if (a.creature === 'leopardSeal' && a.view === 'jaw') key = 'leopardSealHead';
  const view = a.detail?.rest ? 'rest' : a.view ?? 'side';
  const meta = man[key]?.[view];
  return meta ? {key, view, meta} : null;
};

/** Which way every actor faces, decided once for the scene. Drawings and 3D models look right; `flip` turns them
 *  left. An animal must never swim backwards or turn its back on what the line is about, so:
 *   1. an actor that travels sideways faces the way it goes (this beats a hand-written `flip`, unless keepFacing);
 *   2. otherwise `lookAt` turns it toward that actor (or 'left' / 'right');
 *   3. otherwise one that slides in from a side faces into the frame;
 *   4. otherwise a hunter with no `flip` of its own turns toward the nearest animal it hunts in the scene;
 *   5. otherwise `flip` as written.
 *  An actor that mostly rises or sinks and has no `rotate` of its own tilts its nose along its path. */
/** Who looks at whom when nothing else says so: the hunter turns toward these, if one is in the scene. */
export const HUNTS: Record<string, string[]> = {
  leopardSeal: ['seaLion', 'penguin', 'diver', 'krill', 'fishSchool'],
  orca: ['seaLion', 'leopardSeal', 'penguin', 'shark', 'fishSchool', 'diver'],
  shark: ['seaLion', 'fishSchool', 'diver', 'penguin'],
  spermWhale: ['giantSquid', 'diver'],
  giantSquid: ['fishSchool', 'diver'],
  anglerfish: ['fishSchool'],
};

export const orientActors = (actors: Actor[]): Actor[] => actors.map((a) => {
  const onLand = !!(a.detail && ((a.detail as {rest?: boolean; stand?: boolean}).rest || (a.detail as {stand?: boolean}).stand));
  const x0 = a.x ?? 0.5, y0 = a.y ?? 0.5;
  const dx = (a.to?.[0] ?? x0) - x0, dy = (a.to?.[1] ?? y0) - y0;
  let flip = !!a.flip;
  if (Math.abs(dx) > 0.02 && !a.keepFacing) {
    flip = dx < 0;
  } else if (a.lookAt !== undefined && !a.keepFacing) {
    if (a.lookAt === 'left' || a.lookAt === 'right') {
      flip = a.lookAt === 'left';
    } else {
      const target = typeof a.lookAt === 'number' ? actors[a.lookAt] : actors.find((b) => b !== a && b.creature === a.lookAt);
      const tx = target ? (target.x ?? 0.5) : x0;
      if (target && Math.abs(tx - x0) > 0.01) flip = tx < x0;
    }
  } else if (a.flip === undefined && (a.enter === 'left' || a.enter === 'right')) {
    flip = a.enter === 'right';
  } else if (a.flip === undefined && !onLand && a.creature && HUNTS[a.creature]) {
    // a hunter that waits looks at what it hunts (the nearest one), never away from it
    const prey = actors.filter((b) => b !== a && b.creature && HUNTS[a.creature as string].includes(b.creature))
      .map((b) => b.to?.[0] ?? b.x ?? 0.5).filter((bx) => Math.abs(bx - x0) > 0.05)
      .sort((p1, p2) => Math.abs(p1 - x0) - Math.abs(p2 - x0));
    if (prey.length) flip = prey[0] < x0;
  }
  let rotate = a.rotate;
  if (rotate === undefined && !onLand && Math.abs(dy) > 0.12) {
    const tilt = Math.atan2(dy * 9, Math.max(0.0001, Math.abs(dx)) * 16) * 180 / Math.PI;   // + = heading down
    if (Math.abs(tilt) > 12) {
      const t2 = Math.max(-75, Math.min(75, tilt)) * 0.85;
      rotate = flip ? -t2 : t2;
    }
  }
  return {...a, flip, rotate};
});

const ActorView: React.FC<{a: Actor; i: number; maxRight?: number; split?: OceanSceneProps['split']; sprites?: SpriteManifest}> = ({a, i, maxRight, split, sprites}) => {
  const {t, dur, s, width, height} = useT();
  const onLand = !!(a.detail && (a.detail.rest || a.detail.stand));
  const at = a.at ?? 0;
  const k = interpolate(t, [at, Math.max(at + 0.01, dur)], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const ent = prog(t, at, 1.2, Easing.out(Easing.cubic));
  // Idle life: swimmers drift forward a little and bob; land animals stay put (they breathe/nod in their drawing).
  const idle = a.idle !== false && !a.to && !onLand && a.creature !== 'krill' && a.creature !== 'fishSchool';
  const dir = a.flip ? -1 : 1;
  let x = (a.x ?? 0.5) + ((a.to?.[0] ?? a.x ?? 0.5) - (a.x ?? 0.5)) * k + (idle ? dir * 0.05 * (t / Math.max(1, dur)) : 0);
  let y = (a.y ?? 0.5) + ((a.to?.[1] ?? a.y ?? 0.5) - (a.y ?? 0.5)) * k + (onLand ? 0 : Math.sin(t * 0.9 + i) * 0.012);
  if (a.enter === 'left') x -= (1 - ent) * 0.8;
  if (a.enter === 'right') x += (1 - ent) * 0.8;
  const minS = a.allowTiny ? 0 : a.creature === 'penguin' && a.detail?.stand ? STAND_PENGUIN_MIN
    : a.detail?.pup ? PUP_MIN : (a.creature ? MIN_SCALE[a.creature] ?? 0.3 : 0.3);
  const rawS = (a.scale ?? 1) + ((a.scaleTo ?? a.scale ?? 1) - (a.scale ?? 1)) * k;
  const sc = Math.max(minS, rawS) * (width * 0.33) / UNIT;
  const sway = onLand ? 0 : Math.sin(t * 0.7 + i * 1.3) * 1.6; // degrees
  const op = (a.enter === 'none' ? (t >= at ? 1 : 0) : a.enter === 'left' || a.enter === 'right' ? (t >= at ? 1 : 0) : ent) * (a.opacity ?? 1);
  const Comp = a.creature ? CREATURES[a.creature] : undefined;
  let px = x * width;
  let py = y * height;
  // Land animals sit ON the shore/ice: their drawing's ground line (local y = 40, or 120 for standing penguins) meets the surface.
  if (onLand && split) {
    const ground = terrainY(split, px, width, height, s);
    if (ground !== null) py = ground - (a.creature === 'penguin' ? 132 : 40) * sc;
  }
  // Keep the drawing clear of the fact panel (right side) so text never sits on top of an animal.
  if (maxRight !== undefined) {
    const ext = a.creature ? EXTENTS[a.creature] ?? [-300, 300] : [-300, 300];
    const right = (a.flip ? -ext[0] : ext[1]) * sc;
    if (px + right > maxRight * width) px = maxRight * width - right;
  }
  const halfW = (UNIT / 2) * sc, halfH = UNIT * 0.2 * sc;
  const fid = `sil${i}`;
  const tp = a.target ? prog(t, a.target.at ?? at + 0.5, 0.35) : 0;
  const spr = spriteFor(a, sprites);
  let sprite: React.ReactNode = null;
  let sprTop: number | null = null, sprBottom: number | null = null;   // top edge of the sprite's visible body (labels sit just above it)
  if (spr) {
    const {meta} = spr;
    const [bx0, by0, bx1, by1] = meta.bbox;
    const bw = (bx1 - bx0) / meta.w;
    const dw = (UNIT * sc * 0.97) / Math.max(0.05, bw);           // displayed image width (creature matches drawn length)
    const dh = dw * (meta.h / meta.w);
    const cxF = (bx0 + bx1) / 2 / meta.w, cyF = (by0 + by1) / 2 / meta.h;
    let top = py - cyF * dh;
    if (onLand && split && terrainY(split, px, width, height, s) !== null) {
      top = (terrainY(split, px, width, height, s) as number) - (by1 / meta.h) * dh + 0.035 * dh;   // flippers settle into the ground
    }
    const left = px - cxF * dw;
    sprTop = top + (by0 / meta.h) * dh;
    sprBottom = top + (by1 / meta.h) * dh;
    const idx = spriteFrame(meta, t - at, i);
    const file = `sprites/${spr.key}/${spr.view}/${String(idx).padStart(4, '0')}.webp`;
    const shadowW = (bx1 - bx0) / meta.w * dw * 0.8;
    sprite = (
      <>
      {onLand && !a.silhouette ? (
        <div style={{position: 'absolute', left: px - shadowW / 2, top: top + (by1 / meta.h) * dh - 0.035 * dh - 10 * s, width: shadowW, height: 22 * s,
          borderRadius: '50%', background: 'radial-gradient(ellipse at center, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.25) 45%, rgba(0,0,0,0) 72%)', opacity: op}} />
      ) : null}
      <Img src={staticFile(file)} style={{position: 'absolute', left, top, width: dw, height: dh, opacity: op,
        transformOrigin: `${cxF * 100}% ${cyF * 100}%`,
        transform: `${a.flip ? 'scaleX(-1) ' : ''}rotate(${((a.rotate ?? 0) + sway) * (a.flip ? -1 : 1)}deg)`,
        filter: [a.silhouette ? `brightness(0.08) drop-shadow(0 0 ${8 * s}px rgba(150,200,225,0.45))` : '',
                 a.blur ? `blur(${a.blur * s}px)` : ''].join(' ').trim() || undefined}} />
      </>
    );
  }
  return (
    <>
      <svg width={width} height={height} style={{position: 'absolute', opacity: op, overflow: 'visible',
        filter: [a.blur ? `blur(${a.blur * s}px)` : '', a.silhouette ? `drop-shadow(0 0 ${7 * s}px rgba(150,200,225,0.45))` : ''].join(' ').trim() || undefined}}>
        <defs>
          {a.silhouette ? (
            <filter id={fid}><feFlood floodColor={a.silhouette} /><feComposite in2="SourceAlpha" operator="in" /></filter>
          ) : null}
        </defs>
        <g transform={`translate(${px} ${py}) rotate(${(a.rotate ?? 0) + sway}) scale(${a.flip ? -sc : sc} ${sc})`} filter={a.silhouette ? `url(#${fid})` : undefined}>
          {Comp && !spr ? <Comp t={t + i * 1.7} color={a.color} detail={a.detail} /> : null}
        </g>
        {a.waves ? Array.from({length: 4}).map((_, j) => {
          const wt = t - (a.waves!.at ?? at) - j * 0.35;
          if (wt < 0) return null;
          const ph = (wt % 1.4) / 1.4;
          const dir = a.flip ? -1 : 1;
          const cx = px + dir * (halfW + 20 * s + ph * 260 * s);
          const r = (40 + ph * 70) * s;
          return <path key={j} d={`M${cx},${py - r} Q${cx + dir * r * 0.5},${py} ${cx},${py + r}`} stroke={a.waves!.color ?? '#e6f4ff'} strokeWidth={3 * s} fill="none" opacity={(1 - ph) * 0.8} />;
        }) : null}
        {a.ring ? (() => {
          const rp = prog(t, a.ring.at ?? at, 0.6);
          // local: a point on the creature's own drawing (e.g. its ear) — follows the animal wherever it is placed
          const rx = a.ring.local ? px + a.ring.local[0] * sc * (a.flip ? -1 : 1) : a.ring.x !== undefined ? a.ring.x * width : px;
          const ry = a.ring.local ? py + a.ring.local[1] * sc : a.ring.y !== undefined ? a.ring.y * height : py;
          const rr = a.ring.r !== undefined ? a.ring.r * width : halfW * 0.55;
          return <circle cx={rx} cy={ry} r={rr * (1.4 - 0.4 * rp)} fill="none" stroke="#e6f4ff" strokeOpacity={0.6 * rp} strokeWidth={2.5 * s} />;
        })() : null}
        {a.target ? (
          <g stroke={C.red} strokeWidth={3 * s} fill="none" opacity={tp}>
            {[[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([dx, dy], j) => {
              const bx = px + dx * (halfW * 0.6 + (1 - tp) * 40 * s), by = py + dy * (halfH + 30 * s + (1 - tp) * 40 * s);
              const L = 26 * s;
              return <path key={j} d={`M${bx},${by - dy * L} L${bx},${by} L${bx - dx * L},${by}`} />;
            })}
          </g>
        ) : null}
      </svg>
      {sprite}
      {a.image ? (
        <Img src={staticFile(a.image)} style={{position: 'absolute', left: px - halfW, top: py - halfW * 0.5, width: halfW * 2, opacity: op,
          transform: `${a.flip ? 'scaleX(-1) ' : ''}rotate(${(a.rotate ?? 0) + Math.sin(t * 1.4 + i) * 1.5}deg)`,
          filter: [a.silhouette ? 'brightness(0)' : '', a.blur ? `blur(${a.blur * s}px)` : ''].join(' ').trim() || undefined}} />
      ) : null}
      {a.lottie ? (
        <LottieAsset src={a.lottie} style={{position: 'absolute', left: px - halfW, top: py - halfW, width: halfW * 2, height: halfW * 2, opacity: op,
          transform: `${a.flip ? 'scaleX(-1) ' : ''}rotate(${a.rotate ?? 0}deg)`, filter: a.silhouette ? 'brightness(0)' : undefined}} />
      ) : null}
      {a.label ? (
        <div style={{position: 'absolute', left: px, top: a.label.dy === undefined && sprTop !== null ? (onLand ? sprTop - 44 * s : (sprBottom as number) + 12 * s) : py + (a.label.dy ?? (onLand ? -0.2 : 0.16)) * height, transform: 'translateX(-50%)', fontFamily: F.sans, fontWeight: 800,
          fontSize: 28 * s, letterSpacing: 1.5 * s, textTransform: 'uppercase', color: a.label.color ?? C.text, opacity: prog(t, a.label.at ?? at + 0.4, 0.5),
          whiteSpace: 'nowrap', textShadow: '0 2px 12px rgba(0,0,0,.7)'}}>
          {a.label.text}
        </div>
      ) : null}
    </>
  );
};

export const OceanScene: React.FC<OceanSceneProps> = (p) => {
  const {t, dur, s, width, height} = useT();
  // Camera never stands still: a slow push-in unless the scene sets its own zoom.
  const z = interpolate(t, [0, dur], p.zoom ?? [1.0, 1.06], {easing: Easing.inOut(Easing.quad)});
  const [fx, fy] = p.focus ?? [0.5, 0.5];
  const tp = prog(t, p.titleAt ?? 0.3, 0.6);
  const bp = p.bigText ? interpolate(t, [p.bigAt ?? 0.5, (p.bigAt ?? 0.5) + 0.25], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 0;
  const dm = p.depthMeter;
  const dv = dm ? interpolate(t, [0.3, dur * 0.9], [dm.from, dm.to], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad)}) : 0;
  return (
    <DocuFrame {...p} footage={undefined} backdrop="none">
      <AbsoluteFill style={{transform: `scale(${z})`, transformOrigin: `${fx * 100}% ${fy * 100}%`}}>
        {p.footage ? <Footage src={p.footage} startFrom={p.footageStart} dim={p.footageDim} />
          : <OceanBackdrop depth={p.depth ?? (p.split ? 0.35 : 0.6)} depthTo={p.depthTo} surface={p.surface} rays={p.rays} />}
        {p.split && !p.footage ? <SplitSurface cfg={p.split} /> : null}
        {orientActors(p.actors ?? []).map((a, i) => <ActorView key={i} a={a} i={i} maxRight={p.facts && p.facts.length ? 0.66 : undefined} split={p.footage ? undefined : p.split} sprites={p.sprites} />)}
      </AbsoluteFill>
      {p.title ? (
        <div style={{position: 'absolute', left: 0, right: 0, top: 70 * s, textAlign: 'center', opacity: tp}}>
          <span style={{fontSize: 40.0 * s, fontWeight: 900, letterSpacing: 1.5 * s, textTransform: 'uppercase', color: p.titleColor === 'red' ? C.red : C.text,
            borderBottom: p.titleColor === 'red' ? `${3 * s}px solid ${C.red}` : 'none', paddingBottom: 4 * s}}>{p.title}</span>
        </div>
      ) : null}
      {p.bigText ? (
        <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
          <div style={{fontSize: 150.0 * s, fontWeight: 900, color: p.bigColor ?? C.red, opacity: bp, transform: `scale(${1.25 - 0.25 * bp})`, letterSpacing: 2 * s,
            textShadow: '0 10px 60px rgba(0,0,0,.6)'}}>{p.bigText}</div>
        </AbsoluteFill>
      ) : null}
      {p.facts && p.facts.length ? (
        <div style={{position: 'absolute', right: 80 * s, top: 0.3 * height, display: 'flex', flexDirection: 'column', gap: 14 * s, width: 520 * s}}>
          {p.facts.map((f, i) => (
            <Reveal key={i} at={f.at ?? stagger(i, p.facts!.length, dur, 0.6, 0.7)} y={0}>
              <div style={{background: f.red ? 'rgba(212,45,38,0.96)' : 'rgba(14,24,34,0.92)', boxShadow: '0 6px 24px rgba(0,0,0,0.45)', padding: `${14 * s}px ${20 * s}px`, fontWeight: 800, fontSize: 26 * s,
                letterSpacing: 1 * s, textTransform: 'uppercase', borderLeft: `${3 * s}px solid ${f.red ? '#fff' : 'rgba(255,255,255,0.4)'}`}}>{f.text}</div>
            </Reveal>
          ))}
        </div>
      ) : null}
      {p.check ? (
        <div style={{position: 'absolute', left: 90 * s, bottom: 110 * s, display: 'flex', alignItems: 'center', gap: 14 * s, opacity: prog(t, p.check.at ?? 1, 0.5),
          fontWeight: 800, fontSize: 30 * s, letterSpacing: 1.5 * s, textTransform: 'uppercase', color: '#dfe7ec'}}>
          {p.check.text}
          <span style={{width: 34 * s, height: 34 * s, borderRadius: 17 * s, background: p.check.ok === false ? C.red : '#2fbf71', display: 'inline-flex',
            alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 28 * s}}>{p.check.ok === false ? '✕' : '✓'}</span>
        </div>
      ) : null}
      {p.scaleBar ? (() => {
        const sb = p.scaleBar;
        const k = prog(t, sb.at ?? 0.8, 0.8);
        const x1 = sb.x1 * width, x2 = sb.x2 * width, y = sb.y * height;
        return (
          <>
            <div style={{position: 'absolute', left: x1, top: y, width: (x2 - x1) * k, height: 3 * s, background: '#e8eef2'}} />
            <div style={{position: 'absolute', left: x1, top: y - 10 * s, width: 3 * s, height: 23 * s, background: '#e8eef2', opacity: k}} />
            <div style={{position: 'absolute', left: x2, top: y - 10 * s, width: 3 * s, height: 23 * s, background: '#e8eef2', opacity: k > 0.98 ? 1 : 0}} />
            <div style={{position: 'absolute', left: (x1 + x2) / 2, top: y + 18 * s, transform: 'translateX(-50%)', fontWeight: 800, fontSize: 26.0 * s, opacity: k}}>{sb.label}</div>
          </>
        );
      })() : null}
      {dm ? (
        <div style={{position: 'absolute', right: 110 * s, top: 120 * s, bottom: 120 * s, width: 2 * s, background: 'rgba(255,255,255,0.25)'}}>
          {[0, 0.25, 0.5, 0.75, 1].map((f) => (
            <div key={f} style={{position: 'absolute', top: `${f * 100}%`, left: 6 * s, fontFamily: F.mono, fontSize: 20 * s, color: C.dim, whiteSpace: 'nowrap'}}>
              {fmtNum((dm.max ?? dm.to) * f)} {dm.unit ?? 'm'}
            </div>
          ))}
          <div style={{position: 'absolute', top: `${(dv / (dm.max ?? dm.to)) * 100}%`, right: 12 * s, transform: 'translateY(-50%)', display: 'flex', alignItems: 'center', gap: 8 * s,
            fontWeight: 800, fontSize: 30.0 * s, whiteSpace: 'nowrap'}}>
            {fmtNum(dv)} {dm.unit ?? 'm'} <span style={{color: C.red, fontSize: 24 * s}}>▶</span>
          </div>
        </div>
      ) : null}
      {p.timer ? (
        <div style={{position: 'absolute', right: 90 * s, top: 70 * s, background: 'rgba(0,0,0,0.45)', padding: `${10 * s}px ${22 * s}px`, borderRadius: 10 * s,
          fontFamily: F.sans, fontWeight: 800, fontSize: 40.0 * s, color: '#e8eef2'}}>
          {p.timer.label ? <div style={{fontSize: 20 * s, letterSpacing: 2 * s, color: C.dim}}>{p.timer.label}</div> : null}
          {(() => { const v = Math.max(0, (p.timer!.from ?? 0) + t); return `${Math.floor(v / 60)}:${String(Math.floor(v % 60)).padStart(2, '0')}`; })()}
        </div>
      ) : null}
    </DocuFrame>
  );
};

/* ------------------------------------------------------------------ Meter (e.g. 0 → 236 dB) */
export type MeterProps = DocuProps & {
  title?: string; from?: number; to: number; max?: number; unit?: string; note?: string; footnote?: string; countAt?: number; depth?: number;
};

export const Meter: React.FC<MeterProps> = (p) => {
  const {t, dur, s} = useT();
  const at = p.countAt ?? 0.8;
  const v = interpolate(t, [at, at + Math.min(2.5, dur * 0.5)], [p.from ?? 0, p.to], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const frac = (v - (p.from ?? 0)) / ((p.max ?? p.to) - (p.from ?? 0));
  return (
    <DocuFrame {...p} backdrop="none">
      <OceanBackdrop depth={p.depth ?? 0.8} rays={false} />
      <AbsoluteFill style={{alignItems: 'center'}}>
        {p.title ? (
          <div style={{marginTop: 120 * s, opacity: prog(t, 0.2, 0.5)}}>
            <span style={{fontSize: 40.0 * s, fontWeight: 900, color: C.red, textTransform: 'uppercase', borderBottom: `${3 * s}px solid ${C.red}`}}>{p.title}</span>
          </div>
        ) : null}
        <div style={{position: 'absolute', top: 470 * s, width: 1000 * s, height: 56 * s, borderRadius: 28 * s, background: 'rgba(255,255,255,0.07)', overflow: 'hidden'}}>
          <div style={{width: `${Math.max(3, frac * 100)}%`, height: '100%', borderRadius: 28 * s,
            background: 'linear-gradient(90deg, #2fbf71 0%, #e8c547 55%, #e5372f 100%)', backgroundSize: `${1000 * s}px 100%`}} />
        </div>
        <div style={{position: 'absolute', top: 560 * s, fontSize: 84.0 * s, fontWeight: 900}}>{fmtNum(v)} {p.unit}</div>
        {p.note ? <div style={{position: 'absolute', top: 668 * s, fontSize: 23 * s, color: C.dim}}>{p.note}</div> : null}
        {p.footnote ? <Reveal at={at + 2} style={{position: 'absolute', top: 760 * s}}><div style={{fontSize: 24 * s, fontWeight: 800, letterSpacing: 2 * s, textTransform: 'uppercase', color: '#cfd8de'}}>{p.footnote}</div></Reveal> : null}
      </AbsoluteFill>
    </DocuFrame>
  );
};

/* ------------------------------------------------------------------ Sonar / echolocation view */
export type SonarProps = DocuProps & {
  blips: {label: string; x: number; y: number; creature?: string; scale?: number; flip?: boolean; at?: number; color?: string}[];
  title?: string;
};

export const Sonar: React.FC<SonarProps> = (p) => {
  const {t, dur, s, width, height} = useT();
  const G = '#39ff88';
  const cx = width * 0.08, cy = height * 0.85;
  const sweep = ((t * 70) % 120) - 30;
  return (
    <DocuFrame {...p} backdrop="black">
      <svg width={width} height={height} style={{position: 'absolute'}}>
        <defs><filter id="sonar-sil"><feFlood floodColor={G} /><feComposite in2="SourceAlpha" operator="in" /></filter></defs>
        {[0.25, 0.5, 0.75, 1].map((r) => <circle key={r} cx={cx} cy={cy} r={r * width * 0.95} fill="none" stroke={G} strokeOpacity={0.12} strokeWidth={1.5 * s} />)}
        {Array.from({length: 7}).map((_, i) => {
          const a = (-80 + i * 13) * Math.PI / 180;
          return <line key={i} x1={cx} y1={cy} x2={cx + Math.cos(a) * width} y2={cy + Math.sin(a) * width} stroke={G} strokeOpacity={0.08} strokeWidth={1 * s} />;
        })}
        <line x1={cx} y1={cy} x2={cx + Math.cos(-sweep * Math.PI / 180) * width} y2={cy + Math.sin(-sweep * Math.PI / 180) * width} stroke={G} strokeOpacity={0.6} strokeWidth={2 * s} />
        {p.blips.map((b, i) => {
          const at = b.at ?? stagger(i, p.blips.length, dur, 0.6, 0.6);
          const o = prog(t, at, 0.5);
          const Comp = b.creature ? CREATURES[b.creature] : undefined;
          const sc = (b.scale ?? 0.35) * (width * 0.33) / UNIT;
          const x = b.x * width, y = b.y * height;
          return (
            <g key={i} opacity={o}>
              {Comp ? (
                <g transform={`translate(${x} ${y}) scale(${b.flip ? -sc : sc} ${sc})`} filter="url(#sonar-sil)"><Comp t={t + i} /></g>
              ) : <circle cx={x} cy={y} r={10 * s} fill={b.color ?? G} />}
              <text x={x} y={y - 50 * s} fill={b.color ?? G} fontFamily={F.sans} fontWeight={800} fontSize={24 * s} letterSpacing={1.5 * s} textAnchor="middle">{b.label.toUpperCase()}</text>
            </g>
          );
        })}
      </svg>
      {p.title ? <div style={{position: 'absolute', left: 0, right: 0, top: 70 * s, textAlign: 'center', color: G, fontWeight: 900, fontSize: 36.0 * s, letterSpacing: 2 * s,
        textTransform: 'uppercase', opacity: prog(t, 0.2, 0.5)}}>{p.title}</div> : null}
    </DocuFrame>
  );
};
