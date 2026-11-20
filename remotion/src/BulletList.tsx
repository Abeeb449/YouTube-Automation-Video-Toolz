import React from 'react';
import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Background, BaseProps, useSceneOpacity, useTheme} from './theme';

export type BulletListProps = BaseProps & {title: string; items: string[]};

export const BulletList: React.FC<BulletListProps> = ({title, items, theme: t}) => {
  const theme = useTheme(t);
  const frame = useCurrentFrame();
  const {fps, durationInFrames, width} = useVideoConfig();
  const opacity = useSceneOpacity();
  const s = width / 1920;
  const step = Math.max(8, (durationInFrames * 0.75) / Math.max(1, items.length + 1));
  const head = spring({frame, fps, config: {damping: 200}});
  return (
    <AbsoluteFill style={{opacity, fontFamily: theme.font, color: theme.text}}>
      <Background theme={theme} />
      <AbsoluteFill style={{padding: `${120 * s}px ${180 * s}px`, justifyContent: 'center'}}>
        <div style={{fontSize: 90 * s, fontWeight: 800, opacity: head, marginBottom: 50 * s}}>{title}</div>
        {items.map((item, i) => {
          const p = spring({frame: frame - (i + 1) * step, fps, config: {damping: 200}});
          return (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                fontSize: 58 * s,
                margin: `${18 * s}px 0`,
                opacity: p,
                transform: `translateX(${(1 - p) * -80 * s}px)`,
              }}
            >
              <div
                style={{
                  minWidth: 70 * s,
                  height: 70 * s,
                  borderRadius: 35 * s,
                  background: theme.accent,
                  color: theme.bg1,
                  fontWeight: 800,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginRight: 36 * s,
                  fontSize: 40 * s,
                }}
              >
                {i + 1}
              </div>
              {item}
            </div>
          );
        })}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
