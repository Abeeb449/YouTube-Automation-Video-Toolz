import React from 'react';
import {Thumbnail} from './Thumbnail';
import {ThumbnailNoir} from './ThumbnailNoir';
import {CalculateMetadataFunction, Composition, Folder} from 'remotion';
import {BaseProps} from './theme';
import {TitleCard} from './TitleCard';
import {KineticText} from './KineticText';
import {BulletList} from './BulletList';
import {BigNumber} from './BigNumber';
import {Quote} from './Quote';
import {MapScene} from './docu/MapScene';
import {Meter, OceanScene, Sonar} from './ocean/scenes';
import {Globe} from './docu/Globe';
import {Horizon} from './docu/Horizon';
import {PhotoStory} from './motion/PhotoStory';
import {Anatomy} from './motion/Anatomy';
import {ClipCard, DateStamp} from './motion/ClipCard';
import {BarCompare, Clock, Counter, DotGrid, Equation, Radius, SourceList, SplitCompare, Statement, StatCards} from './docu/data';

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

// Minimal neutral values for required props, so a scene that forgets one renders instead of crashing.
const SAFE: Record<string, Record<string, unknown>> = {
  OceanScene: {},
  Meter: {to: 0},
  Sonar: {blips: []},
  TitleCard: {title: ''},
  KineticText: {text: ''},
  BulletList: {title: '', items: []},
  BigNumber: {value: 0},
  Quote: {quote: ''},
  Globe: {to: [0, 20]},
  Counter: {to: 0},
  StatCards: {cards: []},
  DotGrid: {count: 0},
  BarCompare: {bars: []},
  SourceList: {tag: '', rows: []},
  Clock: {seconds: 0},
  Equation: {lines: []},
  SplitCompare: {left: {title: ''}, right: {title: ''}},
  Statement: {line1: ''},
  Radius: {rings: []},
  PhotoStory: {photos: []},
  Anatomy: {},
  ClipCard: {lines: []},
  DateStamp: {date: ''},
};

const DEMOS: Record<string, Record<string, unknown>> = {
  OceanScene: {depth: 0.5, title: 'Biggest predator with teeth', actors: [{creature: 'spermWhale', x: 0.4, y: 0.55, to: [0.45, 0.55], scale: 1.3, detail: {teeth: true}},
    {creature: 'diver', x: 0.85, y: 0.4, scale: 0.35, flip: true, target: {at: 2}}], facts: [{text: 'Biggest predator with teeth, ever'}, {text: 'Sank a ship on purpose', red: true}],
    scaleBar: {x1: 0.16, x2: 0.62, y: 0.78, label: '~16 M'}},
  Polar: {split: {y: 0.36, land: 'rocks'}, actors: [{creature: 'seaLion', x: 0.16, y: 0.25, scale: 0.4, detail: {rest: true}},
    {creature: 'penguin', x: 0.3, y: 0.27, scale: 0.12, detail: {stand: true}}, {creature: 'leopardSeal', x: 0.62, y: 0.7, scale: 1.1}],
    title: 'The ice edge'},
  Meter: {title: 'Loudest animal on Earth', to: 236, unit: 'dB', note: 'measured underwater', footnote: 'Can carry tens of kilometres'},
  Sonar: {title: 'Echolocation', blips: [{label: 'Squid', x: 0.35, y: 0.4, creature: 'giantSquid'}, {label: 'You', x: 0.7, y: 0.3, creature: 'diver', color: '#e5372f'}, {label: 'Fish', x: 0.5, y: 0.62, creature: 'fishSchool'}]},
  TitleCard: {title: 'Your Video Title', subtitle: 'A subtitle goes here', kicker: 'Episode 1'},
  KineticText: {text: 'Every word appears as the narrator speaks it', highlight: ['narrator']},
  BulletList: {title: 'Three key ideas', items: ['First idea', 'Second idea', 'Third idea']},
  BigNumber: {value: 1000000, suffix: '+', label: 'views in the first month'},
  Quote: {quote: 'The best time to start was yesterday. The next best time is now.', author: 'Proverb'},
  Horizon: {title: 'Central Ukraine', subtitle: 'Military airfield · Day one', events: [{type: 'fireball', at: 2}], hud: {label: 'Local time', clock: 15120, format: 'time'}},
  MapScene: {focus: ['Ukraine', 'Belarus'], countryLabels: ['Ukraine', 'Belarus', {name: 'Russia', lon: 36, lat: 53.5}], title: '24 February 2022', subtitle: 'Full-scale invasion',
        cities: [{name: 'Kyiv', lon: 30.52, lat: 50.45}, {name: 'Minsk', lon: 27.56, lat: 53.9}], arrows: [{from: [27.56, 53.9], to: [30.52, 50.45]}], highlight: ['Belarus']},
  Globe: {from: [100, 10], to: [129.87, 32.75], title: '9 August 1945', subtitle: 'Last nuclear weapon used in war', marker: {label: 'Nagasaki'}},
  Counter: {from: 0, to: 81, label: 'Years without a nuclear strike', timeline: {start: 1945, end: 2026, tickEvery: 10, events: [{year: 1962, label: 'Cuban missile crisis'}]}},
  StatCards: {heading: 'New START', subheading: 'Last US-Russia arms-control treaty', cards: [{label: 'Deployed warheads · limit', value: '1,550', bar: 0.8}, {label: 'Launchers · limit', value: '700', bar: 0.5}], stamp: {text: 'Expired'}},
  DotGrid: {value: '1,500', label: 'Tactical nuclear warheads', note: 'Estimate', count: 1500},
  BarCompare: {heading: 'The math', headingColor: 'teal', bars: [{label: 'Hiroshima · 1945', value: 15}, {label: 'Our simulation', value: 10}], unit: 'kt'},
  SourceList: {tag: 'Simulation', tagNote: 'But nothing in it is made up', rows: [{title: 'Real weapons tests', source: 'Hiroshima · Nagasaki · 2,000+ tests'}, {title: 'Real arsenals', source: 'FAS 2025'}]},
  Clock: {seconds: 85, value: '85', label: 'Seconds to midnight', series: [7, 3, 12, 17, 9, 2, 1.5], seriesLabel: 'Minutes to midnight'},
  Equation: {heading: 'The math', lines: [{text: 'Hiroshima ≈ 15 kt'}, {text: '= 15,000 t of TNT'}, {text: 'E = mc^2'}, {text: 'm ≈ 0.7 gram'}]},
  SplitCompare: {left: {title: 'Airburst', subtitle: 'Fireball never touches the ground', footer: 'Little local fallout', orb: true}, right: {title: 'Ground burst', subtitle: 'Scoops up tonnes of soil', footer: 'Heavy fallout', color: '#e5372f', orb: true}},
  Statement: {kicker2: 'Military analysts call it', line1: 'Escalate to', line2: 'de-escalate', footnote: 'One small bomb · to shock the enemy into giving up'},
  Radius: {heading: 'Ground zero', subheading: 'Airburst · 500 m · 10 kt', rings: [{km: 1.5, label: 'Heat', detail: 'Severe burns outdoors'}, {km: 4, label: 'Blast', detail: 'Windows shatter'}]},
};

const common = {fps: 30, width: 1920, height: 1080, durationInFrames: 150, calculateMetadata: metadata} as const;

export const Root: React.FC = () => (
  <>
    <Composition id="Thumbnail" component={Thumbnail as React.FC<any>} fps={30} width={1280} height={720} durationInFrames={1}
      defaultProps={{headline: 'YOUR|HEADLINE', accent: 'HEADLINE', actors: []}} />
    <Composition id="ThumbnailNoir" component={ThumbnailNoir as React.FC<any>} fps={30} width={1280} height={720} durationInFrames={1}
      defaultProps={{headline: 'YOUR|HEADLINE', accent: 'HEADLINE', images: []}} />
    <Composition id="TitleCard" component={TitleCard as React.FC<any>} {...common} defaultProps={SAFE.TitleCard ?? {}} />
    <Composition id="KineticText" component={KineticText as React.FC<any>} {...common} defaultProps={SAFE.KineticText ?? {}} />
    <Composition id="BulletList" component={BulletList as React.FC<any>} {...common} defaultProps={SAFE.BulletList ?? {}} />
    <Composition id="BigNumber" component={BigNumber as React.FC<any>} {...common} defaultProps={SAFE.BigNumber ?? {}} />
    <Composition id="Quote" component={Quote as React.FC<any>} {...common} defaultProps={SAFE.Quote ?? {}} />

    {/* ---- What-if documentary kit (see .claude/skills/whatif-documentary) ----
         Production compositions have NO demo defaults: Remotion merges defaultProps into every
         render, so demo text would leak into real videos. Demos live in the "Demos" folder. */}
    <Composition id="Horizon" component={Horizon as React.FC<any>} {...common} defaultProps={SAFE.Horizon ?? {}} />
    <Composition id="MapScene" component={MapScene as React.FC<any>} {...common} defaultProps={SAFE.MapScene ?? {}} />
    <Composition id="Globe" component={Globe as React.FC<any>} {...common} defaultProps={SAFE.Globe ?? {}} />
    <Composition id="Counter" component={Counter as React.FC<any>} {...common} defaultProps={SAFE.Counter ?? {}} />
    <Composition id="StatCards" component={StatCards as React.FC<any>} {...common} defaultProps={SAFE.StatCards ?? {}} />
    <Composition id="DotGrid" component={DotGrid as React.FC<any>} {...common} defaultProps={SAFE.DotGrid ?? {}} />
    <Composition id="BarCompare" component={BarCompare as React.FC<any>} {...common} defaultProps={SAFE.BarCompare ?? {}} />
    <Composition id="SourceList" component={SourceList as React.FC<any>} {...common} defaultProps={SAFE.SourceList ?? {}} />
    <Composition id="Clock" component={Clock as React.FC<any>} {...common} defaultProps={SAFE.Clock ?? {}} />
    <Composition id="Equation" component={Equation as React.FC<any>} {...common} defaultProps={SAFE.Equation ?? {}} />
    <Composition id="SplitCompare" component={SplitCompare as React.FC<any>} {...common} defaultProps={SAFE.SplitCompare ?? {}} />
    <Composition id="Statement" component={Statement as React.FC<any>} {...common} defaultProps={SAFE.Statement ?? {}} />
    <Composition id="Radius" component={Radius as React.FC<any>} {...common} defaultProps={SAFE.Radius ?? {}} />
    {/* ---- Ocean / animal documentary kit ---- */}
    <Composition id="OceanScene" component={OceanScene as React.FC<any>} {...common} defaultProps={SAFE.OceanScene} />
    <Composition id="Meter" component={Meter as React.FC<any>} {...common} defaultProps={SAFE.Meter} />
    <Composition id="Sonar" component={Sonar as React.FC<any>} {...common} defaultProps={SAFE.Sonar} />
    <Composition id="PhotoStory" component={PhotoStory as React.FC<any>} {...common} defaultProps={SAFE.PhotoStory} />
    <Composition id="Anatomy" component={Anatomy as React.FC<any>} {...common} defaultProps={SAFE.Anatomy} />
    <Composition id="ClipCard" component={ClipCard as React.FC<any>} {...common} defaultProps={SAFE.ClipCard} />
    <Composition id="DateStamp" component={DateStamp as React.FC<any>} {...common} defaultProps={SAFE.DateStamp} />
    <Folder name="Demos">
      <Composition id="Demo-OceanScene" component={OceanScene as React.FC<any>} {...common} defaultProps={DEMOS.OceanScene} />
      <Composition id="Demo-Polar" component={OceanScene as React.FC<any>} {...common} defaultProps={DEMOS.Polar} />
      <Composition id="Demo-Meter" component={Meter as React.FC<any>} {...common} defaultProps={DEMOS.Meter} />
      <Composition id="Demo-Sonar" component={Sonar as React.FC<any>} {...common} defaultProps={DEMOS.Sonar} />
      <Composition id="Demo-TitleCard" component={TitleCard as React.FC<any>} {...common} defaultProps={DEMOS.TitleCard} />
      <Composition id="Demo-KineticText" component={KineticText as React.FC<any>} {...common} defaultProps={DEMOS.KineticText} />
      <Composition id="Demo-BulletList" component={BulletList as React.FC<any>} {...common} defaultProps={DEMOS.BulletList} />
      <Composition id="Demo-BigNumber" component={BigNumber as React.FC<any>} {...common} defaultProps={DEMOS.BigNumber} />
      <Composition id="Demo-Quote" component={Quote as React.FC<any>} {...common} defaultProps={DEMOS.Quote} />
      <Composition id="Demo-Horizon" component={Horizon as React.FC<any>} {...common} defaultProps={DEMOS.Horizon} />
      <Composition id="Demo-MapScene" component={MapScene as React.FC<any>} {...common} defaultProps={DEMOS.MapScene} />
      <Composition id="Demo-Globe" component={Globe as React.FC<any>} {...common} defaultProps={DEMOS.Globe} />
      <Composition id="Demo-Counter" component={Counter as React.FC<any>} {...common} defaultProps={DEMOS.Counter} />
      <Composition id="Demo-StatCards" component={StatCards as React.FC<any>} {...common} defaultProps={DEMOS.StatCards} />
      <Composition id="Demo-DotGrid" component={DotGrid as React.FC<any>} {...common} defaultProps={DEMOS.DotGrid} />
      <Composition id="Demo-BarCompare" component={BarCompare as React.FC<any>} {...common} defaultProps={DEMOS.BarCompare} />
      <Composition id="Demo-SourceList" component={SourceList as React.FC<any>} {...common} defaultProps={DEMOS.SourceList} />
      <Composition id="Demo-Clock" component={Clock as React.FC<any>} {...common} defaultProps={DEMOS.Clock} />
      <Composition id="Demo-Equation" component={Equation as React.FC<any>} {...common} defaultProps={DEMOS.Equation} />
      <Composition id="Demo-SplitCompare" component={SplitCompare as React.FC<any>} {...common} defaultProps={DEMOS.SplitCompare} />
      <Composition id="Demo-Statement" component={Statement as React.FC<any>} {...common} defaultProps={DEMOS.Statement} />
      <Composition id="Demo-Radius" component={Radius as React.FC<any>} {...common} defaultProps={DEMOS.Radius} />
    </Folder>
  </>
);
