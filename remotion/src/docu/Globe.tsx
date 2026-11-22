import React from 'react';
import {AbsoluteFill, Easing, interpolate} from 'remotion';
import {geoGraticule10, geoOrthographic, geoPath} from 'd3-geo';
import {C, DocuFrame, DocuProps, F, prog, useT} from './kit';
import {countries, findCountry} from './geo';

export type GlobeProps = DocuProps & {
  /** Start view [lon, lat] and end view. The globe rotates and zooms between them. */
  from?: [number, number];
  to: [number, number];
  zoomFrom?: number;
  zoomTo?: number;
  marker?: {label?: string; note?: string; at?: number; ring?: boolean};
  highlight?: string[];
  /** Big date/title bottom-left, e.g. "9 AUGUST 1945". */
  title?: string;
  subtitle?: string;
};

export const Globe: React.FC<GlobeProps> = (p) => {
  const {t, dur, s, width, height} = useT();
  const list = countries('low');
  const e = Easing.inOut(Easing.cubic);
  const k = interpolate(t, [0, dur * 0.85], [0, 1], {extrapolateRight: 'clamp', easing: e});
  const from = p.from ?? [p.to[0] - 60, p.to[1] - 10];
  const lon = from[0] + (p.to[0] - from[0]) * k;
  const lat = from[1] + (p.to[1] - from[1]) * k;
  const zoom = (p.zoomFrom ?? 0.8) * Math.pow((p.zoomTo ?? 1.6) / (p.zoomFrom ?? 0.8), k);
  const r = height * 0.42 * zoom;
  const proj = geoOrthographic().scale(r).translate([width / 2, height / 2]).rotate([-lon, -lat]).clipAngle(90);
  const path = geoPath(proj);
  const hl = new Set((p.highlight ?? []).map((n) => findCountry(n, list)?.properties.name));
  const target = proj(p.to);
  const m = p.marker;
  const mp = prog(t, m?.at ?? dur * 0.7, 0.6);
  const tp = prog(t, m?.at ?? dur * 0.6, 0.8);

  return (
    <DocuFrame {...p} defaultBackdrop="black">
      <AbsoluteFill>
        {/* stars */}
        <svg width={width} height={height} style={{position: 'absolute'}}>
          {Array.from({length: 140}).map((_, i) => {
            const x = ((i * 7919) % 1000) / 1000 * width, y = ((i * 104729) % 1000) / 1000 * height;
            return <circle key={i} cx={x} cy={y} r={(i % 3 === 0 ? 1.4 : 0.8) * s} fill="#fff" opacity={0.25 + (i % 5) * 0.08} />;
          })}
        </svg>
        <svg width={width} height={height} style={{position: 'absolute'}}>
          <defs>
            <radialGradient id="ocean" cx="40%" cy="35%" r="75%">
              <stop offset="0%" stopColor="#2a74b0" />
              <stop offset="60%" stopColor="#14456f" />
              <stop offset="100%" stopColor="#0a2440" />
            </radialGradient>
            <radialGradient id="atmo" cx="50%" cy="50%" r="50%">
              <stop offset="88%" stopColor="#6fc3ff" stopOpacity={0} />
              <stop offset="94%" stopColor="#6fc3ff" stopOpacity={0.45} />
              <stop offset="100%" stopColor="#6fc3ff" stopOpacity={0} />
            </radialGradient>
            <radialGradient id="shade" cx="35%" cy="30%" r="80%">
              <stop offset="55%" stopColor="#000" stopOpacity={0} />
              <stop offset="100%" stopColor="#000" stopOpacity={0.55} />
            </radialGradient>
          </defs>
          <circle cx={width / 2} cy={height / 2} r={r * 1.09} fill="url(#atmo)" />
          <circle cx={width / 2} cy={height / 2} r={r} fill="url(#ocean)" />
          <path d={path(geoGraticule10()) ?? ''} fill="none" stroke="#9fd0ff" strokeOpacity={0.08} strokeWidth={1 * s} />
          {list.map((c) => (
            <path key={c.properties.name} d={path(c) ?? ''} fill={hl.has(c.properties.name) ? '#c24a3a' : '#3e7d5c'}
              stroke="#9cc6a8" strokeOpacity={0.35} strokeWidth={0.7 * s} />
          ))}
          <circle cx={width / 2} cy={height / 2} r={r} fill="url(#shade)" />
          {m && target ? (
            <g opacity={mp}>
              {m.ring !== false ? <circle cx={target[0]} cy={target[1]} r={(60 - 25 * mp) * s} fill="none" stroke="#fff" strokeWidth={2 * s} opacity={0.8} /> : null}
              <circle cx={target[0]} cy={target[1]} r={6 * s} fill={C.red} />
              {m.label ? (
                <text x={target[0] + 16 * s} y={target[1] - 8 * s} fill={C.text} fontFamily={F.sans} fontWeight={700} fontSize={23 * s} letterSpacing={2 * s}>
                  {m.label.toUpperCase()}
                </text>
              ) : null}
              {m.note ? <text x={target[0] + 16 * s} y={target[1] + 12 * s} fill={C.dim} fontFamily={F.mono} fontSize={20 * s}>{m.note}</text> : null}
            </g>
          ) : null}
        </svg>
        {p.title ? (
          <div style={{position: 'absolute', left: 80 * s, bottom: 150 * s, opacity: tp, transform: `translateY(${(1 - tp) * 20 * s}px)`}}>
            <div style={{fontSize: 76.0 * s, fontWeight: 800, letterSpacing: 2 * s, textShadow: '0 4px 30px rgba(0,0,0,.6)'}}>{p.title}</div>
            {p.subtitle ? <div style={{fontSize: 23 * s, letterSpacing: 3 * s, color: C.amber, fontWeight: 700, textTransform: 'uppercase'}}>{p.subtitle}</div> : null}
          </div>
        ) : null}
      </AbsoluteFill>
    </DocuFrame>
  );
};
