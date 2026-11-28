/* The video's thumbnail (1280x720 still): big 3D animals on a bright backdrop, a short headline in heavy type with
   one highlighted word, and optionally a label, an arrow and a ring that point at the detail the video is about.
   Everything is placed in fractions of the frame (x, y = centre; w = width), so a design reads the same at any size. */
import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Img, continueRender, delayRender, staticFile} from 'remotion';

export type ThumbActor = {
  creature?: string; view?: string; frame?: number; image?: string;
  x: number; y: number; w: number; flip?: boolean; rotate?: number;
  glow?: string; dim?: number; blur?: number; opacity?: number;
  clip?: {x: number; y: number; rx: number; ry: number};   // show only this oval of the picture (fractions of it)
  blend?: string;                                          // CSS mix-blend-mode
};
export type ThumbProps = {
  headline: string;            // lines separated by "|": "ONLY THE|LIVER"
  accent?: string;             // the word(s) drawn in the accent colour
  kicker?: string;             // small label above the headline
  side?: 'left' | 'right';     // where the words sit
  actors?: ThumbActor[];
  backdrop?: 'sea' | 'deep' | 'shore' | 'night' | 'land';
  photo?: string;              // a background picture instead of the drawn backdrop
  arrow?: {from: [number, number]; to: [number, number]; bend?: number};
  ring?: {x: number; y: number; rx: number; ry?: number};
  accentColor?: string; kickerColor?: string; size?: number; tilt?: number; textWidth?: number;
};

const BACK: Record<string, {top: string; mid: string; low: string; glow: string}> = {
  sea: {top: '#3fd3ea', mid: '#0f86b8', low: '#052a47', glow: 'rgba(255,255,255,0.55)'},
  deep: {top: '#1689b5', mid: '#0a4a78', low: '#03162b', glow: 'rgba(170,235,255,0.40)'},
  shore: {top: '#ffd58a', mid: '#3aa6c4', low: '#06324f', glow: 'rgba(255,244,214,0.60)'},
  night: {top: '#27406b', mid: '#111f3d', low: '#04070f', glow: 'rgba(160,190,255,0.30)'},
  land: {top: '#ffcf7a', mid: '#c9743a', low: '#3a1c12', glow: 'rgba(255,240,200,0.55)'},
};

const useFont = () => {
  const [handle] = useState(() => delayRender('thumbnail font'));
  useEffect(() => {
    const face = new FontFace('Anton', `url(${staticFile('fonts/anton.woff2')})`);
    face.load().then((f) => { (document as any).fonts.add(f); continueRender(handle); }).catch(() => continueRender(handle));
  }, [handle]);
};

export const Thumbnail: React.FC<ThumbProps> = (p) => {
  useFont();
  const W = 1280, H = 720;
  const side = p.side ?? 'left';
  const back = BACK[p.backdrop ?? 'sea'] ?? BACK.sea;
  const accent = p.accentColor ?? '#ffd400';
  const lines = String(p.headline || '').toUpperCase().split('|').map((s) => s.trim()).filter(Boolean);
  const accents = String(p.accent || '').toUpperCase().split(/[\s|]+/).filter(Boolean);
  const boxW = W * (p.textWidth ?? 0.5);
  const longest = Math.max(1, ...lines.map((l) => l.length));
  // Anton: a capital is about 0.46 em wide, a space 0.22 em
  const fit = (boxW - 40) / (longest * 0.47);
  const size = Math.min(p.size ?? 230, fit, (H * 0.74) / Math.max(1, lines.length) / 1.02);
  const lineH = size * 1.04;
  const blockH = lines.length * lineH;
  const textX = side === 'left' ? 46 : W - 46;
  const anchor = side === 'left' ? 'start' : 'end';
  const top = (H - blockH) / 2 + (p.kicker ? 34 : 0);
  const tilt = p.tilt ?? -2.5;
  const rays = [-26, -12, 3, 17, 30];
  return (
    <AbsoluteFill style={{backgroundColor: back.low, overflow: 'hidden'}}>
      {/* backdrop */}
      {p.photo ? (
        <Img src={staticFile(p.photo)} style={{position: 'absolute', width: W, height: H, objectFit: 'cover', filter: 'saturate(1.25) contrast(1.1)'}} />
      ) : (
        <>
          <AbsoluteFill style={{background: `linear-gradient(180deg, ${back.top} 0%, ${back.mid} 42%, ${back.low} 100%)`}} />
          <AbsoluteFill style={{background: `radial-gradient(ellipse 70% 60% at ${side === 'left' ? 68 : 32}% -8%, ${back.glow} 0%, rgba(255,255,255,0) 70%)`}} />
          {rays.map((deg, i) => (
            <div key={i} style={{position: 'absolute', left: (side === 'left' ? 0.68 : 0.32) * W - 70, top: -140, width: 140, height: H * 1.5,
              transformOrigin: '50% 0%', transform: `rotate(${deg}deg)`, filter: 'blur(26px)',
              background: `linear-gradient(180deg, rgba(255,255,255,${0.30 - Math.abs(deg) * 0.004}) 0%, rgba(255,255,255,0) 82%)`}} />
          ))}
        </>
      )}
      {/* a darker bed behind the words, so they read at phone size */}
      <AbsoluteFill style={{background: side === 'left'
        ? 'linear-gradient(90deg, rgba(2,14,28,0.78) 0%, rgba(2,14,28,0.45) 34%, rgba(2,14,28,0) 58%)'
        : 'linear-gradient(270deg, rgba(2,14,28,0.78) 0%, rgba(2,14,28,0.45) 34%, rgba(2,14,28,0) 58%)'}} />
      <AbsoluteFill style={{background: 'radial-gradient(ellipse 120% 110% at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,6,16,0.62) 100%)'}} />
      {/* the animals */}
      {(p.actors ?? []).map((a, i) => {
        const file = a.image ?? `sprites/${a.creature}/${a.view ?? 'side'}/${String(a.frame ?? 12).padStart(4, '0')}.webp`;
        const w = a.w * W;
        const fx = [`drop-shadow(0 ${Math.round(w * 0.02)}px ${Math.round(w * 0.035)}px rgba(0,8,20,0.6))`];
        if (a.glow) fx.push(`drop-shadow(0 0 ${Math.round(w * 0.05)}px ${a.glow})`);
        fx.push(`saturate(${a.dim ? 0.9 : 1.18})`, `contrast(1.1)`, `brightness(${a.dim ? 1 - a.dim : 1.06})`);
        if (a.blur) fx.push(`blur(${a.blur}px)`);
        return (
          <Img key={i} src={staticFile(file)} style={{position: 'absolute', left: a.x * W - w / 2, top: a.y * H - w / 4, width: w, height: w / 2,
            objectFit: 'contain', opacity: a.opacity ?? 1, filter: fx.join(' '), mixBlendMode: (a.blend ?? 'normal') as any,
            clipPath: a.clip ? `ellipse(${a.clip.rx * 100}% ${a.clip.ry * 100}% at ${a.clip.x * 100}% ${a.clip.y * 100}%)` : undefined,
            transform: `${a.flip ? 'scaleX(-1) ' : ''}rotate(${a.rotate ?? 0}deg)`}} />
        );
      })}
      {/* ring and arrow */}
      <svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0}}>
        {p.ring ? (
          <g>
            <ellipse cx={p.ring.x * W} cy={p.ring.y * H} rx={p.ring.rx * W} ry={(p.ring.ry ?? p.ring.rx) * W} fill="none" stroke="#000" strokeWidth={22} />
            <ellipse cx={p.ring.x * W} cy={p.ring.y * H} rx={p.ring.rx * W} ry={(p.ring.ry ?? p.ring.rx) * W} fill="none" stroke={accent} strokeWidth={11} />
          </g>
        ) : null}
        {p.arrow ? (() => {
          const [x1, y1] = [p.arrow.from[0] * W, p.arrow.from[1] * H];
          const [x2, y2] = [p.arrow.to[0] * W, p.arrow.to[1] * H];
          const mx = (x1 + x2) / 2, my = (y1 + y2) / 2, dx = x2 - x1, dy = y2 - y1;
          const len = Math.hypot(dx, dy) || 1, bend = (p.arrow.bend ?? 0.22) * len;
          const cx = mx - (dy / len) * bend, cy = my + (dx / len) * bend;
          const ang = Math.atan2(y2 - cy, x2 - cx);
          const head = 46, bx = x2 - Math.cos(ang) * head, by = y2 - Math.sin(ang) * head;
          const px = Math.cos(ang + Math.PI / 2) * head * 0.62, py = Math.sin(ang + Math.PI / 2) * head * 0.62;
          const d = `M ${x1} ${y1} Q ${cx} ${cy} ${bx} ${by}`;
          const tri = `${x2},${y2} ${bx + px},${by + py} ${bx - px},${by - py}`;
          return (
            <g strokeLinecap="round" strokeLinejoin="round">
              <path d={d} fill="none" stroke="#000" strokeWidth={34} />
              <polygon points={tri} fill="#000" stroke="#000" strokeWidth={20} />
              <path d={d} fill="none" stroke={accent} strokeWidth={18} />
              <polygon points={tri} fill={accent} stroke={accent} strokeWidth={4} />
            </g>
          );
        })() : null}
      </svg>
      {/* the words */}
      <svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0, transform: `rotate(${tilt}deg)`, transformOrigin: side === 'left' ? '0% 50%' : '100% 50%'}}>
        {p.kicker ? (() => {
          const ks = Math.max(34, size * 0.26), kw = String(p.kicker).length * ks * 0.5 + 44;
          const kx = side === 'left' ? textX : textX - kw;
          return (
            <g>
              <rect x={kx} y={top - ks * 1.55} width={kw} height={ks * 1.32} rx={8} fill={p.kickerColor ?? '#e5262b'} stroke="#000" strokeWidth={5} />
              <text x={kx + kw / 2} y={top - ks * 0.56} textAnchor="middle" fontFamily="Anton, Inter, sans-serif" fontSize={ks} fill="#fff" letterSpacing={1.5}>{String(p.kicker).toUpperCase()}</text>
            </g>
          );
        })() : null}
        {lines.map((line, li) => {
          const y = top + (li + 0.86) * lineH;
          const words = line.split(/\s+/);
          const spans = words.map((w, wi) => (
            <tspan key={wi} fill={accents.includes(w.replace(/[^A-Z0-9]/g, '')) ? accent : '#ffffff'}>{(wi ? ' ' : '') + w}</tspan>
          ));
          const base = {x: textX, y, textAnchor: anchor as any, fontFamily: 'Anton, Inter, sans-serif', fontSize: size, letterSpacing: 1};
          return (
            <g key={li}>
              <text {...base} fill="#000" stroke="#000" strokeWidth={size * 0.2} strokeLinejoin="round" transform={`translate(0 ${size * 0.05})`} opacity={0.55}>{line}</text>
              <text {...base} fill="#000" stroke="#000" strokeWidth={size * 0.13} strokeLinejoin="round">{line}</text>
              <text {...base}>{spans}</text>
            </g>
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};
