import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

export type Theme = {
  bg1: string;
  bg2: string;
  accent: string;
  text: string;
  font: string;
};

export const defaultTheme: Theme = {
  bg1: '#0f172a',
  bg2: '#1e3a8a',
  accent: '#facc15',
  text: '#ffffff',
  font: 'Inter, "DejaVu Sans", Arial, sans-serif',
};

export type BaseProps = {
  durationInSeconds?: number;
  width?: number;
  height?: number;
  fps?: number;
  theme?: Partial<Theme>;
};

export const useTheme = (theme?: Partial<Theme>): Theme => ({...defaultTheme, ...(theme ?? {})});

/** Slowly drifting gradient background used by every template. */
export const Background: React.FC<{theme: Theme}> = ({theme}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const angle = interpolate(frame, [0, durationInFrames], [120, 160]);
  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(${angle}deg, ${theme.bg1} 0%, ${theme.bg2} 100%)`,
      }}
    />
  );
};

/** Fade the whole scene in and out so cuts are never harsh. */
export const useSceneOpacity = (fadeFrames = 10) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  return interpolate(
    frame,
    [0, fadeFrames, Math.max(fadeFrames + 1, durationInFrames - fadeFrames), durationInFrames],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );
};
