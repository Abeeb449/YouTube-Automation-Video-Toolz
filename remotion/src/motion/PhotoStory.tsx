/**
 * PhotoStory — real photos that never sit still (the "archive photo" treatment of history/war documentaries,
 * done for nature): framed prints that drop in and tilt in 3D, full-bleed 2.5D parallax (subject cut out and
 * moving in front of its background), slow push toward a focus point, a pen circle on a detail, monochrome that
 * blooms into colour, light leaks, film grain and a credit chip.
 *
 * Props (all `at` values are seconds or cue words resolved by ytauto):
 *   layout: "full" (default) | "print" | "pile"
 *   photos: [{photo, cutout?, caption?, credit?, at?, focus?: [x, y], zoom?: [from, to], mark?: {x, y, r?, at?, label?},
 *             mono?: true, colorAt?: number}]
 *   title?, callout?, calloutAt?
 */
import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile} from 'remotion';
import {C, DocuOverlays, DocuProps, F, prog, useT} from '../docu/kit';
import {Credit, DrawCircle, FilmGrain, LightLeak, Vignette} from './fx';

export type PhotoSpec = {
  photo: string;
  cutout?: string;
  caption?: string;
  credit?: string;
  at?: number;
  focus?: [number, number];
  zoom?: [number, number];
  mark?: {x: number; y: number; r?: number; at?: number; label?: string};
  mono?: boolean;
  colorAt?: number;
};

export type PhotoStoryProps = DocuProps & {
  layout?: 'full' | 'print' | 'pile';
  photos: PhotoSpec[];
  title?: string;
};

const src = (p: string) => (p.startsWith('http') ? p : staticFile(p));

const monoFilter = (t: number, ph: PhotoSpec) => {
  if (!ph.mono) return '';
  const k = ph.colorAt !== undefined ? prog(t, ph.colorAt, 1.2, Easing.inOut(Easing.cubic)) : 0;
  return `grayscale(${1 - k}) contrast(${1.12 - 0.1 * k}) brightness(${0.95 + 0.05 * k})`;
};

/** Full-bleed photo with a slow push toward `focus`; with a cutout, the subject floats in front (parallax). */
const FullPhoto: React.FC<{ph: PhotoSpec; t0: number; t1: number}> = ({ph, t0, t1}) => {
  const {t, s, width, height} = useT();
  const k = interpolate(t, [t0, t1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.sin)});
  const [z0, z1] = ph.zoom ?? [1.06, 1.2];
  const [fx, fy] = ph.focus ?? [0.5, 0.45];
  const z = z0 + (z1 - z0) * k;
  const tx = (0.5 - fx) * (z - 1) * width;
  const ty = (0.5 - fy) * (z - 1) * height;
  const filt = monoFilter(t, ph);
  const bg: React.CSSProperties = {position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover'};
  return (
    <AbsoluteFill>
      <Img src={src(ph.photo)} style={{...bg, transform: `translate(${tx * 0.7}px, ${ty * 0.7}px) scale(${z * (ph.cutout ? 1.02 : 1)})`,
        filter: `${filt} ${ph.cutout ? `blur(${1.6 * s}px) brightness(0.82)` : ''}`.trim() || undefined}} />
      {ph.cutout ? (
        <Img src={src(ph.cutout)} style={{...bg, transform: `translate(${tx * 1.25 + (k - 0.5) * 24 * s}px, ${ty * 1.25}px) scale(${z * 1.04})`,
          filter: `${filt} drop-shadow(0 ${14 * s}px ${22 * s}px rgba(0,0,0,0.45))`.trim()}} />
      ) : null}
      {ph.mark ? (
        <>
          <DrawCircle cx={(0.5 + (ph.mark.x - 0.5) * z) * width + tx} cy={(0.5 + (ph.mark.y - 0.5) * z) * height + ty}
            rx={(ph.mark.r ?? 0.08) * width * z} at={ph.mark.at ?? t0 + 1} />
          {ph.mark.label ? (
            <div style={{position: 'absolute', left: (0.5 + (ph.mark.x - 0.5) * z) * width + tx, top: (0.5 + (ph.mark.y - 0.5) * z) * height + ty - ((ph.mark.r ?? 0.08) * width * z * 0.8) - 54 * s,
              transform: 'translateX(-50%)', fontFamily: F.sans, fontWeight: 800, fontSize: 30 * s, color: '#fff', letterSpacing: 1.5 * s,
              textTransform: 'uppercase', textShadow: '0 2px 14px rgba(0,0,0,0.8)', opacity: prog(t, (ph.mark.at ?? t0 + 1) + 0.4, 0.4)}}>
              {ph.mark.label}
            </div>
          ) : null}
        </>
      ) : null}
    </AbsoluteFill>
  );
};

/** A framed print on a blurred copy of itself: drops in, tilts in 3D, then slowly pushes in. */
const Print: React.FC<{ph: PhotoSpec; i: number; n: number; t0: number; t1: number; pile: boolean}> = ({ph, i, n, t0, t1, pile}) => {
  const {t, s, width, height} = useT();
  const drop = prog(t, t0, 0.75, Easing.out(Easing.back(1.4)));
  const k = interpolate(t, [t0, t1 + 2], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const w = width * (pile ? 0.5 : 0.62);
  const rot0 = pile ? [-6, 5, -3, 7, -4][i % 5] : -2.5;
  const offX = pile ? [-0.16, 0.14, -0.06, 0.18, -0.12][i % 5] * width : 0;
  const offY = pile ? [-0.04, 0.03, 0.07, -0.05, 0.02][i % 5] * height : 0;
  const tiltY = Math.sin(t * 0.35 + i) * 5 + (1 - drop) * 18;
  const tiltX = Math.cos(t * 0.3 + i) * 3 + (1 - drop) * -10;
  const z = (1 + 0.06 * k) * (0.9 + 0.1 * drop);
  return (
    <div style={{position: 'absolute', left: '50%', top: '50%', width: w, transform: `translate(-50%, -50%) translate(${offX}px, ${offY - (1 - drop) * 120 * s}px)
        perspective(${1600 * s}px) rotateX(${tiltX}deg) rotateY(${tiltY}deg) rotate(${rot0 + (1 - drop) * 8 + k * 1.2}deg) scale(${z})`,
      opacity: drop, background: '#f4f1ea', padding: 14 * s, paddingBottom: ph.caption ? 64 * s : 14 * s,
      boxShadow: `0 ${30 * s}px ${60 * s}px rgba(0,0,0,0.55), 0 ${6 * s}px ${14 * s}px rgba(0,0,0,0.35)`}}>
      <div style={{position: 'relative', width: '100%', aspectRatio: '3 / 2', overflow: 'hidden', background: '#222'}}>
        <Img src={src(ph.photo)} style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover',
          transformOrigin: `${(ph.focus?.[0] ?? 0.5) * 100}% ${(ph.focus?.[1] ?? 0.5) * 100}%`, transform: `scale(${1.02 + 0.12 * k})`,
          filter: monoFilter(t, ph) || undefined}} />
        <div style={{position: 'absolute', inset: 0, boxShadow: 'inset 0 0 60px rgba(0,0,0,0.35)'}} />
      </div>
      {ph.caption ? (
        <div style={{position: 'absolute', left: 22 * s, right: 22 * s, bottom: 16 * s, fontFamily: F.serif, fontStyle: 'italic', fontSize: 26 * s,
          color: '#2a2a2a', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>{ph.caption}</div>
      ) : null}
    </div>
  );
};

export const PhotoStory: React.FC<PhotoStoryProps> = (p) => {
  const {t, dur, s} = useT();
  const photos = p.photos ?? [];
  const layout = p.layout ?? 'full';
  const starts = photos.map((ph, i) => ph.at ?? (i * dur) / Math.max(1, photos.length));
  const cur = Math.max(0, starts.reduce((acc, st, i) => (t >= st ? i : acc), 0));
  const ph = photos[cur];
  if (!ph) return <AbsoluteFill style={{background: '#05080b'}} />;
  const end = (i: number) => starts[i + 1] ?? dur;
  return (
    <AbsoluteFill style={{background: '#05080b', overflow: 'hidden'}}>
      {layout === 'full' ? (
        photos.map((q, i) => {
          // cross-dissolve with a push between consecutive photos
          const a = interpolate(t, [starts[i] - 0.01, starts[i] + 0.5, end(i), end(i) + 0.5], [i === 0 ? 1 : 0, 1, 1, i === photos.length - 1 ? 1 : 0],
            {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          if (a <= 0) return null;
          return <AbsoluteFill key={i} style={{opacity: a}}><FullPhoto ph={q} t0={starts[i]} t1={end(i) + 0.5} /></AbsoluteFill>;
        })
      ) : (
        <>
          {/* the print's own photo, blurred and dark, fills the frame behind it */}
          <Img src={src(ph.photo)} style={{position: 'absolute', inset: -40 * s, width: `calc(100% + ${80 * s}px)`, height: `calc(100% + ${80 * s}px)`,
            objectFit: 'cover', filter: `blur(${26 * s}px) brightness(0.38) saturate(0.8)`, transform: `scale(${1.05 + 0.04 * Math.sin(t * 0.2)})`}} />
          {photos.map((q, i) => (layout === 'pile' ? t >= starts[i] - 0.05 : i === cur) ? (
            <Print key={i} ph={q} i={i} n={photos.length} t0={starts[i]} t1={end(i)} pile={layout === 'pile'} />
          ) : null)}
        </>
      )}
      <LightLeak at={0} d={1.3} />
      {photos.slice(1).map((_, i) => <LightLeak key={i} at={starts[i + 1] - 0.3} d={1.1} />)}
      <Vignette strength={0.55} />
      <FilmGrain opacity={0.08} />
      {p.title ? (
        <div style={{position: 'absolute', left: 60 * s, top: 54 * s, fontFamily: F.sans, fontWeight: 800, fontSize: 40 * s, color: C.text,
          letterSpacing: 2 * s, textTransform: 'uppercase', textShadow: '0 2px 16px rgba(0,0,0,0.7)', opacity: prog(t, 0.3, 0.6)}}>{p.title}</div>
      ) : null}
      <Credit text={ph.credit ? `Photo: ${ph.credit}` : undefined} />
      <DocuOverlays {...p} />
    </AbsoluteFill>
  );
};
