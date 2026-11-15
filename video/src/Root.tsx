import React from 'react';
import {AbsoluteFill, Audio, Composition, Sequence, Still, staticFile} from 'remotion';
import {FPS, SCENES, SceneId, VO_LEAD_S, sceneFrames, timings, totalFrames} from './data';
import {C} from './theme';
import {Captions, DraftMark} from './components/ui';
import {ColdOpen, Inspection, Policy, Task, VerdictToVla} from './scenes/Scenes1to5';
import {Compute, Results, Run} from './scenes/Scenes6to8';
import {Thumbnail} from './Thumbnail';
import {Deck, SLIDES, SLIDE_FRAMES} from './deck/Deck';

const COMPONENTS: Record<SceneId, React.FC> = {
  s1: ColdOpen,
  s2: Task,
  s3: Policy,
  s4: Inspection,
  s5: VerdictToVla,
  s6: Run,
  s7: Results,
  s8: Compute,
};

const Video: React.FC = () => {
  let from = 0;
  return (
    <AbsoluteFill style={{background: C.bg}}>
      {SCENES.map((scene) => {
        const start = from;
        const frames = sceneFrames(scene.id);
        from += frames;
        const Scene = COMPONENTS[scene.id];
        const vo = scene.vo ? timings.scenes[scene.vo] : undefined;
        return (
          <Sequence key={scene.id} from={start} durationInFrames={frames} name={scene.id}>
            <Scene />
            {vo && (
              <Sequence from={Math.round(VO_LEAD_S * FPS)}>
                <Audio src={staticFile(vo.file)} />
              </Sequence>
            )}
            {scene.vo && <Captions vo={scene.vo} />}
          </Sequence>
        );
      })}
      <DraftMark />
    </AbsoluteFill>
  );
};

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="Jenssenit" component={Video} durationInFrames={totalFrames()} fps={FPS} width={1920} height={1080} />
    <Still id="Thumbnail" component={Thumbnail} width={1280} height={720} />
    <Composition id="Deck" component={Deck} durationInFrames={SLIDES.length * SLIDE_FRAMES} fps={FPS} width={1920} height={1080} />
  </>
);
