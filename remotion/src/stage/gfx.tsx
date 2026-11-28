/**
 * Graphics drawn over a live 3D shot: labels pinned to moving animals, measuring lines, place-and-date slugs, key
 * phrases, counters, titles. They follow the 3D picture frame by frame and arrive on the narrator's words.
 * Colours are the channel's own (black, white, yellow running into orange).
 */
import React from 'react';
import {AbsoluteFill} from 'remotion';
import {clamp, ease, ramp} from './math';

export const INK = '#0a0a0a';
export const PAPER = '#F7F7F8';
export const YELLOW = '#FDE302';
export const ORANGE = '#FB9002';
export const AMBER = '#FAB903';
export const GRAD = `linear-gradient(90deg, ${YELLOW} 0%, ${ORANGE} 100%)`;
export const HEAD = 'Anton, "Arial Narrow", Impact, sans-serif';
export const BODY = 'Montserrat, Inter, "DejaVu Sans", Arial, sans-serif';

export type Anchor = {actor?: string; point?: string | [number, number, number]; world?: [number, number, number]; screen?: [number, number]};
export type Spot = {x: number; y: number; ok: boolean};
export type Ctx = {t: number; dur: number; s: number; W: number; H: number; at: (a: Anchor | undefined) => Spot; time: (g: {at?: number; u?: number}) => number};

export type Gfx = {
  type: 'tag' | 'stamp' | 'line' | 'measure' | 'title' | 'chapter' | 'ring' | 'count' | 'note' | 'rows' | 'bars' | 'dim';
  at?: number; u?: number; out?: number; hold?: number;
  [k: string]: any;
};

/** How far in (0..1) and how far out (0..1) an element is. */
const life = (g: Gfx, c: Ctx, dIn = 0.55, dOut = 0.35) => {
  const t0 = c.time(g);
  const out = typeof g.out === 'number' ? g.out : typeof g.hold === 'number' ? t0 + g.hold : c.dur + 9;
  return {t0, inn: ramp(c.t, t0, dIn, 'expo'), outp: ramp(c.t, out, dOut, 'in'), on: c.t >= t0 && c.t < out + dOut};
};

/** Text that rises out of a slit (the usual way words arrive). */
const Rise: React.FC<{p: number; out?: number; delay?: number; children: React.ReactNode; style?: React.CSSProperties}> = ({p, out = 0, children, style}) => (
  <div style={{overflow: 'hidden', ...style}}>
    <div style={{transform: `translateY(${(1 - p) * 105 - out * 0}%)`, opacity: 1 - out, willChange: 'transform'}}>{children}</div>
  </div>
);

const shadow = '0 2px 14px rgba(0,0,0,0.65), 0 0 2px rgba(0,0,0,0.9)';

/* ------------------------------------------------------------------------------------------------- label */
const Tag: React.FC<{g: Gfx; c: Ctx}> = ({g, c}) => {
  const {inn, outp, on, t0} = life(g, c);
  if (!on) return null;
  const a = c.at(g.anchor);
  if (!a.ok) return null;
  const s = c.s;
  const dir: string = g.dir ?? 'ne';
  const len = (g.len ?? 120) * s;
  const sx = dir.includes('w') ? -1 : 1;
  const sy = dir.includes('n') ? -1 : dir.includes('s') ? 1 : 0;
  const ex = a.x + sx * len * (sy === 0 ? 1 : 0.62);
  const ey = a.y + sy * len * 0.62;
  const run = (g.run ?? 46) * s;
  const p1 = ramp(c.t, t0, 0.3, 'out');
  const p2 = ramp(c.t, t0 + 0.12, 0.35, 'out');
  const p3 = ramp(c.t, t0 + 0.3, 0.5, 'expo');
  const mx = a.x + (ex - a.x) * p2;
  const my = a.y + (ey - a.y) * p2;
  const hx = ex + sx * run * clamp(p2 * 1.6 - 0.6);
  const col = g.color ?? YELLOW;
  const o = 1 - outp;
  const pulse = 0.5 + 0.5 * Math.sin((c.t - t0) * 3.2);
  return (
    <>
      <svg width={c.W} height={c.H} style={{position: 'absolute', left: 0, top: 0, opacity: o, overflow: 'visible'}}>
        <circle cx={a.x} cy={a.y} r={(11 + 5 * pulse) * s * p1} fill="none" stroke={col} strokeWidth={1.5 * s} opacity={0.55 - 0.3 * pulse} />
        <circle cx={a.x} cy={a.y} r={4.5 * s * p1} fill={col} />
        <polyline points={`${a.x},${a.y} ${mx},${my} ${p2 > 0.62 ? hx : mx},${my}`} fill="none" stroke={PAPER} strokeWidth={2 * s} strokeLinejoin="round" style={{filter: 'drop-shadow(0 1px 3px rgba(0,0,0,0.7))'}} />
      </svg>
      <div style={{position: 'absolute', left: sx > 0 ? ex + run + 12 * s : undefined, right: sx < 0 ? c.W - (ex - run - 12 * s) : undefined, top: ey, transform: 'translateY(-50%)', opacity: o,
        textAlign: sx > 0 ? 'left' : 'right', fontFamily: BODY, color: PAPER, textShadow: shadow}}>
        <Rise p={p3}><div style={{fontWeight: 900, fontSize: (g.size ?? 30) * s, letterSpacing: '0.06em', textTransform: 'uppercase', lineHeight: 1.12, whiteSpace: 'nowrap'}}>{g.text}</div></Rise>
        {g.sub ? <Rise p={ramp(c.t, t0 + 0.42, 0.5, 'expo')}><div style={{fontWeight: 800, fontSize: 19 * s, letterSpacing: '0.12em', textTransform: 'uppercase', color: col, marginTop: 5 * s, whiteSpace: 'nowrap'}}>{g.sub}</div></Rise> : null}
      </div>
    </>
  );
};

/* ---------------------------------------------------------------------------------- place and date slug */
const Stamp: React.FC<{g: Gfx; c: Ctx}> = ({g, c}) => {
  const {outp, on, t0} = life(g, c);
  if (!on) return null;
  const s = c.s;
  const right = g.side === 'right';
  const bar = ramp(c.t, t0, 0.45, 'expo');
  return (
    <div style={{position: 'absolute', left: right ? undefined : 96 * s, right: right ? 96 * s : undefined, bottom: (g.y ?? 120) * s, opacity: 1 - outp, fontFamily: BODY, color: PAPER, textShadow: shadow, textAlign: right ? 'right' : 'left'}}>
      <div style={{height: 5 * s, width: 74 * s * bar, background: GRAD, marginBottom: 14 * s, marginLeft: right ? 'auto' : 0}} />
      <Rise p={ramp(c.t, t0 + 0.1, 0.55, 'expo')}><div style={{fontFamily: HEAD, fontSize: (g.size ?? 76) * s, lineHeight: 1.02, letterSpacing: '0.02em', textTransform: 'uppercase'}}>{g.text}</div></Rise>
      {g.sub ? <Rise p={ramp(c.t, t0 + 0.28, 0.55, 'expo')}><div style={{fontWeight: 800, fontSize: 22 * s, letterSpacing: '0.22em', textTransform: 'uppercase', marginTop: 10 * s, color: 'rgba(247,247,248,0.86)'}}>{g.sub}</div></Rise> : null}
    </div>
  );
};

/* ------------------------------------------------------------------------------------------- key phrase */
const Line: React.FC<{g: Gfx; c: Ctx}> = ({g, c}) => {
  const {outp, on, t0} = life(g, c);
  if (!on) return null;
  const s = c.s;
  const words = String(g.text).split(' ');
  const hi = String(g.hi ?? '').toLowerCase().split(' ').filter(Boolean);
  return (
    <div style={{position: 'absolute', left: 0, right: 0, bottom: (g.y ?? 92) * s, display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: 1 - outp, fontFamily: BODY, textShadow: shadow}}>
      <div style={{height: 4 * s, width: 64 * s * ramp(c.t, t0, 0.4, 'expo'), background: GRAD, marginBottom: 12 * s}} />
      <div style={{display: 'flex', gap: 11 * s, flexWrap: 'wrap', justifyContent: 'center', maxWidth: c.W * 0.8}}>
        {words.map((w, i) => {
          const p = ramp(c.t, t0 + 0.08 + i * 0.045, 0.45, 'expo');
          const on_ = hi.includes(w.toLowerCase().replace(/[^a-z0-9]/g, ''));
          return <Rise key={i} p={p}><span style={{fontWeight: 900, fontSize: (g.size ?? 34) * s, letterSpacing: '0.07em', textTransform: 'uppercase', color: on_ ? YELLOW : PAPER, whiteSpace: 'nowrap'}}>{w}</span></Rise>;
        })}
      </div>
    </div>
  );
};

/* --------------------------------------------------------------------------------------- measuring line */
const Measure: React.FC<{g: Gfx; c: Ctx}> = ({g, c}) => {
  const {outp, on, t0} = life(g, c);
  if (!on) return null;
  const a = c.at(g.from);
  const b = c.at(g.to);
  if (!a.ok || !b.ok) return null;
  const s = c.s;
  const off = (g.off ?? 70) * s;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const L = Math.hypot(dx, dy) || 1;
  const nx = -dy / L;
  const ny = dx / L;
  const ax = a.x + nx * off;
  const ay = a.y + ny * off;
  const bx = b.x + nx * off;
  const by = b.y + ny * off;
  const p = ramp(c.t, t0, g.d ?? 1.1, 'inOut');
  const mx = ax + (bx - ax) * 0.5;
  const my = ay + (by - ay) * 0.5;
  const ex = ax + (bx - ax) * p;
  const ey = ay + (by - ay) * p;
  const val = (g.value ?? 0) * p;
  const txt = `${val.toFixed(g.decimals ?? 1)}${g.unit ?? ''}`;
  const tick = 13 * s;
  return (
    <>
      <svg width={c.W} height={c.H} style={{position: 'absolute', left: 0, top: 0, opacity: 1 - outp, overflow: 'visible', filter: 'drop-shadow(0 1px 4px rgba(0,0,0,0.8))'}}>
        <line x1={a.x} y1={a.y} x2={ax} y2={ay} stroke={PAPER} strokeWidth={1.2 * s} strokeDasharray={`${4 * s} ${5 * s}`} opacity={0.6 * clamp(p * 4)} />
        <line x1={b.x} y1={b.y} x2={bx} y2={by} stroke={PAPER} strokeWidth={1.2 * s} strokeDasharray={`${4 * s} ${5 * s}`} opacity={0.6 * clamp(p * 4 - 3)} />
        <line x1={ax} y1={ay} x2={ex} y2={ey} stroke={YELLOW} strokeWidth={3 * s} />
        <line x1={ax - nx * tick} y1={ay - ny * tick} x2={ax + nx * tick} y2={ay + ny * tick} stroke={YELLOW} strokeWidth={3 * s} />
        <line x1={ex - nx * tick} y1={ey - ny * tick} x2={ex + nx * tick} y2={ey + ny * tick} stroke={YELLOW} strokeWidth={3 * s} />
      </svg>
      <div style={{position: 'absolute', left: mx, top: my, transform: `translate(-50%, ${ny >= 0 ? 18 * s : -118 * s}px)`, opacity: (1 - outp) * clamp(p * 5), textAlign: 'center', fontFamily: HEAD, color: PAPER, textShadow: shadow, whiteSpace: 'nowrap'}}>
        <div style={{fontSize: (g.size ?? 82) * s, lineHeight: 1, fontVariantNumeric: 'tabular-nums'}}>{txt}</div>
        {g.label ? <div style={{fontFamily: BODY, fontWeight: 800, fontSize: 19 * s, letterSpacing: '0.2em', textTransform: 'uppercase', color: YELLOW, marginTop: 6 * s}}>{g.label}</div> : null}
      </div>
    </>
  );
};

/* ------------------------------------------------------------------------------------------------ title */
const Title: React.FC<{g: Gfx; c: Ctx}> = ({g, c}) => {
  const {outp, on, t0} = life(g, c, 0.6, 0.45);
  if (!on) return null;
  const s = c.s;
  const lines: (string | {text: string; accent?: boolean; size?: number})[] = g.lines ?? [g.text];
  const align = g.align ?? 'center';
  return (
    <AbsoluteFill style={{justifyContent: g.v === 'top' ? 'flex-start' : g.v === 'bottom' ? 'flex-end' : 'center', alignItems: align === 'left' ? 'flex-start' : align === 'right' ? 'flex-end' : 'center',
      padding: `${(g.pad ?? 120) * s}px ${110 * s}px`, opacity: 1 - outp, fontFamily: HEAD, color: PAPER, textAlign: align}}>
      {g.kicker ? <Rise p={ramp(c.t, t0, 0.5, 'expo')}><div style={{fontFamily: BODY, fontWeight: 800, fontSize: 24 * s, letterSpacing: '0.34em', textTransform: 'uppercase', color: YELLOW, marginBottom: 18 * s, textShadow: shadow}}>{g.kicker}</div></Rise> : null}
      {lines.map((ln, i) => {
        const l = typeof ln === 'string' ? {text: ln} : ln;
        const p = ramp(c.t, t0 + 0.1 + i * 0.13, 0.7, 'expo');
        return (
          <Rise key={i} p={p}>
            <div style={{fontSize: (l.size ?? g.size ?? 150) * s, lineHeight: 1.04, letterSpacing: '0.015em', textTransform: 'uppercase', whiteSpace: 'nowrap',
              ...(l.accent ? {background: GRAD, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent', filter: 'drop-shadow(0 3px 16px rgba(0,0,0,0.6))'} : {textShadow: '0 4px 30px rgba(0,0,0,0.7), 0 0 3px rgba(0,0,0,0.9)'})}}>{l.text}</div>
          </Rise>
        );
      })}
      {g.sub ? <Rise p={ramp(c.t, t0 + 0.2 + lines.length * 0.13, 0.6, 'expo')}><div style={{fontFamily: BODY, fontWeight: 800, fontSize: 26 * s, letterSpacing: '0.2em', textTransform: 'uppercase', marginTop: 22 * s, textShadow: shadow}}>{g.sub}</div></Rise> : null}
    </AbsoluteFill>
  );
};

/* ---------------------------------------------------------------------------------------- chapter marker */
const Chapter: React.FC<{g: Gfx; c: Ctx}> = ({g, c}) => {
  const {outp, on, t0} = life({hold: 5.5, ...g}, c);
  if (!on) return null;
  const s = c.s;
  return (
    <div style={{position: 'absolute', left: 96 * s, top: 84 * s, display: 'flex', alignItems: 'center', gap: 20 * s, opacity: 1 - outp, fontFamily: BODY, color: PAPER, textShadow: shadow}}>
      <Rise p={ramp(c.t, t0, 0.5, 'expo')}><div style={{fontFamily: HEAD, fontSize: 64 * s, lineHeight: 1, background: GRAD, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent'}}>{g.n}</div></Rise>
      <div style={{width: 3 * s, height: 54 * s * ramp(c.t, t0 + 0.1, 0.4, 'expo'), background: PAPER, opacity: 0.8}} />
      <Rise p={ramp(c.t, t0 + 0.18, 0.55, 'expo')}><div style={{fontWeight: 900, fontSize: 26 * s, letterSpacing: '0.24em', textTransform: 'uppercase'}}>{g.text}</div></Rise>
    </div>
  );
};

/* ----------------------------------------------------------------------------------------- target ring */
const Ring: React.FC<{g: Gfx; c: Ctx}> = ({g, c}) => {
  const {outp, on, t0} = life(g, c);
  if (!on) return null;
  const a = c.at(g.anchor);
  if (!a.ok) return null;
  const s = c.s;
  const r = (g.r ?? 90) * s;
  const p = ramp(c.t, t0, 0.7, 'expo');
  const circ = 2 * Math.PI * r;
  const spin = (c.t - t0) * 22;
  const col = g.color ?? YELLOW;
  return (
    <svg width={c.W} height={c.H} style={{position: 'absolute', left: 0, top: 0, opacity: 1 - outp, overflow: 'visible', filter: 'drop-shadow(0 1px 4px rgba(0,0,0,0.7))'}}>
      <circle cx={a.x} cy={a.y} r={r * (1.35 - 0.35 * p)} fill="none" stroke={col} strokeWidth={2.5 * s} strokeDasharray={`${circ * p} ${circ}`} transform={`rotate(${-90 + spin} ${a.x} ${a.y})`} />
      <circle cx={a.x} cy={a.y} r={r * 1.16} fill="none" stroke={PAPER} strokeWidth={1.2 * s} strokeDasharray={`${3 * s} ${14 * s}`} opacity={0.5 * p} transform={`rotate(${-spin * 0.6} ${a.x} ${a.y})`} />
      {[0, 90, 180, 270].map((d) => <line key={d} x1={a.x + r * 0.86} y1={a.y} x2={a.x + r * 1.0} y2={a.y} stroke={col} strokeWidth={3 * s} opacity={p} transform={`rotate(${d + 45} ${a.x} ${a.y})`} />)}
    </svg>
  );
};

/* ------------------------------------------------------------------------------------------- big number */
const Count: React.FC<{g: Gfx; c: Ctx}> = ({g, c}) => {
  const {outp, on, t0} = life(g, c);
  if (!on) return null;
  const s = c.s;
  const p = ramp(c.t, t0 + 0.1, g.d ?? 1.4, 'out');
  const v = (g.from ?? 0) + ((g.to ?? 0) - (g.from ?? 0)) * p;
  const txt = `${g.prefix ?? ''}${v.toLocaleString('en-US', {minimumFractionDigits: g.decimals ?? 0, maximumFractionDigits: g.decimals ?? 0})}${g.suffix ?? ''}`;
  const x = (g.x ?? 0.5) * c.W;
  const y = (g.y ?? 0.5) * c.H;
  const al = g.align ?? 'center';
  return (
    <div style={{position: 'absolute', left: x, top: y, transform: `translate(${al === 'left' ? '0' : al === 'right' ? '-100%' : '-50%'}, -50%)`, opacity: 1 - outp, textAlign: al, fontFamily: HEAD, color: PAPER, whiteSpace: 'nowrap'}}>
      {g.kicker ? <Rise p={ramp(c.t, t0, 0.5, 'expo')}><div style={{fontFamily: BODY, fontWeight: 800, fontSize: 22 * s, letterSpacing: '0.26em', textTransform: 'uppercase', color: YELLOW, marginBottom: 8 * s, textShadow: shadow}}>{g.kicker}</div></Rise> : null}
      <Rise p={ramp(c.t, t0 + 0.05, 0.6, 'expo')}><div style={{fontSize: (g.size ?? 190) * s, lineHeight: 1, fontVariantNumeric: 'tabular-nums', textShadow: '0 4px 30px rgba(0,0,0,0.7)'}}>{txt}</div></Rise>
      {g.label ? <Rise p={ramp(c.t, t0 + 0.3, 0.55, 'expo')}><div style={{fontFamily: BODY, fontWeight: 800, fontSize: 24 * s, letterSpacing: '0.2em', textTransform: 'uppercase', marginTop: 10 * s, textShadow: shadow}}>{g.label}</div></Rise> : null}
    </div>
  );
};

/* -------------------------------------------------------------------------------- small pinned note (no line) */
const Note: React.FC<{g: Gfx; c: Ctx}> = ({g, c}) => {
  const {outp, on, t0} = life(g, c);
  if (!on) return null;
  const a = c.at(g.anchor);
  if (!a.ok) return null;
  const s = c.s;
  const p = ramp(c.t, t0, 0.45, 'expo');
  return (
    <div style={{position: 'absolute', left: a.x + (g.dx ?? 0) * s, top: a.y + (g.dy ?? -60) * s, transform: `translate(-50%, -50%) scale(${0.85 + 0.15 * p})`, opacity: p * (1 - outp), fontFamily: BODY}}>
      <div style={{background: g.fill ?? YELLOW, color: INK, fontWeight: 900, fontSize: (g.size ?? 22) * s, letterSpacing: '0.1em', textTransform: 'uppercase', padding: `${6 * s}px ${12 * s}px`, whiteSpace: 'nowrap', boxShadow: '0 4px 18px rgba(0,0,0,0.5)'}}>{g.text}</div>
    </div>
  );
};

/* ------------------------------------------------------------------------------ rows of facts in a panel */
const Rows: React.FC<{g: Gfx; c: Ctx}> = ({g, c}) => {
  const {outp, on, t0} = life(g, c);
  if (!on) return null;
  const s = c.s;
  const rows: {k: string; v?: string; at?: number; u?: number; hot?: boolean}[] = g.rows ?? [];
  const right = g.side === 'right';
  return (
    <div style={{position: 'absolute', left: right ? undefined : 96 * s, right: right ? 96 * s : undefined, top: (g.y ?? 0.3) * c.H, width: (g.w ?? 640) * s, opacity: 1 - outp, fontFamily: BODY, color: PAPER}}>
      {g.title ? <Rise p={ramp(c.t, t0, 0.5, 'expo')}><div style={{fontFamily: HEAD, fontSize: 54 * s, letterSpacing: '0.02em', textTransform: 'uppercase', textShadow: shadow, marginBottom: 6 * s}}>{g.title}</div></Rise> : null}
      <div style={{height: 4 * s, width: `${100 * ramp(c.t, t0 + 0.1, 0.6, 'expo')}%`, background: GRAD, marginBottom: 10 * s}} />
      {rows.map((r, i) => {
        const rt = typeof r.at === 'number' || typeof r.u === 'number' ? c.time(r) : t0 + 0.3 + i * 0.22;
        const p = ramp(c.t, rt, 0.5, 'expo');
        return (
          <div key={i} style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 24 * s, padding: `${11 * s}px 0`, borderBottom: `${1 * s}px solid rgba(247,247,248,${0.22 * p})`, opacity: p, transform: `translateX(${(1 - p) * (right ? 30 : -30) * s}px)`, textShadow: shadow}}>
            <span style={{fontWeight: 800, fontSize: 25 * s, letterSpacing: '0.08em', textTransform: 'uppercase'}}>{r.k}</span>
            {r.v ? <span style={{fontFamily: HEAD, fontSize: 38 * s, color: r.hot ? YELLOW : PAPER, whiteSpace: 'nowrap'}}>{r.v}</span> : null}
          </div>
        );
      })}
    </div>
  );
};

/* ------------------------------------------------------------------------------------------------- bars */
const Bars: React.FC<{g: Gfx; c: Ctx}> = ({g, c}) => {
  const {outp, on, t0} = life(g, c);
  if (!on) return null;
  const s = c.s;
  const bars: {label: string; value: number; show?: string; at?: number; u?: number; hot?: boolean}[] = g.bars ?? [];
  const max = g.max ?? Math.max(...bars.map((b) => b.value), 1);
  const W = (g.w ?? 1100) * s;
  return (
    <div style={{position: 'absolute', left: (g.x ?? 0.5) * c.W - W / 2, top: (g.y ?? 0.34) * c.H, width: W, opacity: 1 - outp, fontFamily: BODY, color: PAPER, textShadow: shadow}}>
      {g.title ? <Rise p={ramp(c.t, t0, 0.5, 'expo')}><div style={{fontFamily: HEAD, fontSize: 58 * s, textTransform: 'uppercase', marginBottom: 26 * s}}>{g.title}</div></Rise> : null}
      {bars.map((b, i) => {
        const bt = typeof b.at === 'number' || typeof b.u === 'number' ? c.time(b) : t0 + 0.35 + i * 0.5;
        const p = ramp(c.t, bt, 1.1, 'out');
        const on_ = ramp(c.t, bt, 0.4, 'expo');
        return (
          <div key={i} style={{marginBottom: 30 * s, opacity: on_}}>
            <div style={{fontWeight: 800, fontSize: 24 * s, letterSpacing: '0.16em', textTransform: 'uppercase', marginBottom: 8 * s}}>{b.label}</div>
            <div style={{display: 'flex', alignItems: 'center', gap: 20 * s}}>
              <div style={{height: 46 * s, width: Math.max(4 * s, (W - 230 * s) * (b.value / max) * p), background: b.hot ? GRAD : 'rgba(247,247,248,0.86)'}} />
              <div style={{fontFamily: HEAD, fontSize: 60 * s, lineHeight: 1, color: b.hot ? YELLOW : PAPER, fontVariantNumeric: 'tabular-nums'}}>{b.show ?? Math.round(b.value * p).toLocaleString('en-US')}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

const KINDS: Record<string, React.FC<{g: Gfx; c: Ctx}>> = {tag: Tag, stamp: Stamp, line: Line, measure: Measure, title: Title, chapter: Chapter, ring: Ring, count: Count, note: Note, rows: Rows, bars: Bars};

export const GfxLayer: React.FC<{items: Gfx[]; c: Ctx}> = ({items, c}) => {
  // "dim" darkens the picture behind words that need the whole frame
  let dim = 0;
  for (const g of items) if (g.type === 'dim') { const l = life(g, c, g.d ?? 0.8, g.d ?? 0.8); dim = Math.max(dim, (g.to ?? 0.5) * ease('soft', l.inn) * (1 - l.outp)); }
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {dim > 0 ? <AbsoluteFill style={{background: `rgba(2,6,10,${dim})`}} /> : null}
      {items.map((g, i) => {
        const K = KINDS[g.type];
        return K ? <K key={i} g={g} c={c} /> : null;
      })}
    </AbsoluteFill>
  );
};
