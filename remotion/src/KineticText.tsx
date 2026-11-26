import React from 'react';
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {BaseProps, useSceneOpacity, useTheme} from './theme';
import {Dust, FilmGrain, Vignette} from './motion/fx';

export type KineticTextProps = BaseProps & {text: string; highlight?: string[]};

/**
 * The narration as kinetic type in a 3D space: words arrive from depth, one after another across the scene, on a
 * stage the camera slowly orbits and pushes into, above a perspective floor that glides toward the viewer.
 * Numbers and the longest words are picked out in the accent colour (or pass `highlight`).
 */
export const KineticText: React.FC<KineticTextProps> = ({text, highlight, theme: t}) => {
  const theme = useTheme(t);
  const frame = useCurrentFrame();
  const {fps, durationInFrames, width, height} = useVideoConfig();
  const opacity = useSceneOpacity();
  const s = width / 1920;
  const words = text.split(/\s+/).filter(Boolean);
  // Spread word reveals over the first 80% of the scene.
  const per = Math.max(2, (durationInFrames * 0.8) / Math.max(1, words.length));
  const clean = (w: string) => w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
  // what stands out when nothing is given: figures, and the two longest words
  const auto = new Set<string>();
  if (!highlight || !highlight.length) {
    words.filter((w) => /\d/.test(w)).forEach((w) => auto.add(clean(w)));
    [...words].map(clean).filter((w) => w.length > 6).sort((a, b) => b.length - a.length).slice(0, 2).forEach((w) => auto.add(w));
  }
  const hl = new Set([...(highlight ?? []).map((w) => w.toLowerCase()), ...auto]);
  const fontSize = (words.length > 40 ? 56 : words.length > 20 ? 72 : 94) * s;
  const k = frame / Math.max(1, durationInFrames);
  // camera: a slow orbit and push
  const ry = interpolate(k, [0, 1], [-7, 7], {easing: Easing.inOut(Easing.sin)});
  const rx = interpolate(k, [0, 1], [5, 1.5]);
  const push = interpolate(k, [0, 1], [0, 90 * s]);
  return (
    <AbsoluteFill style={{opacity, fontFamily: theme.font, color: theme.text, overflow: 'hidden',
      background: `radial-gradient(ellipse at 50% 38%, ${theme.bg2}55 0%, ${theme.bg1} 58%, #05080f 100%)`}}>
      {/* the floor: a grid in perspective that drifts toward the camera */}
      <AbsoluteFill style={{perspective: 900 * s, perspectiveOrigin: '50% 42%'}}>
        <div style={{position: 'absolute', left: '-50%', width: '200%', top: '58%', height: '120%',
          transform: `rotateX(74deg) rotateZ(${ry * 0.6}deg)`, transformOrigin: '50% 0%',
          backgroundImage: `linear-gradient(${theme.accent}26 ${2 * s}px, transparent ${2 * s}px), linear-gradient(90deg, ${theme.accent}26 ${2 * s}px, transparent ${2 * s}px)`,
          backgroundSize: `${120 * s}px ${120 * s}px`, backgroundPosition: `0 ${(frame * 1.6 * s) % (120 * s)}px`,
          maskImage: 'linear-gradient(to bottom, transparent 0%, rgba(0,0,0,0.9) 22%, rgba(0,0,0,0.25) 70%, transparent 100%)',
          WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, rgba(0,0,0,0.9) 22%, rgba(0,0,0,0.25) 70%, transparent 100%)'}} />
      </AbsoluteFill>
      <Dust count={36} />
      {/* the type, on a stage in 3D space */}
      <AbsoluteFill style={{perspective: 1500 * s, perspectiveOrigin: '50% 46%'}}>
        <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', padding: 150 * s, transformStyle: 'preserve-3d',
          transform: `translateZ(${push}px) rotateY(${ry}deg) rotateX(${rx}deg)`}}>
          <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: `${16 * s}px ${22 * s}px`,
            maxWidth: 1560 * s, transformStyle: 'preserve-3d', marginTop: -height * 0.04}}>
            {words.map((w, i) => {
              const p = spring({frame: frame - i * per, fps, config: {damping: 200}, durationInFrames: 14});
              const isHl = hl.has(clean(w));
              return (
                <span key={i} style={{fontSize, fontWeight: isHl ? 800 : 600, color: isHl ? theme.accent : theme.text,
                  opacity: p, display: 'inline-block',
                  filter: p < 0.98 ? `blur(${(1 - p) * 10 * s}px)` : undefined,
                  textShadow: `0 ${6 * s}px ${22 * s}px rgba(0,0,0,0.55)`,
                  transform: `translateZ(${(1 - p) * -520 * s + (isHl ? 46 * s : 0)}px) translateY(${(1 - p) * 26 * s}px)`}}>
                  {w}
                </span>
              );
            })}
          </div>
        </AbsoluteFill>
      </AbsoluteFill>
      <Vignette strength={0.55} />
      <FilmGrain opacity={0.06} />
    </AbsoluteFill>
  );
};
