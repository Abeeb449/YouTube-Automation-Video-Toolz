/**
 * Shot3D: one live 3D shot. A place (under water, surface, beach, studio, from the air), animals that really swim
 * through it, a camera that really moves, and graphics pinned to the picture that arrive on the narrator's words.
 *
 *   {remotion: Shot3D, props: {
 *      env:    {kind: sea, depth: 0.3},
 *      cast:   [{id: shark, model: greatWhite, length: 4.9, path: [{u: 0, p: [-14, -6, 0]}, {u: 1, p: [10, -5, 3]}]}],
 *      camera: [{u: 0, pos: [0, -5, 14], look: shark}, {u: 1, pos: [3, -4.5, 9], look: shark}],
 *      gfx:    [{type: tag, at: "enemies", anchor: {actor: shark, point: dorsal}, text: "Great white"}]}}
 *
 * Distances are metres; y is up and the sea surface is y = 0. Moments are `at` (seconds, or a word of the narration)
 * or `u` (a share of the shot, 0..1). ytauto fills in `models` (the 3D files of the animals named in `cast`).
 */
import React, {useEffect, useLayoutEffect, useMemo, useRef, useState} from 'react';
import {AbsoluteFill, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import * as THREE from 'three';
import {BaseProps} from '../theme';
import {Actor, ActorSpec, loadModels, Loaded, ModelRef} from './creatures';
import {Anchor, Ctx, Gfx, GfxLayer} from './gfx';
import {clamp, ease, Key, keyTime, noise1, ramp, track, V3} from './math';
import {buildEnv, Env, EnvSpec} from './world';
import {buildGlobe, buildMap, GeoEnv, MapSpec} from './mapworld';
import {buildProp, Prop, PropSpec} from './props';

export type CamKey = {
  at?: number; u?: number;
  /** where the camera is; with `rel` it is measured from that animal */
  pos?: V3; rel?: string;
  /** map and globe shots: the place looked at [lon, lat], from how far, how steeply (90 = straight down) and from which compass bearing */
  over?: [number, number]; dist?: number; tilt?: number; bearing?: number;
  /** what it looks at: a point, or an animal's id (optionally one of its named points) */
  look?: V3 | string; point?: string;
  fov?: number; ease?: string; cut?: boolean;
};

export type Shot3DProps = BaseProps & {
  env?: EnvSpec & {map?: MapSpec};
  /** things that are not animals: boat, island, net, denticles, teeth, spray, longline */
  props?: PropSpec[];
  models?: Record<string, ModelRef>;
  cast?: ActorSpec[];
  camera?: CamKey[];
  gfx?: Gfx[];
  /** hand-held life in the camera, 0 = locked off */
  shake?: number;
  /** how the shot opens and closes: cut (default) · fade · dip (through dark water) */
  enter?: 'cut' | 'fade' | 'dip';
  exit?: 'cut' | 'fade' | 'dip';
  /** letterbox bars (a wide, film-like frame) */
  bars?: boolean;
};

const FONTS: [string, string, string, string][] = [
  ['Montserrat', '900', 'normal', 'fonts/montserrat-900.woff2'],
  ['Montserrat', '800', 'normal', 'fonts/montserrat-800.woff2'],
  ['Anton', '400', 'normal', 'fonts/anton.woff2'],
];

type World = {env: Env; actors: Record<string, Actor>; things: Record<string, Prop>; camera: THREE.PerspectiveCamera; renderer: THREE.WebGLRenderer};

export const Shot3D: React.FC<Shot3DProps> = (props) => {
  const frame = useCurrentFrame();
  const {width, height, fps, durationInFrames} = useVideoConfig();
  const dur = durationInFrames / fps;
  const t = frame / fps;
  const canvas = useRef<HTMLCanvasElement>(null);
  const [world, setWorld] = useState<World | null>(null);
  const [handle] = useState(() => delayRender('3D stage', {timeoutInMilliseconds: 120000}));
  const released = useRef(false);

  useEffect(() => {
    let dead = false;
    (async () => {
      const fonts = Promise.all(FONTS.map(([fam, wt, st, file]) => new FontFace(fam, `url(${staticFile(file)})`, {weight: wt, style: st}).load().then((f) => (document as any).fonts.add(f)).catch(() => undefined)));
      const renderer = new THREE.WebGLRenderer({canvas: canvas.current!, antialias: true, preserveDrawingBuffer: true, powerPreference: 'high-performance'});
      renderer.setPixelRatio(1);
      renderer.setSize(width, height, false);
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      const es: any = {...(props.env ?? {}), __dur: dur, __size: props.env?.kind === 'globe' ? 0.55 : 1.6};
      const env: Env = es.kind === 'map' ? buildMap(es) : es.kind === 'globe' ? buildGlobe(es) : buildEnv(es);
      renderer.toneMappingExposure = env.exposure;
      renderer.localClippingEnabled = true;
      const things: Record<string, Prop> = {};
      for (const ps of props.props ?? []) {
        const pr = buildProp(ps, env, dur);
        env.scene.add(pr.group);
        things[ps.id] = pr;
      }
      const loaded: Record<string, Loaded> = await loadModels(props.models ?? {}, (p) => staticFile(p));
      await fonts;
      const actors: Record<string, Actor> = {};
      for (const spec of props.cast ?? []) {
        const model = loaded[spec.model];
        if (!model) continue;
        const a = new Actor(spec, model, env, dur);
        env.scene.add(a.group);
        actors[spec.id] = a;
      }
      const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 2000);
      if (dead) return;
      // compile every material before the first frame is asked for
      renderer.compile(env.scene, camera);
      setWorld({env, actors, things, camera, renderer});
    })().catch((err) => { console.error(err); throw err; });
    return () => { dead = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // everything in the shot at this moment (a pure function of the frame)
  const ctx: Ctx | null = useMemo(() => {
    if (!world) return null;
    const {env, actors, things, camera} = world;
    for (const a of Object.values(actors)) a.update(t);
    for (const th of Object.values(things)) th.update(t);
    const genv = env as GeoEnv;
    const keysSpec: CamKey[] = props.camera?.length ? props.camera : [{u: 0, pos: [0, -4, 16] as V3}];
    const keys: Key<number[]>[] = keysSpec.map((k, i) => {
      const rel = k.rel ? (actors[k.rel]?.group.position ?? things[k.rel]?.group.position) : undefined;
      const kp = k.pos ?? [0, 0, 0];
      let pos = [kp[0] + (rel?.x ?? 0), kp[1] + (rel?.y ?? 0), kp[2] + (rel?.z ?? 0)];
      let look: number[] = [0, pos[1], 0];
      if (k.over && genv.view) {
        const v = genv.view(k.over, k.dist ?? 60, k.tilt ?? 55, k.bearing ?? 0);
        pos = [v.pos.x, v.pos.y, v.pos.z];
        look = [v.look.x, v.look.y, v.look.z];
      } else if (typeof k.look === 'string') {
        const a = actors[k.look];
        const th = things[k.look];
        if (a) { const p = k.point ? a.point(k.point) : a.group.position; look = [p.x, p.y, p.z]; }
        else if (th) { const p = th.group.position; look = [p.x, p.y, p.z]; }
      } else if (k.look) look = k.look;
      return {t: keyTime(k, dur, (i / Math.max(1, keysSpec.length - 1)) * dur), v: [...pos, ...look, k.fov ?? 38], ease: k.ease, cut: k.cut};
    }).sort((a, b) => a.t - b.t);
    const v = track(keys, t);
    const sh = props.shake ?? 1;
    camera.position.set(v[0] + noise1(t * 0.35, 1) * 0.07 * sh, v[1] + noise1(t * 0.42, 2) * 0.06 * sh, v[2] + noise1(t * 0.3, 3) * 0.07 * sh);
    camera.fov = v[6];
    camera.up.set(noise1(t * 0.2, 7) * 0.012 * sh, 1, 0);
    camera.lookAt(v[3] + noise1(t * 0.5, 4) * 0.05 * sh, v[4] + noise1(t * 0.46, 5) * 0.04 * sh, v[5]);
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld(true);
    env.update(t, camera);
    const shadows = (env as any).shadows as undefined | ((l: number[][]) => void);
    if (shadows) shadows(Object.values(actors).filter((a) => a.group.visible && a.group.position.y < a.spec.length * 0.5).map((a) => a.footprint()));
    const proj = new THREE.Vector3();
    const s = width / 1920;
    const at = (a: Anchor | undefined) => {
      if (!a) return {x: width / 2, y: height / 2, ok: true};
      if (a.screen) return {x: a.screen[0] * width, y: a.screen[1] * height, ok: true};
      if (a.actor) { const ac = actors[a.actor]; if (!ac || !ac.group.visible) return {x: 0, y: 0, ok: false}; proj.copy(ac.point(a.point)); }
      else if (a.prop) {
        const th = things[a.prop];
        if (!th) return {x: 0, y: 0, ok: false};
        const lp = (typeof a.point === 'string' ? th.points[a.point] : a.point) ?? [0, 0, 0];
        proj.set(lp[0], lp[1], lp[2]);
        th.group.updateMatrixWorld(true);
        proj.applyMatrix4(th.group.matrixWorld);
      }
      else if (a.geo && genv.geo) proj.copy(genv.geo(a.geo[0], a.geo[1], a.h ?? 0));
      else if (a.world) proj.set(a.world[0], a.world[1], a.world[2]);
      proj.project(camera);
      return {x: (proj.x * 0.5 + 0.5) * width, y: (-proj.y * 0.5 + 0.5) * height, ok: proj.z < 1 && proj.z > -1};
    };
    return {t, dur, s, W: width, H: height, at, time: (g) => keyTime(g, dur, 0)};
  }, [world, t, dur, width, height, props.camera, props.shake]);

  useLayoutEffect(() => {
    if (!world || !ctx) return;
    world.renderer.render(world.env.scene, world.camera);
    if (!released.current) { released.current = true; continueRender(handle); }
  }, [world, ctx, handle]);

  const enter = props.enter ?? 'cut';
  const exit = props.exit ?? 'cut';
  let black = 0;
  if (enter !== 'cut') black = Math.max(black, 1 - ramp(t, 0, enter === 'dip' ? 0.5 : 0.7, 'soft'));
  if (exit !== 'cut') black = Math.max(black, ramp(t, dur - (exit === 'dip' ? 0.45 : 0.7), exit === 'dip' ? 0.45 : 0.7, 'soft'));
  const s = width / 1920;
  const under = world?.env.underwater;
  return (
    <AbsoluteFill style={{background: '#02060a'}}>
      <canvas ref={canvas} width={width} height={height} style={{position: 'absolute', width: '100%', height: '100%'}} />
      {/* the lens: darker corners, and under water a little veil of depth */}
      <AbsoluteFill style={{pointerEvents: 'none', background: `radial-gradient(ellipse at 50% 46%, rgba(0,0,0,0) 52%, rgba(0,4,10,${under ? 0.5 : 0.4}) 100%)`}} />
      {ctx && props.gfx?.length ? <GfxLayer items={props.gfx} c={ctx} /> : null}
      {props.bars ? (<>
        <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 62 * s, background: '#000'}} />
        <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 62 * s, background: '#000'}} />
      </>) : null}
      {black > 0 ? <AbsoluteFill style={{background: enter === 'dip' || exit === 'dip' ? `rgba(2,10,18,${ease('soft', clamp(black))})` : `rgba(0,0,0,${clamp(black)})`}} /> : null}
    </AbsoluteFill>
  );
};
