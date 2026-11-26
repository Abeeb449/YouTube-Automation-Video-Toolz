/**
 * Shared design system for the "what-if documentary" templates:
 * navy infographic screens, dark maps, HUD overlays, callouts and source lines.
 *
 * Timing convention: every `at` prop is seconds from the start of the clip.
 * ytauto resolves word cues (e.g. at: "Hiroshima") to seconds before rendering,
 * so elements land exactly when the narrator says the word.
 */
import React from 'react';
import {AbsoluteFill, Easing, interpolate, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {BaseProps} from '../theme';
import {OceanBackdrop} from '../ocean/OceanBackdrop';

export const C = {
  bg0: '#06121d',
  bg1: '#0c2640',
  bg2: '#15406a',
  red: '#e5372f',
  teal: '#62b6cb',
  text: '#f1f4f8',
  dim: '#8aa1b6',
  faint: '#4d6477',
  panel: 'rgba(6,14,24,0.78)',
  land: '#33383e',
  landHi: '#41474e',
  border: '#5d636b',
  amber: '#f2b35a',
};

export const F = {
  sans: 'Inter, "DejaVu Sans", Arial, sans-serif',
  mono: '"DejaVu Sans Mono", "Liberation Mono", Menlo, monospace',
  serif: '"DejaVu Serif", Georgia, "Times New Roman", serif',
};

export type Backdrop = 'navy' | 'dark' | 'horizon' | 'ember' | 'black' | 'ocean' | 'abyss' | 'none';

export type HudSpec = {
  label?: string;
  value?: string;
  /** Live clock: seconds at clip start, counts with time. Negative = countdown ("T-04:42"). */
  clock?: number;
  prefix?: string;
  decimals?: number;
  /** "countdown" = T-mm:ss / T+mm:ss (default); "time" = HH:MM:SS wall clock. */
  format?: 'countdown' | 'time';
  color?: string;
};

export type StatRow = {label: string; value: string; color?: string};

export type DocuProps = BaseProps & {
  backdrop?: Backdrop;
  /** Section heading, top-left (e.g. "NUCLEAR DOCTRINE"). */
  heading?: string;
  headingColor?: 'white' | 'teal';
  /** Small line under the heading. */
  subheading?: string;
  /** Tiny label above the heading (e.g. "CHAPTER 02"). */
  kicker?: string;
  /** Key-phrase box, bottom centre (the reference style uses these instead of full subtitles). */
  callout?: string;
  calloutAt?: number;
  /** Tiny citation, bottom-left. */
  source?: string;
  /** Top-right HUD value, e.g. a countdown. */
  hud?: HudSpec;
  /** Bottom-right data panel. */
  stats?: StatRow[];
  statsAt?: number;
  /** Real B-roll behind the graphics (file staged by ytauto, or "pexels:query" in script.yaml). */
  footage?: string;
  footageStart?: number;
  footageDim?: number;
};

export const useT = () => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames, width, height} = useVideoConfig();
  return {t: frame / fps, dur: durationInFrames / fps, s: width / 1920, width, height, fps, frame};
};

/** 0→1 eased progress starting at `at` over `d` seconds. */
export const prog = (t: number, at: number, d = 0.6, easing = Easing.out(Easing.cubic)) =>
  interpolate(t, [at, at + d], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing});

/** Default stagger for list items that have no explicit `at`. */
export const stagger = (i: number, n: number, dur: number, start = 0.5, end = 0.7) =>
  start + (n <= 1 ? 0 : (i * (dur * end - start)) / Math.max(1, n - 1));

/** Content-layer fade so consecutive scenes on the same backdrop blend seamlessly. */
export const useContentOpacity = () => {
  const {t, dur} = useT();
  return interpolate(t, [0, 0.25, Math.max(0.3, dur - 0.35), dur], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
};

export const Reveal: React.FC<{at: number; d?: number; y?: number; blur?: boolean; style?: React.CSSProperties; children: React.ReactNode}> = ({
  at, d = 0.6, y = 24, blur = true, style, children,
}) => {
  const {t, s} = useT();
  const p = prog(t, at, d);
  return (
    <div style={{opacity: p, transform: `translateY(${(1 - p) * y * s}px)`, filter: blur ? `blur(${(1 - p) * 10 * s}px)` : undefined, ...style}}>
      {children}
    </div>
  );
};

/** Slowly "breathing" backgrounds. Same backdrop on consecutive scenes = no visible cut. */
export const BackdropLayer: React.FC<{kind?: Backdrop}> = ({kind = 'navy'}) => {
  const {t, dur} = useT();
  const drift = interpolate(t, [0, Math.max(1, dur)], [0, 1]);
  if (kind === 'none') return null;
  if (kind === 'black') return <AbsoluteFill style={{background: '#030508'}} />;
  if (kind === 'dark')
    return <AbsoluteFill style={{background: `radial-gradient(ellipse at ${50 + drift * 4}% 45%, #23282e 0%, #181b20 55%, #0d0f12 100%)`}} />;
  if (kind === 'ember')
    return <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% ${45 - drift * 3}%, #3a1f17 0%, #22120e 50%, #0c0706 100%)`}} />;
  if (kind === 'horizon') return <HorizonSky mood="dusk" />;
  if (kind === 'ocean') return <OceanBackdrop depth={0.55} />;
  if (kind === 'abyss') return <OceanBackdrop depth={0.9} rays={false} />;
  return (
    <AbsoluteFill
      style={{background: `radial-gradient(ellipse at ${48 + drift * 6}% ${40 + drift * 4}%, ${C.bg2} 0%, ${C.bg1} 48%, ${C.bg0} 100%)`}}
    />
  );
};

export const HorizonSky: React.FC<{mood?: 'dusk' | 'night' | 'grey'; horizonY?: number}> = ({mood = 'dusk', horizonY = 0.66}) => {
  const sky =
    mood === 'night'
      ? 'linear-gradient(180deg, #05070c 0%, #0d1320 55%, #1c2433 100%)'
      : mood === 'grey'
        ? 'linear-gradient(180deg, #2b2d31 0%, #4a4a4c 60%, #77706a 100%)'
        : 'linear-gradient(180deg, #1c2029 0%, #3a3438 40%, #7a5446 78%, #c98552 100%)';
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{background: sky, height: `${horizonY * 100}%`}} />
      <AbsoluteFill
        style={{
          top: `${horizonY * 100}%`,
          background: mood === 'night' ? 'linear-gradient(180deg,#0b0e14,#030405)' : 'linear-gradient(180deg,#1b1917 0%,#0e0d0c 60%,#070706 100%)',
        }}
      />
      {/* haze band on the horizon */}
      <AbsoluteFill
        style={{
          top: `${(horizonY - 0.05) * 100}%`,
          height: '10%',
          background: 'linear-gradient(180deg, transparent, rgba(255,190,140,0.18), transparent)',
          filter: 'blur(8px)',
        }}
      />
    </AbsoluteFill>
  );
};

const Vignette: React.FC = () => (
  <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 50%, transparent 55%, rgba(0,0,0,0.55) 100%)', pointerEvents: 'none'}} />
);

const fmtTime = (v: number) => {
  const a = ((Math.floor(v) % 86400) + 86400) % 86400;
  return [Math.floor(a / 3600), Math.floor((a % 3600) / 60), a % 60].map((x) => String(x).padStart(2, '0')).join(':');
};

const fmtClock = (v: number, prefix = '', decimals = 0) => {
  const neg = v < 0;
  const a = Math.abs(v);
  const m = Math.floor(a / 60);
  const sec = a - m * 60;
  const ss = decimals > 0 ? sec.toFixed(decimals).padStart(3 + decimals, '0') : String(Math.floor(sec)).padStart(2, '0');
  return `${prefix || (neg ? 'T-' : 'T+')}${String(m).padStart(2, '0')}:${ss}`;
};

/** Heading, callout, source, HUD and stats panel shared by every documentary template. */
export const DocuOverlays: React.FC<DocuProps> = ({heading, headingColor = 'white', subheading, kicker, callout, calloutAt, source, hud, stats, statsAt}) => {
  const {t, dur, s} = useT();
  const hp = prog(t, 0.15, 0.6);
  const cp = prog(t, calloutAt ?? Math.min(1.2, dur * 0.3), 0.5);
  const sp = prog(t, statsAt ?? 0.8, 0.6);
  return (
    <AbsoluteFill style={{fontFamily: F.sans, color: C.text}}>
      {heading ? (
        <div style={{position: 'absolute', left: 80 * s, top: 64 * s, opacity: hp, transform: `translateX(${(1 - hp) * -20 * s}px)`}}>
          {kicker ? <div style={{fontSize: 22 * s, letterSpacing: 3 * s, color: '#c5ced6', marginBottom: 6 * s, fontWeight: 700, textShadow: '0 1px 8px rgba(0,0,0,0.85), 0 0 2px rgba(0,0,0,0.6)'}}>{kicker}</div> : null}
          <div style={{fontSize: 46.0 * s, fontWeight: 800, color: headingColor === 'teal' ? C.teal : C.text, letterSpacing: -0.5 * s, lineHeight: 1.05, textTransform: 'uppercase',
            textShadow: '0 2px 14px rgba(0,0,0,0.6)'}}>
            {heading}
          </div>
          {headingColor === 'white' ? <div style={{height: 3 * s, width: 90 * s * hp, background: C.red, marginTop: 10 * s}} /> : null}
          {subheading ? <div style={{fontSize: 22 * s, letterSpacing: 2.5 * s, color: C.dim, marginTop: 10 * s, fontWeight: 600, textTransform: 'uppercase'}}>{subheading}</div> : null}
        </div>
      ) : null}
      {hud ? (
        <div style={{position: 'absolute', right: 80 * s, top: 56 * s, textAlign: 'right', opacity: hp}}>
          {hud.label ? <div style={{fontSize: 20 * s, letterSpacing: 2.5 * s, color: C.dim, textTransform: 'uppercase'}}>{hud.label}</div> : null}
          <div style={{fontFamily: F.mono, fontSize: 40.0 * s, color: hud.color ?? (hud.clock !== undefined && hud.clock + t < 0 ? C.red : C.teal)}}>
            {hud.clock !== undefined
              ? hud.format === 'time' ? fmtTime(hud.clock + t) : fmtClock(hud.clock + t, hud.prefix, hud.decimals ?? 0)
              : hud.value}
          </div>
        </div>
      ) : null}
      {stats && stats.length ? (
        <div
          style={{
            position: 'absolute', right: 80 * s, bottom: 70 * s, minWidth: 380 * s, padding: `${14 * s}px ${20 * s}px`,
            background: C.panel, borderLeft: `${3 * s}px solid ${C.red}`, opacity: sp, transform: `translateY(${(1 - sp) * 16 * s}px)`,
          }}
        >
          {stats.map((r, i) => (
            <div key={i} style={{display: 'flex', justifyContent: 'space-between', gap: 40 * s, fontSize: 23 * s, lineHeight: 1.9}}>
              <span style={{color: C.dim, letterSpacing: 1.5 * s, textTransform: 'uppercase', fontSize: 20 * s}}>{r.label}</span>
              <span style={{fontFamily: F.mono, color: r.color ?? C.text}}>{r.value}</span>
            </div>
          ))}
        </div>
      ) : null}
      {callout ? (
        <div style={{position: 'absolute', left: 0, right: 0, bottom: 84 * s, display: 'flex', justifyContent: 'center'}}>
          <div
            style={{
              background: 'rgba(12,14,18,0.86)', padding: `${12 * s}px ${26 * s}px`, borderBottom: `${3 * s}px solid ${C.red}`,
              fontWeight: 800, fontSize: 30 * s, letterSpacing: 0.5 * s, textTransform: 'uppercase',
              clipPath: `inset(0 ${(1 - cp) * 50}% 0 ${(1 - cp) * 50}%)`,
            }}
          >
            {callout}
          </div>
        </div>
      ) : null}
      {source ? (
        <div style={{position: 'absolute', left: 80 * s, bottom: 34 * s, fontSize: 20 * s, color: C.dim, opacity: hp, letterSpacing: 0.5 * s, textShadow: '0 1px 6px rgba(0,0,0,0.8)'}}>{source}</div>
      ) : null}
    </AbsoluteFill>
  );
};

/** Wrap every documentary template: backdrop → content (fades) → overlays → vignette. */
export const DocuFrame: React.FC<DocuProps & {children: React.ReactNode; defaultBackdrop?: Backdrop}> = ({children, defaultBackdrop = 'navy', ...p}) => {
  const o = useContentOpacity();
  const {fps, t, dur} = useT();
  return (
    <AbsoluteFill style={{fontFamily: F.sans, color: C.text, background: '#000'}}>
      {p.footage ? (
        <AbsoluteFill>
          <OffthreadVideo src={staticFile(p.footage)} muted startFrom={Math.round((p.footageStart ?? 0) * fps)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
          <AbsoluteFill style={{background: `rgba(2,8,14,${p.footageDim ?? 0.45})`}} />
        </AbsoluteFill>
      ) : (
        <BackdropLayer kind={p.backdrop ?? defaultBackdrop} />
      )}
      <AbsoluteFill style={{opacity: o}}>
        <AbsoluteFill style={{transform: `scale(${1 + 0.035 * (t / Math.max(1, dur))})`}}>{children}</AbsoluteFill>
        <DocuOverlays {...p} />
      </AbsoluteFill>
      <Vignette />
    </AbsoluteFill>
  );
};

/** Animated number with optional thousands separators. */
export const fmtNum = (v: number, decimals = 0) =>
  v.toLocaleString('en-US', {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
