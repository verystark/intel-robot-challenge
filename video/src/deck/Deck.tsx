// The submission deck, drawn as screens of the cell's own operator HMI (loop/dashboard, ISA-101):
// nine static 16:9 pages from video/public/data.json (facts.json is passed through as data.facts).
// scripts/deck.mjs renders the last frame of each page to a PNG; scripts/deck_pdf.py joins them.
import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import rawCoverage from '../../public/coverage.json';
import {data} from '../data';
import {
  ArrowDefs,
  Col,
  CoveragePlot,
  Disp,
  Equip,
  Events,
  Ev,
  Faceplate,
  Gauge,
  H,
  KV,
  MONO,
  Photo,
  Pipe,
  SANS,
  Screen,
  Swatch,
  TagBox,
  Tbl,
  Text,
  Val,
} from './hmi';

export const SLIDE_FRAMES = 180;

// ── Facts (video/facts.json) ──────────────────────────────────────────────────────────────

interface Stop {
  deg: number;
  median: number;
  label: string;
}
interface Facts {
  policy: {family: string; training: string; chunk_ms_gpu: number};
  inspection: {
    crop: string;
    stops_deg: number[];
    frames_per_stop: number;
    bands: [number, number];
    train_photos: number;
    train_photos_at_show_pose: number;
    held_out: string;
    ms_gpu_loop: number;
    ms_gpu_loop_p95: number;
    ms_cpu: number;
    ms_npu: number;
    int8: string;
    train_time: string;
  };
  results: {
    runs: string[];
    model: string;
    bricks_through_loop: number;
    verdicts_correct: number;
    defective_rejected: [number, number];
    clean_accepted: [number, number];
    picks_ok: number;
    pick_attempts: number;
    pick_timeouts: number;
    picks_stopped_by_operator: number;
    median_cycle_s: number;
    median_pick_s: number;
    median_inspect_s: number;
    median_sort_s: number;
    thermal: string;
    failures: string[];
    placements_checked: string | null;
    verdicts_checked: string;
  };
}
const f = data.facts;
const F = data.facts as unknown as Facts;
const pol = F.policy;
const insp = F.inspection;
const res = F.results;
const n = data.numbers;
const loop = data.loop;
const model = f.models.sort.name;

// What's still missing for the deck (shown as the P2 DATA.DRAFT banner on every page).
const DRAFT: string[] = [
  ...(res.placements_checked ? [] : ['landing plate not counted (loop does not log it)']),
  'PatchCore CPU / NPU times measured while the loop ran',
  ...(f.team.length ? [] : ['team names missing']),
];

// ── Helpers ───────────────────────────────────────────────────────────────────────────────

const deg = (d: number) => `${d < 0 ? '−' : ''}${Math.abs(d)}°`;
const stopsText = insp.stops_deg.map(deg).join(' / ');
const coverage = rawCoverage as unknown as {releases: {GOOD: number[][]; DEFECTIVE: number[][]}};
const sides = (pts: number[][]) => `${pts.filter((q) => q[1] > 0).length} left / ${pts.filter((q) => q[1] <= 0).length} right`;
type PolicyRow = {model: string; device: string; median_ms: number};
const bench = (prefix: string, device: string) => (data.bench.policy as PolicyRow[]).find((r) => r.model.startsWith(prefix) && r.device === device)?.median_ms ?? null;
const ms = (v: number | null | undefined) => (v === null || v === undefined ? null : v < 100 ? Math.round(v * 10) / 10 : Math.round(v));
const [lowBand, highBand] = insp.bands;

type Cycle = {cycle: number; inspect?: {verdict: string; stops?: Stop[]}};
const cycles = data.run.cycles as unknown as Cycle[];
const byCycle = (c: number) => cycles.find((x) => x.cycle === c);
const worst = (c: Cycle) => Math.max(...(c.inspect?.stops ?? []).map((s) => s.median));
// Example bricks from the arm run (photos checked by eye): a clean red brick and a white brick with marker.
const CLEAN = 69;
const MARKED = 34;
const failureEvents = (): Ev[] =>
  res.failures.map((x) => {
    const [tag, ...rest] = x.split(': ');
    return {prio: tag.startsWith('INSP.FACES') || tag.startsWith('INSP.MARGIN') ? 3 : 2, tag, msg: rest.join(': ')};
  });

// ── F1 SYSTEM ─────────────────────────────────────────────────────────────────────────────

const S1: React.FC = () => (
  <Screen page={1} title="SYSTEM" draftItems={DRAFT}>
    <Col w={990}>
      <Faceplate title="SYSTEM DESCRIPTION" grow={1} pad={22}>
        <div style={{fontSize: 84, fontWeight: 700, letterSpacing: '.02em', lineHeight: 1}}>JENSSENIT</div>
        <Text size={27}>
          A pi0.5 vision-language-action model picks and sorts bricks lying at random positions onto plates that can be moved.
          Anomalib inspects every brick in the loop. All inference runs on one Intel Core Ultra laptop.
        </Text>
        <div style={{marginTop: 10}}>
          <KV
            size={24}
            labelW={360}
            rows={[
              ['BRICKS', 'any number, random positions'],
              ['TARGET SURFACE', 'two plates, movable, named by colour'],
              ['COORDINATES IN CODE', 'none: picking and placing are learned'],
              ['DEFECT CHECK', 'Anomalib PatchCore on the brick, every brick'],
              ['POLICY', `pi0.5 (${model})`],
              ['RESULT ON THE ARM', `${res.verdicts_correct} / ${res.bricks_through_loop} verdicts right · ${res.defective_rejected[0]} / ${res.defective_rejected[1]} defects rejected`],
              ['INFERENCE', 'on the laptop, OpenVINO'],
              ['TEAM', f.team.length ? f.team.join(', ') : <Val key="t" v={null} name="TEAM NAMES" />],
            ]}
          />
        </div>
      </Faceplate>
    </Col>
    <Col>
      <Faceplate title="WORKSPACE · TOP VIEW" hint={`where the training data (${f.dataset.name}) grasped and released bricks`} grow={1}>
        <CoveragePlot w={868} h={780} />
      </Faceplate>
    </Col>
  </Screen>
);

// ── F2 TASK ───────────────────────────────────────────────────────────────────────────────

const S2: React.FC = () => (
  <Screen page={2} title="TASK" draftItems={DRAFT}>
    <Col w={1010}>
      <Faceplate title="TASK SPECIFICATION" pad={18}>
        <Text size={24}>
          A replayed or hard-coded motion only works with one brick in one place and one fixed target. Here the brick count, the
          brick positions and the plate positions change from run to run.
        </Text>
        <KV
          size={23}
          labelW={330}
          rows={[
            ['BRICKS', 'any number, random position and rotation'],
            ['TARGET SURFACE', 'two plates, movable: the task names the plate by colour'],
            ['COORDINATES IN CODE', 'none'],
            ['DEFECT CHECK', 'Anomalib, every brick, before sorting'],
            ['OPERATOR INPUT', 'none during a run'],
          ]}
        />
      </Faceplate>
      <Faceplate title="TASK SENTENCES" hint="exact; the training data uses the same strings" grow={1} pad={18}>
        <Tbl
          head={['STAGE', 'TASK SENTENCE TO THE VLA']}
          widths="250px 1fr"
          size={22}
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
        <Text size={20} colour={H.muted}>
          The verdict picks the sentence. The sentence names the target by its colour, not by a position, and the same policy
          finds that plate.
        </Text>
      </Faceplate>
    </Col>
    <Col>
      <Faceplate title="TARGET SURFACES · WHERE THE PLATES STOOD IN TRAINING" hint={`${f.dataset.name}, top view`} grow={1}>
        <CoveragePlot w={858} h={720} grasps={false} />
        <Text size={19} colour={H.muted}>
          Release points of all {coverage.releases.GOOD.length + coverage.releases.DEFECTIVE.length} sorts. The plates were moved
          while recording: green {sides(coverage.releases.GOOD)}, orange {sides(coverage.releases.DEFECTIVE)} of the centre line.
        </Text>
      </Faceplate>
    </Col>
  </Screen>
);

// ── F3 PROCESS (the mimic) ────────────────────────────────────────────────────────────────

const CameraIcon: React.FC<{x: number; y: number}> = ({x, y}) => (
  <g transform={`translate(${x},${y})`} fill="none" stroke={H.strong} strokeWidth={3}>
    <rect x={0} y={0} width={46} height={30} />
    <path d="M 46 9 L 64 0 L 64 30 L 46 21" />
  </g>
);

const ArmIcon: React.FC<{x: number; y: number}> = ({x, y}) => (
  <g transform={`translate(${x},${y})`} fill="none" stroke="#fff" strokeWidth={3}>
    <rect x={0} y={44} width={30} height={14} />
    <path d="M 15 44 L 30 14 L 66 4 M 60 0 L 70 4 L 62 12" />
  </g>
);

const S3: React.FC = () => (
  <Screen page={3} title="PROCESS" draftItems={DRAFT}>
    <Col>
      <Faceplate title="PROCESS · BRICK INSPECTION AND SORTING" hint="learned where the scene varies, scripted where it must not" grow={1} pad={0}>
        <svg width={1878} height={520} style={{display: 'block'}}>
          <ArrowDefs />
          <Equip x={40} y={110} w={300} h={190} title="PICK AREA" sub="bricks at random positions" dashed />
          <TagBox x={40} y={318} w={300} k="BRICKS" v="any number" />
          <TagBox x={40} y={354} w={300} k="POSITIONS" v="random" />
          <Pipe d="M 340 205 L 430 205" />
          <Equip x={440} y={90} w={360} h={230} title="SO-101 ARM" sub="VLA CONTROL · LEARNED" on icon={<ArmIcon x={585} y={210} />} />
          <TagBox x={440} y={338} w={360} k="POLICY" v={`pi0.5 · ${model}`} />
          <TagBox x={440} y={374} w={360} k="TASK" v={`"${f.sentences.pick}"`} />
          <TagBox x={440} y={410} w={360} k="CHUNK" v={`${pol.chunk_ms_gpu} ms · GPU · OPENVINO`} />
          <Pipe d="M 800 205 L 890 205" />
          <Equip x={900} y={90} w={360} h={230} title="INSPECTION STN" sub="ANOMALIB · SCRIPTED POSE" icon={<CameraIcon x={1046} y={210} />} />
          <TagBox x={900} y={338} w={360} k="STOPS" v={stopsText} />
          <TagBox x={900} y={374} w={360} k="CROP" v="brick square, 360 px" />
          <TagBox x={900} y={410} w={360} k="BANDS" v={`${lowBand.toFixed(2)} / ${highBand.toFixed(2)} · GPU`} />
          <Pipe d="M 1260 205 L 1342 205" />
          <polygon points="1400,147 1458,205 1400,263 1342,205" fill={H.strong} />
          <text x={1400} y={211} textAnchor="middle" fontFamily={SANS} fontSize={17} fontWeight={700} fill="#fff">
            VERDICT
          </text>
          <Pipe d="M 1400 147 L 1400 90 L 1500 90" />
          <Pipe d="M 1400 263 L 1400 400 L 1500 400" />
          <text x={1412} y={128} fontFamily={MONO} fontSize={15} fill={H.muted}>
            task → VLA
          </text>
          <text x={1412} y={300} fontFamily={MONO} fontSize={15} fill={H.muted}>
            task → VLA
          </text>
          {(
            [
              [30, H.good, 'GOOD', 'green plate · movable', '"…Put it on the green plate."'],
              [340, H.reject, 'REJECT', 'orange plate · movable', '"…Put it on the orange plate."'],
            ] as [number, string, string, string, string][]
          ).map(([y, c, t, s, q]) => (
            <g key={t}>
              <rect x={1510} y={y} width={330} height={120} fill={H.panel} stroke={H.strong} strokeWidth={2} strokeDasharray="8 6" />
              <rect x={1528} y={y + 20} width={20} height={20} fill={c} stroke={H.strong} />
              <text x={1560} y={y + 38} fontFamily={SANS} fontSize={20} fontWeight={700} fill={H.text}>
                {t}
              </text>
              <text x={1560} y={y + 64} fontFamily={SANS} fontSize={16} fill={H.muted}>
                {s}
              </text>
              <text x={1528} y={y + 102} fontFamily={MONO} fontSize={14} fill={H.muted}>
                {q}
              </text>
            </g>
          ))}
          <text x={1675} y={250} textAnchor="middle" fontFamily={SANS} fontSize={16} fill={H.muted}>
            placed by the same VLA,
          </text>
          <text x={1675} y={272} textAnchor="middle" fontFamily={SANS} fontSize={16} fill={H.muted}>
            wherever the plate stands
          </text>
          <text x={1675} y={494} textAnchor="middle" fontFamily={SANS} fontSize={15} fill={H.muted}>
            dashed: position not fixed
          </text>
        </svg>
      </Faceplate>
      <div style={{display: 'flex', gap: 10, height: 300}}>
        <Faceplate title="SEQUENCE" hint={`one cycle · median ${res.median_cycle_s} s on the arm`} grow={1} pad={14}>
          <div style={{display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 6}}>
            {[
              ['10', 'HOME', 'scripted'],
              ['20', 'PICK', `pi0.5 · ${res.median_pick_s} s`],
              ['30', 'SHOW', 'scripted'],
              ['40', 'INSPECT', `Anomalib · ${res.median_inspect_s} s`],
              ['50', 'HOME', 'scripted'],
              ['60', 'SORT', `pi0.5 · ${res.median_sort_s} s`],
            ].map(([num, name, how]) => {
              const learned = how.startsWith('pi0.5');
              return (
                <div key={num} style={{border: `1px solid ${H.strong}`, background: learned ? H.on : H.panel, color: learned ? '#fff' : H.text, textAlign: 'center', padding: '8px 0'}}>
                  <div style={{fontFamily: MONO, fontSize: 15, color: learned ? '#d0d0d0' : H.faint}}>{num}</div>
                  <div style={{fontSize: 21, fontWeight: 700}}>{name}</div>
                  <div style={{fontSize: 15, color: learned ? '#d0d0d0' : H.muted}}>{how}</div>
                </div>
              );
            })}
          </div>
          <Text size={19} colour={H.muted}>
            Filled: learned by the policy. Outline: scripted. Inspection is scripted because anomaly detection needs the same view
            every time (INSPECTION, F6). Stage times are medians of {res.bricks_through_loop} bricks on the arm.
          </Text>
        </Faceplate>
        <Faceplate title="INTERLOCKS AND RECOVERY" grow={1} pad={14}>
          <KV
            size={20}
            labelW={250}
            rows={[
              ['STEP CLAMP', "2 → 12 units per tick over each stage's first second"],
              ['STAGE TIMEOUT', `pick ${loop.pick_timeout_s ?? '–'} s · sort ${loop.sort_timeout_s ?? '–'} s: the arm stops, the operator resumes`],
              ['UNSURE VIEW', 'second look; still unsure → reject'],
              ['STOP', 'Esc / s: the arm holds position'],
              ['DEVICE LOCK', "Studio's lock: one program drives the arm"],
            ]}
          />
        </Faceplate>
      </div>
    </Col>
  </Screen>
);

// ── F4 POLICY ─────────────────────────────────────────────────────────────────────────────

const S4: React.FC = () => (
  <Screen page={4} title="POLICY" draftItems={DRAFT}>
    <Col w={1010}>
      <Faceplate title={`VLA CONTROLLER · PI0.5 · ${model.toUpperCase()} · OPENVINO ${f.models.sort.device}`} pad={0}>
        <svg width={1008} height={300} style={{display: 'block'}}>
          <ArrowDefs />
          {['TOP CAMERA · RealSense D415', 'WRIST CAMERA', 'JOINT STATE · J1–J6', 'TASK SENTENCE'].map((label, i) => (
            <g key={label}>
              <rect x={24} y={28 + i * 64} width={330} height={46} fill={H.display} stroke="#9a9a9a" />
              <text x={40} y={58 + i * 64} fontFamily={SANS} fontSize={18} fontWeight={700} fill={H.text}>
                {label}
              </text>
              <Pipe d={`M 354 ${51 + i * 64} L 430 ${51 + i * 64} L 430 150 L 470 150`} arrow={i === 1} />
            </g>
          ))}
          <rect x={480} y={92} width={220} height={116} fill={H.on} stroke={H.strong} strokeWidth={2} />
          <text x={590} y={144} textAnchor="middle" fontFamily={SANS} fontSize={28} fontWeight={700} fill="#fff">pi0.5</text>
          <text x={590} y={172} textAnchor="middle" fontFamily={SANS} fontSize={15} fill="#d0d0d0">vision-language-action</text>
          <text x={590} y={192} textAnchor="middle" fontFamily={MONO} fontSize={13} fill="#d0d0d0">images 224 × 224</text>
          <Pipe d="M 700 150 L 770 150" />
          <rect x={780} y={104} width={204} height={92} fill={H.display} stroke="#9a9a9a" />
          <text x={796} y={138} fontFamily={MONO} fontSize={17} fill={H.text}>50 actions × 6</text>
          <text x={796} y={164} fontFamily={MONO} fontSize={15} fill={H.muted}>per chunk, 30 Hz</text>
          <text x={796} y={186} fontFamily={MONO} fontSize={15} fill={H.muted}>{pol.chunk_ms_gpu} ms, async</text>
        </svg>
      </Faceplate>
      <Faceplate title="TRAINING" grow={1} pad={16}>
        <KV
          size={22}
          labelW={320}
          rows={[
            ['TRAINING DATA', f.dataset.name],
            ['EPISODES', <Val key="e" v={n.EPISODES} name="EPISODES" />],
            ['PICKS / SORTS', <span key="ps"><Val v={n.PICKS} name="PICKS" /> / <Val v={n.SORTS} name="SORTS" /></span>],
            ['SORTS · GREEN / ORANGE', `${coverage.releases.GOOD.length} / ${coverage.releases.DEFECTIVE.length}`],
            ['TRAINING RUN', '8 × H100 on Modal · 4 epochs · 5,116 steps'],
            ['CHECKPOINT', 'final weights, validation split 0'],
            ['IMAGE AUGMENTATION', 'off (see LIMITS, F9)'],
            ['RECORDED WITH', 'leader arm, Physical AI Studio'],
            ['ON THE LAPTOP', `${pol.chunk_ms_gpu} ms per chunk, GPU, measured on the arm`],
          ]}
        />
      </Faceplate>
    </Col>
    <Col>
      <Faceplate title="TRAINING DATA · GRASP AND RELEASE POINTS" hint="top view, forward kinematics, ± a few cm" grow={1}>
        <CoveragePlot w={858} h={700} />
        <Text size={19} colour={H.muted}>
          Bricks were picked all over the table, and both plates appear on both sides of the centre line: green{' '}
          {sides(coverage.releases.GOOD)}, orange {sides(coverage.releases.DEFECTIVE)}.
        </Text>
      </Faceplate>
    </Col>
  </Screen>
);

// ── F5 DATA ───────────────────────────────────────────────────────────────────────────────

const S5: React.FC = () => (
  <Screen page={5} title="DATA" draftItems={DRAFT}>
    <Col w={930}>
      <Faceplate title="DATASET PIPELINE" pad={16}>
        <KV
          size={21}
          labelW={430}
          rows={[
            ['RAW · main', '501 episodes, never edited'],
            ['CLEANED · main-clean3', '486 episodes (15 removed)'],
            ['SORT LABELS CHECKED', '242 / 242 correct'],
            ['PICKS CHECKED · BRICK IN GRIPPER', '244 / 244'],
            ['TRAINING SET · main-clean4', '424: main-clean3 minus 62 picks ending at home'],
            ['NEW RECORDING · one-clean', '298 single-brick episodes (193 / 58 / 47)'],
          ]}
        />
        <Text size={18} colour={H.muted}>
          Sort labels: a script compares the top camera before the pick and after the sort to see which plate changed; the 35
          unclear cases were checked by eye. Picks: the last wrist-camera frame of each. Cleaning goes through Studio's API.
        </Text>
      </Faceplate>
      <Faceplate title="FINDINGS" grow={1} pad={12}>
        <Events
          size={18}
          tagW={180}
          rows={[
            {prio: 2, tag: 'TRAIN.CKPT', msg: 'Studio kept the best-validation epoch: the first SmolVLA shipped epoch 3 and moved jerkily. Fixed: validation split 0, final weights.'},
            {prio: 3, tag: 'DATA.ENDING', msg: '62 of 244 picks ended at home, 182 lifted. main-clean4 drops the 62, so every pick ends lifted.'},
            {prio: 3, tag: 'DATA.LABEL', msg: 'Two episodes held a pick and a sort but were labelled as picks: removed.'},
            {prio: 2, tag: 'CAM.TOP', msg: 'The top camera moved about 20 px after recording; pi0.5 was trained with image augmentation off.'},
          ]}
        />
      </Faceplate>
    </Col>
    <Col>
      <Faceplate title="MODEL HISTORY" hint="every model trained in Physical AI Studio on Modal" grow={1} pad={16}>
        <Tbl
          head={['MODEL', 'DATA', 'STEPS', 'RESULT']}
          widths="1.25fr 1.1fr 0.7fr 2fr"
          size={19}
          rows={[
            ['SmolVLA', 'main-clean · 108', '2,068', 'epoch-3 snapshot: jerky on the arm'],
            ['SmolVLA-v2', 'main-clean2 · 315', '11,322', 'offline jerk 8.5 / 7.6 (v1: 19.6 / 16.4)'],
            ['SmolVLA-v2-long', 'main-clean2 · 315', '20,757', 'offline jerk 6.1 / 5.0'],
            ['ACT-pick-v1', 'main-picks · 158', '18,120', 'offline: pick only, 15 ms GPU / 17 ms NPU'],
            [<b key="p">{model}</b>, `${f.dataset.name} · ${n.EPISODES ?? '–'}`, '5,116', <b key="r">on the arm: {res.verdicts_correct} / {res.bricks_through_loop} verdicts, {res.picks_ok} / {res.pick_attempts} picks</b>],
            ['Pi0.5-one-8gpu-b', 'one-clean · 298', '–', 'trained 23:17, not measured yet'],
          ]}
        />
        <Text size={17} colour={H.muted}>
          Jerk: 99th percentile of the change in speed per frame (shoulder_lift / elbow) on recorded episodes. Source:
          MODEL_RUN_NOTES.md, Studio's database.
        </Text>
      </Faceplate>
    </Col>
  </Screen>
);

// ── F6 INSPECTION ─────────────────────────────────────────────────────────────────────────

const OSD: React.FC<{text: string}> = ({text}) => (
  <span style={{position: 'absolute', left: 8, top: 6, fontFamily: MONO, fontSize: 15, color: '#fff', textShadow: '1px 1px 0 #000, -1px -1px 0 #000'}}>{text}</span>
);

const S6: React.FC = () => {
  const clean = byCycle(CLEAN);
  const marked = byCycle(MARKED);
  const rows: React.ReactNode[][] = [];
  for (const [c, what] of [
    [clean, 'clean'],
    [marked, 'marker'],
  ] as [Cycle | undefined, string][]) {
    for (const s of c?.inspect?.stops ?? []) {
      rows.push([`C${c?.cycle} · ${what}`, deg(s.deg), s.median.toFixed(3), String(insp.frames_per_stop), s.label]);
    }
  }
  return (
    <Screen page={6} title="INSPECTION" draftItems={DRAFT}>
      <Col w={1010}>
        <Faceplate title={`INSPECTION STATION · ANOMALIB PATCHCORE · OPENVINO ${f.models.anomaly.device}`} hint={`two bricks from loop run ${data.run.folder?.split('/').pop()}`} pad={16}>
          <div style={{display: 'flex', alignItems: 'baseline', gap: 16}}>
            <span style={{fontSize: 40, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 12}}>
              <Swatch colour={H.reject} size={22} />
              {marked?.inspect?.verdict ?? '—'}
            </span>
            {marked && <span style={{fontFamily: MONO, fontSize: 19, color: H.muted}}>C{MARKED} · worst {worst(marked).toFixed(2)} · rejected at the first stop</span>}
          </div>
          <Gauge value={marked ? Math.min(worst(marked), 1) : null} bands={[lowBand, highBand]} width={974} />
          <Tbl head={['BRICK', 'VIEW', 'MEDIAN', 'FRAMES', 'RESULT']} widths="1.3fr 0.7fr 1fr 0.8fr 1.2fr" size={20} rows={rows} />
        </Faceplate>
        <Faceplate title="SETTINGS" grow={1} pad={14}>
          <KV
            size={19}
            labelW={260}
            rows={[
              ['CROP', insp.crop],
              ['STOPS', `${stopsText} · the faces no gripper finger covers`],
              ['SCORE PER STOP', `median of ${insp.frames_per_stop} frames`],
              ['BANDS', `GOOD < ${lowBand.toFixed(2)} · DEFECTIVE > ${highBand.toFixed(2)} · between: second look, then reject`],
              ['HELD-OUT CHECK', '28 photos at the stops (14 clean, 14 marked): no overlap'],
              ['', 'highest clean 0.491 · lowest marked 0.588'],
              ['TRAINING', `${insp.train_photos} good photos (${insp.train_photos_at_show_pose} at the show pose) · ${insp.train_time.split(' (')[0]}`],
              ['INT8, WEIGHTS ONLY', `${insp.int8.split(',')[0]} · Δscore ≤ 0.05 · full INT8 not used (0.28)`],
            ]}
          />
        </Faceplate>
      </Col>
      <Col>
        <Faceplate title="WHY ONLY THE BRICK IS SCORED" pad={12}>
          <Events
            size={18}
            tagW={150}
            rows={[
              {prio: 2, tag: 'INSP.CROP', msg: 'First live run: a clean brick scored 1.0. The heat was on the camera bracket and the table, not the brick: the model scored the whole crop.'},
              {prio: 3, tag: 'INSP.FIX', msg: 'Each frame is cut to a 360 px square around the brick, found at the red finger tips, so photos from any arm pose train the same view.'},
              {prio: 3, tag: 'INSP.FINGER', msg: 'At 0° and 180° a gripper finger hides the brick, so the stops are 90° and −90°.'},
            ]}
          />
        </Faceplate>
        <Faceplate title="CAM 03 · INSPECTION · ANOMALIB OVERLAY" hint="before: whole crop · after: brick square" grow={1} pad={10}>
          <div style={{display: 'flex', gap: 8, flex: 1, minHeight: 0}}>
            {(
              [
                ['deck/first_live_failure_heat.jpg', 'BEFORE · whole crop · 1.00'],
                [`inspect/c${String(CLEAN).padStart(3, '0')}_90deg_heat.jpg`, `C${CLEAN} · clean · ${clean ? worst(clean).toFixed(2) : '–'}`],
                [`inspect/c${String(MARKED).padStart(3, '0')}_90deg_heat.jpg`, `C${MARKED} · marker · ${marked ? worst(marked).toFixed(2) : '–'}`],
              ] as [string, string][]
            ).map(([src, label]) => (
              <div key={src} style={{flex: 1, background: '#111', position: 'relative'}}>
                <Photo src={src} style={{objectFit: 'contain'}} />
                <OSD text={label} />
              </div>
            ))}
          </div>
          <Text size={17} colour={H.muted}>
            Heatmap: where the model sees something unlike its training photos. White box: the brick square that is scored. Scores
            are normalised so that 0.5 is the model's threshold.
          </Text>
        </Faceplate>
      </Col>
    </Screen>
  );
};

// ── F7 COMPUTE ────────────────────────────────────────────────────────────────────────────

type Row = {label: string; vals: (number | null | string)[]; used: string; note?: string};

/** Latency per model and device on a log axis (1 ms to 10 s); the device the loop uses is filled. */
const LogBars: React.FC<{rows: Row[]; devices: readonly string[]; w: number}> = ({rows, devices, w}) => {
  const left = 300;
  const span = w - left - 120;
  const x = (v: number) => left + (Math.log10(Math.max(v, 1)) / 4) * span;
  const rowH = 22;
  const groupH = devices.length * rowH + 12;
  const h = rows.length * groupH + 30;
  return (
    <svg width={w} height={h} style={{display: 'block'}}>
      {[1, 10, 100, 1000, 10000].map((v) => (
        <g key={v}>
          <line x1={x(v)} x2={x(v)} y1={0} y2={h - 22} stroke={H.rule} />
          <text x={x(v)} y={h - 5} textAnchor="middle" fontFamily={MONO} fontSize={14} fill={H.muted}>
            {v >= 1000 ? `${v / 1000} s` : `${v} ms`}
          </text>
        </g>
      ))}
      {rows.map((r, i) => (
        <g key={r.label} transform={`translate(0, ${i * groupH + 4})`}>
          <text x={0} y={rowH + 2} fontFamily={SANS} fontSize={16} fontWeight={700} fill={H.text}>
            {r.label.split(' · ')[0]}
          </text>
          {devices.map((d, j) => {
            const v = r.vals[j];
            const y = j * rowH;
            const used = r.used === d;
            return (
              <g key={d}>
                <text x={left - 12} y={y + 16} textAnchor="end" fontFamily={MONO} fontSize={13} fill={H.muted}>
                  {d}
                </text>
                {typeof v === 'number' ? (
                  <>
                    <rect x={left} y={y + 3} width={x(v) - left} height={16} fill={used ? H.on : '#b4b4b4'} stroke={H.strong} strokeWidth={1} />
                    <text x={x(v) + 8} y={y + 16} fontFamily={MONO} fontSize={14} fill={H.text}>
                      {v} ms
                    </text>
                  </>
                ) : (
                  <text x={left + 4} y={y + 16} fontFamily={MONO} fontSize={14} fill={H.muted}>
                    {v ?? 'not measured'}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      ))}
    </svg>
  );
};

/** One action chunk in asynchronous execution: when the next one is requested and when it arrives. */
const ChunkTiming: React.FC<{w: number; fps: number; inferMs: number}> = ({w, fps, inferMs}) => {
  const chunkMs = Math.round((50 / fps) * 1000);
  const requestAt = chunkMs - Math.round((25 / fps) * 1000);
  const x = (t: number) => 20 + (t / (chunkMs * 1.08)) * (w - 40);
  const arrive = requestAt + inferMs;
  return (
    <svg width={w} height={190} style={{display: 'block'}}>
      <ArrowDefs />
      <text x={20} y={22} fontFamily={SANS} fontSize={15} fontWeight={700} fill={H.muted} letterSpacing=".05em">
        ARM PLAYS THE CURRENT CHUNK · 50 ACTIONS AT {fps} HZ
      </text>
      <rect x={x(0)} y={34} width={x(chunkMs) - x(0)} height={30} fill={H.display} stroke={H.strong} />
      {Array.from({length: 51}, (_, i) => (
        <line key={i} x1={x((i * chunkMs) / 50)} x2={x((i * chunkMs) / 50)} y1={i % 5 ? 56 : 48} y2={64} stroke={H.faint} />
      ))}
      <line x1={x(requestAt)} x2={x(requestAt)} y1={28} y2={150} stroke={H.text} strokeWidth={2} strokeDasharray="5 4" />
      <text x={x(requestAt) + 6} y={86} fontFamily={MONO} fontSize={15} fill={H.text}>
        request next chunk (25 left)
      </text>
      <rect x={x(requestAt)} y={100} width={x(arrive) - x(requestAt)} height={24} fill={H.on} />
      <text x={x(arrive) + 8} y={118} fontFamily={MONO} fontSize={15} fill={H.text}>
        pi0.5 computes it: {Math.round(inferMs)} ms
      </text>
      <Pipe d={`M ${x(arrive)} 136 L ${x(chunkMs) - 2} 136`} />
      <text x={x(arrive) + 6} y={160} fontFamily={MONO} fontSize={15} fill={H.text}>
        {chunkMs - Math.round(arrive)} ms to spare
      </text>
      <text x={x(0)} y={182} fontFamily={MONO} fontSize={13} fill={H.muted}>0</text>
      <text x={x(chunkMs)} y={182} fontFamily={MONO} fontSize={13} fill={H.muted} textAnchor="end">{chunkMs} ms</text>
    </svg>
  );
};

const S7: React.FC = () => {
  const devices = ['GPU', 'NPU', 'CPU'] as const;
  const now: Row[] = [
    {label: `pi0.5 · ${model} · 50-action chunk`, vals: [pol.chunk_ms_gpu, null, null], used: 'GPU'},
    {label: 'PatchCore · brick square · one photo', vals: [insp.ms_gpu_loop, insp.ms_npu, insp.ms_cpu], used: f.models.anomaly.device},
  ];
  const earlier: Row[] = [
    {label: 'SmolVLA-v2 · 50-action chunk', vals: [ms(bench('SmolVLA', 'GPU')), "won't compile", ms(bench('SmolVLA', 'CPU'))], used: ''},
    {label: 'ACT-pick-v1 · 100-action chunk', vals: [ms(bench('ACT', 'GPU')), ms(bench('ACT', 'NPU')), ms(bench('ACT', 'CPU'))], used: ''},
  ];
  const cell = (r: Row) => {
    const nums = r.vals.filter((v): v is number => typeof v === 'number');
    const best = nums.length > 1 ? Math.min(...nums) : null;
    return [
      r.label,
      ...r.vals.map((v, j) => (
        <span key={j} style={{textDecoration: typeof v === 'number' && v === best ? 'underline' : 'none', fontWeight: r.used === devices[j] ? 700 : 400, color: typeof v === 'number' ? H.text : H.muted}}>
          {v === null ? '–' : v}
          {r.used === devices[j] ? ' ■' : ''}
        </span>
      )),
    ];
  };
  const budget = Math.round((25 / loop.fps) * 1000);
  const alarms: Ev[] = [
    {prio: 2, tag: 'NODE.TEMP', msg: `${res.thermal.split(' (')[0]}; alarm at 90 °C. Laptop on mains, rested before runs.`},
    {prio: 2, tag: 'BENCH.BUSY', msg: 'PatchCore CPU and NPU times were measured while the loop ran. Re-measure on a quiet laptop.'},
  ];
  return (
    <Screen page={7} title="COMPUTE" draftItems={DRAFT}>
      <Col w={1110}>
        <Faceplate title="COMPUTE NODE · OPENVINO · ON-DEVICE" hint={`median latency per call, ms · ${f.laptop}`} grow={1} pad={14}>
          <div style={{fontSize: 15, fontWeight: 700, letterSpacing: '.05em', color: H.muted}}>THE LOOP TONIGHT · MEASURED ON THE ARM</div>
          <Tbl head={['MODEL', 'GPU', 'NPU', 'CPU']} widths="2.3fr 0.9fr 0.9fr 0.9fr" align={['l', 'r', 'r', 'r']} size={22} rows={now.map(cell)} />
          <Text size={16} colour={H.muted}>
            pi0.5: median of 97 policy stages. PatchCore GPU: {insp.ms_gpu_loop} ms (p95 {insp.ms_gpu_loop_p95}) over 210 photos in the loop.
            ■: the device the loop uses. –: not measured.
          </Text>
          <div style={{fontSize: 15, fontWeight: 700, letterSpacing: '.05em', color: H.muted, marginTop: 4}}>EARLIER MODELS · BENCHMARK 13:24, BUSY LAPTOP</div>
          <Tbl head={['MODEL', 'GPU', 'NPU', 'CPU']} widths="2.3fr 0.9fr 0.9fr 0.9fr" align={['l', 'r', 'r', 'r']} size={20} rows={earlier.map(cell)} />
          <div style={{borderTop: `1px solid ${H.line}`, paddingTop: 8}}>
            <div style={{fontSize: 15, fontWeight: 700, letterSpacing: '.05em', color: H.muted, marginBottom: 4}}>LATENCY · LOG SCALE · FILLED = USED BY THE LOOP</div>
            <LogBars rows={[...now, ...earlier]} devices={devices} w={1080} />
          </div>
          <div style={{marginTop: 'auto'}}>
            <Events size={18} tagW={160} rows={alarms} />
          </div>
        </Faceplate>
      </Col>
      <Col>
        <Faceplate title="DEVICE ASSIGNMENT" grow={1} pad={16}>
          <KV
            size={20}
            labelW={250}
            rows={[
              ['PI0.5 → GPU', `${pol.chunk_ms_gpu} ms per 50-action chunk, on the arm`],
              ['CHUNK BUDGET', `${budget} ms · ×${(budget / pol.chunk_ms_gpu).toFixed(1)} on the median`],
              ['EXECUTION', 'asynchronous: the next chunk is computed while the arm moves'],
              ['PATCHCORE → GPU', `${insp.ms_gpu_loop} ms per photo, while no policy runs`],
              ['ANOMALIB TRAINING', insp.train_time],
              ['NPU', 'ACT pick benchmarked at 17 ms; not used by the pi0.5 loop'],
              ['LOGGED EVERY CYCLE', 'package temperature, CPU / GPU / NPU load'],
            ]}
          />
          <div style={{marginTop: 'auto', borderTop: `1px solid ${H.line}`, paddingTop: 10}}>
            <ChunkTiming w={740} fps={loop.fps} inferMs={pol.chunk_ms_gpu} />
          </div>
        </Faceplate>
      </Col>
    </Screen>
  );
};

// ── F8 RESULTS ────────────────────────────────────────────────────────────────────────────

/** Worst stop score per inspected brick, in cycle order, against the bands: an HMI trend display. */
const ScoreTrend: React.FC<{w: number; h: number}> = ({w, h}) => {
  const pts = cycles.filter((c) => c.inspect?.stops?.length && c.cycle <= 85);
  const left = 56;
  const bottom = 34;
  const x = (i: number) => left + 12 + (i / Math.max(pts.length - 1, 1)) * (w - left - 30);
  const y = (v: number) => 12 + (1 - Math.min(v, 1)) * (h - bottom - 12);
  return (
    <div style={{background: H.display, border: '1px solid', borderColor: '#9a9a9a #f7f7f7 #f7f7f7 #9a9a9a'}}>
      <svg width={w} height={h} style={{display: 'block'}}>
        <rect x={left} y={y(lowBand)} width={w - left - 8} height={y(0) - y(lowBand)} fill={H.range} opacity={0.6} />
        {[0, 0.25, 0.5, 0.75, 1].map((v) => (
          <g key={v}>
            <line x1={left} x2={w - 8} y1={y(v)} y2={y(v)} stroke={H.rule} />
            <text x={left - 8} y={y(v) + 5} textAnchor="end" fontFamily={MONO} fontSize={13} fill={H.muted}>
              {v.toFixed(2)}
            </text>
          </g>
        ))}
        {[lowBand, highBand].map((b) => (
          <line key={b} x1={left} x2={w - 8} y1={y(b)} y2={y(b)} stroke={H.strong} strokeWidth={2} strokeDasharray={b === highBand ? '7 5' : undefined} />
        ))}
        <text x={w - 12} y={y(lowBand) + 18} textAnchor="end" fontFamily={MONO} fontSize={13} fill={H.text}>GOOD &lt; {lowBand.toFixed(2)}</text>
        <text x={w - 12} y={y(highBand) - 8} textAnchor="end" fontFamily={MONO} fontSize={13} fill={H.text}>DEFECTIVE &gt; {highBand.toFixed(2)}</text>
        {pts.map((c, i) => {
          const v = worst(c);
          const bad = c.inspect?.verdict === 'DEFECTIVE';
          return bad ? (
            <rect key={c.cycle} x={x(i) - 6} y={y(v) - 6} width={12} height={12} fill={H.reject} stroke={H.strong} />
          ) : (
            <circle key={c.cycle} cx={x(i)} cy={y(v)} r={6} fill={H.strong} />
          );
        })}
        <text x={left} y={h - 10} fontFamily={MONO} fontSize={13} fill={H.muted}>
          C{pts[0]?.cycle}
        </text>
        <text x={w - 8} y={h - 10} textAnchor="end" fontFamily={MONO} fontSize={13} fill={H.muted}>
          C{pts[pts.length - 1]?.cycle} · {pts.length} bricks in this run
        </text>
      </svg>
    </div>
  );
};

const S8: React.FC = () => (
  <Screen page={8} title="RESULTS" draftItems={DRAFT}>
    <Col w={960}>
      <Faceplate title="PRODUCTION · ON THE ARM, FINAL SETTINGS" hint={`${res.model} · bands ${lowBand} / ${highBand}`} pad={16}>
        <KV
          size={23}
          labelW={430}
          rows={[
            ['BRICKS THROUGH THE FULL LOOP', String(res.bricks_through_loop)],
            ['INSPECTION VERDICT CORRECT', `${res.verdicts_correct} / ${res.bricks_through_loop}`],
            ['DEFECTIVE BRICKS REJECTED', `${res.defective_rejected[0]} / ${res.defective_rejected[1]}`],
            ['CLEAN BRICKS ACCEPTED', `${res.clean_accepted[0]} / ${res.clean_accepted[1]}`],
            ['PICKS OK', `${res.picks_ok} / ${res.pick_attempts}  (+${res.picks_stopped_by_operator} stopped by the operator)`],
            ['MEDIAN PER BRICK', `${res.median_cycle_s} s`],
            ['STAGES · PICK / INSPECT / SORT', `${res.median_pick_s} / ${res.median_inspect_s} / ${res.median_sort_s} s`],
            ['LANDED ON THE TOLD PLATE', <Val key="l" v={res.placements_checked} name="NOT LOGGED" />],
          ]}
        />
        <Text size={17} colour={H.muted}>
          Runs {res.runs.map((r) => r.replace('loop/runs/', '')).join(', ')}. Every verdict checked by eye against the photos. A pick that
          times out stops the arm until the operator resumes.
        </Text>
      </Faceplate>
      <Faceplate title="EVENTS · FAILURES" grow={1} pad={12}>
        <Events size={17} tagW={150} rows={failureEvents()} />
      </Faceplate>
    </Col>
    <Col>
      <Faceplate title="TREND · WORST STOP SCORE PER BRICK" hint={`loop run ${data.run.folder?.split('/').pop()}, cycles 1–85`} grow={1}>
        <ScoreTrend w={888} h={640} />
        <div style={{display: 'flex', gap: 24, fontSize: 17, color: H.muted, alignItems: 'center'}}>
          <span style={{display: 'flex', gap: 8, alignItems: 'center'}}>
            <span style={{width: 12, height: 12, borderRadius: 6, background: H.strong, display: 'inline-block'}} /> accepted (GOOD)
          </span>
          <span style={{display: 'flex', gap: 8, alignItems: 'center'}}>
            <Swatch colour={H.reject} size={12} /> rejected (DEFECTIVE)
          </span>
          <span>shaded: good band</span>
        </div>
        <Text size={17} colour={H.muted}>
          Rejected bricks between the lines were unsure at first and got a second look. Three of the rejected bricks were clean (see
          INSP.FALSE).
        </Text>
      </Faceplate>
    </Col>
  </Screen>
);

// ── F9 LIMITS ─────────────────────────────────────────────────────────────────────────────

const S9: React.FC = () => (
  <Screen page={9} title="LIMITS" draftItems={DRAFT}>
    <Col w={1050}>
      <Faceplate title="ALARMS · KNOWN LIMITS" grow={1} pad={12}>
        <Events
          size={20}
          tagW={180}
          rows={[
            ...failureEvents(),
            {prio: 2, tag: 'NODE.TEMP', msg: `${res.thermal.split(' (')[0]}.`},
            {prio: 3, tag: 'INSP.LIGHT', msg: 'Inspection is trained on our bricks under one lamp and backdrop. Other lighting needs new photos.'},
          ]}
        />
      </Faceplate>
    </Col>
    <Col>
      <Faceplate title="WORK ORDERS · NEXT" grow={1} pad={14}>
        <Tbl
          head={['WO', 'ACTION']}
          widths="80px 1fr"
          size={20}
          rows={[
            ['01', 'Put the top camera back where it was during recording, and train with image augmentation on.'],
            ['02', 'Add good photos of long and tall bricks held at one end (the three false rejects).'],
            ['03', 'Test Pi0.5-one-8gpu-b (298 new single-brick episodes) on the arm with the same counts.'],
            ['04', 'Log where each brick lands (operator marks on the HMI) to count placements.'],
            ['05', 'Detect an empty gripper in the inspection photo and pick again instead of sorting nothing.'],
          ]}
        />
        <div style={{marginTop: 'auto'}}>
          <Disp size={18}>All code, logs and numbers: the team repo · video/, loop/, anomaly/, bench/</Disp>
        </div>
      </Faceplate>
    </Col>
  </Screen>
);

export const SLIDES: React.FC[] = [S1, S2, S3, S4, S5, S6, S7, S8, S9];

export const Deck: React.FC = () => (
  <AbsoluteFill style={{background: H.bg}}>
    {SLIDES.map((S, i) => (
      <Sequence key={i} from={i * SLIDE_FRAMES} durationInFrames={SLIDE_FRAMES} name={`page ${i + 1}`}>
        <S />
      </Sequence>
    ))}
  </AbsoluteFill>
);
