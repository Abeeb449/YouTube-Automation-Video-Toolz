import React from 'react';
import {AbsoluteFill, Easing, interpolate} from 'remotion';
import {C, DocuFrame, DocuProps, F, fmtNum, prog, Reveal, stagger, useT} from './kit';

/* ------------------------------------------------------------------ Counter + timeline */
export type CounterProps = DocuProps & {
  from?: number; to: number; prefix?: string; suffix?: string; decimals?: number;
  label?: string; countAt?: number; countDur?: number;
  /** No thousands separators (for years). */
  plain?: boolean;
  /** Big and centred (default when there is no timeline or footage). */
  center?: boolean;
  timeline?: {start: number; end: number; tickEvery?: number; events?: {year: number; label: string; at?: number}[]; band?: {from: number; to: number; label: string}};
};

export const Counter: React.FC<CounterProps> = (p) => {
  const {t, dur, s, width} = useT();
  const at = p.countAt ?? 0.3;
  const cd = p.countDur ?? Math.min(dur * 0.7, 3.5);
  const v = interpolate(t, [at, at + cd], [p.from ?? 0, p.to], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const tl = p.timeline;
  const x0 = 120 * s, x1 = width - 120 * s, y = 760 * s;
  const frac = (yr: number) => (tl ? (yr - tl.start) / (tl.end - tl.start) : 0);
  const k = tl ? interpolate(v, [p.from ?? 0, p.to], [0, 1]) : 0;
  // on its own (no timeline, no footage behind it) the number is the whole shot: big and centred
  const centered = p.center ?? (!tl && !(p as {footage?: string}).footage);
  return (
    <DocuFrame {...p}>
      <div style={centered
        ? {position: 'absolute', left: 0, right: 0, top: '50%', transform: 'translateY(-55%)', textAlign: 'center', opacity: prog(t, Math.max(0, at - 0.5), 0.5), filter: `blur(${(1 - prog(t, at, 0.4)) * 12 * s}px)`}
        : {position: 'absolute', left: 110 * s, top: p.heading ? 200 * s : 90 * s, filter: `blur(${(1 - prog(t, at, 0.4)) * 12 * s}px)`}}>
        <div style={{fontSize: (centered ? 210 : 150) * s, fontWeight: 800, lineHeight: 1, fontVariantNumeric: 'tabular-nums'}}>
          {p.prefix}{p.plain ? Math.round(v).toString() : fmtNum(v, p.decimals ?? 0)}{p.suffix}
        </div>
        {p.label ? <Reveal at={at + cd * 0.6}><div style={{fontSize: (centered ? 40 : 28) * s, color: C.red, fontWeight: 800, letterSpacing: 2.5 * s, marginTop: (centered ? 22 : 12) * s, textTransform: 'uppercase'}}>{p.label}</div></Reveal> : null}
      </div>
      {tl ? (
        <svg width={width} height={1080 * s} style={{position: 'absolute', left: 0, top: 0}}>
          <line x1={x0} x2={x1} y1={y} y2={y} stroke={C.faint} strokeWidth={2 * s} strokeDasharray={`${2 * s} ${6 * s}`} />
          <line x1={x0} x2={x0 + (x1 - x0) * k} y1={y} y2={y} stroke={C.teal} strokeWidth={2 * s} />
          {Array.from({length: Math.floor((tl.end - tl.start) / (tl.tickEvery ?? 10)) + 1}).map((_, i) => {
            const yr = tl.start + i * (tl.tickEvery ?? 10);
            const x = x0 + (x1 - x0) * frac(yr);
            return <text key={i} x={x} y={y + 34 * s} fill={C.dim} fontSize={21 * s} fontFamily={F.sans} textAnchor="middle" opacity={k >= frac(yr) - 0.001 ? 1 : 0.35}>{yr}</text>;
          })}
          <circle cx={x0 + (x1 - x0) * k} cy={y} r={7 * s} fill={C.teal} />
          {(tl.events ?? []).map((ev, i) => {
            const x = x0 + (x1 - x0) * frac(ev.year);
            const a = prog(t, ev.at ?? at + cd * frac(ev.year), 0.4);
            return (
              <g key={i} opacity={a}>
                <line x1={x} x2={x} y1={y} y2={y - 90 * s} stroke={C.amber} strokeWidth={1.5 * s} />
                <circle cx={x} cy={y - 90 * s} r={4 * s} fill={C.amber} />
                <text x={x + 10 * s} y={y - 86 * s} fill={C.amber} fontSize={21 * s} fontFamily={F.sans} fontWeight={700} letterSpacing={1.5 * s}>{ev.label.toUpperCase()}</text>
              </g>
            );
          })}
          {tl.band ? (
            <g opacity={prog(t, at + cd * 0.5, 0.6)}>
              <rect x={x0 + (x1 - x0) * frac(tl.band.from)} y={y + 56 * s} width={(x1 - x0) * (frac(tl.band.to) - frac(tl.band.from))} height={30 * s} fill={C.teal} fillOpacity={0.15} stroke={C.teal} strokeOpacity={0.5} />
              <text x={x0 + (x1 - x0) * frac(tl.band.from) + 12 * s} y={y + 76 * s} fill={C.teal} fontSize={20 * s} fontFamily={F.sans} fontWeight={700} letterSpacing={2 * s}>{tl.band.label.toUpperCase()}</text>
            </g>
          ) : null}
        </svg>
      ) : null}
    </DocuFrame>
  );
};

/* ------------------------------------------------------------------ Stat cards + stamp */
export type StatCardsProps = DocuProps & {
  cards: {label: string; value: string; bar?: number; at?: number}[];
  stamp?: {text: string; at?: number; color?: string};
};

export const StatCards: React.FC<StatCardsProps> = (p) => {
  const {t, dur, s} = useT();
  const st = p.stamp;
  const sa = st ? (st.at ?? dur * 0.6) : 0;
  const sp = st ? interpolate(t, [sa, sa + 0.18, sa + 0.3], [0, 1.08, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 0;
  const shake = st && t > sa && t < sa + 0.3 ? Math.sin(t * 90) * 6 * s : 0;
  return (
    <DocuFrame {...p}>
      <AbsoluteFill style={{transform: `translateX(${shake}px)`}}>
        <div style={{position: 'absolute', left: 110 * s, top: 280 * s, display: 'flex', flexDirection: 'column', gap: 22 * s}}>
          {p.cards.map((c, i) => {
            const at = c.at ?? stagger(i, p.cards.length, dur, 0.5, 0.5);
            const bp = prog(t, at + 0.2, 0.9);
            return (
              <Reveal key={i} at={at}>
                <div style={{background: C.panel, borderLeft: `${3 * s}px solid ${C.faint}`, padding: `${14 * s}px ${22 * s}px`, width: 420 * s}}>
                  <div style={{fontSize: 20 * s, color: C.dim, letterSpacing: 2 * s, textTransform: 'uppercase'}}>{c.label}</div>
                  <div style={{fontFamily: F.mono, fontSize: 34.0 * s, marginTop: 4 * s}}>{c.value}</div>
                  {c.bar !== undefined ? <div style={{height: 3 * s, width: `${c.bar * 100 * bp}%`, background: C.red, marginTop: 8 * s}} /> : null}
                </div>
              </Reveal>
            );
          })}
        </div>
        {st ? (
          <div style={{position: 'absolute', right: 260 * s, top: 330 * s, transform: `rotate(-9deg) scale(${sp === 0 ? 2 : 2 - sp})`, opacity: Math.min(1, sp)}}>
            <div style={{border: `${6 * s}px solid ${st.color ?? C.red}`, color: st.color ?? C.red, fontSize: 84.0 * s, fontWeight: 900, padding: `${6 * s}px ${28 * s}px`, letterSpacing: 4 * s}}>
              {st.text.toUpperCase()}
            </div>
          </div>
        ) : null}
      </AbsoluteFill>
    </DocuFrame>
  );
};

/* ------------------------------------------------------------------ Dot grid (waffle) */
export type DotGridProps = DocuProps & {
  count: number; highlight?: number; value?: string; label?: string; note?: string;
  color?: string; fillAt?: number; fillDur?: number; cols?: number;
};

export const DotGrid: React.FC<DotGridProps> = (p) => {
  const {t, dur, s} = useT();
  const n = Math.min(p.count, 3000);
  const cols = p.cols ?? Math.ceil(Math.sqrt(n * 2.2));
  const rows = Math.ceil(n / cols);
  const area = {x: 860 * s, y: 250 * s, w: 940 * s, h: 560 * s};
  const step = Math.min(area.w / cols, area.h / rows);
  const fa = p.fillAt ?? 0.6, fd = p.fillDur ?? Math.min(dur * 0.6, 3);
  const shown = interpolate(t, [fa, fa + fd], [0, n], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const hiCount = p.highlight ?? n;
  return (
    <DocuFrame {...p}>
      <div style={{position: 'absolute', left: 110 * s, top: 260 * s, width: 640 * s}}>
        {p.value ? <Reveal at={0.2}><div style={{fontSize: 120.0 * s, fontWeight: 800, lineHeight: 1}}>{p.value}</div></Reveal> : null}
        {p.label ? <Reveal at={0.5}><div style={{fontSize: 28 * s, color: p.color ?? C.red, fontWeight: 800, letterSpacing: 2.5 * s, marginTop: 10 * s, textTransform: 'uppercase'}}>{p.label}</div></Reveal> : null}
        {p.note ? <Reveal at={0.8}><div style={{fontSize: 22 * s, color: C.dim, letterSpacing: 2 * s, marginTop: 10 * s, textTransform: 'uppercase'}}>{p.note}</div></Reveal> : null}
      </div>
      <svg width={1920 * s} height={1080 * s} style={{position: 'absolute', left: 0, top: 0}}>
        {Array.from({length: n}).map((_, i) => {
          const c = i % cols, r = Math.floor(i / cols);
          const on = i < shown;
          return (
            <circle key={i} cx={area.x + c * step + step / 2} cy={area.y + r * step + step / 2} r={step * 0.32}
              fill={i < hiCount ? (p.color ?? C.red) : C.faint} opacity={on ? 0.95 : 0.08} />
          );
        })}
      </svg>
    </DocuFrame>
  );
};

/* ------------------------------------------------------------------ Bar comparison */
export type BarCompareProps = DocuProps & {
  bars: {label: string; value: number; display?: string; color?: string; at?: number}[];
  unit?: string; max?: number;
};

export const BarCompare: React.FC<BarCompareProps> = (p) => {
  const {t, dur, s} = useT();
  const max = p.max ?? Math.max(...p.bars.map((b) => b.value));
  return (
    <DocuFrame {...p}>
      <div style={{position: 'absolute', left: 110 * s, right: 110 * s, top: 260 * s, display: 'flex', flexDirection: 'column', gap: 46 * s}}>
        {p.bars.map((b, i) => {
          const at = b.at ?? stagger(i, p.bars.length, dur, 0.5, 0.5);
          const k = prog(t, at, 1.1);
          return (
            <div key={i} style={{opacity: Math.min(1, k * 3)}}>
              <div style={{fontSize: 21 * s, color: C.dim, letterSpacing: 2.5 * s, textTransform: 'uppercase', marginBottom: 8 * s}}>{b.label}</div>
              <div style={{display: 'flex', alignItems: 'center', gap: 18 * s}}>
                <div style={{height: 34 * s, width: `${(b.value / max) * 78 * k}%`, background: b.color ?? (i === p.bars.length - 1 ? C.red : '#7f8fa0'), minWidth: 4 * s}} />
                <div style={{fontFamily: F.mono, fontSize: 30 * s}}>{b.display ?? `${fmtNum(b.value * k)}${p.unit ? ` ${p.unit}` : ''}`}</div>
              </div>
            </div>
          );
        })}
      </div>
    </DocuFrame>
  );
};

/* ------------------------------------------------------------------ Source list ("SIMULATION – nothing made up") */
export type SourceListProps = DocuProps & {
  tag: string; tagNote?: string;
  rows: {title: string; source?: string; at?: number}[];
};

export const SourceList: React.FC<SourceListProps> = (p) => {
  const {t, dur, s} = useT();
  const tp = prog(t, 0.2, 0.5);
  return (
    <DocuFrame {...p}>
      <div style={{position: 'absolute', left: 0, right: 0, top: p.rows.length ? 230 * s : 420 * s, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
        <div style={{border: `${2.5 * s}px solid ${C.red}`, padding: `${12 * s}px ${30 * s}px`, display: 'flex', alignItems: 'center', gap: 16 * s,
          transform: `scale(${0.9 + 0.1 * tp})`, opacity: tp, background: 'rgba(229,55,47,0.06)'}}>
          <div style={{width: 14 * s, height: 14 * s, borderRadius: 7 * s, background: C.red, opacity: 0.6 + 0.4 * Math.abs(Math.sin(t * 3))}} />
          <div style={{fontSize: 46.0 * s, fontWeight: 800, letterSpacing: 1 * s}}>{p.tag.toUpperCase()}</div>
        </div>
        {p.tagNote ? <Reveal at={0.6}><div style={{fontSize: 22 * s, color: C.red, letterSpacing: 3 * s, marginTop: 14 * s, fontWeight: 700, textTransform: 'uppercase'}}>{p.tagNote}</div></Reveal> : null}
        <div style={{marginTop: 70 * s, width: 1150 * s}}>
          {p.rows.map((r, i) => (
            <Reveal key={i} at={r.at ?? stagger(i, p.rows.length, dur, 1.2, 0.75)}>
              <div style={{display: 'flex', alignItems: 'baseline', gap: 30 * s, padding: `${12 * s}px 0`, borderBottom: `1px solid rgba(138,161,182,0.15)`}}>
                <span style={{fontFamily: F.mono, color: C.faint, fontSize: 22 * s, width: 40 * s}}>{String(i + 1).padStart(2, '0')}</span>
                <span style={{fontSize: 30 * s, fontWeight: 800, flex: 1, textTransform: 'uppercase'}}>{r.title}</span>
                <span style={{fontSize: 21 * s, color: C.dim}}>{r.source}</span>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </DocuFrame>
  );
};

/* ------------------------------------------------------------------ Doomsday-style clock */
export type ClockProps = DocuProps & {
  /** Seconds before midnight shown by the hands. */
  seconds: number; value?: string; label?: string; series?: number[]; seriesLabel?: string;
};

export const Clock: React.FC<ClockProps> = (p) => {
  const {t, dur, s} = useT();
  const k = interpolate(t, [0.3, Math.min(dur * 0.6, 3)], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const startMin = 15;
  const minutesBefore = startMin - (startMin - p.seconds / 60) * k;
  const ang = -minutesBefore * 6; // minute hand degrees from 12
  const cx = 600 * s, cy = 560 * s, R = 270 * s;
  const rad = (d: number) => ((d - 90) * Math.PI) / 180;
  const arc = `M${cx},${cy} L${cx + R * Math.cos(rad(ang))},${cy + R * Math.sin(rad(ang))} A${R},${R} 0 0 1 ${cx},${cy - R} Z`;
  const ser = p.series ?? [];
  const chart = {x: 1100 * s, y: 380 * s, w: 520 * s, h: 200 * s};
  const mn = Math.min(...(ser.length ? ser : [0])), mx = Math.max(...(ser.length ? ser : [1]));
  const pts = ser.map((v, i) => [chart.x + (i / Math.max(1, ser.length - 1)) * chart.w, chart.y + chart.h - ((v - mn) / Math.max(1e-9, mx - mn)) * chart.h]);
  const cp = prog(t, 1, 2);
  return (
    <DocuFrame {...p} defaultBackdrop="ember">
      <svg width={1920 * s} height={1080 * s} style={{position: 'absolute'}}>
        <circle cx={cx} cy={cy} r={R} fill="rgba(0,0,0,0.25)" stroke="rgba(255,255,255,0.75)" strokeWidth={2 * s} />
        {Array.from({length: 60}).map((_, i) => {
          const a = rad(i * 6), L = i % 5 === 0 ? 22 * s : 9 * s;
          return <line key={i} x1={cx + (R - 6 * s) * Math.cos(a)} y1={cy + (R - 6 * s) * Math.sin(a)} x2={cx + (R - 6 * s - L) * Math.cos(a)} y2={cy + (R - 6 * s - L) * Math.sin(a)} stroke="#fff" strokeOpacity={0.8} strokeWidth={(i % 5 === 0 ? 3 : 1.5) * s} />;
        })}
        <path d={arc} fill={C.red} fillOpacity={0.45} />
        <line x1={cx} y1={cy} x2={cx + R * 0.88 * Math.cos(rad(ang))} y2={cy + R * 0.88 * Math.sin(rad(ang))} stroke="#fff" strokeWidth={5 * s} strokeLinecap="round" />
        <line x1={cx} y1={cy} x2={cx + R * 0.55 * Math.cos(rad(-1))} y2={cy + R * 0.55 * Math.sin(rad(-1))} stroke="#fff" strokeWidth={7 * s} strokeLinecap="round" />
        <circle cx={cx} cy={cy} r={9 * s} fill={C.red} />
        {pts.length > 1 ? (
          <g opacity={prog(t, 1, 0.5)}>
            <text x={chart.x} y={chart.y - 24 * s} fill={C.dim} fontSize={20 * s} fontFamily={F.sans} letterSpacing={2 * s}>{(p.seriesLabel ?? '').toUpperCase()}</text>
            <polyline points={pts.map((q) => q.join(',')).join(' ')} fill="none" stroke={C.teal} strokeWidth={2.5 * s}
              strokeDasharray={chart.w * 3} strokeDashoffset={chart.w * 3 * (1 - cp)} />
          </g>
        ) : null}
      </svg>
      {p.value ? (
        <div style={{position: 'absolute', left: 1100 * s, top: 640 * s, display: 'flex', alignItems: 'baseline', gap: 14 * s, opacity: prog(t, dur * 0.45, 0.6)}}>
          <div style={{fontSize: 130.0 * s, fontWeight: 900, color: C.red, lineHeight: 1}}>{p.value}</div>
          <div style={{fontSize: 28 * s, color: C.red, fontWeight: 800, letterSpacing: 2 * s, textTransform: 'uppercase', maxWidth: 260 * s}}>{p.label}</div>
        </div>
      ) : null}
    </DocuFrame>
  );
};

/* ------------------------------------------------------------------ Step-by-step maths */
export type EquationProps = DocuProps & {lines: {text: string; note?: string; at?: number; big?: boolean}[]};

const mathText = (txt: string) =>
  txt.split(/(\^[-\w.]+)/g).map((part, i) => (part.startsWith('^') ? <sup key={i} style={{fontSize: '0.6em'}}>{part.slice(1)}</sup> : <span key={i}>{part}</span>));

export const Equation: React.FC<EquationProps> = (p) => {
  const {dur, s} = useT();
  return (
    <DocuFrame {...p} headingColor={p.headingColor ?? 'teal'}>
      <div style={{position: 'absolute', left: 110 * s, top: 250 * s, display: 'flex', flexDirection: 'column', gap: 26 * s}}>
        {p.lines.map((l, i) => (
          <Reveal key={i} at={l.at ?? stagger(i, p.lines.length, dur, 0.4, 0.7)}>
            <div style={{fontFamily: F.serif, fontStyle: 'italic', fontSize: (l.big ? 64 : i === 0 ? 46 : 34) * s, color: i === p.lines.length - 1 && p.lines.length > 1 ? C.teal : C.text}}>
              {mathText(l.text)}
            </div>
            {l.note ? <div style={{fontSize: 20 * s, color: C.faint, marginTop: 4 * s}}>{l.note}</div> : null}
          </Reveal>
        ))}
      </div>
    </DocuFrame>
  );
};

/* ------------------------------------------------------------------ Side-by-side comparison */
type Side = {title: string; subtitle?: string; footer?: string; color?: string; orb?: boolean; at?: number};
export type SplitCompareProps = DocuProps & {left: Side; right: Side};

export const SplitCompare: React.FC<SplitCompareProps> = (p) => {
  const {t, dur, s} = useT();
  const col = (sd: Side, x: number, at: number) => {
    const a = prog(t, at, 0.7);
    return (
      <div style={{position: 'absolute', left: x, top: 200 * s, width: 820 * s, display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: 0.25 + 0.75 * a}}>
        <div style={{fontSize: 30.0 * s, fontWeight: 800, textTransform: 'uppercase'}}>{sd.title}</div>
        {sd.subtitle ? <div style={{fontSize: 21 * s, letterSpacing: 2 * s, color: sd.color ?? C.teal, marginTop: 8 * s, textTransform: 'uppercase', fontWeight: 700}}>{sd.subtitle}</div> : null}
        {sd.orb ? (
          <div style={{marginTop: 120 * s, width: 150 * s, height: 150 * s, borderRadius: 75 * s, opacity: a,
            background: 'radial-gradient(circle, #fff4c2 0%, #ffb347 40%, #e8571f 75%, rgba(232,87,31,0) 100%)', boxShadow: `0 0 ${90 * s}px ${30 * s}px rgba(255,140,40,0.35)`}} />
        ) : <div style={{height: 270 * s}} />}
        {sd.footer ? (
          <div style={{marginTop: 120 * s, background: C.panel, padding: `${16 * s}px ${40 * s}px`, fontSize: 21 * s, letterSpacing: 2 * s, textTransform: 'uppercase', color: sd.color ?? C.dim, fontWeight: 700, opacity: a}}>
            {sd.footer}
          </div>
        ) : null}
      </div>
    );
  };
  return (
    <DocuFrame {...p}>
      <div style={{position: 'absolute', left: 960 * s, top: 170 * s, bottom: 170 * s, width: 1, background: 'rgba(138,161,182,0.25)'}} />
      {col(p.left, 140 * s, p.left.at ?? 0.4)}
      {col(p.right, 960 * s, p.right.at ?? dur * 0.5)}
    </DocuFrame>
  );
};

/* ------------------------------------------------------------------ Big statement */
export type StatementProps = DocuProps & {kicker2?: string; line1: string; line2?: string; footnote?: string};

export const Statement: React.FC<StatementProps> = (p) => {
  const {s} = useT();
  return (
    <DocuFrame {...p} defaultBackdrop="ember">
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', textAlign: 'center'}}>
        {p.kicker2 ? <Reveal at={0.2}><div style={{fontSize: 22 * s, letterSpacing: 3 * s, color: C.amber, fontWeight: 700, marginBottom: 20 * s, textTransform: 'uppercase'}}>{p.kicker2}</div></Reveal> : null}
        <Reveal at={0.4}><div style={{fontSize: 84.0 * s, fontWeight: 900, lineHeight: 1.02, textTransform: 'uppercase'}}>{p.line1}</div></Reveal>
        {p.line2 ? <Reveal at={0.9}><div style={{fontSize: 84.0 * s, fontWeight: 900, lineHeight: 1.02, color: C.red, textTransform: 'uppercase'}}>{p.line2}</div></Reveal> : null}
        {p.footnote ? <Reveal at={1.5}><div style={{fontSize: 22 * s, letterSpacing: 2.5 * s, color: C.dim, marginTop: 34 * s, textTransform: 'uppercase'}}>{p.footnote}</div></Reveal> : null}
      </AbsoluteFill>
    </DocuFrame>
  );
};

/* ------------------------------------------------------------------ Impact radius (top-down) */
export type RadiusProps = DocuProps & {
  rings: {km: number; label: string; detail?: string; color?: string; at?: number}[];
  centerLabel?: string;
};

export const Radius: React.FC<RadiusProps> = (p) => {
  const {t, dur, s} = useT();
  const maxKm = Math.max(...p.rings.map((r) => r.km));
  const scale = (330 * s) / maxKm;
  const cx = 860 * s, cy = 560 * s;
  const palette = [C.red, C.amber, '#e8d36a', C.teal];
  return (
    <DocuFrame {...p} defaultBackdrop="dark">
      <svg width={1920 * s} height={1080 * s} style={{position: 'absolute'}}>
        {/* faint terrain lines */}
        {Array.from({length: 14}).map((_, i) => (
          <path key={i} d={`M0,${120 * s + i * 70 * s} C${500 * s},${80 * s + i * 72 * s} ${1300 * s},${170 * s + i * 66 * s} ${1920 * s},${110 * s + i * 70 * s}`} stroke="#fff" strokeOpacity={0.035} fill="none" strokeWidth={2 * s} />
        ))}
        {[...p.rings].sort((a, b) => b.km - a.km).map((r, i) => {
          const at = r.at ?? stagger(p.rings.indexOf(r), p.rings.length, dur, 0.6, 0.6);
          const k = prog(t, at, 1.0, Easing.out(Easing.exp));
          const col = r.color ?? palette[p.rings.indexOf(r) % palette.length];
          return (
            <g key={i} opacity={k > 0 ? 1 : 0}>
              <circle cx={cx} cy={cy} r={r.km * scale * k} fill={col} fillOpacity={0.12} stroke={col} strokeWidth={2.5 * s} />
              <text x={cx + r.km * scale * k * 0.71 + 8 * s} y={cy - r.km * scale * k * 0.71} fill={col} fontFamily={F.mono} fontSize={22 * s} opacity={k}>{`${r.km} KM`}</text>
            </g>
          );
        })}
        <circle cx={cx} cy={cy} r={7 * s} fill="#fff" />
        {p.centerLabel ? <text x={cx + 14 * s} y={cy + 26 * s} fill={C.text} fontFamily={F.sans} fontWeight={700} fontSize={21 * s} letterSpacing={2 * s}>{p.centerLabel.toUpperCase()}</text> : null}
      </svg>
      <div style={{position: 'absolute', right: 110 * s, top: 320 * s, width: 420 * s, background: C.panel, borderLeft: `${3 * s}px solid ${C.faint}`, padding: `${16 * s}px ${22 * s}px`}}>
        {p.rings.map((r, i) => (
          <Reveal key={i} at={(r.at ?? stagger(i, p.rings.length, dur, 0.6, 0.6)) + 0.3} y={8}>
            <div style={{display: 'flex', gap: 14 * s, alignItems: 'baseline', padding: `${6 * s}px 0`}}>
              <span style={{width: 12 * s, height: 12 * s, background: r.color ?? palette[i % palette.length], display: 'inline-block'}} />
              <span style={{fontFamily: F.mono, fontSize: 21 * s, color: C.dim, width: 70 * s}}>{r.km} km</span>
              <span style={{fontSize: 24 * s, fontWeight: 700}}>{r.label}{r.detail ? <span style={{color: C.dim, fontWeight: 400}}> · {r.detail}</span> : null}</span>
            </div>
          </Reveal>
        ))}
      </div>
    </DocuFrame>
  );
};
