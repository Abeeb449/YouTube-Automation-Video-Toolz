import React from 'react';
import {AbsoluteFill, Easing, interpolate} from 'remotion';
import {C, DocuFrame, DocuProps, F, HorizonSky, prog, Reveal, useT} from './kit';

export type HorizonEvent = {
  type: 'flash' | 'fireball' | 'shockwave' | 'mushroom' | 'sun';
  at?: number;
  /** Horizontal position 0..1 */
  x?: number;
  size?: number;
};

export type HorizonProps = DocuProps & {
  mood?: 'dusk' | 'night' | 'grey';
  /** Big establishing title, e.g. "CENTRAL UKRAINE". */
  title?: string;
  subtitle?: string;
  titleAt?: number;
  events?: HorizonEvent[];
  /** Vertical scale bar on the right (e.g. ["0 KM","5 KM","10 KM"]). */
  ruler?: string[];
  /** Small silhouettes on the horizon (buildings/aircraft). */
  silhouettes?: boolean;
};

const HY = 0.66;

const Glow: React.FC<{x: number; y: number; r: number; core: string; halo: string; opacity?: number}> = ({x, y, r, core, halo, opacity = 1}) => (
  <div style={{position: 'absolute', left: x - r, top: y - r, width: r * 2, height: r * 2, borderRadius: '50%', opacity,
    background: `radial-gradient(circle, ${core} 0%, ${core} 22%, ${halo} 48%, rgba(0,0,0,0) 72%)`}} />
);

export const Horizon: React.FC<HorizonProps> = (p) => {
  const {t, dur, s, width, height} = useT();
  const hy = height * HY;
  const drift = interpolate(t, [0, dur], [0, -30 * s]);
  return (
    <DocuFrame {...p} backdrop="none">
      <AbsoluteFill style={{transform: `scale(${1 + 0.04 * (t / Math.max(1, dur))})`}}>
        <HorizonSky mood={p.mood ?? 'dusk'} horizonY={HY} />
        {p.silhouettes !== false ? (
          <svg width={width} height={height} style={{position: 'absolute'}}>
            {Array.from({length: 18}).map((_, i) => {
              const x = ((i * 337) % 100) / 100 * width + drift;
              const w = (20 + (i * 53) % 60) * s, h = (6 + (i * 17) % 18) * s;
              return <rect key={i} x={x} y={hy - h} width={w} height={h} fill="#0c0b0a" opacity={0.85} />;
            })}
          </svg>
        ) : null}
        {(p.events ?? []).map((ev, i) => {
          const at = ev.at ?? dur * 0.3;
          const x = (ev.x ?? 0.5) * width;
          const k = t - at;
          if (k < 0) return null;
          const size = (ev.size ?? 1) * s;
          if (ev.type === 'sun') return <Glow key={i} x={x} y={height * 0.22} r={110 * size} core="#fffbe8" halo="rgba(255,240,200,0.35)" />;
          if (ev.type === 'flash') {
            const o = interpolate(k, [0, 0.08, 1.6], [0, 1, 0], {extrapolateRight: 'clamp'});
            return <AbsoluteFill key={i} style={{background: '#fff', opacity: o}} />;
          }
          if (ev.type === 'fireball') {
            const g = interpolate(k, [0, 2.5, 8], [0.15, 0.8, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
            const rise = interpolate(k, [0, 8], [0, 90 * size], {extrapolateRight: 'clamp'});
            return (
              <React.Fragment key={i}>
                <Glow x={x} y={hy - 40 * size - rise} r={170 * size * g} core="#fff6d8" halo="rgba(255,150,60,0.55)" />
                <div style={{position: 'absolute', left: x - 260 * size * g, top: hy - 8 * size, width: 520 * size * g, height: 18 * size, borderRadius: '50%',
                  background: 'radial-gradient(ellipse, rgba(255,140,60,0.9), rgba(255,90,30,0) 70%)'}} />
              </React.Fragment>
            );
          }
          if (ev.type === 'shockwave') {
            const r = interpolate(k, [0, 4], [20 * size, 520 * size], {extrapolateRight: 'clamp', easing: Easing.out(Easing.quad)});
            const o = interpolate(k, [0, 3, 4.5], [0.9, 0.5, 0], {extrapolateRight: 'clamp'});
            return (
              <div key={i} style={{position: 'absolute', left: x - r, top: hy - r, width: r * 2, height: r, borderRadius: `${r}px ${r}px 0 0`,
                border: `${3 * s}px solid rgba(255,230,200,${o})`, borderBottom: 'none', background: `rgba(255,220,180,${o * 0.12})`}} />
            );
          }
          // mushroom cloud: stem + layered cap of blurred puffs, rising and spreading
          const g = interpolate(k, [0, 10], [0, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
          const capY = hy - 60 * size - 380 * size * g;
          const capW = 140 * size + 260 * size * g;
          return (
            <div key={i} style={{position: 'absolute', left: 0, top: 0, width, height, filter: `blur(${3 * s}px)`}}>
              <div style={{position: 'absolute', left: x - (22 + 30 * g) * size, top: capY + 40 * size, width: (44 + 60 * g) * size, height: hy - capY - 40 * size,
                background: 'linear-gradient(180deg, rgba(222,140,110,0.85), rgba(150,90,80,0.7))', borderRadius: `${30 * size}px`}} />
              {[-0.5, -0.2, 0.15, 0.45, 0].map((o, j) => (
                <div key={j} style={{position: 'absolute', left: x + o * capW - capW * 0.4, top: capY - (j === 4 ? 40 : 0) * size * g, width: capW * 0.8, height: capW * 0.45,
                  borderRadius: '50%', background: `radial-gradient(ellipse, rgba(240,${150 - j * 12},${110 - j * 8},0.95), rgba(160,90,80,0.55) 60%, rgba(0,0,0,0) 75%)`}} />
              ))}
              <div style={{position: 'absolute', left: x - capW * 1.1, top: hy - 30 * size, width: capW * 2.2, height: 60 * size, borderRadius: '50%',
                background: 'radial-gradient(ellipse, rgba(200,130,100,0.6), rgba(0,0,0,0) 70%)'}} />
            </div>
          );
        })}
      </AbsoluteFill>
      {p.ruler && p.ruler.length > 1 ? (
        <div style={{position: 'absolute', right: 260 * s, top: hy - 520 * s, height: 520 * s, borderLeft: `${2 * s}px solid rgba(255,255,255,0.6)`, opacity: prog(t, 1, 0.6)}}>
          {p.ruler.map((r, i) => (
            <div key={i} style={{position: 'absolute', bottom: `${(i / (p.ruler!.length - 1)) * 100}%`, left: 0, display: 'flex', alignItems: 'center', gap: 8 * s, transform: 'translateY(50%)'}}>
              <div style={{width: 14 * s, height: 2 * s, background: 'rgba(255,255,255,0.7)'}} />
              <span style={{fontFamily: F.mono, fontSize: 20 * s, color: C.text}}>{r}</span>
            </div>
          ))}
        </div>
      ) : null}
      {p.title ? (
        <div style={{position: 'absolute', left: 110 * s, top: height * 0.52}}>
          <Reveal at={p.titleAt ?? 0.6} d={1.2} y={0}>
            <div style={{fontSize: 92.0 * s, fontWeight: 800, letterSpacing: 8 * s, textShadow: '0 6px 40px rgba(0,0,0,0.5)'}}>{p.title.toUpperCase()}</div>
          </Reveal>
          {p.subtitle ? (
            <Reveal at={(p.titleAt ?? 0.6) + 0.7}>
              <div style={{fontSize: 23 * s, color: C.amber, letterSpacing: 3 * s, fontWeight: 700, textTransform: 'uppercase', marginTop: 4 * s}}>{p.subtitle}</div>
            </Reveal>
          ) : null}
        </div>
      ) : null}
    </DocuFrame>
  );
};
