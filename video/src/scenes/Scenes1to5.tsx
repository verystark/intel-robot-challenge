// Scenes 1–5, drawn as screens of the cell's operator HMI (see components/frame.tsx, components/hmi.tsx).
import React from 'react';
import {AbsoluteFill, Loop, Sequence, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {Example, data} from '../data';
import {Appear, Footage, Photo, Typewriter, Value} from '../components/ui';
import {Cam, Frame} from '../components/frame';
import {ArrowDefs, CoveragePlot, Faceplate, H, KV, MONO, Pipe, SANS, Swatch, Tbl, Text} from '../components/hmi';

const n = data.numbers;
const f = data.facts;
const deg = (d: number) => `${d < 0 ? '−' : '+'}${Math.abs(d)}°`;
const LIVE = [
  {k: 'MODE', v: 'AUTO'},
  {k: 'SPEED', v: '1×'},
];

// ── Scene 1: cold open. Real footage with our own live voices; no narration. ──
export const ColdOpen: React.FC = () => (
  <Frame title="OVERVIEW · CAM 04 · SIDE VIEW" fields={LIVE} dark>
    <div style={{position: 'relative', flex: 1}}>
      <Footage id="a1" label="wide: bricks scattered, plates at odd spots, the arm picks one" startFrom={f.run_take.footage_offset_s} />
      <div style={{position: 'absolute', left: 20, bottom: 20, font: `22px ${MONO}`, color: '#fff', background: 'rgba(44,44,44,.9)', border: '1px solid #6a6a6a', padding: '6px 12px'}}>
        JENSSENIT · INTEL PHYSICAL AI CHALLENGE · JUNCTION 2026
      </div>
    </div>
  </Frame>
);

// ── Scene 2: the task. Setup footage at 4×, the specification, the three sentences. ──
const SPEC: [string, string][] = [
  ['BRICKS', 'any number, random positions'],
  ['PLATES · TARGET SURFACE', 'can be moved or swapped'],
  ['COORDINATES IN CODE', 'none'],
  ['DEFECT CHECK', 'every brick, before sorting'],
  ['OPERATOR INPUT', 'none during a run'],
];

export const Task: React.FC = () => (
  <Frame title="TASK" fields={[{k: 'MODE', v: 'SETUP'}, {k: 'SPEED', v: '4×'}]}>
    <Cam title="CAM 04 · SIDE VIEW · SETTING UP" osd="CAM04  4×" style={{width: 1000}}>
      <Footage id="a4" label="bricks and plates being placed (4×)" speed={4} volume={0} />
    </Cam>
    <div style={{flex: 1, display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0}}>
      <Faceplate title="TASK SPECIFICATION" pad={16}>
        {SPEC.map(([k, v], i) => (
          <Appear key={k} delay={0.8 + i * 1.3}>
            <KV size={25} labelW={330} rows={[[k, v]]} />
          </Appear>
        ))}
      </Faceplate>
      <Appear delay={7.5} style={{flex: 1, display: 'flex'}}>
        <Faceplate title="TASK SENTENCES TO THE VLA" hint="exact, as in the training data" grow={1} pad={14}>
          <Tbl
            head={['STAGE', 'SENTENCE']}
            widths="230px 1fr"
            size={20}
            rows={[
              ['Pick', `"${f.sentences.pick}"`],
              [
                <span key="g" style={{display: 'flex', gap: 10, alignItems: 'center'}}>
                  <Swatch colour={H.good} /> Sort, good
                </span>,
                `"${f.sentences.GOOD}"`,
              ],
              [
                <span key="d" style={{display: 'flex', gap: 10, alignItems: 'center'}}>
                  <Swatch colour={H.reject} /> Sort, defective
                </span>,
                `"${f.sentences.DEFECTIVE}"`,
              ],
            ]}
          />
        </Faceplate>
      </Appear>
    </div>
  </Frame>
);

// ── Scene 3: the policy. What it sees (a recorded episode), what it is, where its data was. ──
const MAP_AT = 8; // s: the controller block gives way to the coverage map

export const Policy: React.FC = () => {
  const {fps} = useVideoConfig();
  const policy = f.policy;
  return (
    <Frame title={`POLICY · ${f.models.sort.name.toUpperCase()}`} fields={[{k: 'VLA', v: 'PI0.5'}, {k: 'DEVICE', v: f.models.sort.device}]}>
      <div style={{width: 760, display: 'flex', flexDirection: 'column', gap: 10}}>
        <Cam title="CAM 01 · TOP · POLICY INPUT" osd="CAM01  RECORDED TELEOP EPISODE" style={{flex: 1}}>
          <Loop durationInFrames={Math.round(7.6 * fps)}>
            <Footage id="rec_top" label="recorded teleop episode" volume={0} />
          </Loop>
        </Cam>
        <Cam title="CAM 02 · WRIST · POLICY INPUT" osd="CAM02  RECORDED TELEOP EPISODE" style={{flex: 1}}>
          <Loop durationInFrames={Math.round(7.6 * fps)}>
            <Footage id="rec_wrist" label="recorded teleop episode" volume={0} />
          </Loop>
        </Cam>
      </div>
      <div style={{flex: 1, position: 'relative', minWidth: 0}}>
        <Sequence durationInFrames={Math.round(MAP_AT * fps)}>
          <AbsoluteFill style={{display: 'flex', flexDirection: 'column', gap: 10}}>
            <Faceplate title={`VLA CONTROLLER · ${f.models.sort.name.toUpperCase()} · OPENVINO ${f.models.sort.device}`} pad={0}>
              <svg width={1108} height={330} style={{display: 'block'}}>
                <ArrowDefs />
                {['TOP CAMERA', 'WRIST CAMERA', 'JOINT STATE · J1–J6', 'TASK SENTENCE'].map((label, i) => (
                  <g key={label}>
                    <rect x={30} y={34 + i * 70} width={330} height={50} fill={H.display} stroke="#9a9a9a" />
                    <text x={48} y={66 + i * 70} fontFamily={SANS} fontSize={20} fontWeight={700} fill={H.text}>
                      {label}
                    </text>
                    <Pipe d={`M 360 ${59 + i * 70} L 440 ${59 + i * 70} L 440 165 L 486 165`} arrow={i === 1} />
                  </g>
                ))}
                <rect x={496} y={100} width={250} height={130} fill={H.on} stroke={H.strong} strokeWidth={2} />
                <text x={621} y={158} textAnchor="middle" fontFamily={SANS} fontSize={30} fontWeight={700} fill="#fff">
                  pi0.5
                </text>
                <text x={621} y={190} textAnchor="middle" fontFamily={SANS} fontSize={17} fill="#d0d0d0">
                  vision-language-action
                </text>
                <Pipe d="M 746 165 L 820 165" />
                <rect x={830} y={112} width={250} height={106} fill={H.display} stroke="#9a9a9a" />
                <text x={848} y={150} fontFamily={MONO} fontSize={19} fill={H.text}>joint actions</text>
                <text x={848} y={178} fontFamily={MONO} fontSize={16} fill={H.muted}>one chunk per call</text>
                <text x={848} y={202} fontFamily={MONO} fontSize={16} fill={H.muted}>
                  ≈{policy?.chunk_ms_gpu ?? '–'} ms on the GPU
                </text>
              </svg>
            </Faceplate>
            <Appear delay={4.5}>
              <Faceplate title="TRAINING · PHYSICAL AI STUDIO" pad={14}>
                <KV
                  size={23}
                  labelW={330}
                  rows={[
                    ['TRAINING DATA', f.dataset.name],
                    [
                      'EPISODES',
                      <span key="e">
                        <Value v={n.EPISODES} name="EPISODES" /> (<Value v={n.PICKS} name="PICKS" /> picks, <Value v={n.SORTS} name="SORTS" /> sorts)
                      </span>,
                    ],
                    ['TRAINED', policy?.training ?? '–'],
                  ]}
                />
              </Faceplate>
            </Appear>
          </AbsoluteFill>
        </Sequence>
        <Sequence from={Math.round(MAP_AT * fps)}>
          <AbsoluteFill>
            <Faceplate title="TRAINING DATA · WHERE BRICKS WERE GRASPED AND RELEASED" hint="top view · forward kinematics, ± a few cm" grow={1}>
              <CoverageMap />
            </Faceplate>
          </AbsoluteFill>
        </Sequence>
      </div>
    </Frame>
  );
};

const CoverageMap: React.FC = () => (
  <>
    <CoveragePlot w={1088} h={700} />
    <Text size={21} colour={H.muted}>
      The plates stood in many places, both colours on both sides of the table, so the sentence, not the position, tells the
      policy where to go.
    </Text>
  </>
);

// ── Scene 4: inspection. One fixed pose, two faces, only the brick scored. Real photos from the arm. ──
const ExampleView: React.FC<{ex: Example; delay: number; w: number}> = ({ex, delay, w}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const views = data.loop.stops_deg.map((d) => ex.stops.find((s) => s.deg === d) ?? null);
  const worst = Math.max(...ex.stops.map((s) => s.median));
  const bands = data.run.cycles.find((c) => c.inspect)?.inspect?.bands ?? f.inspection?.bands ?? [0.45, 0.56];
  const sw = ex.verdict === 'GOOD' ? H.good : ex.verdict === 'DEFECTIVE' ? H.reject : undefined;
  return (
    <Appear delay={delay} style={{width: w, display: 'flex', flexDirection: 'column', gap: 8}}>
      <div style={{display: 'flex', gap: 8, height: 400}}>
        {views.map((v, i) => {
          const wipe = interpolate(frame, [(delay + 0.8 + i * 0.6) * fps, (delay + 1.6 + i * 0.6) * fps], [0, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const d = data.loop.stops_deg[i];
          return (
            <Cam key={d} title={`CAM 03 · ${deg(d)}`} osd={v ? `${deg(d)}  median ${v.median.toFixed(2)}` : `${deg(d)}  not taken`} style={{flex: 1}}>
              {v ? (
                <>
                  <Photo src={v.photo} />
                  <Photo src={v.heat} style={{position: 'absolute', inset: 0, clipPath: `inset(0 ${100 - wipe}% 0 0)`}} />
                </>
              ) : (
                <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, textAlign: 'center', font: `20px ${MONO}`, color: '#bbb'}}>
                  rejected at the first stop: no second view needed
                </div>
              )}
            </Cam>
          );
        })}
      </div>
      <div style={{display: 'flex', alignItems: 'center', gap: 14, background: H.panel, border: `1px solid ${H.line}`, padding: '8px 12px'}}>
        <Swatch colour={sw} size={22} />
        <span style={{fontSize: 34, fontWeight: 700}}>{ex.verdict}</span>
        <span style={{font: `19px ${MONO}`, color: H.muted}}>
          worst {worst.toFixed(2)} · {ex.what} · cycle {ex.cycle}
        </span>
        <span style={{marginLeft: 'auto', font: `16px ${MONO}`, color: H.muted}}>
          GOOD &lt; {bands[0].toFixed(2)} · REJECT &gt; {bands[1].toFixed(2)}
        </span>
      </div>
    </Appear>
  );
};

export const Inspection: React.FC = () => {
  const ex = data.run.examples;
  const good = ex.find((e) => e.kind === 'good');
  const bad = ex.find((e) => e.kind === 'defective');
  const insp = f.inspection;
  return (
    <Frame title="INSPECTION · ANOMALIB PATCHCORE" fields={[{k: 'DEVICE', v: f.models.anomaly.device}, {k: 'STOPS', v: data.loop.stops_deg.map(deg).join(' ')}]}>
      <div style={{flex: 1, display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0}}>
        <Faceplate title="INSPECTION STATION · SCRIPTED POSE · ONLY THE BRICK IS SCORED" hint={`real photos from the arm · ${data.run.folder ?? ''}`} pad={12}>
          <div style={{display: 'flex', gap: 14}}>
            {good ? <ExampleView ex={good} delay={0.5} w={930} /> : null}
            {bad ? <ExampleView ex={bad} delay={4.5} w={930} /> : null}
          </div>
        </Faceplate>
        <Appear delay={8.5} style={{flex: 1, display: 'flex'}}>
          <Faceplate title="SETTINGS" grow={1} pad={12}>
            <KV
              size={21}
              labelW={300}
              rows={[
                ['SCORED REGION', insp?.crop ?? '–'],
                ['SCORE PER STOP', `median of ${data.loop.frames_per_stop} frames; a defective stop rejects at once, an unsure one gets a second look`],
                ['TRAINING', `${insp?.train_photos ?? '–'} photos of good bricks · ${insp?.train_time ?? '–'}`],
              ]}
            />
          </Faceplate>
        </Appear>
      </div>
    </Frame>
  );
};

// ── Scene 5: the verdict becomes the VLA's next task sentence. ──
export const VerdictToVla: React.FC = () => (
  <Frame title="SORT · TASK → VLA" fields={LIVE}>
    <div style={{flex: 1, display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0}}>
      <Faceplate title="VERDICT → TASK SENTENCE → VLA" grow={1} pad={24}>
        <Appear delay={0.2}>
          <div style={{display: 'flex', alignItems: 'center', gap: 14}}>
            <Swatch colour={H.reject} size={30} />
            <span style={{fontSize: 58, fontWeight: 700}}>DEFECTIVE</span>
          </div>
        </Appear>
        <Appear delay={0.9}>
          <div style={{fontSize: 17, fontWeight: 700, letterSpacing: '.05em', color: H.muted, margin: '18px 0 6px'}}>TASK → VLA</div>
          <div style={{background: H.display, border: '1px solid', borderColor: '#9a9a9a #f7f7f7 #f7f7f7 #9a9a9a', font: `30px ${MONO}`, padding: '12px 16px'}}>
            "<Typewriter text={f.sentences.DEFECTIVE} delay={1.2} seconds={2.4} />"
          </div>
        </Appear>
        <Appear delay={4}>
          <svg width={860} height={150} style={{display: 'block', marginTop: 20}}>
            <ArrowDefs />
            <rect x={0} y={30} width={250} height={90} fill={H.on} stroke={H.strong} strokeWidth={2} />
            <text x={125} y={82} textAnchor="middle" fontFamily={SANS} fontSize={26} fontWeight={700} fill="#fff">pi0.5 · SORT</text>
            <Pipe d="M 250 75 L 450 75" />
            <rect x={460} y={20} width={380} height={110} fill={H.panel} stroke={H.strong} strokeWidth={2} />
            <rect x={482} y={44} width={24} height={24} fill={H.reject} stroke={H.strong} />
            <text x={520} y={66} fontFamily={SANS} fontSize={26} fontWeight={700} fill={H.text}>REJECT</text>
            <text x={520} y={100} fontFamily={SANS} fontSize={20} fill={H.muted}>orange plate, wherever it stands</text>
          </svg>
        </Appear>
      </Faceplate>
    </div>
    <Cam title="CAM 04 · SIDE VIEW · SORT" osd="CAM04  1×" style={{width: 880}}>
      <Footage id="a2" label="the arm carrying the brick to the orange plate" volume={0.25} />
    </Cam>
  </Frame>
);
