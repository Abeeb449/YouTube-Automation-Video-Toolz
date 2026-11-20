import React from 'react';
import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Background, BaseProps, useSceneOpacity, useTheme} from './theme';

export type QuoteProps = BaseProps & {quote: string; author?: string};

export const Quote: React.FC<QuoteProps> = ({quote, author, theme: t}) => {
  const theme = useTheme(t);
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const opacity = useSceneOpacity();
  const s = width / 1920;
  const p = spring({frame, fps, config: {damping: 200}});
  const a = spring({frame: frame - 20, fps, config: {damping: 200}});
  return (
    <AbsoluteFill style={{opacity, fontFamily: theme.font, color: theme.text}}>
      <Background theme={theme} />
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', padding: 200 * s}}>
        <div style={{fontSize: 260 * s, lineHeight: 0.6, color: theme.accent, opacity: p}}>“</div>
        <div style={{fontSize: 72 * s, fontStyle: 'italic', textAlign: 'center', opacity: p, transform: `scale(${0.95 + 0.05 * p})`}}>{quote}</div>
        {author ? <div style={{fontSize: 48 * s, marginTop: 50 * s, opacity: a, color: theme.accent}}>— {author}</div> : null}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
