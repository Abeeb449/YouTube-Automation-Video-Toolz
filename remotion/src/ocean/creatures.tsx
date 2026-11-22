/**
 * Flat-vector animated sea creatures. Each one is drawn facing RIGHT, centred on (0,0),
 * about 600 units long, and animates from `t` (seconds). Place them with <Actor>.
 */
import React from 'react';

export type CreatureProps = {t: number; color?: string; detail?: Record<string, unknown>};

const sw = (t: number, f = 1.6, a = 1) => Math.sin(t * f) * a;

export const SpermWhale: React.FC<CreatureProps> = ({t, color = '#8b8f94', detail = {}}) => {
  const fl = sw(t, 1.4, 10);
  return (
    <g>
      <defs>
        <linearGradient id="sw-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} />
          <stop offset="100%" stopColor="#5d6166" />
        </linearGradient>
      </defs>
      <g transform={`rotate(${fl} -255 0)`}>
        <path d="M-248,-8 C-268,-18 -290,-44 -318,-58 C-312,-34 -300,-14 -284,0 C-300,14 -312,34 -318,58 C-290,44 -268,18 -248,8 Z" fill="#6c7075" />
      </g>
      <path d="M296,-28 Q302,-82 238,-86 L60,-84 Q-60,-80 -170,-44 Q-230,-20 -258,-6 L-258,8 Q-220,22 -150,42 Q-40,70 60,70 L232,64 Q292,60 298,22 Z" fill="url(#sw-body)" />
      {/* dorsal hump + knuckles */}
      <path d="M-150,-46 Q-128,-64 -104,-56 Q-90,-52 -80,-60" fill="none" stroke="#6f7378" strokeWidth={10} strokeLinecap="round" />
      {/* wrinkles */}
      {[-40, -10, 20].map((x, i) => <path key={i} d={`M${x},-60 q8,30 0,60`} stroke="#000" strokeOpacity={0.08} strokeWidth={3} fill="none" />)}
      {/* lower jaw */}
      <path d="M250,56 Q170,66 90,60" stroke="#4a4e52" strokeWidth={6} fill="none" strokeLinecap="round" />
      {detail.teeth ? Array.from({length: 9}).map((_, i) => {
        const x = 120 + i * 14;
        return <path key={i} d={`M${x},${60 - i * 0.3} l5,-12 l5,12 Z`} fill="#f2f2ee" />;
      }) : null}
      {/* eye + flipper */}
      <circle cx={205} cy={18} r={4.5} fill="#111" />
      <g transform={`rotate(${sw(t, 1.4, 6)} 150 50)`}><path d="M150,48 Q140,78 112,84 Q126,62 132,48 Z" fill="#62666b" /></g>
      {detail.scars ? [[40, -20], [70, 10], [10, 25], [100, -40], [-20, 0]].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={8 + (i % 3) * 3} fill="none" stroke="#e8e8e8" strokeOpacity={0.55} strokeWidth={2} />
      )) : null}
    </g>
  );
};

export const GiantSquid: React.FC<CreatureProps> = ({t, color = '#c4473a'}) => {
  const arm = (i: number, len: number, w: number) => {
    const ph = t * 2.2 + i * 0.8;
    const y0 = -18 + i * 6;
    const c1y = y0 + Math.sin(ph) * 26, c2y = y0 + Math.sin(ph + 1.3) * 34, ey = y0 + Math.sin(ph + 2.2) * 40;
    return <path key={i} d={`M40,${y0 / 2} C${40 + len * 0.35},${c1y} ${40 + len * 0.7},${c2y} ${40 + len},${ey}`} stroke={color} strokeWidth={w} strokeLinecap="round" fill="none" />;
  };
  const pulse = 1 + sw(t, 2.2, 0.03);
  return (
    <g>
      {Array.from({length: 8}).map((_, i) => arm(i, 210 + (i % 3) * 20, 9))}
      {[0, 1].map((i) => {
        const ph = t * 1.6 + i * 2;
        const y0 = i ? 14 : -10;
        const ex = 470, ey = y0 + Math.sin(ph + 2) * 50;
        return (
          <g key={`t${i}`}>
            <path d={`M40,${y0} C180,${y0 + Math.sin(ph) * 40} 330,${y0 + Math.sin(ph + 1) * 60} ${ex},${ey}`} stroke={color} strokeWidth={5} fill="none" strokeLinecap="round" />
            <ellipse cx={ex + 10} cy={ey} rx={22} ry={8} fill={color} />
          </g>
        );
      })}
      <g transform={`scale(1 ${pulse})`}>
        <path d="M-290,0 Q-250,-40 -170,-52 Q-60,-62 10,-44 Q40,-30 40,0 Q40,30 10,44 Q-60,62 -170,52 Q-250,40 -290,0 Z" fill={color} />
        <path d="M-300,0 L-250,-58 L-215,-40 Z M-300,0 L-250,58 L-215,40 Z" fill={color} opacity={0.85} />
        <path d="M-250,-20 Q-120,-40 0,-30" stroke="#fff" strokeOpacity={0.12} strokeWidth={6} fill="none" />
      </g>
      <circle cx={30} cy={0} r={46} fill={color} />
      <circle cx={34} cy={-2} r={24} fill="#e8e3d8" />
      <circle cx={36} cy={-2} r={16} fill="#18242c" />
      <circle cx={30} cy={-8} r={5} fill="#fff" opacity={0.8} />
    </g>
  );
};

export const Orca: React.FC<CreatureProps> = ({t}) => {
  const fl = sw(t, 1.6, 9);
  return (
    <g>
      <g transform={`rotate(${fl} -250 0)`}><path d="M-245,-4 Q-270,-10 -300,-40 Q-306,-46 -296,-46 Q-276,-30 -258,-6 L-258,6 Q-276,30 -296,46 Q-306,46 -300,40 Q-270,10 -245,4 Z" fill="#0d0f12" /></g>
      <path d="M290,6 Q290,-40 200,-58 Q60,-80 -80,-60 Q-200,-36 -255,-6 L-255,6 Q-190,34 -60,54 Q100,70 220,52 Q288,38 290,6 Z" fill="#0d0f12" />
      <path d="M-60,-62 Q-40,-170 -20,-176 Q-12,-120 30,-70 Z" fill="#0d0f12" />
      <path d="M270,20 Q200,50 60,56 Q-40,58 -120,40 Q-20,30 80,30 Q190,24 270,20 Z" fill="#f4f4f1" />
      <ellipse cx={175} cy={-18} rx={34} ry={11} fill="#f4f4f1" transform="rotate(-8 175 -18)" />
      <path d="M-30,-40 Q10,-52 40,-40 Q10,-30 -30,-40 Z" fill="#9aa0a6" opacity={0.6} />
      <g transform={`rotate(${sw(t, 1.6, 6)} 130 40)`}><path d="M130,38 Q118,84 84,92 Q104,62 108,40 Z" fill="#0d0f12" /></g>
    </g>
  );
};

export const Shark: React.FC<CreatureProps> = ({t, color = '#6e7d88'}) => {
  const fl = sw(t, 2.4, 12);
  return (
    <g>
      <g transform={`rotate(${fl} -230 0)`}><path d="M-225,-4 L-300,-90 Q-296,-60 -262,0 L-290,52 Q-260,36 -225,6 Z" fill={color} /></g>
      <path d="M300,8 Q280,-36 180,-50 Q40,-66 -100,-40 Q-190,-20 -232,-4 L-232,6 Q-180,26 -80,42 Q80,56 200,42 Q270,34 300,8 Z" fill={color} />
      <path d="M296,10 Q260,36 190,42 Q60,52 -60,40 Q-140,32 -200,14 Q-100,22 40,24 Q200,22 296,10 Z" fill="#eef0f1" />
      <path d="M-10,-54 L-50,-140 L50,-58 Z" fill={color} />
      <path d="M60,34 L10,96 L110,40 Z" fill={color} opacity={0.9} />
      {[0, 1, 2, 3, 4].map((i) => <path key={i} d={`M${150 - i * 12},-14 q-6,16 0,30`} stroke="#3c464d" strokeWidth={2.5} fill="none" />)}
      <circle cx={238} cy={-12} r={5} fill="#0b0d0f" />
      <path d="M300,14 Q270,24 230,22" stroke="#3c464d" strokeWidth={3} fill="none" />
    </g>
  );
};

export const Anglerfish: React.FC<CreatureProps> = ({t, color = '#2a2420'}) => {
  const glow = 0.65 + sw(t, 3, 0.35);
  const lx = 210 + sw(t, 1.2, 8), ly = -175 + sw(t, 1.5, 6);
  return (
    <g>
      <defs>
        <radialGradient id="lure"><stop offset="0%" stopColor="#fffbd6" /><stop offset="35%" stopColor="#bff7ff" stopOpacity={0.9} /><stop offset="100%" stopColor="#5fe0ff" stopOpacity={0} /></radialGradient>
      </defs>
      <g transform={`rotate(${sw(t, 2, 10)} -150 0)`}><path d="M-150,0 L-250,-70 Q-235,0 -250,70 Z" fill={color} /></g>
      <path d="M-160,0 Q-150,-120 20,-130 Q170,-128 230,-40 L240,40 Q170,120 20,120 Q-150,110 -160,0 Z" fill={color} />
      <path d="M230,-40 Q120,0 240,40" fill="#120e0c" />
      {Array.from({length: 9}).map((_, i) => <path key={i} d={`M${150 + i * 10},${-26 + i * 1.5} l4,22 l4,-22`} fill="#eee6d6" />)}
      {Array.from({length: 8}).map((_, i) => <path key={`b${i}`} d={`M${155 + i * 10},${30 - i * 1.2} l4,-20 l4,20`} fill="#eee6d6" />)}
      <circle cx={110} cy={-60} r={10} fill="#0a0a0a" stroke="#4a3f38" strokeWidth={3} />
      <path d={`M70,-120 Q120,-210 ${lx},${ly}`} stroke={color} strokeWidth={6} fill="none" />
      <circle cx={lx} cy={ly} r={70} fill="url(#lure)" opacity={glow} />
      <circle cx={lx} cy={ly} r={12} fill="#fffde8" />
      <path d="M-20,90 Q20,150 80,110" fill={color} />
    </g>
  );
};

export const Jellyfish: React.FC<CreatureProps> = ({t, color = '#9fd8ff'}) => {
  const p = sw(t, 2.2, 1);
  return (
    <g>
      <defs><radialGradient id="jelly" cx="50%" cy="40%"><stop offset="0%" stopColor="#fff" stopOpacity={0.8} /><stop offset="100%" stopColor={color} stopOpacity={0.35} /></radialGradient></defs>
      {Array.from({length: 7}).map((_, i) => {
        const x = -60 + i * 20;
        return <path key={i} d={`M${x},10 C${x + Math.sin(t * 2 + i) * 20},90 ${x - Math.sin(t * 2 + i) * 20},170 ${x + Math.sin(t * 1.5 + i) * 25},${240 + i * 8}`} stroke={color} strokeOpacity={0.6} strokeWidth={3} fill="none" />;
      })}
      <path d={`M${-90 - p * 8},10 Q${-90 - p * 8},${-100 - p * 6} 0,${-100 - p * 6} Q${90 + p * 8},${-100 - p * 6} ${90 + p * 8},10 Q0,${-10 + p * 6} ${-90 - p * 8},10 Z`} fill="url(#jelly)" />
      <circle cx={0} cy={-40} r={80} fill={color} opacity={0.12} />
    </g>
  );
};

export const Diver: React.FC<CreatureProps> = ({t, color = '#2c3640'}) => {
  const k = sw(t, 4, 14);
  return (
    <g>
      <g transform={`rotate(${k} -120 10)`}><path d="M-120,4 L-215,-22 L-210,8 Z" fill="#f2c230" /></g>
      <g transform={`rotate(${-k} -120 18)`}><path d="M-120,14 L-215,30 L-205,52 Z" fill="#e0b020" /></g>
      <path d="M-125,0 Q-60,-14 60,-12 Q110,-10 130,8 Q110,26 60,24 Q-60,28 -125,20 Z" fill={color} />
      <rect x={-50} y={-44} width={130} height={30} rx={15} fill="#eef2f4" />
      <rect x={-20} y={2} width={70} height={5} fill="#46b4c9" />
      <circle cx={150} cy={4} r={22} fill={color} />
      <rect x={154} y={-8} width={20} height={14} rx={4} fill="#7fd4e6" />
      <path d={`M100,18 Q150,${40 + sw(t, 2, 6)} 200,${30 + sw(t, 2, 6)}`} stroke={color} strokeWidth={12} strokeLinecap="round" fill="none" />
      <rect x={196} y={24 + sw(t, 2, 6)} width={22} height={12} rx={4} fill="#e9eef0" />
    </g>
  );
};

export const FishSchool: React.FC<CreatureProps> = ({t, color = '#9cc9d8', detail = {}}) => {
  const n = Number(detail.count ?? 40);
  return (
    <g>
      {Array.from({length: n}).map((_, i) => {
        const a = (i * 2.39996) % (Math.PI * 2);
        const r = 30 + ((i * 53) % 220);
        const x = Math.cos(a) * r * 1.4 + Math.sin(t * 1.3 + i) * 10;
        const y = Math.sin(a) * r * 0.5 + Math.cos(t * 1.1 + i) * 8;
        const w = 4 + (i % 3);
        return <path key={i} d={`M${x + 18},${y} Q${x + 6},${y - w} ${x - 8},${y} L${x - 16},${y - w} L${x - 14},${y} L${x - 16},${y + w} L${x - 8},${y} Q${x + 6},${y + w} ${x + 18},${y} Z`} fill={color} opacity={0.85} />;
      })}
    </g>
  );
};

export const Octopus: React.FC<CreatureProps> = ({t, color = '#b0553f'}) => (
  <g>
    {Array.from({length: 8}).map((_, i) => {
      const x0 = -60 + i * 17, ph = t * 2 + i;
      return <path key={i} d={`M${x0},40 C${x0 + Math.sin(ph) * 40},120 ${x0 - Math.sin(ph + 1) * 50},180 ${x0 + Math.sin(ph + 2) * 60},${230 + (i % 3) * 20}`} stroke={color} strokeWidth={16 - (i % 2) * 3} strokeLinecap="round" fill="none" />;
    })}
    <ellipse cx={0} cy={-40} rx={95} ry={110 + sw(t, 2, 6)} fill={color} />
    <circle cx={-35} cy={10} r={16} fill="#f0e6d8" /><circle cx={35} cy={10} r={16} fill="#f0e6d8" />
    <rect x={-43} y={6} width={16} height={6} fill="#1a1a1a" /><rect x={27} y={6} width={16} height={6} fill="#1a1a1a" />
  </g>
);

export const CREATURES: Record<string, React.FC<CreatureProps>> = {
  spermWhale: SpermWhale, giantSquid: GiantSquid, orca: Orca, shark: Shark, anglerfish: Anglerfish,
  jellyfish: Jellyfish, diver: Diver, fishSchool: FishSchool, octopus: Octopus,
};

/** Horizontal drawing extent [left, right] in local units, used to keep creatures clear of text panels. */
export const EXTENTS: Record<string, [number, number]> = {
  spermWhale: [-320, 300], giantSquid: [-300, 495], orca: [-305, 292], shark: [-300, 302], anglerfish: [-250, 290],
  jellyfish: [-100, 100], diver: [-215, 222], fishSchool: [-330, 330], octopus: [-100, 100],
};
