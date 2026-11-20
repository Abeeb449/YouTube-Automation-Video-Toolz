import React from 'react';
import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig, interpolate} from 'remotion';
import {Background, BaseProps, useSceneOpacity, useTheme} from './theme';

export type TitleCardProps = BaseProps & {title: string; subtitle?: string; kicker?: string};

export const TitleCard: React.FC<TitleCardProps> = ({title, subtitle, kicker, theme: t}) => {
  const theme = useTheme(t);
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const opacity = useSceneOpacity();
  const pop = spring({frame, fps, config: {damping: 14}});
  const sub = spring({frame: frame - 12, fps, config: {damping: 200}});
  const bar = spring({frame: frame - 6, fps, config: {damping: 200}});
  const s = width / 1920;
  return (
    <AbsoluteFill style={{opacity, fontFamily: theme.font, color: theme.text}}>
      <Background theme={theme} />
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', padding: 120 * s}}>
        {kicker ? (
          <div style={{fontSize: 40 * s, letterSpacing: 8 * s, color: theme.accent, textTransform: 'uppercase', opacity: sub, marginBottom: 24 * s}}>
            {kicker}
          </div>
        ) : null}
        <div
          style={{
            fontSize: 130 * s,
            fontWeight: 800,
            textAlign: 'center',
            lineHeight: 1.05,
            transform: `scale(${interpolate(pop, [0, 1], [0.7, 1])})`,
            opacity: pop,
            textShadow: `0 ${8 * s}px ${40 * s}px rgba(0,0,0,0.45)`,
          }}
        >
          {title}
        </div>
        <div style={{height: 10 * s, width: 420 * s * bar, background: theme.accent, borderRadius: 10 * s, margin: `${40 * s}px 0`}} />
        {subtitle ? (
          <div style={{fontSize: 56 * s, opacity: sub, transform: `translateY(${(1 - sub) * 40 * s}px)`, textAlign: 'center', maxWidth: 1500 * s}}>
            {subtitle}
          </div>
        ) : null}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
