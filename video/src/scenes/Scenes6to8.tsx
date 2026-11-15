// Scenes 6–8: the run, the results measured on the arm, and the compute node, as HMI screens.
import React from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {VO_LEAD_S, data, timings} from '../data';
import {Appear, Footage, Value} from '../components/ui';
import {Frame} from '../components/frame';
import {Events, Ev, Faceplate, H, KV, MONO, SANS, Swatch, Text, Val} from '../components/hmi';

const f = data.facts;
const r = f.results;

// ── Scene 6: the run. One take: 1× / 4× (/ plate swap at 1×) / 4×. Our own voices, no narration. ──
// `at` is where each part starts in the footage (s after the take's offset). Set it from the real take.
const ALL_SEGMENTS = [
  {len: 13, speed: 1, at: 0, label: 'cycle 1', swap: false},
  {len: 10, speed: 4, at: 13, label: 'cycles 2–3', swap: false},
  {len: 7, speed: 1, at: 58, label: 'plate swap, next cycle', swap: true},
  {len: 5, speed: 4, at: 65, label: 'until the table is empty', swap: false},
];
// Without footage of a plate swap, its 7 s go to the first cycle (VIDEO_PLAN 13.5).
const SEGMENTS = f.run_take.plate_swap_shown
  ? ALL_SEGMENTS
  : ALL_SEGMENTS.filter((s) => !s.swap).map((s, i) => (i === 0 ? {...s, len: s.len + 7} : s));

const StepStrip: React.FC = () => {
  // The first logged cycle's stages, as the HMI's sequence steps; the running one is filled.
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const c = data.run.cycles[0];
  if (!c) return null;
  const pickEnd = c.pick?.s ?? 8;
  const inspEnd = pickEnd + (c.inspect_s ?? c.show_s ?? 4);
  const sortEnd = inspEnd + (c.sort?.s ?? 6);
  const active = t < pickEnd ? 0 : t < inspEnd ? 1 : t < sortEnd ? 2 : 3;
  const steps = [
    ['20', 'PICK'],
    ['40', 'INSPECT'],
    ['60', 'SORT'],
    ['10', 'HOME'],
  ];
  const v = c.inspect?.verdict;
  return (
    <div style={{position: 'absolute', left: 16, top: 16, display: 'flex', flexDirection: 'column', gap: 8, width: 620}}>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 4, background: 'rgba(227,227,227,.95)', border: `1px solid ${H.line}`, padding: 6}}>
        {steps.map(([num, name], i) => (
          <div key={name} style={{border: `1px solid ${H.strong}`, textAlign: 'center', padding: '4px 0', background: i === active ? H.on : H.panel, color: i === active ? '#fff' : H.muted}}>
            <div style={{font: `13px ${MONO}`}}>{num}</div>
            <div style={{fontSize: 18, fontWeight: 700, fontFamily: SANS}}>{name}</div>
          </div>
        ))}
      </div>
      {t > pickEnd + 0.5 && c.inspect && (
        <div style={{background: 'rgba(227,227,227,.95)', border: `1px solid ${H.line}`, padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 4}}>
          <div style={{display: 'flex', alignItems: 'center', gap: 10, fontFamily: SANS}}>
            <Swatch colour={v === 'GOOD' ? H.good : v === 'DEFECTIVE' ? H.reject : undefined} size={18} />
            <b style={{fontSize: 26}}>{v}</b>
            <span style={{font: `17px ${MONO}`, color: H.muted}}>
              {(c.inspect.stops ?? []).map((s) => `${s.deg > 0 ? '+' : '−'}${Math.abs(s.deg)}° ${s.median.toFixed(2)}`).join(' · ')}
            </span>
          </div>
          {t > inspEnd && c.sort && <div style={{font: `17px ${MONO}`, color: H.text}}>TASK → VLA "{c.sort.sentence}"</div>}
        </div>
      )}
    </div>
  );
};

export const Run: React.FC = () => {
  const {fps} = useVideoConfig();
  let start = 0;
  return (
    <AbsoluteFill>
      {SEGMENTS.map((s, i) => {
        const from = start;
        start += s.len;
        return (
          <Sequence key={i} from={Math.round(from * fps)} durationInFrames={Math.round(s.len * fps)}>
            <Frame
              title="OVERVIEW · CAM 04 · ONE TAKE"
              fields={[
                {k: 'MODE', v: 'AUTO'},
                {k: 'SPEED', v: s.speed === 1 ? '1×' : `${s.speed}×`},
                {k: 'TAKE', v: 'NO CUTS'},
              ]}
              dark
            >
              <div style={{position: 'relative', flex: 1}}>
                <Footage id="a1" label={`the run, one take: ${s.label}`} startFrom={f.run_take.footage_offset_s + s.at} speed={s.speed} volume={s.speed === 1 ? 1 : 0.3} />
                {i === 0 && <StepStrip />}
                {s.swap && (
                  <div style={{position: 'absolute', left: 16, top: 16, background: 'rgba(227,227,227,.95)', border: `1px solid ${H.line}`, padding: '8px 12px', fontFamily: SANS}}>
                    <b style={{fontSize: 24}}>PLATES SWAPPED BY HAND</b>
                    <div style={{fontSize: 19, color: H.muted}}>the next brick goes by colour, not by the old position</div>
                  </div>
                )}
                {i === SEGMENTS.length - 1 && (
                  <div style={{position: 'absolute', left: 16, bottom: 16, background: 'rgba(227,227,227,.95)', border: `1px solid ${H.line}`, padding: '8px 12px', fontSize: 24, fontFamily: SANS}}>
                    TABLE CLEARED · <Value v={f.run_take.result_line} name="N / M ON THE CORRECT PLATE" />
                  </div>
                )}
              </div>
            </Frame>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

// ── Scene 7: results measured on the arm, failures included. ──
const prio = (tag: string): 1 | 2 | 3 => (tag === 'PICK.MISS' || tag === 'INSP.FALSE' ? 2 : 3);

const CycleBar: React.FC<{w: number}> = ({w}) => {
  if (!r) return null;
  const parts: [string, number][] = [
    ['PICK', r.median_pick_s],
    ['INSPECT', r.median_inspect_s],
    ['SORT', r.median_sort_s],
  ];
  const other = Math.max(0, r.median_cycle_s - parts.reduce((s, p) => s + p[1], 0));
  const all: [string, number][] = [...parts, ['MOVES', other]];
  const scale = (w - 20) / r.median_cycle_s;
  let x = 10;
  return (
    <svg width={w} height={96} style={{display: 'block'}}>
      {all.map(([k, v], i) => {
        const x0 = x;
        x += v * scale;
        return (
          <g key={k}>
            <rect x={x0} y={10} width={v * scale} height={40} fill={i % 2 ? '#b4b4b4' : H.on} stroke={H.strong} />
            <text x={x0 + 8} y={36} fontFamily={MONO} fontSize={17} fill={i % 2 ? H.text : '#fff'}>
              {k}
            </text>
            <text x={x0 + 8} y={74} fontFamily={MONO} fontSize={17} fill={H.text}>
              {v.toFixed(1)} s
            </text>
          </g>
        );
      })}
    </svg>
  );
};

export const Results: React.FC = () => {
  const rows: [React.ReactNode, React.ReactNode][] = r
    ? [
        ['MODEL', r.model],
        ['BRICKS THROUGH THE WHOLE LOOP', r.bricks_through_loop],
        ['INSPECTION VERDICT CORRECT', `${r.verdicts_correct} / ${r.bricks_through_loop}`],
        ['DEFECTIVE BRICKS REJECTED', `${r.defective_rejected[0]} / ${r.defective_rejected[1]}`],
        ['CLEAN BRICKS ACCEPTED', `${r.clean_accepted[0]} / ${r.clean_accepted[1]}`],
        ['PICKS', `${r.picks_ok} / ${r.pick_attempts} attempts`],
        ['MEDIAN PER BRICK', `${r.median_cycle_s.toFixed(1)} s`],
      ]
    : [['RESULTS', <Val key="v" v={null} name="NOT MEASURED" />]];
  const events: Ev[] = (r?.failures ?? []).map((x) => {
    const [tag, ...rest] = x.split(': ');
    return {prio: prio(tag), tag, msg: rest.join(': ')};
  });
  return (
    <Frame title="RESULTS · ON THE ARM" fields={[{k: 'RUNS', v: String(r?.runs.length ?? 0)}, {k: 'CHECK', v: 'BY EYE'}]}>
      <div style={{width: 900, display: 'flex', flexDirection: 'column', gap: 10}}>
        <Appear delay={0.3}>
          <Faceplate title="PRODUCTION · SINCE START" hint={r?.verdicts_checked ?? ''} pad={16}>
            <KV size={26} labelW={460} rows={rows} />
          </Faceplate>
        </Appear>
        <Appear delay={5} style={{flex: 1, display: 'flex'}}>
          <Faceplate title="CYCLE TIME · MEDIAN PER BRICK" grow={1} pad={14}>
            <CycleBar w={866} />
            <Text size={18} colour={H.muted}>
              {r?.thermal ?? ''}
            </Text>
          </Faceplate>
        </Appear>
      </div>
      <Appear delay={7} style={{flex: 1, display: 'flex', minWidth: 0}}>
        <Faceplate title="EVENTS · FAILURES AND LIMITS" hint="every cycle counted" grow={1} pad={12}>
          <Events rows={events} size={20} tagW={170} />
          <div style={{marginTop: 'auto', font: `16px ${MONO}`, color: H.muted}}>{(r?.runs ?? []).join(' · ')}</div>
        </Faceplate>
      </Appear>
    </Frame>
  );
};

// ── Scene 8: the compute node, then the end card. ──
const Bar: React.FC<{label: string; dev: string; ms: number | null; note: string; used?: boolean; max: number}> = ({label, dev, ms, note, used, max}) => (
  <div style={{display: 'grid', gridTemplateColumns: '360px 70px 1fr 300px', alignItems: 'center', gap: 12, borderBottom: '1px solid #d0d0d0', padding: '10px 0'}}>
    <span style={{fontSize: 22, fontWeight: 700}}>{label}</span>
    <span style={{font: `20px ${MONO}`, color: H.muted}}>{dev}</span>
    <span style={{display: 'flex', alignItems: 'center', gap: 10}}>
      <span style={{height: 18, width: `${ms ? Math.max(1.5, (Math.log10(ms) / Math.log10(max)) * 100) : 0}%`, background: used ? H.on : '#b4b4b4', border: `1px solid ${H.strong}`}} />
      <span style={{font: `22px ${MONO}`}}>{ms ?? '–'} ms</span>
    </span>
    <span style={{fontSize: 17, color: H.muted}}>{note}</span>
  </div>
);

export const Compute: React.FC = () => {
  const {fps} = useVideoConfig();
  const ins = f.inspection;
  const cardAt = Math.max(6.5, VO_LEAD_S + (timings.scenes.s8?.duration ?? 6) + 0.4);
  return (
    <AbsoluteFill>
      <Sequence durationInFrames={Math.round(cardAt * fps)}>
        <Frame title="COMPUTE NODE · OPENVINO · ON-DEVICE" fields={[{k: 'NODE', v: 'CORE ULTRA X9 388H'}]}>
          <div style={{flex: 1, display: 'flex', flexDirection: 'column', gap: 10}}>
            <Faceplate title="LATENCY PER CALL · LOG SCALE · FILLED = THE DEVICE THE LOOP USES" pad={16}>
              <Appear delay={0.4}>
                <Bar label="pi0.5 · pick and sort" dev="GPU" ms={f.policy?.chunk_ms_gpu ?? null} note="per action chunk · on the arm" used max={1000} />
              </Appear>
              <Appear delay={1.2}>
                <Bar label="PatchCore · brick square" dev="GPU" ms={ins?.ms_gpu_loop ?? null} note={`p95 ${ins?.ms_gpu_loop_p95 ?? '–'} ms · on the arm`} used max={1000} />
              </Appear>
              <Appear delay={1.8}>
                <Bar label="PatchCore · brick square" dev="CPU" ms={ins?.ms_cpu ?? null} note="measured during a loop run" max={1000} />
              </Appear>
              <Appear delay={2.4}>
                <Bar label="PatchCore · brick square" dev="NPU" ms={ins?.ms_npu ?? null} note="measured during a loop run" max={1000} />
              </Appear>
            </Faceplate>
            <Appear delay={3.5} style={{flex: 1, display: 'flex'}}>
              <Faceplate title="NODE" grow={1} pad={16}>
                <KV
                  size={22}
                  labelW={360}
                  rows={[
                    ['EXECUTION', 'asynchronous: the next chunk is computed while the arm moves'],
                    ['INSPECTION ON THE GPU', 'no policy runs while the brick is shown'],
                    ['INT8 INSPECTION MODEL', `${ins?.fp32_mb ?? '–'} → ${ins?.int8_mb ?? '–'} MB · scores within ${ins?.int8_diff_max?.toFixed(2) ?? '–'} of FP32`],
                    ['INSPECTION TRAINING', ins?.train_time ?? '–'],
                    ['THERMAL', r?.thermal ?? '–'],
                  ]}
                />
              </Faceplate>
            </Appear>
          </div>
        </Frame>
      </Sequence>
      <Sequence from={Math.round(cardAt * fps)}>
        <EndCard />
      </Sequence>
    </AbsoluteFill>
  );
};

const EndCard: React.FC = () => (
  <Frame title="JENSSENIT" fields={[{k: 'TEAM', v: 'JENSSENIT'}]}>
    <div style={{flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
      <Appear delay={0.1}>
        <Faceplate title="SYSTEM" pad={36} style={{width: 1100}}>
          <div style={{fontSize: 96, fontWeight: 700, letterSpacing: '.02em', lineHeight: 1}}>JENSSENIT</div>
          <Text size={28}>Intel Physical AI Challenge · Junction 2026</Text>
          <KV
            size={24}
            labelW={260}
            rows={[
              ['CODE', <Val key="r" v={f.repo_url} name="REPO LINK" />],
              ['TEAM', f.team.length ? f.team.join(', ') : <Val key="t" v={null} name="TEAM NAMES" />],
            ]}
          />
          <Text size={18} colour={H.muted}>
            Narration: synthetic voice (Kokoro-82M). Footage: real, as labelled. Numbers: the cell's own logs.
          </Text>
        </Faceplate>
      </Appear>
    </div>
  </Frame>
);
