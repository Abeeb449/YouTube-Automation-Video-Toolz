/**
 * Anatomy — show exactly the body part the narrator is talking about. A 3D creature (Blender sprite, e.g. the
 * leopard seal head whose jaw opens) or a photo fills the frame; callouts draw leader lines from points on the
 * animal to labelled cards in sync with the words, and the camera pushes in on the part being described.
 *
 *   sprite: {creature: "leopardSealHead", view: "jaw"}   (or image: "photo.jpg")
 *   callouts: [{x, y, label, sub?, at, side?: "left"|"right"}]   x, y = 0-1 inside the visible animal
 *   zoom: [{at, x, y, scale}]                                       camera pushes to (x, y) at `scale`
 *   backdrop: ocean | abyss | dark …, title?, kicker?, callout?
 */
import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile} from 'remotion';
import {BackdropLayer, Backdrop, C, DocuOverlays, DocuProps, F, prog, useT} from '../docu/kit';
import {spriteFrame, SpriteManifest} from '../ocean/scenes';
import {Dust, FilmGrain, TypeOn, Vignette} from './fx';

type Callout = {x: number; y: number; label: string; sub?: string; at?: number; side?: 'left' | 'right'; color?: string};

export type AnatomyProps = DocuProps & {
  sprite?: {creature: string; view: string; hold?: boolean};
  image?: string;
  sprites?: SpriteManifest;
  callouts?: Callout[];
  zoom?: {at?: number; x: number; y: number; scale?: number}[];
  title?: string;
  backdrop?: Backdrop;
  flip?: boolean;
};

export const Anatomy: React.FC<AnatomyProps> = (p) => {
  const {t, dur, s, width, height} = useT();
  const meta = p.sprite ? p.sprites?.[p.sprite.creature]?.[p.sprite.view] : undefined;
  // subject box: the visible animal fills ~78% of the frame width, centred slightly left of the callouts
  let file: string | null = null;
  let file2: string | null = null, mix = 0;      // next frame + how far we are into it (blended turns)
  let iw = 1, ih = 1, bx0 = 0, by0 = 0, bx1 = 1, by1 = 1;
  if (meta) {
    iw = meta.w; ih = meta.h; [bx0, by0, bx1, by1] = meta.bbox;
    file = `sprites/${p.sprite!.creature}/${p.sprite!.view}/${String(p.sprite!.hold ? meta.frames : spriteFrame(meta, t - 0.2)).padStart(4, '0')}.webp`;
    if (meta.blend && meta.loop !== false && !p.sprite!.hold && meta.frames > 1) {
      const pos = Math.max(0, t) * meta.fps;
      const a = Math.floor(pos) % meta.frames, b = (a + 1) % meta.frames;
      mix = pos - Math.floor(pos);
      file = `sprites/${p.sprite!.creature}/${p.sprite!.view}/${String(a + 1).padStart(4, '0')}.webp`;
      file2 = `sprites/${p.sprite!.creature}/${p.sprite!.view}/${String(b + 1).padStart(4, '0')}.webp`;
    }
  } else if (p.image) {
    file = p.image;
  }
  const bw = (bx1 - bx0) / iw, bh = (by1 - by0) / ih;
  const boxW = Math.min(width * 0.74, (height * 0.78) * (bw * iw) / (bh * ih));
  const dw = boxW / bw, dh = dw * ih / iw;
  const enter = prog(t, 0, 1.1, Easing.out(Easing.cubic));
  const left = width * 0.47 - (bx0 / iw + bw / 2) * dw;
  const top = height * 0.53 - (by0 / ih + bh / 2) * dh + Math.sin(t * 0.8) * 6 * s;
  // point in the animal → screen
  const pt = (x: number, y: number) => {
    const xx = p.flip ? 1 - x : x;
    return [left + (bx0 / iw + xx * bw) * dw, top + (by0 / ih + y * bh) * dh] as const;
  };
  // camera: piecewise push-ins
  const zooms = p.zoom ?? [];
  let camS = 1, camX = width / 2, camY = height / 2;
  for (const z of zooms) {
    const k = prog(t, z.at ?? 0, 1.4, Easing.inOut(Easing.cubic));
    const [zx, zy] = pt(z.x, z.y);
    camS = camS + ((z.scale ?? 1.6) - camS) * k;
    camX = camX + (zx - camX) * k;
    camY = camY + (zy - camY) * k;
  }
  const slow = 1 + 0.03 * (t / Math.max(1, dur));
  const camT = `translate(${width / 2}px, ${height / 2}px) scale(${camS * slow}) translate(${-camX}px, ${-camY}px)`;
  const callouts = p.callouts ?? [];
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <BackdropLayer kind={p.backdrop ?? 'ocean'} />
      <Dust count={30} />
      <AbsoluteFill style={{transform: camT, transformOrigin: '0 0'}}>
        {file ? (
          <Img src={staticFile(file)} style={{position: 'absolute', left, top, width: dw, height: dh, opacity: enter,
            transform: `${p.flip ? 'scaleX(-1) ' : ''}translateX(${(1 - enter) * -40 * s}px)`,
            filter: `drop-shadow(0 ${20 * s}px ${40 * s}px rgba(0,0,0,0.45))`}} />
        ) : null}
        {file2 ? (
          <Img src={staticFile(file2)} style={{position: 'absolute', left, top, width: dw, height: dh, opacity: enter * mix,
            transform: `${p.flip ? 'scaleX(-1) ' : ''}translateX(${(1 - enter) * -40 * s}px)`}} />
        ) : null}
        {/* callout anchors + leader lines live in the zoomed space so they stay glued to the animal */}
        <svg width={width} height={height} style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
          {callouts.map((c, i) => {
            const at = c.at ?? 0.8 + i * 1.2;
            const [ax, ay] = pt(c.x, c.y);
            const pd = prog(t, at, 0.35);
            const pl = prog(t, at + 0.15, 0.55, Easing.inOut(Easing.cubic));
            const side = c.side ?? (c.x > 0.5 ? 'right' : 'left');
            const ex = side === 'right' ? ax + 150 * s : ax - 150 * s;
            const ey = ay - 110 * s;
            const len = Math.hypot(ex - ax, ey - ay) + 90 * s;
            const col = c.color ?? '#ffd34d';
            return (
              <g key={i} opacity={pd}>
                <circle cx={ax} cy={ay} r={(9 + 16 * ((t * 1.2 + i * 0.3) % 1)) * s / camS} fill="none" stroke={col}
                  strokeOpacity={1 - ((t * 1.2 + i * 0.3) % 1)} strokeWidth={3 * s / camS} />
                <circle cx={ax} cy={ay} r={7 * s / camS} fill={col} />
                <polyline points={`${ax},${ay} ${ex},${ey} ${ex + (side === 'right' ? 90 : -90) * s},${ey}`} fill="none" stroke={col}
                  strokeWidth={3 * s / camS} strokeDasharray={len} strokeDashoffset={len * (1 - pl)} />
              </g>
            );
          })}
        </svg>
      </AbsoluteFill>
      {/* label cards are drawn unzoomed (always readable), positioned where the zoomed leader line ends */}
      {callouts.map((c, i) => {
        const at = c.at ?? 0.8 + i * 1.2;
        const [ax, ay] = pt(c.x, c.y);
        const side = c.side ?? (c.x > 0.5 ? 'right' : 'left');
        const exW = (side === 'right' ? ax + 240 * s : ax - 240 * s);
        const eyW = ay - 110 * s;
        const sx = width / 2 + (exW - camX) * camS * slow, sy = height / 2 + (eyW - camY) * camS * slow;
        const pc = prog(t, at + 0.55, 0.4);
        // keep the card on screen whatever the camera does
        const cw = Math.min(520 * s, Math.max(c.label.length * 23.5 * s, (c.sub ?? '').length * 12 * s) + 46 * s);
        const lx = Math.max(24 * s, Math.min(width - cw - 24 * s, side === 'right' ? sx + 10 * s : sx - 10 * s - cw));
        const ly = Math.max(24 * s, Math.min(height - 130 * s, sy - 30 * s));
        return (
          <div key={i} style={{position: 'absolute', left: lx, width: cw, boxSizing: 'border-box',
            top: ly, opacity: pc, transform: `translateY(${(1 - pc) * 12 * s}px)`, fontFamily: F.sans,
            background: 'rgba(6,14,24,0.82)', borderLeft: `${5 * s}px solid ${c.color ?? '#ffd34d'}`, padding: `${10 * s}px ${18 * s}px`,
            boxShadow: '0 10px 30px rgba(0,0,0,0.4)', maxWidth: 520 * s}}>
            <div style={{fontWeight: 800, fontSize: 32 * s, color: C.text, letterSpacing: 1 * s, textTransform: 'uppercase', whiteSpace: 'nowrap', overflow: 'hidden'}}>
              <TypeOn text={c.label} at={at + 0.55} cps={30} caret={false} />
            </div>
            {c.sub ? <div style={{fontSize: 23 * s, color: C.dim, marginTop: 4 * s}}>{c.sub}</div> : null}
          </div>
        );
      })}
      {p.title ? (
        <div style={{position: 'absolute', left: 64 * s, top: 56 * s, fontFamily: F.sans, opacity: prog(t, 0.2, 0.6)}}>
          {p.kicker ? <div style={{fontSize: 22 * s, color: C.teal, letterSpacing: 3 * s, fontWeight: 700, textTransform: 'uppercase'}}>{p.kicker}</div> : null}
          <div style={{fontSize: 46 * s, color: C.text, fontWeight: 800, letterSpacing: 1.5 * s, textTransform: 'uppercase'}}>{p.title}</div>
        </div>
      ) : null}
      <Vignette strength={0.5} />
      <FilmGrain opacity={0.05} />
      <DocuOverlays {...p} kicker={undefined} />
    </AbsoluteFill>
  );
};
