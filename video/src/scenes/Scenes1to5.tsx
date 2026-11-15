import React from 'react';
import {AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {data} from '../data';
import {C, monoFont} from '../theme';
import {Appear, Arrow, Badge, Box, Footage, Line, Photo, Title, Typewriter, Value} from '../components/ui';
import {CoverageMap, LayoutMap, coverageCounts} from '../components/CoverageMap';

const n = data.numbers;
const f = data.facts;

// ── Scene 1: cold open. Real footage with our own live voices; no narration. ──
export const ColdOpen: React.FC = () => (
  <AbsoluteFill style={{background: C.bg}}>
    <Footage id="a1" label="wide: six bricks scattered, plates at odd spots, the arm picks one" startFrom={f.run_take.footage_offset_s} />
    <Badge text="Autonomous · 1×" />
    <div style={{position: 'absolute', left: 48, bottom: 40}}>
      <Line size={28} colour={C.dim}>
        Jenssenit · Intel Physical AI Challenge, Junction 2026
      </Line>
    </div>
  </AbsoluteFill>
);

// ── Scene 2: the task. Setup at 4×, the random draw, the spec list. ──
const SPEC: [string, string][] = [
  ['Bricks', 'variable count'],
  ['Positions', 'random'],
  ['Plates', 'movable'],
  ['Coordinates in code', 'none'],
];

export const Task: React.FC = () => (
  <AbsoluteFill style={{background: C.bg, flexDirection: 'row'}}>
    <div style={{width: 1100, height: '100%', position: 'relative'}}>
      <Footage id="a4" label="a round being set up from the random draw (4×)" speed={4} volume={0} />
      <Badge text="Setup · 4×" corner="tl" />
      <div style={{position: 'absolute', left: 40, bottom: 40}}>
        <LayoutMap size={300} delay={0.5} />
      </div>
    </div>
    <div style={{flex: 1, padding: '160px 64px', display: 'flex', flexDirection: 'column', gap: 30}}>
      <Appear delay={0.3}>
        <Title size={44}>The task</Title>
      </Appear>
      {SPEC.map(([k, v], i) => (
        <Appear key={k} delay={1.2 + i * 1.6}>
          <div style={{display: 'flex', justifyContent: 'space-between', borderBottom: `1px solid ${C.line}`, paddingBottom: 12}}>
            <Line colour={C.dim}>{k}</Line>
            <Line mono colour={i === 3 ? C.good : C.text}>
              {v}
            </Line>
          </div>
        </Appear>
      ))}
    </div>
  </AbsoluteFill>
);

// ── Scene 3: the policy. Inputs → SmolVLA → action chunk; then where the training data was. ──
const INPUTS = ['Top camera', 'Wrist camera', 'Joint state', `Task: "${f.sentences.pick}"`];
const MAP_AT = 7.5; // s: the diagram gives way to the coverage map

export const Policy: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const glow = interpolate(frame, [3 * fps, 4 * fps], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const diagramOut = interpolate(frame, [(MAP_AT - 0.4) * fps, MAP_AT * fps], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: C.bg, flexDirection: 'row'}}>
      <div style={{width: 760, height: '100%', position: 'relative'}}>
        <Footage id="a1" label="the arm picking a brick" volume={0.25} />
      </div>
      <div style={{flex: 1, position: 'relative'}}>
        <Sequence durationInFrames={Math.round(MAP_AT * fps)}>
          <AbsoluteFill style={{padding: '150px 60px', display: 'flex', flexDirection: 'column', gap: 44, opacity: diagramOut}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 22}}>
              <div style={{display: 'flex', flexDirection: 'column', gap: 12}}>
                {INPUTS.map((label, i) => (
                  <Appear key={label} delay={0.3 + i * 0.5} dy={0}>
                    <Box style={{padding: '10px 16px'}}>
                      <Line size={24} mono={i === 3}>
                        {label}
                      </Line>
                    </Box>
                  </Appear>
                ))}
              </div>
              <Appear delay={2.4} dy={0}>
                <Arrow />
              </Appear>
              <Appear delay={2.8} dy={0}>
                <Box colour={C.stage} style={{boxShadow: `0 0 ${36 * glow}px ${C.stage}88`, padding: '26px 30px'}}>
                  <Title size={40}>SmolVLA</Title>
                  <Line size={22} colour={C.dim}>
                    vision-language-action
                  </Line>
                </Box>
              </Appear>
              <Appear delay={3.6} dy={0}>
                <Arrow />
              </Appear>
              <Appear delay={4} dy={0}>
                <Box style={{padding: '16px 18px'}}>
                  <Line size={24} mono>
                    50 joint actions
                  </Line>
                  <Line size={20} colour={C.dim}>
                    per chunk, 30 Hz
                  </Line>
                </Box>
              </Appear>
            </div>
            <Appear delay={5}>
              <Line size={30}>SmolVLA · fine-tuned in Physical AI Studio</Line>
              <Line size={30} colour={C.dim}>
                <Value v={n.EPISODES} name="EPISODES" /> teleoperated episodes: <Value v={n.PICKS} name="PICKS" /> picks,{' '}
                <Value v={n.SORTS} name="SORTS" /> sorts
              </Line>
            </Appear>
          </AbsoluteFill>
        </Sequence>
        <Sequence from={Math.round(MAP_AT * fps)}>
          <AbsoluteFill style={{padding: '60px 60px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16}}>
            <Appear delay={0.1}>
              <Line size={30}>Where the training data grasped and released, from above</Line>
            </Appear>
            <CoverageMap size={760} delay={0.4} />
            <Appear delay={2.4}>
              <Line size={24} colour={C.dim}>
                {coverageCounts.grasps} grasps · {coverageCounts.good + coverageCounts.defective} releases · both plates on both sides ·
                forward kinematics, ±a few cm
              </Line>
            </Appear>
          </AbsoluteFill>
        </Sequence>
      </div>
    </AbsoluteFill>
  );
};

// ── Scene 4: inspection. Fixed pose, three angles, heatmaps, score bands. ──
export const Inspection: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const images = data.run.images.slice(0, 3);
  const bands = data.run.cycles[0]?.inspect?.bands ?? [0.4, 0.6];
  const score = data.run.scores.length ? Math.max(...data.run.scores) : null;
  const marker = interpolate(frame, [7 * fps, 9 * fps], [0, score ?? 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: C.bg, padding: '90px 80px', gap: 40}}>
      <Appear delay={0.2}>
        <Title size={44}>Inspection: the one scripted step</Title>
        <Line colour={C.dim}>Fixed pose, three wrist angles · Anomalib PatchCore, trained on good bricks only</Line>
      </Appear>
      <div style={{display: 'flex', gap: 36, height: 470}}>
        {[0, 1, 2].map((i) => {
          const img = images[i];
          const wipe = interpolate(frame, [(2.5 + i) * fps, (3.5 + i) * fps], [0, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          return (
            <Appear key={i} delay={1 + i * 0.4} style={{flex: 1, position: 'relative', borderRadius: 12, overflow: 'hidden', border: `2px solid ${C.line}`}}>
              <div style={{position: 'relative', width: '100%', height: 470}}>
                {img ? (
                  <>
                    <Photo src={img.photo} />
                    {img.heat && <Photo src={img.heat} style={{position: 'absolute', inset: 0, clipPath: `inset(0 ${100 - wipe}% 0 0)`}} />}
                  </>
                ) : (
                  <Footage id="a2" label={`view ${i + 1} at the show pose`} />
                )}
                <div style={{position: 'absolute', left: 14, top: 12}}>
                  <Line size={22} mono>
                    {['0°', '90°', '180°'][i]}
                  </Line>
                </div>
              </div>
            </Appear>
          );
        })}
      </div>
      <Appear delay={6.5}>
        <div style={{position: 'relative', height: 80}}>
          <div style={{position: 'absolute', top: 30, left: 0, right: 0, height: 20, borderRadius: 10, overflow: 'hidden', display: 'flex'}}>
            <div style={{width: `${bands[0] * 100}%`, background: C.good}} />
            <div style={{width: `${(bands[1] - bands[0]) * 100}%`, background: C.unsure}} />
            <div style={{flex: 1, background: C.defective}} />
          </div>
          <div style={{position: 'absolute', top: 18, left: `${Math.min(marker, 1) * 100}%`, width: 6, height: 44, background: C.text, borderRadius: 3}} />
          <div style={{position: 'absolute', top: 60, left: 0, right: 0, display: 'flex', justifyContent: 'space-between', fontFamily: monoFont, fontSize: 22, color: C.dim}}>
            <span>good</span>
            <span>unsure</span>
            <span>defective</span>
          </div>
          <div style={{position: 'absolute', top: -14, right: 0}}>
            <Line size={24} mono colour={C.dim}>
              <Value v={n.INSPECT_MS} name="INSPECT_MS" digits={0} unit=" ms per view" /> · GPU · OpenVINO
            </Line>
          </div>
        </div>
      </Appear>
    </AbsoluteFill>
  );
};

// ── Scene 5: the verdict becomes the VLA's next task sentence. ──
export const VerdictToVla: React.FC = () => (
  <AbsoluteFill style={{background: C.bg, flexDirection: 'row'}}>
    <div style={{flex: 1, padding: '200px 70px', display: 'flex', flexDirection: 'column', gap: 40}}>
      <Appear delay={0.2}>
        <Line colour={C.dim}>Verdict</Line>
        <Title size={60} colour={C.defective}>
          DEFECTIVE
        </Title>
      </Appear>
      <Appear delay={0.9}>
        <Box colour={C.defective}>
          <Line size={22} colour={C.dim} mono>
            task =
          </Line>
          <Line size={32} mono>
            "<Typewriter text={f.sentences.DEFECTIVE} delay={1.2} seconds={2.4} />"
          </Line>
        </Box>
      </Appear>
      <Appear delay={4} dy={0} style={{display: 'flex', alignItems: 'center', gap: 20}}>
        <Arrow length={90} colour={C.defective} />
        <Box colour={C.stage}>
          <Title size={36}>SmolVLA</Title>
        </Box>
      </Appear>
    </div>
    <div style={{width: 820, height: '100%', position: 'relative'}}>
      <Footage id="a2" label="the arm carrying the brick to the orange plate" volume={0.25} />
    </div>
  </AbsoluteFill>
);
