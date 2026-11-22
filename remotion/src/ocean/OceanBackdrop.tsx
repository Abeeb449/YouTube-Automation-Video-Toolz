import React from 'react';
import {AbsoluteFill, interpolate, interpolateColors, useCurrentFrame, useVideoConfig} from 'remotion';

/**
 * Procedural underwater world. `depth` 0 = just below the surface (light shafts),
 * 1 = the abyss (black, only drifting marine snow). `depthTo` animates a descent.
 */
export const OceanBackdrop: React.FC<{depth?: number; depthTo?: number; surface?: boolean; rays?: boolean; snow?: number}> = ({
  depth = 0.4, depthTo, surface = false, rays, snow = 70,
}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames, width, height} = useVideoConfig();
  const t = frame / fps, dur = durationInFrames / fps, s = width / 1920;
  const d = depthTo === undefined ? depth : interpolate(t, [0, dur], [depth, depthTo]);
  const top = interpolateColors(d, [0, 0.35, 0.7, 1], ['#2f7fa3', '#14506e', '#0a2a3d', '#03090f']);
  const mid = interpolateColors(d, [0, 0.35, 0.7, 1], ['#16577a', '#0c3550', '#061a27', '#020508']);
  const bot = interpolateColors(d, [0, 0.35, 0.7, 1], ['#0a2c42', '#061c2b', '#030c13', '#010204']);
  const rayOn = rays ?? d < 0.55;
  const rayAlpha = interpolate(d, [0, 0.55], [0.22, 0], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: `linear-gradient(180deg, ${top} 0%, ${mid} 45%, ${bot} 100%)`}}>
      {rayOn ? (
        <svg width={width} height={height} style={{position: 'absolute', mixBlendMode: 'screen'}}>
          <defs>
            <linearGradient id="ray" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#bfefff" stopOpacity={rayAlpha} />
              <stop offset="100%" stopColor="#bfefff" stopOpacity={0} />
            </linearGradient>
            <filter id="rayblur"><feGaussianBlur stdDeviation={18 * s} /></filter>
          </defs>
          {Array.from({length: 9}).map((_, i) => {
            const x = ((i * 0.13 + 0.05) % 1) * width + Math.sin(t * 0.35 + i * 1.7) * 40 * s;
            const w = (60 + (i * 37) % 90) * s;
            const sway = Math.sin(t * 0.25 + i) * 120 * s;
            return <polygon key={i} points={`${x},0 ${x + w},0 ${x + w * 2.2 + sway},${height} ${x - w * 0.6 + sway},${height}`} fill="url(#ray)" filter="url(#rayblur)" />;
          })}
        </svg>
      ) : null}
      {surface ? (
        <AbsoluteFill style={{height: 6 * s, top: 0, background: 'linear-gradient(90deg, rgba(200,240,255,0.0), rgba(200,240,255,0.5), rgba(200,240,255,0.0))'}} />
      ) : null}
      {/* marine snow */}
      <svg width={width} height={height} style={{position: 'absolute'}}>
        {Array.from({length: snow}).map((_, i) => {
          const seed = (i * 9301 + 49297) % 233280;
          const x0 = (seed / 233280) * width;
          const sp = 8 + (i % 7) * 4;
          const y = (((i * 7919) % 1000) / 1000 * (height + 40) + t * sp * s) % (height + 40) - 20;
          const x = x0 + Math.sin(t * 0.6 + i) * 12 * s;
          const r = (i % 5 === 0 ? 2.2 : 1.2) * s;
          return <circle key={i} cx={x} cy={y} r={r} fill="#dff6ff" opacity={0.12 + (i % 4) * 0.06} />;
        })}
      </svg>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, transparent 45%, rgba(0,0,0,0.6) 100%)'}} />
    </AbsoluteFill>
  );
};
