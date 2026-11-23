/**
 * Motion-graphics effects shared by the motion kit: film grain, vignette, light leaks, dust,
 * hand-drawn circles/arrows, marker highlights and typed text. Everything is deterministic per frame
 * (Remotion renders frames in parallel), so no Math.random — use remotion's random(seed).
 */
import React from 'react';
import {AbsoluteFill, Easing, interpolate, random} from 'remotion';
import {C, F, prog, useT} from '../docu/kit';

/** Animated film grain (SVG turbulence with a per-frame seed). */
export const FilmGrain: React.FC<{opacity?: number}> = ({opacity = 0.09}) => {
  const {frame} = useT();
  const seed = frame % 12;
  return (
    <AbsoluteFill style={{pointerEvents: 'none', mixBlendMode: 'overlay', opacity}}>
      <svg width="100%" height="100%">
        <filter id={`grain${seed}`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed={seed} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter={`url(#grain${seed})`} />
      </svg>
    </AbsoluteFill>
  );
};

export const Vignette: React.FC<{strength?: number}> = ({strength = 0.6}) => (
  <AbsoluteFill style={{pointerEvents: 'none', background: `radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0) 55%, rgba(0,0,0,${strength}) 100%)`}} />
);

/** Warm light leak sweeping across the frame (on a cut or a reveal). */
export const LightLeak: React.FC<{at?: number; d?: number; color?: string}> = ({at = 0, d = 1.4, color = '255,170,90'}) => {
  const {t} = useT();
  const p = interpolate(t, [at, at + d], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  if (p <= 0 || p >= 1) return null;
  const a = Math.sin(p * Math.PI) * 0.55;
  return (
    <AbsoluteFill style={{pointerEvents: 'none', mixBlendMode: 'screen',
      background: `radial-gradient(ellipse 55% 90% at ${-20 + p * 140}% ${30 + p * 20}%, rgba(${color},${a}) 0%, rgba(${color},0) 70%)`}} />
  );
};

/** Floating dust / plankton specks. */
export const Dust: React.FC<{count?: number; color?: string}> = ({count = 40, color = 'rgba(220,235,245,0.35)'}) => {
  const {t, width, height, s} = useT();
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {Array.from({length: count}).map((_, i) => {
        const x = (random(`dx${i}`) * width + t * (6 + random(`vx${i}`) * 14) * s) % width;
        const y = (random(`dy${i}`) * height - t * (3 + random(`vy${i}`) * 8) * s + height) % height;
        const r = (1 + random(`r${i}`) * 2.2) * s;
        return <div key={i} style={{position: 'absolute', left: x, top: y, width: r * 2, height: r * 2, borderRadius: '50%', background: color,
          opacity: 0.4 + 0.6 * Math.abs(Math.sin(t * 0.8 + i))}} />;
      })}
    </AbsoluteFill>
  );
};

/** A hand-drawn ellipse that draws itself on (like a pen circling something on a photo). */
export const DrawCircle: React.FC<{cx: number; cy: number; rx: number; ry?: number; at: number; d?: number; color?: string; width?: number}> = ({
  cx, cy, rx, ry, at, d = 0.7, color = C.red, width = 5,
}) => {
  const {t, s} = useT();
  const p = prog(t, at, d, Easing.inOut(Easing.cubic));
  const R = ry ?? rx * 0.8;
  // slightly over-rotated, wobbly loop: start and end don't meet exactly, like a real pen stroke
  const pts: string[] = [];
  const N = 64;
  for (let k = 0; k <= N; k++) {
    const a = -0.6 + (k / N) * Math.PI * 2.15;
    const wob = 1 + 0.035 * Math.sin(a * 3 + 1.3) + (k / N) * 0.06;
    pts.push(`${cx + Math.cos(a) * rx * wob},${cy + Math.sin(a) * R * wob}`);
  }
  const len = 2 * Math.PI * Math.sqrt((rx * rx + R * R) / 2) * 1.1;
  return (
    <svg style={{position: 'absolute', inset: 0, overflow: 'visible', pointerEvents: 'none'}} width="100%" height="100%">
      <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth={width * s} strokeLinecap="round" strokeLinejoin="round"
        strokeDasharray={len} strokeDashoffset={len * (1 - p)} style={{filter: `drop-shadow(0 0 ${6 * s}px rgba(0,0,0,0.5))`}} />
    </svg>
  );
};

/** Text typed on character by character, with a blinking caret while typing. */
export const TypeOn: React.FC<{text: string; at: number; cps?: number; style?: React.CSSProperties; caret?: boolean}> = ({
  text, at, cps = 22, style, caret = true,
}) => {
  const {t} = useT();
  const n = Math.max(0, Math.min(text.length, Math.floor((t - at) * cps)));
  const typing = t >= at && n < text.length;
  const blink = Math.floor(t * 2.5) % 2 === 0;
  return (
    <span style={style}>
      {text.slice(0, n)}
      {caret && (typing || (t >= at && blink && t < at + text.length / cps + 1.2)) ? <span style={{opacity: 0.9}}>▍</span> : null}
    </span>
  );
};

/** Yellow marker that sweeps across a phrase (multiply blend over paper). */
export const Marker: React.FC<{at: number; d?: number; color?: string; children: React.ReactNode}> = ({at, d = 0.6, color = 'rgba(255,214,0,0.75)', children}) => {
  const {t} = useT();
  const p = prog(t, at, d, Easing.inOut(Easing.quad));
  return (
    <span style={{position: 'relative', display: 'inline'}}>
      <span style={{position: 'absolute', left: '-0.15em', right: '-0.15em', top: '0.08em', bottom: '0.02em', background: color,
        transformOrigin: 'left center', transform: `scaleX(${p}) skewX(-8deg)`, mixBlendMode: 'multiply', borderRadius: '0.15em'}} />
      <span style={{position: 'relative'}}>{children}</span>
    </span>
  );
};

/** Small credit chip (bottom-left): photo credits required by CC BY / BY-SA. */
export const Credit: React.FC<{text?: string}> = ({text}) => {
  const {s} = useT();
  if (!text) return null;
  return (
    <div style={{position: 'absolute', left: 36 * s, bottom: 30 * s, fontFamily: F.sans, fontSize: 17 * s, color: 'rgba(235,240,245,0.78)',
      background: 'rgba(0,0,0,0.42)', padding: `${5 * s}px ${12 * s}px`, borderRadius: 4 * s, letterSpacing: 0.3 * s, maxWidth: '60%',
      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>
      {text}
    </div>
  );
};
