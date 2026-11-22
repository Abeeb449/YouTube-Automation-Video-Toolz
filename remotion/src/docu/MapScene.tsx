import React, {useMemo} from 'react';
import {AbsoluteFill, interpolate} from 'remotion';
import {geoCentroid, geoMercator, geoPath} from 'd3-geo';
import type {FeatureCollection, Geometry} from 'geojson';
import {C, DocuFrame, DocuProps, F, prog, stagger, useT} from './kit';
import {countries, findCountry} from './geo';

type LonLat = [number, number];
type Highlight = string | {name: string; at?: number; color?: string; opacity?: number};
type City = {name: string; lon: number; lat: number; at?: number; color?: string; note?: string};
type Arrow = {from: LonLat; to: LonLat; at?: number; dur?: number; color?: string; curve?: number; label?: string};
type Pulse = {lon: number; lat: number; at?: number; color?: string; label?: string};

export type MapSceneProps = DocuProps & {
  /** Countries to frame the camera on. */
  focus?: string[];
  /** Or an explicit box: [[west, south], [east, north]]. */
  bbox?: [LonLat, LonLat];
  highlight?: Highlight[];
  /** Country names in spaced capitals, at the country centre or at an explicit position. Defaults to the focus list. */
  countryLabels?: (string | {name: string; lon: number; lat: number})[];
  cities?: City[];
  arrows?: Arrow[];
  pulses?: Pulse[];
  /** Camera push-in over the scene (1 = none). */
  zoom?: number;
  /** Big date/title on the map, top-left (e.g. "24 FEBRUARY 2022"). */
  title?: string;
  subtitle?: string;
};

export const MapScene: React.FC<MapSceneProps> = (p) => {
  const {t, dur, s, width, height} = useT();
  const all = countries('high');
  const focus = p.focus ?? [];

  const {path, project, shapes} = useMemo(() => {
    const proj = geoMercator();
    const pad = 110 * s;
    if (p.bbox) {
      const [[w, so], [e, n]] = p.bbox;
      // MultiPoint avoids d3's spherical polygon winding rules (a "wrong-way" box means "the whole world").
      proj.fitExtent([[pad, pad], [width - pad, height - pad]], {
        type: 'MultiPoint', coordinates: [[w, so], [e, so], [e, n], [w, n], [(w + e) / 2, so], [(w + e) / 2, n]],
      } as any);
    } else {
      const feats = focus.map((n) => findCountry(n, all)).filter(Boolean);
      const fc: FeatureCollection<Geometry> = {type: 'FeatureCollection', features: (feats.length ? feats : all) as any};
      proj.fitExtent([[pad, pad], [width - pad, height - pad]], fc as any);
    }
    const gp = geoPath(proj);
    return {
      path: gp,
      project: (ll: LonLat) => proj(ll) ?? [0, 0],
      shapes: all.map((c) => ({name: c.properties.name, d: gp(c) ?? '', c})),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [width, height, JSON.stringify(p.bbox), JSON.stringify(focus)]);

  const z = interpolate(t, [0, dur], [1, p.zoom ?? 1.06]);
  const hl = (p.highlight ?? []).map((h, i) => (typeof h === 'string' ? {name: h, at: stagger(i, (p.highlight ?? []).length, dur, 0.8, 0.4)} : h));
  const labels = p.countryLabels ?? focus;
  const tp = prog(t, 0.2, 0.6);

  return (
    <DocuFrame {...p} defaultBackdrop="dark">
      <AbsoluteFill>
        <svg width={width} height={height} style={{position: 'absolute'}}>
          <defs>
            <filter id="glow"><feGaussianBlur stdDeviation={6 * s} /></filter>
          </defs>
          <g transform={`translate(${width / 2} ${height / 2}) scale(${z}) translate(${-width / 2} ${-height / 2})`}>
            {shapes.map((sh) => (
              <path key={sh.name} d={sh.d} fill={focus.some((f) => findCountry(f, all)?.properties.name === sh.name) ? C.landHi : C.land}
                stroke={C.border} strokeWidth={1.1 * s / z} />
            ))}
            {hl.map((h, i) => {
              const c = findCountry(h.name, all);
              if (!c) return null;
              const a = prog(t, h.at ?? 0.8, 0.8);
              return <path key={`h${i}`} d={path(c) ?? ''} fill={h.color ?? C.red} fillOpacity={(h.opacity ?? 0.55) * a} stroke={h.color ?? C.red} strokeOpacity={a} strokeWidth={2 * s / z} />;
            })}
            {labels.map((lab, i) => {
              const n = typeof lab === 'string' ? lab : lab.name;
              let ll: LonLat;
              if (typeof lab === 'string') {
                const c = findCountry(n, all);
                if (!c) return null;
                ll = geoCentroid(c) as LonLat;
              } else ll = [lab.lon, lab.lat];
              const [x, y] = project(ll);
              if (x < 0 || y < 0 || x > width || y > height) return null;
              return (
                <text key={`l${i}`} x={x} y={y} fill={C.dim} fontFamily={F.sans} fontWeight={700} fontSize={26 * s / z}
                  letterSpacing={6 * s / z} textAnchor="middle" opacity={prog(t, 0.4 + i * 0.15, 0.8)}>
                  {n.toUpperCase()}
                </text>
              );
            })}
            {(p.arrows ?? []).map((a, i) => {
              const [x1, y1] = project(a.from);
              const [x2, y2] = project(a.to);
              const at = a.at ?? stagger(i, (p.arrows ?? []).length, dur, 1, 0.6);
              const k = interpolate(t, [at, at + (a.dur ?? 1.6)], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
              const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
              const len = Math.hypot(x2 - x1, y2 - y1);
              const bend = (a.curve ?? 0.18) * len;
              const cx = mx - ((y2 - y1) / len) * bend, cy = my + ((x2 - x1) / len) * bend;
              const qx = (1 - k) ** 2 * x1 + 2 * (1 - k) * k * cx + k * k * x2;
              const qy = (1 - k) ** 2 * y1 + 2 * (1 - k) * k * cy + k * k * y2;
              const col = a.color ?? C.red;
              return (
                <g key={`a${i}`} opacity={k > 0 ? 1 : 0}>
                  <path d={`M${x1},${y1} Q${cx},${cy} ${x2},${y2}`} fill="none" stroke={col} strokeWidth={3 * s / z}
                    strokeDasharray={len * 1.3} strokeDashoffset={len * 1.3 * (1 - k)} strokeLinecap="round" />
                  <circle cx={qx} cy={qy} r={7 * s / z} fill="#fff" />
                  <circle cx={qx} cy={qy} r={16 * s / z} fill={col} opacity={0.5} filter="url(#glow)" />
                  {a.label ? <text x={x1 + 12 * s} y={y1 - 12 * s} fill={col} fontFamily={F.sans} fontWeight={700} fontSize={21 * s / z} letterSpacing={2 * s}>{a.label.toUpperCase()}</text> : null}
                </g>
              );
            })}
            {(p.pulses ?? []).map((pu, i) => {
              const [x, y] = project([pu.lon, pu.lat]);
              const at = pu.at ?? 1;
              const a = prog(t, at, 0.4);
              const ring = ((t - at) % 1.6) / 1.6;
              return (
                <g key={`p${i}`} opacity={a}>
                  <circle cx={x} cy={y} r={(10 + ring * 40) * s / z} fill="none" stroke={pu.color ?? C.red} strokeWidth={2 * s / z} opacity={t > at ? 1 - ring : 0} />
                  <circle cx={x} cy={y} r={8 * s / z} fill={pu.color ?? C.red} />
                  {pu.label ? <text x={x + 16 * s} y={y + 5 * s} fill={C.text} fontFamily={F.sans} fontWeight={700} fontSize={23 * s / z}>{pu.label}</text> : null}
                </g>
              );
            })}
            {(p.cities ?? []).map((c, i) => {
              const [x, y] = project([c.lon, c.lat]);
              const a = prog(t, c.at ?? 0.6 + i * 0.12, 0.5);
              return (
                <g key={`c${i}`} opacity={a}>
                  <circle cx={x} cy={y} r={5 * s / z} fill={c.color ?? C.text} />
                  <text x={x + 10 * s / z} y={y + 5 * s / z} fill={c.color ?? C.text} fontFamily={F.sans} fontWeight={700} fontSize={22 * s / z} letterSpacing={1.5 * s / z}>
                    {c.name.toUpperCase()}
                  </text>
                  {c.note ? <text x={x + 10 * s / z} y={y + 24 * s / z} fill={C.dim} fontFamily={F.sans} fontSize={20 * s / z}>{c.note}</text> : null}
                </g>
              );
            })}
          </g>
        </svg>
        {p.title ? (
          <div style={{position: 'absolute', left: 80 * s, top: 60 * s, opacity: tp, fontFamily: F.sans}}>
            <div style={{fontSize: 50.0 * s, fontWeight: 800, color: C.text}}>{p.title}</div>
            {p.subtitle ? <div style={{fontSize: 22 * s, letterSpacing: 2.5 * s, color: C.red, fontWeight: 700, marginTop: 6 * s, textTransform: 'uppercase'}}>{p.subtitle}</div> : null}
          </div>
        ) : null}
      </AbsoluteFill>
    </DocuFrame>
  );
};
