// The submission deck: nine 16:9 slides from the same data and components as the video.
// Each slide is a 6 s sequence; scripts/deck.mjs renders the last frame of each to a PNG
// (all animations finished) and scripts/deck_pdf.py joins them into one PDF.
import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {data} from '../data';
import {C, font, monoFont} from '../theme';
import {Arrow, Box, Footage, Line, Photo, Title, Value} from '../components/ui';
import {CoverageMap, LayoutMap, coverageCounts, trials} from '../components/CoverageMap';

export const SLIDE_FRAMES = 180;

const f = data.facts;
const n = data.numbers;

// ── Layout ──────────────────────────────────────────────────────────────────────────────

const Slide: React.FC<{num: number; title: string; kicker?: string; children: React.ReactNode}> = ({num, title, kicker, children}) => (
  <AbsoluteFill style={{background: C.bg, padding: '64px 90px 0 90px'}}>
    {kicker && (
      <div style={{fontFamily: monoFont, fontSize: 22, color: C.stage, letterSpacing: 1, marginBottom: 8}}>{kicker}</div>
    )}
    <Title size={56}>{title}</Title>
    <div style={{flex: 1, display: 'flex', marginTop: 36, marginBottom: 90, gap: 60, minHeight: 0}}>{children}</div>
    <Footer num={num} />
  </AbsoluteFill>
);

const Footer: React.FC<{num: number}> = ({num}) => (
  <div
    style={{
      position: 'absolute',
      left: 90,
      right: 90,
      bottom: 30,
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-end',
      fontFamily: font,
      fontSize: 20,
      color: C.dim,
      borderTop: `1px solid ${C.line}`,
      paddingTop: 12,
    }}
  >
    <span style={{whiteSpace: 'nowrap'}}>Jenssenit · Intel Physical AI Challenge, Junction 2026</span>
    {data.draft.length > 0 && (
      <span style={{fontFamily: monoFont, fontSize: 14, color: C.placeholder, flex: 1, textAlign: 'center', padding: '0 24px', lineHeight: 1.3}}>
        draft: {data.draft.join(' · ')}
      </span>
    )}
    <span style={{fontFamily: monoFont, whiteSpace: 'nowrap'}}>{num} / 9</span>
  </div>
);

const Col: React.FC<{children: React.ReactNode; width?: number; gap?: number}> = ({children, width, gap = 22}) => (
  <div style={{display: 'flex', flexDirection: 'column', gap, flex: width ? undefined : 1, width, minWidth: 0}}>{children}</div>
);

const Bullet: React.FC<{children: React.ReactNode; size?: number; colour?: string}> = ({children, size = 28, colour = C.text}) => (
  <div style={{display: 'flex', gap: 14, fontFamily: font, fontSize: size, color: colour, lineHeight: 1.35}}>
    <span style={{color: C.stage}}>·</span>
    <span>{children}</span>
  </div>
);

/** A two-column fact table. */
const Rows: React.FC<{rows: [React.ReactNode, React.ReactNode][]; size?: number; valueWidth?: number}> = ({rows, size = 28, valueWidth}) => (
  <div style={{display: 'flex', flexDirection: 'column'}}>
    {rows.map(([k, v], i) => (
      <div
        key={i}
        style={{display: 'flex', justifyContent: 'space-between', gap: 30, borderBottom: `1px solid ${C.line}`, padding: '12px 0', alignItems: 'baseline'}}
      >
        <span style={{fontFamily: font, fontSize: size, color: C.dim}}>{k}</span>
        <span style={{fontFamily: monoFont, fontSize: size - 2, color: C.text, textAlign: 'right', width: valueWidth}}>{v}</span>
      </div>
    ))}
  </div>
);

const Tag: React.FC<{text: string; colour: string}> = ({text, colour}) => (
  <span style={{fontFamily: monoFont, fontSize: 18, color: colour, border: `1.5px solid ${colour}`, borderRadius: 6, padding: '2px 8px'}}>{text}</span>
);

const Note: React.FC<{children: React.ReactNode}> = ({children}) => (
  <div style={{fontFamily: font, fontSize: 20, color: C.dim, lineHeight: 1.4}}>{children}</div>
);

// ── Numbers from the benchmark files ───────────────────────────────────────────────────

type PolicyRow = {model: string; device: string; median_ms: number; p95_ms?: number; chunk: number};
const policyMs = (prefix: string, device: string): PolicyRow | null =>
  (data.bench.policy as PolicyRow[]).find((r) => r.model.startsWith(prefix) && r.device === device) ?? null;
const anomalyMs = (precision: string, device: string) =>
  data.bench.anomaly.find((r) => r.precision === precision && r.device === device) ?? null;
const ms = (v: number | undefined | null) => (v === null || v === undefined ? null : v < 100 ? Math.round(v * 10) / 10 : Math.round(v));

// ── Slides ─────────────────────────────────────────────────────────────────────────────

const S1Title: React.FC = () => (
  <AbsoluteFill style={{background: C.bg, flexDirection: 'row', padding: '90px 90px 0 90px', gap: 70}}>
    <Col gap={30}>
      <div style={{fontFamily: monoFont, fontSize: 24, color: C.stage}}>Intel Physical AI Challenge · Junction 2026</div>
      <Title size={120}>Jenssenit</Title>
      <Line size={36}>
        A vision-language-action model picks and sorts bricks lying at random positions onto plates that can be anywhere.
        Anomalib inspects every brick in the loop. All inference runs on one Intel Core Ultra laptop.
      </Line>
      <Rows
        rows={[
          ['Bricks', 'any number, random positions'],
          ['Plates', 'movable'],
          ['Coordinates in code', 'none'],
          ['Defect check', 'every brick, before sorting'],
        ]}
        size={30}
      />
      <Line size={26} colour={C.dim}>
        {f.team.length ? f.team.join(' · ') : <Value v={null} name="team names" />}
      </Line>
    </Col>
    <div style={{width: 760, height: 860, position: 'relative', borderRadius: 14, overflow: 'hidden', alignSelf: 'flex-start'}}>
      {data.footage.a1 ? (
        <Footage id="a1" label="" startFrom={f.run_take.footage_offset_s + 2} volume={0} />
      ) : (
        <CoverageMap size={760} delay={-10} />
      )}
    </div>
    <Footer num={1} />
  </AbsoluteFill>
);

const S2Task: React.FC = () => (
  <Slide num={2} title="The task: nothing is in a fixed place" kicker="WHAT IS DIFFERENT">
    <Col>
      <Line size={30} colour={C.dim}>
        A recorded or hard-coded motion only works with one brick in one place. Here the bricks, their positions and the
        plates change from run to run.
      </Line>
      <Rows
        rows={[
          ['Bricks', 'any number, random position and rotation'],
          ['Plates', f.run_take.plate_swap_shown ? 'two, anywhere within reach; swapped mid-run in tests' : 'two, anywhere within reach'],
          ['Coordinates in code', 'none: picking and placing are learned'],
          ['Defect check', 'Anomalib on every brick, before it is sorted'],
          ['Who chooses', 'nobody: the loop runs on its own'],
        ]}
        size={28}
      />
      <Box>
        <Line size={22} colour={C.dim}>
          The three task sentences (exact; the training data uses the same)
        </Line>
        <Line size={24} mono>
          pick: "{f.sentences.pick}"
        </Line>
        <Line size={24} mono colour={C.good}>
          good: "{f.sentences.GOOD}"
        </Line>
        <Line size={24} mono colour={C.defective}>
          defective: "{f.sentences.DEFECTIVE}"
        </Line>
      </Box>
    </Col>
    <Col width={560} gap={14}>
      <LayoutMap size={560} delay={-10} />
      <Note>Test layouts come from a random draw (tools/random_layout.py), not from us choosing positions.</Note>
    </Col>
  </Slide>
);

const Stage: React.FC<{name: string; learned: boolean; lines: React.ReactNode[]; device: string}> = ({name, learned, lines, device}) => (
  <Box colour={learned ? C.stage : C.line} style={{flex: 1, display: 'flex', flexDirection: 'column', gap: 12, padding: '20px 22px'}}>
    <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
      <Title size={36}>{name}</Title>
      <Tag text={learned ? 'learned' : 'scripted'} colour={learned ? C.stage : C.dim} />
    </div>
    {lines.map((l, i) => (
      <Line key={i} size={23} colour={i === 0 ? C.text : C.dim}>
        {l}
      </Line>
    ))}
    <div style={{marginTop: 'auto'}}>
      <Tag text={device} colour={C.text} />
    </div>
  </Box>
);

const S3Cell: React.FC = () => (
  <Slide num={3} title="The cell: learned where it varies, scripted where it must not" kicker="ARCHITECTURE">
    <Col gap={30}>
      <div style={{display: 'flex', alignItems: 'stretch', gap: 14, height: 400}}>
        <Stage
          name="Pick"
          learned
          lines={[`${f.models.pick.name}, task "${f.sentences.pick}"`, 'Top and wrist cameras, joint state in; joint actions out']}
          device={`${f.models.pick.device} · OpenVINO`}
        />
        <div style={{alignSelf: 'center'}}>
          <Arrow length={40} />
        </div>
        <Stage
          name="Show"
          learned={false}
          lines={['One saved pose in front of the inspection camera', 'Wrist stops at 0°, 90°, 180°']}
          device="CPU"
        />
        <div style={{alignSelf: 'center'}}>
          <Arrow length={40} />
        </div>
        <Stage
          name="Inspect"
          learned={false}
          lines={[
            'Anomalib PatchCore, median of 3 frames per stop',
            'A defective stop rejects at once; an unsure stop gets a second look; still unsure → defective',
          ]}
          device={`${f.models.anomaly.device} · OpenVINO`}
        />
        <div style={{alignSelf: 'center'}}>
          <Arrow length={40} />
        </div>
        <Stage
          name="Sort"
          learned
          lines={[`${f.models.sort.name}, told the verdict as its task`, 'Finds the plate of that colour, wherever it is']}
          device={`${f.models.sort.device} · OpenVINO`}
        />
      </div>
      <div style={{display: 'flex', alignItems: 'center', gap: 20}}>
        <Box colour={C.defective} style={{padding: '12px 18px'}}>
          <Line size={26} mono colour={C.defective}>
            DEFECTIVE
          </Line>
        </Box>
        <Arrow length={60} colour={C.defective} />
        <Box colour={C.defective} style={{padding: '12px 18px', flex: 1}}>
          <Line size={26} mono>
            task = "{f.sentences.DEFECTIVE}"
          </Line>
        </Box>
        <Arrow length={60} colour={C.defective} />
        <Box colour={C.stage} style={{padding: '12px 18px'}}>
          <Line size={26}>{f.models.sort.name}</Line>
        </Box>
      </div>
      <Note>
        Inspection is scripted because anomaly detection needs the same view every time (slide 6). Safety: every policy step
        is clamped (2 units per tick at the start of a stage, up to 12 within its first second), stages time out (pick 25 s,
        sort 15 s), one key stops the arm, and Studio's device lock keeps other programs off it.
      </Note>
    </Col>
  </Slide>
);

const S4Policy: React.FC = () => (
  <Slide num={4} title="The policy and the data it learned from" kicker="VLA · PHYSICAL AI STUDIO">
    <Col gap={26}>
      <div style={{display: 'flex', alignItems: 'center', gap: 14}}>
        <Col width={250} gap={8}>
          {['Top camera', 'Wrist camera', 'Joint state', 'Task sentence'].map((x) => (
            <Box key={x} style={{padding: '8px 14px'}}>
              <Line size={22}>{x}</Line>
            </Box>
          ))}
        </Col>
        <Arrow length={44} />
        <Box colour={C.stage} style={{padding: '20px 24px'}}>
          <Title size={34}>SmolVLA</Title>
          <Line size={20} colour={C.dim}>
            vision-language-action
          </Line>
        </Box>
        <Arrow length={44} />
        <Box style={{padding: '12px 16px'}}>
          <Line size={22} mono>
            50 joint actions
          </Line>
          <Line size={18} colour={C.dim}>
            per chunk, 30 Hz
          </Line>
        </Box>
      </div>
      <Rows
        rows={[
          ['Training data', f.dataset.name],
          ['Teleoperated episodes', <Value key="e" v={n.EPISODES} name="EPISODES" />],
          ['Picks', <Value key="p" v={n.PICKS} name="PICKS" />],
          ['Sorts: green / orange plate', `${coverageCounts.good} / ${coverageCounts.defective}`],
          ['Recorded with', 'the leader arm, in Physical AI Studio'],
          ['Fine-tuned on', 'Modal (H100), exported to OpenVINO'],
        ]}
        size={26}
      />
      <Note>
        Each recorded flow is two episodes: a pick, then a sort with its sentence. The sentences were set after recording,
        from where the brick really landed.
      </Note>
    </Col>
    <Col width={680} gap={8}>
      <CoverageMap size={620} delay={-10} />
      <Note>
        From above: {coverageCounts.grasps} grasps and {coverageCounts.good + coverageCounts.defective} releases in the
        training data. Both plates appear on both sides of the table in all three recording batches. Forward kinematics,
        good to a few cm.
      </Note>
    </Col>
  </Slide>
);

const S5Data: React.FC = () => (
  <Slide num={5} title="Data and training checks" kicker="DATASET & PIPELINE QUALITY">
    <Col gap={20}>
      <Line size={28}>Raw recordings stay untouched. Training uses cleaned copies.</Line>
      <Rows
        rows={[
          ['Raw dataset main', '501 episodes, never edited'],
          ['Cleaned copy main-clean3', '486 episodes (15 removed)'],
          ['Sort labels: brick on the plate its sentence names?', '242 / 242'],
          ['Picks: brick in the gripper at the end?', '244 / 244'],
        ]}
        size={25}
      />
      <Note>
        Sort labels were checked by a script comparing top-camera frames before and after each sort; the 35 unclear cases
        were checked by eye. Picks were checked on the last wrist-camera frame.
      </Note>
      <Box colour={C.unsure} style={{padding: '16px 20px'}}>
        <Line size={26} colour={C.unsure}>
          A training trap we found
        </Line>
        <Line size={23}>
          Studio exports the epoch with the lowest validation loss. Our first SmolVLA shipped the epoch-3 snapshot (step
          2,068 of 5,169, training loss still about 0.15 to 0.2) and moved jerkily on the arm. Fix: validation split 0, train
          to the end. SmolVLA-v2: final checkpoint, 11,322 steps.
        </Line>
      </Box>
    </Col>
    <Col width={720} gap={14}>
      <Line size={26}>Offline test on recorded episodes (shoulder_lift / elbow)</Line>
      <div style={{display: 'grid', gridTemplateColumns: '1.6fr 1fr 1fr', fontFamily: font, fontSize: 22}}>
        {[
          ['', 'v1 (epoch 3)', 'v2 (final)'],
          ['Same input, 5 runs: spread (°)', '18–24 / 12–44', '11–15 / 11–18'],
          ['Error vs teleop, next 50 actions (°)', '5–6 / 4–10', '2–5 / 3–6'],
          ['Jerk, 99th percentile', '19.6 / 16.4', '8.5 / 7.6'],
          ['Jerk with zero noise + blend', '1.6 / 1.3', '1.5 / 1.1'],
          ['Jerk of the teleop itself', '2.1 / 1.7', ''],
        ].map((row, i) =>
          row.map((cell, j) => (
            <div
              key={`${i}-${j}`}
              style={{
                padding: '12px 8px',
                borderBottom: `1px solid ${C.line}`,
                color: i === 0 ? C.dim : j === 0 ? C.dim : C.text,
                fontFamily: j === 0 ? font : monoFont,
                textAlign: j === 0 ? 'left' : 'right',
              }}
            >
              {cell}
            </div>
          )),
        )}
      </div>
      <Note>
        Jerk: change in speed per frame during asynchronous playback. Zero noise feeds SmolVLA an all-zero noise input; the
        loop uses it.
      </Note>
    </Col>
  </Slide>
);

const S6Inspection: React.FC = () => {
  const images = data.run.images.slice(0, 2);
  const bands = data.run.cycles[0]?.inspect?.bands ?? [0.4, 0.6];
  const int8 = anomalyMs('INT8 weights', 'GPU');
  const fp32 = anomalyMs('FP32', 'GPU');
  return (
    <Slide num={6} title="Inspection: the same view every time" kicker="ANOMALIB">
      <Col gap={18}>
        <Box colour={C.unsure} style={{padding: '14px 20px'}}>
          <Line size={24}>
            Why the pose is scripted: in our first photo set the arm held each brick in a different pose. A trial model
            rejected 3 of 15 good bricks. Anomaly detection flags anything unlike its training photos, including the arm.
          </Line>
        </Box>
        <Bullet>One saved show pose; the wrist turns to 0°, 90° and 180°</Bullet>
        <Bullet>PatchCore scores the median of 3 frames at each stop</Bullet>
        <Bullet>
          Bands: good below {bands[0]}, unsure up to {bands[1]}, defective above. A defective stop rejects at once; an unsure
          one gets a second look; still unsure means defective
        </Bullet>
        <Bullet>Trained on good bricks only, on the laptop's Intel GPU: 2.7 min for the slowest step vs 12 to 17 min on the CPU</Bullet>
        <Bullet>
          INT8 weight-only: {fp32?.size_mb ?? '[MB]'} MB to {int8?.size_mb ?? '[MB]'} MB, scores within{' '}
          {int8 ? int8.score_diff_max.toFixed(2) : '[x]'} of FP32. Full INT8 moved scores by up to 0.28, so we don't use it
        </Bullet>
      </Col>
      <Col width={700} gap={14}>
        <div style={{display: 'flex', gap: 16, height: 340}}>
          {[0, 1].map((i) =>
            images[i] ? (
              <div key={i} style={{flex: 1, borderRadius: 12, overflow: 'hidden', border: `2px solid ${C.line}`}}>
                <Photo src={images[i].heat ?? images[i].photo} />
              </div>
            ) : (
              <div key={i} style={{flex: 1, border: `2px dashed ${C.line}`, borderRadius: 12}} />
            ),
          )}
        </div>
        <Note>Heatmaps from a loop test run: the score is highest where the model sees something unusual.</Note>
        <div style={{position: 'relative', height: 70, marginTop: 10}}>
          <div style={{position: 'absolute', top: 10, left: 0, right: 0, height: 18, borderRadius: 9, overflow: 'hidden', display: 'flex'}}>
            <div style={{width: `${bands[0] * 100}%`, background: C.good}} />
            <div style={{width: `${(bands[1] - bands[0]) * 100}%`, background: C.unsure}} />
            <div style={{flex: 1, background: C.defective}} />
          </div>
          <div style={{position: 'absolute', top: 38, left: 0, right: 0, display: 'flex', justifyContent: 'space-between', fontFamily: monoFont, fontSize: 20, color: C.dim}}>
            <span>good</span>
            <span>unsure</span>
            <span>defective</span>
          </div>
        </div>
        <Note>Scores are normalised so that 0.5 is the model's threshold.</Note>
      </Col>
    </Slide>
  );
};

const S7Laptop: React.FC = () => {
  const devices = ['GPU', 'NPU', 'CPU'] as const;
  const rows: {label: string; cells: (number | null | string)[]; used: string}[] = [
    {
      label: 'SmolVLA, per 50-action chunk',
      cells: devices.map((d) => (d === 'NPU' ? "won't compile" : ms(policyMs('SmolVLA', d)?.median_ms))),
      used: f.models.sort.device,
    },
    {label: 'ACT pick, per 100-action chunk', cells: devices.map((d) => ms(policyMs('ACT', d)?.median_ms)), used: f.models.pick.name.startsWith('ACT') ? f.models.pick.device : ''},
    {label: 'PatchCore FP32, per view', cells: devices.map((d) => ms(anomalyMs('FP32', d)?.median_ms)), used: f.models.anomaly.device},
    {label: 'PatchCore INT8 weights, per view', cells: devices.map((d) => ms(anomalyMs('INT8 weights', d)?.median_ms)), used: ''},
  ];
  const smol = policyMs('SmolVLA', f.models.sort.device);
  const headroom = smol?.p95_ms ? 833 / smol.p95_ms : null;
  return (
    <Slide num={7} title="On the laptop: each model where it runs best" kicker="OPENVINO · CORE ULTRA">
      <Col gap={20}>
        <div style={{display: 'grid', gridTemplateColumns: '2.2fr 1fr 1fr 1fr', fontSize: 26}}>
          {['Median latency (ms)', ...devices].map((h, i) => (
            <div key={h} style={{fontFamily: i ? monoFont : font, color: C.dim, padding: '10px 8px', borderBottom: `1px solid ${C.line}`, textAlign: i ? 'right' : 'left'}}>
              {h}
            </div>
          ))}
          {rows.map((r) => [
            <div key={r.label} style={{fontFamily: font, color: C.text, padding: '14px 8px', borderBottom: `1px solid ${C.line}`}}>
              {r.label}
            </div>,
            ...r.cells.map((c, j) => {
              const used = r.used === devices[j];
              return (
                <div
                  key={`${r.label}${j}`}
                  style={{
                    fontFamily: monoFont,
                    color: typeof c === 'string' ? C.dim : used ? C.good : C.text,
                    fontWeight: used ? 600 : 400,
                    padding: '14px 8px',
                    borderBottom: `1px solid ${C.line}`,
                    textAlign: 'right',
                    fontSize: typeof c === 'string' ? 20 : 26,
                  }}
                >
                  {c === null ? '–' : c}
                  {used ? ' ●' : ''}
                </div>
              );
            }),
          ])}
        </div>
        <Note>● the device the loop uses. {f.laptop}, all models in OpenVINO.</Note>
      </Col>
      <Col width={640} gap={16}>
        <Bullet size={25}>
          SmolVLA runs on the GPU: it doesn't compile for the NPU and takes seconds on the CPU. With asynchronous chunking the
          next chunk is requested 833 ms before it's needed; p95 latency {smol?.p95_ms ? Math.round(smol.p95_ms) : '[ms]'} ms gives{' '}
          {headroom ? headroom.toFixed(1) : '[x]'}× headroom, so the arm never waits.
        </Bullet>
        <Bullet size={25}>ACT runs almost as fast on the NPU as on the GPU, so a pick on the NPU leaves the GPU to the other models.</Bullet>
        <Bullet size={25}>PatchCore runs on the GPU while the brick is being shown, when no policy needs it.</Bullet>
        <Bullet size={25}>Temperature, CPU, GPU and NPU load are logged every cycle. The package reached 90 to 97 °C under load.</Bullet>
        {data.bench.contended.length > 0 && (
          <Note>
            <span style={{color: C.placeholder}}>Measured while the laptop was busy; to be re-measured on a quiet laptop.</span>
          </Note>
        )}
      </Col>
    </Slide>
  );
};

const S8Results: React.FC = () => {
  const ev = data.evaluation;
  const row = (label: string, num: React.ReactNode): [React.ReactNode, React.ReactNode] => [label, num];
  const frac = (a: keyof typeof n) => (
    <>
      <Value v={n[a]} name={a} /> / <Value v={n.M} name="M" />
    </>
  );
  return (
    <Slide num={8} title="Results over random layouts" kicker="EVALUATION ON THE ARM">
      <Col gap={20}>
        <Rows
          rows={[
            row('Random layouts', <Value v={n.R} name="R" />),
            row('Cycles', <Value v={n.M} name="M" />),
            row('Pick, first try', frac('P')),
            row('Inspection verdict correct', frac('I')),
            row('Placed on the plate it was told', frac('S')),
            row('Correct end to end', frac('E')),
            row('Median cycle', <Value v={n.X} name="X" digits={1} unit=" s" />),
          ]}
          size={30}
        />
        <Note>
          Each round: 6 bricks (2 with marker defects) and both plates at positions from a random draw; the plates are swapped
          by hand mid-run in at least one round. Every cycle counted, failures included.
        </Note>
        <Line size={24} colour={C.dim}>
          Failures:{' '}
          {ev.failures.length ? ev.failures.slice(0, 6).join(' · ') : <Value v={null} name="one line per failure" />}
        </Line>
      </Col>
      <Col width={680} gap={8}>
        <CoverageMap size={640} delay={-10} show={{grasps: true, releases: false}} trials={trials()} />
        <Note>Test positions over the training grasps: ✓ brick on the correct plate, ✗ not.</Note>
      </Col>
    </Slide>
  );
};

const S9Limits: React.FC = () => (
  <Slide num={9} title="Limits and next steps" kicker="HONESTLY">
    <Col gap={20}>
      <Line size={32} colour={C.unsure}>
        Where it's weak
      </Line>
      <Bullet>
        New positions are the hard part. Offline, on 13 pick episodes neither model trained on, SmolVLA-v2 headed the right
        way 8 times and ACT 6 times. Slide 8 measures it on the arm.
      </Bullet>
      <Bullet>
        The soft gripper gives no grasp signal: it closes to about 3.5 on a brick and 2.6 on nothing. An empty grasp is only
        caught at inspection.
      </Bullet>
      <Bullet>Inspection is trained on our bricks under one lamp. Other lighting or backdrops need new photos.</Bullet>
      <Bullet>The laptop runs hot: 90 to 97 °C package temperature under load.</Bullet>
    </Col>
    <Col gap={20}>
      <Line size={32} colour={C.good}>
        What we'd do next
      </Line>
      <Bullet>Record more teleoperation at the positions where picks fail (the ✗ on slide 8).</Bullet>
      <Bullet>Use the inspection photo to detect an empty gripper and pick again instead of sorting nothing.</Bullet>
      <Bullet>More defect types: cracks, missing studs, wrong colours.</Bullet>
      {f.models.pick.name.startsWith('ACT') && f.models.pick.device === 'NPU' ? (
        <Bullet>Measure package power per cycle (it needs one permission change on the laptop that we haven't made).</Bullet>
      ) : (
        <Bullet>Move the pick to ACT on the NPU (17 ms per chunk) to leave the GPU to SmolVLA and inspection.</Bullet>
      )}
    </Col>
  </Slide>
);

export const SLIDES: React.FC[] = [S1Title, S2Task, S3Cell, S4Policy, S5Data, S6Inspection, S7Laptop, S8Results, S9Limits];

export const Deck: React.FC = () => (
  <AbsoluteFill style={{background: C.bg}}>
    {SLIDES.map((S, i) => (
      <Sequence key={i} from={i * SLIDE_FRAMES} durationInFrames={SLIDE_FRAMES} name={`slide ${i + 1}`}>
        <S />
      </Sequence>
    ))}
  </AbsoluteFill>
);
