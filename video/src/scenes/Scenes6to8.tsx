import React from 'react';
import {AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {VO_LEAD_S, data, timings} from '../data';
import {C, monoFont, verdictColour} from '../theme';
import {Appear, Badge, Box, Footage, Line, Title, Value} from '../components/ui';
import {CoverageMap, trials} from '../components/CoverageMap';

const n = data.numbers;
const f = data.facts;

// ── Scene 6: the run. One take: 1× / 4× / 1× (plate swap) / 4×. Our own voices, no narration. ──
// `at` is where each part starts in the footage (s after the take's offset). Set it from the real take.
const ALL_SEGMENTS = [
  {len: 18, speed: 1, at: 0, label: 'cycle 1', swap: false},
  {len: 10, speed: 4, at: 18, label: 'cycles 2–3', swap: false},
  {len: 7, speed: 1, at: 58, label: 'plate swap, next cycle', swap: true},
  {len: 5, speed: 4, at: 65, label: 'until the table is empty', swap: false},
];
// Without a tested plate swap, its 7 s go to the first cycle (VIDEO_PLAN 13.5).
const SEGMENTS = f.run_take.plate_swap_shown
  ? ALL_SEGMENTS
  : ALL_SEGMENTS.filter((s) => !s.swap).map((s, i) => (i === 0 ? {...s, len: s.len + 7} : s));

const StageOverlay: React.FC = () => {
  // Stage timeline of the take's first cycle, from its loop log.
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const c = data.run.cycles[0];
  if (!c) return null;
  const pickEnd = c.pick?.s ?? 8;
  const showEnd = pickEnd + (c.show_s ?? 5);
  const stage = t < pickEnd ? 'PICK' : t < showEnd ? 'SHOW + INSPECT' : 'SORT';
  const verdict = c.inspect?.verdict;
  return (
    <div style={{position: 'absolute', left: 48, top: 40, display: 'flex', flexDirection: 'column', gap: 12}}>
      <Box colour={C.stage} style={{padding: '8px 16px'}}>
        <Line size={26} mono>
          {stage}
        </Line>
      </Box>
      {t > pickEnd + 1 && c.inspect && (
        <Box style={{padding: '8px 16px'}}>
          <Line size={24} mono colour={C.dim}>
            scores {c.inspect.scores.map((s) => s.toFixed(2)).join(' · ')}
          </Line>
          <Line size={30} mono colour={verdictColour(verdict)}>
            {verdict}
          </Line>
        </Box>
      )}
      {t > showEnd && c.sort && (
        <Box colour={verdictColour(verdict)} style={{padding: '8px 16px', maxWidth: 900}}>
          <Line size={24} mono>
            task = "{c.sort.sentence}"
          </Line>
        </Box>
      )}
    </div>
  );
};

export const Run: React.FC = () => {
  const {fps} = useVideoConfig();
  let start = 0;
  return (
    <AbsoluteFill style={{background: C.bg}}>
      {SEGMENTS.map((s, i) => {
        const from = start;
        start += s.len;
        return (
          <Sequence key={i} from={Math.round(from * fps)} durationInFrames={Math.round(s.len * fps)}>
            <Footage
              id="a1"
              label={`the run, one take: ${s.label}`}
              startFrom={f.run_take.footage_offset_s + s.at}
              speed={s.speed}
              volume={s.speed === 1 ? 1 : 0.3}
            />
            <Badge text={s.speed === 1 ? '1×' : `${s.speed}× · still uncut`} corner="br" />
            {i === 0 && <StageOverlay />}
            {s.swap && (
              <div style={{position: 'absolute', left: 48, top: 40}}>
                <Box style={{padding: '8px 16px'}}>
                  <Line size={28}>Plates swapped by hand</Line>
                  <Line size={24} colour={C.dim}>
                    It goes by colour, not by the old position
                  </Line>
                </Box>
              </div>
            )}
            {i === SEGMENTS.length - 1 && (
              <div style={{position: 'absolute', left: 48, bottom: 40}}>
                <Box style={{padding: '8px 16px'}}>
                  <Line size={30}>
                    Table cleared · <Value v={f.run_take.result_line} name="N / 6 on the correct plate" />
                  </Line>
                </Box>
              </div>
            )}
          </Sequence>
        );
      })}
      <Badge text="One take · no cuts" />
    </AbsoluteFill>
  );
};

// ── Scene 7: results over every random round, failures included. ──
type NumKey = keyof typeof data.numbers;
const ROWS: [string, NumKey, NumKey][] = [
  ['Pick, first try', 'P', 'M'],
  ['Inspection verdict correct', 'I', 'M'],
  ['Placed on the plate it was told', 'S', 'M'],
  ['Correct end to end', 'E', 'M'],
];

export const Results: React.FC = () => (
  <AbsoluteFill style={{background: C.bg, padding: '100px 120px', flexDirection: 'row', gap: 70}}>
    <div style={{flex: 1, display: 'flex', flexDirection: 'column', gap: 34}}>
    <Appear delay={0.2}>
      <Title size={46}>
        <Value v={n.R} name="R" /> random {n.R === 1 ? 'layout' : 'layouts'} · <Value v={n.M} name="M" /> cycles
      </Title>
    </Appear>
    {ROWS.map(([label, num, den], i) => (
      <Appear key={label} delay={1 + i * 1.2}>
        <div style={{display: 'flex', justifyContent: 'space-between', borderBottom: `1px solid ${C.line}`, paddingBottom: 14, maxWidth: 1100}}>
          <Line size={38}>{label}</Line>
          <Line size={38} mono>
            <Value v={n[num]} name={num} /> / <Value v={n[den]} name={den} />
          </Line>
        </div>
      </Appear>
    ))}
    <Appear delay={5.6}>
      <div style={{display: 'flex', justifyContent: 'space-between', maxWidth: 1100}}>
        <Line size={38}>Median cycle</Line>
        <Line size={38} mono>
          <Value v={n.X} name="X" digits={1} unit=" s" />
        </Line>
      </div>
    </Appear>
    <Appear delay={6.8}>
      <Line size={26} colour={C.dim}>
        Failures:{' '}
        {data.evaluation.failures.length ? data.evaluation.failures.slice(0, 6).join(' · ') : <Value v={null} name="one line per failure" />}
      </Line>
    </Appear>
    </div>
    <Appear delay={1} style={{width: 700}}>
      <CoverageMap size={700} delay={1.2} show={{grasps: true, releases: false}} trials={trials()} />
      {trials().length === 0 && (
        <Line size={22} colour={C.placeholder}>
          [test positions with ✓ / ✗ appear here after the evaluation rounds]
        </Line>
      )}
    </Appear>
  </AbsoluteFill>
);

// ── Scene 8: compute, then the end card. ──
const Chip: React.FC<{device: string; rows: {what: string; ms: number | null; unit: string}[]; delay: number}> = ({device, rows, delay}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const grow = interpolate(frame, [(delay + 0.4) * fps, (delay + 1.4) * fps], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <Appear delay={delay} style={{flex: 1}}>
      <Box style={{height: 330, display: 'flex', flexDirection: 'column', gap: 18}}>
        <Title size={40}>{device}</Title>
        {rows.map((r) => (
          <div key={r.what}>
            <Line size={24}>{r.what}</Line>
            {r.ms !== null && (
              <div style={{display: 'flex', alignItems: 'center', gap: 14}}>
                <div style={{flex: 1}}>
                  <div style={{height: 14, width: `${Math.max(2, (r.ms / 250) * 100) * grow}%`, background: C.stage, borderRadius: 7}} />
                </div>
                <span style={{fontFamily: monoFont, fontSize: 26, color: C.text, width: 110, textAlign: 'right'}}>
                  {Math.round(r.ms)} ms{r.unit}
                </span>
              </div>
            )}
          </div>
        ))}
      </Box>
    </Appear>
  );
};

export const Compute: React.FC = () => {
  const {fps} = useVideoConfig();
  // The end card comes in once the narration has finished.
  const cardAt = Math.max(6.5, VO_LEAD_S + (timings.scenes.s8?.duration ?? 6) + 0.4);
  const pick = f.models.pick;
  const actOnNpu = pick.name.toUpperCase().startsWith('ACT') && pick.device === 'NPU';
  const actNpu = data.bench.policy.find((r) => r.model.startsWith('ACT') && r.device === 'NPU')?.median_ms ?? null;
  const gpuRows = [
    {what: 'SmolVLA, per 50-action chunk', ms: n.SORT_MS, unit: ''},
    {what: 'PatchCore, per view', ms: n.INSPECT_MS, unit: ''},
  ];
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <Sequence durationInFrames={Math.round(cardAt * fps)}>
        <AbsoluteFill style={{padding: '110px 100px', gap: 40}}>
          <Appear delay={0.1}>
            <Title size={44}>All inference on the laptop · OpenVINO</Title>
            <Line colour={C.dim}>{f.laptop}</Line>
          </Appear>
          <div style={{display: 'flex', gap: 30}}>
            <Chip device="CPU" delay={0.8} rows={[{what: 'The loop, scripted moves, cameras', ms: null, unit: ''}]} />
            <Chip device="GPU" delay={1.4} rows={gpuRows} />
            <Chip
              device="NPU"
              delay={2}
              rows={[{what: actOnNpu ? 'ACT pick, per 100-action chunk' : 'ACT pick (benchmarked, not in this take)', ms: actNpu, unit: ''}]}
            />
          </div>
        </AbsoluteFill>
      </Sequence>
      <Sequence from={Math.round(cardAt * fps)}>
        <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', gap: 22}}>
          <Appear delay={0.1}>
            <Title size={96}>Jenssenit</Title>
          </Appear>
          <Appear delay={0.5}>
            <Line colour={C.dim}>Intel Physical AI Challenge · Junction 2026</Line>
          </Appear>
          <Appear delay={0.9}>
            <Line size={28} mono>
              <Value v={f.repo_url} name="repo link" />
            </Line>
          </Appear>
          <Appear delay={1.2}>
            <Line size={28} colour={C.dim}>
              {f.team.length ? f.team.join(' · ') : <Value v={null} name="team names" />}
            </Line>
          </Appear>
          <div style={{position: 'absolute', bottom: 36}}>
            <Line size={20} colour={C.dim}>
              Narration: synthetic voice (Kokoro-82M). Footage: real, as labelled.
            </Line>
          </div>
        </AbsoluteFill>
      </Sequence>
    </AbsoluteFill>
  );
};
