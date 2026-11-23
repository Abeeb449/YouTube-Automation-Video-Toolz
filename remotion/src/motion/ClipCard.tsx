/**
 * ClipCard — a "source clipping": a paper card with the key lines of a study or article, slightly rotated with a
 * shadow; a marker highlight sweeps over the key phrase exactly when it is spoken; "SOURCE:" label in the corner.
 *   publication, title, date?, lines: [string], highlight: {text, at}, source
 *
 * DateStamp — a big date / time / place card typed on with a caret (pair with sfx: ticks).
 *   date, time?, place?, at?
 */
import React from 'react';
import {AbsoluteFill, Easing, interpolate} from 'remotion';
import {BackdropLayer, Backdrop, C, F, prog, useT} from '../docu/kit';
import {FilmGrain, LightLeak, Marker, TypeOn, Vignette} from './fx';

export type ClipCardProps = {
  publication?: string;
  title?: string;
  date?: string;
  lines: string[];
  highlight?: {text: string; at?: number}[] | {text: string; at?: number};
  source?: string;
  backdrop?: Backdrop;
};

export const ClipCard: React.FC<ClipCardProps> = (p) => {
  const {t, dur, s} = useT();
  const inn = prog(t, 0, 0.9, Easing.out(Easing.back(1.2)));
  const push = interpolate(t, [0, dur], [1, 1.09]);
  const hl = Array.isArray(p.highlight) ? p.highlight : p.highlight ? [p.highlight] : [];
  const renderLine = (line: string, i: number) => {
    for (const h of hl) {
      const k = line.indexOf(h.text);
      if (k >= 0) {
        return (
          <p key={i} style={{margin: `0 0 ${14 * s}px`}}>
            {line.slice(0, k)}<Marker at={h.at ?? 1.2}>{h.text}</Marker>{line.slice(k + h.text.length)}
          </p>
        );
      }
    }
    return <p key={i} style={{margin: `0 0 ${14 * s}px`}}>{line}</p>;
  };
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <BackdropLayer kind={p.backdrop ?? 'dark'} />
      <AbsoluteFill style={{display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        <div style={{width: 1180 * s, background: '#f3efe4', color: '#1d1d1d', padding: `${54 * s}px ${70 * s}px`, fontFamily: F.serif,
          transform: `perspective(${1800 * s}px) rotateX(${(1 - inn) * 14 + Math.sin(t * 0.3) * 1.5}deg) rotateY(${Math.cos(t * 0.25) * 2.5}deg) rotate(${-1.6 + (1 - inn) * 5}deg) scale(${push * (0.92 + 0.08 * inn)}) translateY(${(1 - inn) * 80 * s}px)`,
          opacity: inn, boxShadow: `0 ${34 * s}px ${70 * s}px rgba(0,0,0,0.6)`,
          backgroundImage: 'radial-gradient(ellipse at 30% 20%, rgba(255,255,255,0.5), rgba(0,0,0,0) 60%), repeating-linear-gradient(0deg, rgba(0,0,0,0.018) 0 2px, rgba(0,0,0,0) 2px 4px)'}}>
          {p.publication ? (
            <div style={{fontFamily: F.sans, fontSize: 22 * s, letterSpacing: 4 * s, textTransform: 'uppercase', color: '#6b5f4a', borderBottom: `${2 * s}px solid #1d1d1d`,
              paddingBottom: 10 * s, marginBottom: 22 * s, display: 'flex', justifyContent: 'space-between'}}>
              <span>{p.publication}</span><span>{p.date ?? ''}</span>
            </div>
          ) : null}
          {p.title ? <div style={{fontSize: 52 * s, fontWeight: 700, lineHeight: 1.12, marginBottom: 26 * s}}>{p.title}</div> : null}
          <div style={{fontSize: 34 * s, lineHeight: 1.45}}>{p.lines.map(renderLine)}</div>
        </div>
      </AbsoluteFill>
      {p.source ? (
        <div style={{position: 'absolute', right: 52 * s, bottom: 40 * s, fontFamily: F.sans, fontSize: 21 * s, color: C.dim, letterSpacing: 1 * s,
          background: 'rgba(0,0,0,0.45)', padding: `${6 * s}px ${14 * s}px`, opacity: prog(t, 0.8, 0.5)}}>SOURCE: {p.source}</div>
      ) : null}
      <LightLeak at={0.1} d={1.4} />
      <Vignette strength={0.55} />
      <FilmGrain opacity={0.07} />
    </AbsoluteFill>
  );
};

export type DateStampProps = {date: string; time?: string; place?: string; at?: number; backdrop?: Backdrop};

export const DateStamp: React.FC<DateStampProps> = (p) => {
  const {t, dur, s} = useT();
  const at = p.at ?? 0.3;
  const push = interpolate(t, [0, dur], [1, 1.06]);
  const line = prog(t, at - 0.2, 0.6, Easing.inOut(Easing.cubic));
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <BackdropLayer kind={p.backdrop ?? 'abyss'} />
      <AbsoluteFill style={{display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', transform: `scale(${push})`}}>
        {p.place ? (
          <div style={{fontFamily: F.sans, fontSize: 30 * s, color: C.teal, letterSpacing: 6 * s, textTransform: 'uppercase', marginBottom: 18 * s, opacity: prog(t, at, 0.5)}}>
            {p.place}
          </div>
        ) : null}
        <div style={{fontFamily: F.mono, fontWeight: 700, fontSize: 132 * s, color: C.text, letterSpacing: 6 * s, textShadow: '0 4px 30px rgba(0,0,0,0.6)'}}>
          <TypeOn text={p.date} at={at} cps={12} />
        </div>
        <div style={{width: 760 * s * line, height: 3 * s, background: C.red, margin: `${18 * s}px 0`}} />
        {p.time ? (
          <div style={{fontFamily: F.mono, fontSize: 54 * s, color: C.amber, letterSpacing: 4 * s}}>
            <TypeOn text={p.time} at={at + p.date.length / 12 + 0.2} cps={12} />
          </div>
        ) : null}
      </AbsoluteFill>
      <Vignette strength={0.6} />
      <FilmGrain opacity={0.06} />
    </AbsoluteFill>
  );
};
