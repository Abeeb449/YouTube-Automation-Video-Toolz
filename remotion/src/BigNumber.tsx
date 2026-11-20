import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {Background, BaseProps, useSceneOpacity, useTheme} from './theme';

export type BigNumberProps = BaseProps & {value: number; prefix?: string; suffix?: string; label?: string; decimals?: number};

export const BigNumber: React.FC<BigNumberProps> = ({value, prefix = '', suffix = '', label, decimals = 0, theme: t}) => {
  const theme = useTheme(t);
  const frame = useCurrentFrame();
  const {fps, durationInFrames, width} = useVideoConfig();
  const opacity = useSceneOpacity();
  const s = width / 1920;
  const countFrames = Math.min(durationInFrames * 0.6, fps * 2.5);
  const current = interpolate(frame, [0, countFrames], [0, value], {
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const lab = spring({frame: frame - countFrames * 0.5, fps, config: {damping: 200}});
  return (
    <AbsoluteFill style={{opacity, fontFamily: theme.font, color: theme.text}}>
      <Background theme={theme} />
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
        <div style={{fontSize: 260 * s, fontWeight: 900, color: theme.accent, fontVariantNumeric: 'tabular-nums'}}>
          {prefix}
          {current.toLocaleString('en-US', {minimumFractionDigits: decimals, maximumFractionDigits: decimals})}
          {suffix}
        </div>
        {label ? <div style={{fontSize: 64 * s, opacity: lab, marginTop: 20 * s, textAlign: 'center', maxWidth: 1500 * s}}>{label}</div> : null}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
