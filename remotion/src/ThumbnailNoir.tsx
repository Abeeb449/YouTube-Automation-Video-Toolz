/* Thumbnail, "noir" look (1280x720 still): a black frame, one or two real animals cut out of their photos in high
   contrast black and white, and two to four huge words in white with one in colour. Nothing else, except, when a
   design asks for them: a curved arrow, a small label, a bar beside the words, a stroke under them, or a real photo
   on one side fading into the black.
   Colours: scheme "red" (white + red, the look of the reference thumbnails) or "brand" (the channel's colours:
   white over a yellow that runs into orange). Positions are fractions of the frame; x, y are centres. */
import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Img, continueRender, delayRender, staticFile} from 'remotion';

type Pic = {image: string; x: number; y: number; w: number; flip?: boolean; rotate?: number; opacity?: number; rim?: number;
  fade?: [number, number]};   // the picture comes out of the black: invisible up to the first fraction of its width, whole from the second
type Scheme = {white: string; accent: string; accent2?: string; tagText?: string};
export type NoirProps = {
  headline: string;                   // lines separated by "|"
  accent?: string;                    // the words drawn in the accent colour ("LIVER", or "GREAT WHITES")
  scheme?: 'red' | 'brand' | Scheme;
  text?: {at?: 'left' | 'right' | 'top' | 'top-left'; width?: number; maxSize?: number; font?: 'wide' | 'condensed';
          italic?: boolean; x?: number; y?: number; lineGap?: number};
  images?: Pic[];
  photo?: {image: string; side?: 'left' | 'right'; width?: number; brightness?: number};
  spot?: {x: number; y: number; r: number; strength?: number};   // a faint light on the black behind the animal
  arrow?: {from: [number, number]; to: [number, number]; bend?: number};
  tag?: string;
  bar?: boolean;
  stroke?: boolean;
  dust?: boolean;
};

const SCHEMES: Record<string, Scheme> = {
  red: {white: '#ffffff', accent: '#ff2323', tagText: '#ffffff'},
  brand: {white: '#f7f7f8', accent: '#fde302', accent2: '#fb9002', tagText: '#000000'},
};
const FONTS = [
  ['Montserrat', '900', 'normal', 'fonts/montserrat-900.woff2'],
  ['Montserrat', '900', 'italic', 'fonts/montserrat-900-italic.woff2'],
  ['Montserrat', '800', 'normal', 'fonts/montserrat-800.woff2'],
  ['Anton', '400', 'normal', 'fonts/anton.woff2'],
] as const;

const rand = (seed: number) => () => {
  seed = (seed * 1664525 + 1013904223) % 4294967296;
  return seed / 4294967296;
};

export const ThumbnailNoir: React.FC<NoirProps> = (p) => {
  const W = 1280, H = 720;
  const scheme: Scheme = typeof p.scheme === 'object' ? p.scheme : SCHEMES[p.scheme ?? 'red'] ?? SCHEMES.red;
  const t = p.text ?? {};
  const at = t.at ?? 'left';
  const condensed = t.font === 'condensed';
  const family = condensed ? 'Anton' : 'Montserrat';
  const weight = condensed ? '400' : '900';
  const style = t.italic && !condensed ? 'italic' : 'normal';
  const lines = String(p.headline || '').toUpperCase().split('|').map((s) => s.trim()).filter(Boolean);
  const accents = String(p.accent || '').toUpperCase().split(/[\s|]+/).filter(Boolean).map((w) => w.replace(/[^A-Z0-9]/g, ''));
  const boxW = W * (t.width ?? (at === 'top' || at === 'top-left' ? 0.92 : 0.5));
  const gap = t.lineGap ?? (condensed ? 1.06 : 1.0);

  // the words are measured with the real font, then sized to fill their box
  const [size, setSize] = useState<number | null>(null);
  const [handle] = useState(() => delayRender('thumbnail fonts'));
  useEffect(() => {
    Promise.all(FONTS.map(([fam, wt, st, file]) => new FontFace(fam, `url(${staticFile(file)})`, {weight: wt, style: st}).load()
      .then((f) => (document as any).fonts.add(f)).catch(() => null)))
      .then(() => {
        const ctx = document.createElement('canvas').getContext('2d')!;
        ctx.font = `${style} ${weight} 100px ${family}`;
        const widest = Math.max(1, ...lines.map((l) => ctx.measureText(l).width + (condensed ? l.length * 1 : 0)));
        const maxH = at === 'top' || at === 'top-left' ? H * 0.30 : H * 0.80;
        const s = Math.min(t.maxSize ?? 400, (boxW / widest) * 100, maxH / (lines.length * gap));
        setSize(s);
        continueRender(handle);
      });
  }, [handle]);

  const sz = size ?? 100;
  const lineH = sz * gap;
  const blockH = lines.length * lineH;
  const pad = W * 0.045;
  const anchor = at === 'right' ? 'end' : at === 'top' ? 'middle' : 'start';
  const tx = t.x !== undefined ? t.x * W : at === 'right' ? W - pad : at === 'top' ? W / 2 : pad + (p.bar ? 26 : 0);
  const top = t.y !== undefined ? t.y * H - blockH / 2
    : at === 'top' || at === 'top-left' ? H * 0.055 + (p.tag ? 52 : 0)
    : (H - blockH) / 2 + (p.tag ? 26 : 0);
  // capitals sit on the baseline and are about 0.7 em tall (Montserrat) or 0.86 em (Anton)
  const cap = condensed ? 0.86 : 0.70;
  const baseline = (i: number) => top + i * lineH + (lineH - sz * cap) / 2 + sz * cap;
  const dots = (() => {
    const r = rand(7);
    return Array.from({length: 240}, () => ({x: r() * W, y: r() * H, s: 0.6 + r() * 1.6, o: 0.10 + r() * 0.45}));
  })();
  const photoSide = p.photo?.side ?? 'left';
  const photoW = (p.photo?.width ?? 0.66) * W;

  return (
    <AbsoluteFill style={{backgroundColor: '#000', overflow: 'hidden'}}>
      {p.spot ? (
        <AbsoluteFill style={{background: `radial-gradient(circle ${p.spot.r * W}px at ${p.spot.x * 100}% ${p.spot.y * 100}%, rgba(255,255,255,${p.spot.strength ?? 0.10}) 0%, rgba(255,255,255,0) 100%)`}} />
      ) : null}
      {p.photo ? (
        <Img src={staticFile(p.photo.image)} style={{position: 'absolute', top: 0, [photoSide]: 0, width: photoW, height: H, objectFit: 'cover',
          filter: `brightness(${p.photo.brightness ?? 0.95}) contrast(1.08)`,
          WebkitMaskImage: `linear-gradient(${photoSide === 'left' ? 90 : 270}deg, #000 0%, #000 52%, rgba(0,0,0,0) 100%)`,
          maskImage: `linear-gradient(${photoSide === 'left' ? 90 : 270}deg, #000 0%, #000 52%, rgba(0,0,0,0) 100%)`} as any} />
      ) : null}
      {(p.dust ?? true) ? (
        <svg width={W} height={H} style={{position: 'absolute'}}>
          {dots.map((d, i) => <circle key={i} cx={d.x} cy={d.y} r={d.s} fill="#fff" opacity={d.o} />)}
        </svg>
      ) : null}
      {(p.images ?? []).map((a, i) => (
        <Img key={i} src={staticFile(a.image)} style={{position: 'absolute', left: a.x * W, top: a.y * H, width: a.w * W, height: 'auto',
          opacity: a.opacity ?? 1,
          WebkitMaskImage: a.fade ? `linear-gradient(90deg, rgba(0,0,0,0) ${a.fade[0] * 100}%, #000 ${a.fade[1] * 100}%)` : undefined,
          maskImage: a.fade ? `linear-gradient(90deg, rgba(0,0,0,0) ${a.fade[0] * 100}%, #000 ${a.fade[1] * 100}%)` : undefined,
          filter: `drop-shadow(0 0 ${Math.round((a.rim ?? 1) * 2)}px rgba(255,255,255,${0.22 * (a.rim ?? 1)})) drop-shadow(0 0 28px rgba(255,255,255,${0.07 * (a.rim ?? 1)}))`,
          transform: `translate(-50%, -50%) ${a.flip ? 'scaleX(-1) ' : ''}rotate(${a.rotate ?? 0}deg)`}} />
      ))}
      <svg width={W} height={H} style={{position: 'absolute', left: 0, top: 0, visibility: size ? 'visible' : 'hidden'}}>
        <defs>
          <linearGradient id="acc" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={scheme.accent} />
            <stop offset="100%" stopColor={scheme.accent2 ?? scheme.accent} />
          </linearGradient>
          <filter id="bed" x="-10%" y="-20%" width="120%" height="140%">
            <feGaussianBlur stdDeviation="16" />
          </filter>
        </defs>
        {p.arrow ? (() => {
          const [x1, y1] = [p.arrow.from[0] * W, p.arrow.from[1] * H];
          const [x2, y2] = [p.arrow.to[0] * W, p.arrow.to[1] * H];
          const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1, bend = (p.arrow.bend ?? 0.3) * len;
          const cx = (x1 + x2) / 2 - (dy / len) * bend, cy = (y1 + y2) / 2 + (dx / len) * bend;
          const ang = Math.atan2(y2 - cy, x2 - cx), head = 44;
          const bx = x2 - Math.cos(ang) * head * 0.9, by = y2 - Math.sin(ang) * head * 0.9;
          const px = Math.cos(ang + Math.PI / 2) * head * 0.55, py = Math.sin(ang + Math.PI / 2) * head * 0.55;
          return (
            <g strokeLinecap="round" strokeLinejoin="round">
              <path d={`M ${x1} ${y1} Q ${cx} ${cy} ${bx} ${by}`} fill="none" stroke={scheme.accent} strokeWidth={13} />
              <polygon points={`${x2},${y2} ${bx + px},${by + py} ${bx - px},${by - py}`} fill={scheme.accent} stroke={scheme.accent} strokeWidth={6} />
            </g>
          );
        })() : null}
        {p.tag ? (() => {
          const ts = 30, tw = String(p.tag).length * ts * 0.72 + 30;
          const x = at === 'right' ? W - pad - tw : at === 'top' ? (W - tw) / 2 : pad;
          const y = at === 'top' || at === 'top-left' ? H * 0.055 : top - 66;
          return (
            <g>
              <rect x={x} y={y} width={tw} height={ts * 1.5} fill={scheme.accent2 ?? scheme.accent} />
              <text x={x + tw / 2} y={y + ts * 1.1} textAnchor="middle" fontFamily="Montserrat" fontWeight={800} fontSize={ts} letterSpacing={1.5}
                fill={scheme.tagText ?? '#fff'}>{String(p.tag).toUpperCase()}</text>
            </g>
          );
        })() : null}
        {p.bar ? <rect x={pad} y={top + lineH * 0.06} width={11} height={blockH - lineH * 0.12} fill="url(#acc)" /> : null}
        {/* a soft black bed under the words, so they stay clean where they cross the animal */}
        <g filter="url(#bed)" opacity={0.85}>
          {lines.map((line, i) => (
            <text key={i} x={tx} y={baseline(i)} textAnchor={anchor} fontFamily={family} fontWeight={weight} fontStyle={style} fontSize={sz}
              letterSpacing={condensed ? 1 : -sz * 0.012} fill="#000" stroke="#000" strokeWidth={sz * 0.22}>{line}</text>
          ))}
        </g>
        {lines.map((line, i) => (
          <text key={i} x={tx} y={baseline(i)} textAnchor={anchor} fontFamily={family} fontWeight={weight} fontStyle={style} fontSize={sz}
            letterSpacing={condensed ? 1 : -sz * 0.012}>
            {line.split(/\s+/).map((w, wi) => (
              <tspan key={wi} fill={accents.includes(w.replace(/[^A-Z0-9]/g, '')) ? 'url(#acc)' : scheme.white}>{(wi ? ' ' : '') + w}</tspan>
            ))}
          </text>
        ))}
        {p.stroke ? (() => {
          const y = top + blockH + sz * 0.10, x0 = at === 'right' ? W - pad - boxW * 0.9 : at === 'top' ? W / 2 - boxW * 0.4 : tx;
          const x1 = x0 + boxW * (at === 'top' ? 0.8 : 0.86);
          return <path d={`M ${x0} ${y + 10} Q ${(x0 + x1) / 2} ${y - 14} ${x1} ${y + 2} Q ${(x0 + x1) / 2} ${y - 2} ${x0} ${y + 10} Z`} fill="url(#acc)" />;
        })() : null}
      </svg>
    </AbsoluteFill>
  );
};
