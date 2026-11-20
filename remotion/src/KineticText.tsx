import React from 'react';
import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Background, BaseProps, useSceneOpacity, useTheme} from './theme';

export type KineticTextProps = BaseProps & {text: string; highlight?: string[]};

/** Words appear one after another across the scene duration — great for narration-driven scenes. */
export const KineticText: React.FC<KineticTextProps> = ({text, highlight = [], theme: t}) => {
  const theme = useTheme(t);
  const frame = useCurrentFrame();
  const {fps, durationInFrames, width} = useVideoConfig();
  const opacity = useSceneOpacity();
  const s = width / 1920;
  const words = text.split(/\s+/).filter(Boolean);
  // Spread word reveals over the first 80% of the scene.
  const per = Math.max(2, (durationInFrames * 0.8) / Math.max(1, words.length));
  const hl = new Set(highlight.map((w) => w.toLowerCase()));
  const fontSize = (words.length > 40 ? 58 : words.length > 20 ? 74 : 96) * s;
  return (
    <AbsoluteFill style={{opacity, fontFamily: theme.font, color: theme.text}}>
      <Background theme={theme} />
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', padding: 140 * s}}>
        <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: `${16 * s}px ${22 * s}px`, maxWidth: 1600 * s}}>
          {words.map((w, i) => {
            const p = spring({frame: frame - i * per, fps, config: {damping: 200}, durationInFrames: 10});
            const clean = w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
            const isHl = hl.has(clean);
            return (
              <span
                key={i}
                style={{
                  fontSize,
                  fontWeight: isHl ? 800 : 600,
                  color: isHl ? theme.accent : theme.text,
                  opacity: p,
                  transform: `translateY(${(1 - p) * 30 * s}px)`,
                  display: 'inline-block',
                }}
              >
                {w}
              </span>
            );
          })}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
