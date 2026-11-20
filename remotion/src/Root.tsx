import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {BaseProps} from './theme';
import {TitleCard} from './TitleCard';
import {KineticText} from './KineticText';
import {BulletList} from './BulletList';
import {BigNumber} from './BigNumber';
import {Quote} from './Quote';

// ytauto passes durationInSeconds/width/height/fps as input props, so every
// template adapts to the narration length and the project's resolution.
const metadata: CalculateMetadataFunction<BaseProps> = ({props}) => {
  const fps = props.fps ?? 30;
  return {
    fps,
    width: props.width ?? 1920,
    height: props.height ?? 1080,
    durationInFrames: Math.max(1, Math.round((props.durationInSeconds ?? 5) * fps)),
  };
};

const common = {fps: 30, width: 1920, height: 1080, durationInFrames: 150, calculateMetadata: metadata} as const;

export const Root: React.FC = () => (
  <>
    <Composition id="TitleCard" component={TitleCard as React.FC<any>} {...common}
      defaultProps={{title: 'Your Video Title', subtitle: 'A subtitle goes here', kicker: 'Episode 1'}} />
    <Composition id="KineticText" component={KineticText as React.FC<any>} {...common}
      defaultProps={{text: 'Every word appears as the narrator speaks it', highlight: ['narrator']}} />
    <Composition id="BulletList" component={BulletList as React.FC<any>} {...common}
      defaultProps={{title: 'Three key ideas', items: ['First idea', 'Second idea', 'Third idea']}} />
    <Composition id="BigNumber" component={BigNumber as React.FC<any>} {...common}
      defaultProps={{value: 1000000, suffix: '+', label: 'views in the first month'}} />
    <Composition id="Quote" component={Quote as React.FC<any>} {...common}
      defaultProps={{quote: 'The best time to start was yesterday. The next best time is now.', author: 'Proverb'}} />
  </>
);
