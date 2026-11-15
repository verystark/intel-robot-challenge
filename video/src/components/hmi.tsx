// Copied from src/deck/hmi.tsx (the deck owns that one) so the video keeps a stable copy.
// Building blocks for the deck in the style of the cell's own operator screen
// (loop/dashboard/static/hmi, after ISA-101): grey when normal, colour only for abnormal states,
// faceplates with title bars, values in monospace, equipment that runs is filled dark grey.
// Colours come from the dashboard's palette.json, so the deck and the HMI can't drift apart.
import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import palette from '../../../loop/dashboard/palette.json';
import rawCoverage from '../../public/coverage.json';
import {Num, data} from '../data';

const p = palette.hmi;
export const H = {
  bg: p.background,
  panel: p.panel,
  display: p.display,
  line: p.line,
  strong: p.equipment_on,
  on: p.equipment_on,
  text: p.text,
  muted: p.muted,
  faint: '#8f8f8f',
  range: p.normal_range,
  p1: p.alarm_high,
  p2: p.alarm_medium,
  info: p.info,
  good: p.plate_good,
  reject: p.plate_reject,
  head: '#cfcfcf',
  top: '#3e3e3e',
  rule: '#c4c4c4',
};
export const SANS = 'Arial, "Liberation Sans", Helvetica, "DejaVu Sans", sans-serif';
export const MONO = '"DejaVu Sans Mono", "Liberation Mono", "Courier New", monospace';

export const SCREENS = ['SYSTEM', 'TASK', 'PROCESS', 'POLICY', 'DATA', 'INSPECTION', 'COMPUTE', 'RESULTS', 'LIMITS'];

// ── The screen frame: top bar, alarm banner, screen tabs, status line ───────────────────────

const HBox: React.FC<{k: string; v: React.ReactNode; tone?: 'normal' | 'p2'}> = ({k, v, tone = 'normal'}) => (
  <div style={{display: 'flex', alignItems: 'stretch', border: '1px solid #6a6a6a', background: '#2c2c2c', height: 38}}>
    <div style={{padding: '0 10px', color: '#a8a8a8', fontSize: 15, display: 'flex', alignItems: 'center', borderRight: '1px solid #555', letterSpacing: '.06em', fontFamily: SANS}}>
      {k}
    </div>
    <div
      style={{
        padding: '0 14px',
        font: `19px/38px ${MONO}`,
        color: tone === 'p2' ? '#111' : '#f0f0f0',
        background: tone === 'p2' ? H.p2 : 'transparent',
        minWidth: 70,
        textAlign: 'center',
      }}
    >
      {v}
    </div>
  </div>
);

export const Screen: React.FC<{page: number; title: string; draftItems: string[]; children: React.ReactNode}> = ({page, title, draftItems, children}) => {
  const draft = draftItems.length > 0;
  return (
    <AbsoluteFill style={{background: H.bg, color: H.text, fontFamily: SANS, display: 'flex', flexDirection: 'column'}}>
      <div style={{flex: '0 0 58px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 14px', background: H.top, color: '#e8e8e8', borderBottom: '1px solid #222'}}>
        <div style={{fontSize: 24, letterSpacing: '.04em'}}>
          <b>CELL 01</b>
          <span style={{color: '#8a8a8a', margin: '0 14px'}}>|</span>BRICK QC &amp; SORT
          <span style={{color: '#8a8a8a', margin: '0 14px'}}>|</span>
          {title}
        </div>
        <div style={{display: 'flex', gap: 10}}>
          <HBox k="TEAM" v="JENSSENIT" />
          <HBox k="DATA" v={draft ? 'DRAFT' : 'FINAL'} tone={draft ? 'p2' : 'normal'} />
          <HBox k="PAGE" v={`${String(page).padStart(2, '0')} / ${String(SCREENS.length).padStart(2, '0')}`} />
        </div>
      </div>
      <div
        style={{
          flex: '0 0 38px',
          display: 'flex',
          alignItems: 'center',
          gap: 18,
          padding: '0 16px',
          background: draft ? H.p2 : H.panel,
          color: draft ? '#111' : H.muted,
          borderBottom: `1px solid ${H.line}`,
          font: `17px ${MONO}`,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
        }}
      >
        {draft ? (
          <>
            <b>P2</b>
            <span>DATA.DRAFT</span>
            <span style={{overflow: 'hidden', textOverflow: 'ellipsis'}}>{draftItems.join(' · ')}</span>
          </>
        ) : (
          'NO UNACKNOWLEDGED ALARMS'
        )}
      </div>
      <div style={{flex: '0 0 42px', display: 'flex', gap: 3, padding: '6px 10px 0', borderBottom: `1px solid ${H.line}`}}>
        {SCREENS.map((s, i) => {
          const on = i + 1 === page;
          return (
            <div
              key={s}
              style={{
                background: on ? H.panel : '#c6c6c6',
                border: `1px solid ${H.line}`,
                borderBottom: 0,
                padding: '0 18px',
                fontSize: 16,
                fontWeight: 700,
                letterSpacing: '.05em',
                color: on ? H.text : H.muted,
                display: 'flex',
                alignItems: 'center',
                position: 'relative',
                top: on ? 1 : 0,
              }}
            >
              {s}
              <span style={{fontWeight: 400, color: H.faint, marginLeft: 6, fontSize: 13}}>F{i + 1}</span>
            </div>
          );
        })}
      </div>
      <div style={{flex: 1, minHeight: 0, padding: 10, display: 'flex', gap: 10}}>{children}</div>
      <div style={{flex: '0 0 34px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 14px', background: '#c6c6c6', borderTop: `1px solid ${H.line}`, font: `15px ${MONO}`, color: H.muted}}>
        <span>JENSSENIT · INTEL PHYSICAL AI CHALLENGE · JUNCTION 2026</span>
        <span>VALUES FROM video/public/data.json · LOGS AND BENCHMARKS IN THE REPO</span>
      </div>
    </AbsoluteFill>
  );
};

// ── Faceplates and their contents ─────────────────────────────────────────────────────────

export const Col: React.FC<{children: React.ReactNode; w?: number; gap?: number; grow?: number}> = ({children, w, gap = 10, grow}) => (
  <div style={{display: 'flex', flexDirection: 'column', gap, width: w, flex: w ? '0 0 auto' : grow ?? 1, minWidth: 0, minHeight: 0}}>{children}</div>
);

export const Faceplate: React.FC<{title: string; hint?: string; children: React.ReactNode; grow?: number; style?: React.CSSProperties; pad?: number}> = ({
  title,
  hint,
  children,
  grow,
  style,
  pad = 12,
}) => (
  <div style={{background: H.panel, border: `1px solid ${H.line}`, display: 'flex', flexDirection: 'column', minHeight: 0, minWidth: 0, flex: grow ?? '0 0 auto', ...style}}>
    <div style={{background: H.head, borderBottom: `1px solid ${H.line}`, padding: '6px 12px', fontSize: 17, fontWeight: 700, letterSpacing: '.05em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>
      {title}
      {hint && <span style={{fontWeight: 400, color: H.muted, marginLeft: 12, letterSpacing: 0}}>{hint}</span>}
    </div>
    <div style={{padding: pad, display: 'flex', flexDirection: 'column', gap: 10, flex: 1, minHeight: 0}}>{children}</div>
  </div>
);

/** A value, or an amber "not measured yet" badge (ISA-101: bad-quality values are marked, not hidden). */
export const Val: React.FC<{v: Num | string | undefined; name: string; digits?: number; unit?: string}> = ({v, name, digits = 0, unit = ''}) => {
  if (v === null || v === undefined || v === '') {
    return <span style={{background: H.p2, color: '#111', padding: '0 8px', fontFamily: MONO}}>{name}</span>;
  }
  const text = typeof v === 'number' ? v.toLocaleString('en-GB', {maximumFractionDigits: digits, minimumFractionDigits: digits}) : v;
  return (
    <span>
      {text}
      {unit}
    </span>
  );
};

/** Label / value rows, like the HMI's production faceplate. */
export const KV: React.FC<{rows: [React.ReactNode, React.ReactNode][]; size?: number; labelW?: number}> = ({rows, size = 22, labelW = 330}) => (
  <div style={{display: 'flex', flexDirection: 'column'}}>
    {rows.map(([k, v], i) => (
      <div key={i} style={{display: 'flex', alignItems: 'baseline', gap: 16, borderBottom: '1px solid #d0d0d0', padding: '7px 2px'}}>
        <span style={{width: labelW, flex: '0 0 auto', fontSize: size - 6, fontWeight: 700, letterSpacing: '.04em', color: H.muted}}>{k}</span>
        <span style={{fontFamily: MONO, fontSize: size, textAlign: 'right', flex: 1}}>{v}</span>
      </div>
    ))}
  </div>
);

/** A plain table: small bold header, monospace cells. */
export const Tbl: React.FC<{head: string[]; rows: React.ReactNode[][]; widths?: string; size?: number; align?: ('l' | 'r')[]}> = ({
  head,
  rows,
  widths,
  size = 20,
  align,
}) => (
  <div style={{display: 'grid', gridTemplateColumns: widths ?? `repeat(${head.length}, 1fr)`}}>
    {head.map((h, j) => (
      <div key={`h${j}`} style={{fontSize: 15, fontWeight: 700, letterSpacing: '.04em', color: H.muted, padding: '4px 8px', borderBottom: `1px solid ${H.line}`, textAlign: align?.[j] === 'r' ? 'right' : 'left'}}>
        {h}
      </div>
    ))}
    {rows.map((r, i) =>
      r.map((c, j) => (
        <div
          key={`${i}-${j}`}
          style={{fontFamily: j === 0 ? SANS : MONO, fontSize: j === 0 ? size - 1 : size, padding: '7px 8px', borderBottom: '1px solid #d0d0d0', textAlign: align?.[j] === 'r' ? 'right' : 'left'}}
        >
          {c}
        </div>
      )),
    )}
  </div>
);

/** Alarm / event rows: P1 red, P2 amber, P3 information. */
export interface Ev {
  prio: 1 | 2 | 3;
  tag: string;
  msg: React.ReactNode;
}
export const Events: React.FC<{rows: Ev[]; size?: number; tagW?: number}> = ({rows, size = 20, tagW = 210}) => (
  <div style={{display: 'grid', gridTemplateColumns: `70px ${tagW}px 1fr`}}>
    {['PRIO', 'TAG', 'MESSAGE'].map((h) => (
      <div key={h} style={{fontSize: 15, fontWeight: 700, letterSpacing: '.04em', color: H.muted, padding: '4px 8px', borderBottom: `1px solid ${H.line}`}}>
        {h}
      </div>
    ))}
    {rows.map((r, i) => [
      <div
        key={`p${i}`}
        style={{
          fontWeight: 700,
          fontSize: 16,
          textAlign: 'center',
          padding: '8px 0',
          borderBottom: '1px solid #d0d0d0',
          background: r.prio === 1 ? H.p1 : r.prio === 2 ? H.p2 : 'transparent',
          color: r.prio === 1 ? '#fff' : r.prio === 2 ? '#111' : H.muted,
        }}
      >
        {r.prio === 3 ? 'INFO' : `P${r.prio}`}
      </div>,
      <div key={`t${i}`} style={{fontFamily: MONO, fontSize: size - 2, padding: '8px', borderBottom: '1px solid #d0d0d0'}}>
        {r.tag}
      </div>,
      <div key={`m${i}`} style={{fontSize: size, padding: '8px', borderBottom: '1px solid #d0d0d0', lineHeight: 1.3}}>
        {r.msg}
      </div>,
    ])}
  </div>
);

export const Disp: React.FC<{children: React.ReactNode; size?: number; style?: React.CSSProperties}> = ({children, size = 20, style}) => (
  <div style={{background: H.display, border: '1px solid', borderColor: '#9a9a9a #f7f7f7 #f7f7f7 #9a9a9a', fontFamily: MONO, fontSize: size, padding: '6px 10px', ...style}}>{children}</div>
);

export const Swatch: React.FC<{colour?: string; size?: number}> = ({colour, size = 16}) => (
  <span style={{width: size, height: size, border: `1px solid ${H.strong}`, display: 'inline-block', background: colour ?? 'transparent', flex: '0 0 auto'}} />
);

export const Text: React.FC<{children: React.ReactNode; size?: number; colour?: string}> = ({children, size = 21, colour = H.text}) => (
  <div style={{fontSize: size, color: colour, lineHeight: 1.35}}>{children}</div>
);

export const Photo: React.FC<{src: string; style?: React.CSSProperties}> = ({src, style}) => (
  <Img src={staticFile(src)} style={{width: '100%', height: '100%', objectFit: 'cover', display: 'block', ...style}} />
);

/** Score gauge: normal range shaded, threshold ticks, a pointer at the value. */
export const Gauge: React.FC<{value: number | null; bands: number[]; width: number}> = ({value, bands, width}) => {
  const h = 70;
  const x = (v: number) => 10 + v * (width - 20);
  return (
    <svg width={width} height={h} style={{display: 'block'}}>
      <rect x={10} y={22} width={width - 20} height={16} fill={H.display} stroke={H.line} />
      <rect x={x(0)} y={22} width={x(bands[0]) - x(0)} height={16} fill={H.range} />
      {bands.map((b) => (
        <line key={b} x1={x(b)} x2={x(b)} y1={16} y2={44} stroke={H.strong} strokeWidth={2} />
      ))}
      {value !== null && <polygon points={`${x(value) - 9},${54} ${x(value) + 9},${54} ${x(value)},${40}`} fill={H.text} />}
      <text x={x(0)} y={64} fontFamily={MONO} fontSize={14} fill={H.muted}>0.0</text>
      <text x={x(bands[0]) - 4} y={12} fontFamily={MONO} fontSize={14} fill={H.muted} textAnchor="end">GOOD ≤ {bands[0].toFixed(2)}</text>
      <text x={x(bands[1]) + 4} y={12} fontFamily={MONO} fontSize={14} fill={H.muted}>REJECT ≥ {bands[1].toFixed(2)}</text>
      <text x={x(1)} y={64} fontFamily={MONO} fontSize={14} fill={H.muted} textAnchor="end">1.0</text>
    </svg>
  );
};

// ── Top-view plots of the workspace (cm from the turret; forward is up) ──────────────────

type Pt = [number, number, number, number];
const coverage = rawCoverage as unknown as {grasps: Pt[]; releases: {GOOD: Pt[]; DEFECTIVE: Pt[]}};
export const coverageCounts = {grasps: coverage.grasps.length, good: coverage.releases.GOOD.length, defective: coverage.releases.DEFECTIVE.length};

interface Frame {
  w: number;
  h: number;
  s: number;
  px: (x: number, y: number) => [number, number];
}
const frameFor = (w: number, h: number): Frame => {
  const s = Math.min(w / 56, (h - 34) / 47);
  return {w, h, s, px: (x, y) => [w / 2 - y * s, h - 22 - x * s]};
};

const Grid: React.FC<{fr: Frame}> = ({fr}) => {
  const lines = [];
  for (let c = -25; c <= 25; c += 5) {
    const [x] = fr.px(0, c);
    lines.push(<line key={`v${c}`} x1={x} x2={x} y1={8} y2={fr.h - 22} stroke={c % 10 === 0 ? H.rule : '#dcdcdc'} strokeWidth={1} />);
  }
  for (let r = 0; r <= 45; r += 5) {
    const [, y] = fr.px(r, 0);
    lines.push(<line key={`h${r}`} x1={6} x2={fr.w - 6} y1={y} y2={y} stroke={r % 10 === 0 ? H.rule : '#dcdcdc'} strokeWidth={1} />);
    if (r % 10 === 0 && r > 0) lines.push(<text key={`t${r}`} x={8} y={y - 4} fontFamily={MONO} fontSize={13} fill={H.muted}>{r} cm</text>);
  }
  const [bx, by] = fr.px(0, 0);
  lines.push(<rect key="base" x={bx - 10} y={by - 10} width={20} height={20} fill={H.strong} />);
  lines.push(<text key="bt" x={bx + 16} y={by + 5} fontFamily={MONO} fontSize={13} fill={H.muted}>J1 BASE</text>);
  return <>{lines}</>;
};

export interface Trial {
  x: number;
  y: number;
  ok: boolean | null;
}

export const CoveragePlot: React.FC<{w: number; h: number; releases?: boolean; grasps?: boolean; trials?: Trial[]}> = ({w, h, releases = true, grasps = true, trials = []}) => {
  const fr = frameFor(w, h);
  const dot = (pt: Pt, i: number, fill: string, r = 3.2) => {
    const [cx, cy] = fr.px(pt[0], pt[1]);
    return <circle key={`${fill}${i}`} cx={cx} cy={cy} r={r} fill={fill} />;
  };
  return (
    <div style={{position: 'relative', width: w, height: h, background: H.display, border: '1px solid', borderColor: '#9a9a9a #f7f7f7 #f7f7f7 #9a9a9a'}}>
      <svg width={w} height={h} style={{display: 'block'}}>
        <Grid fr={fr} />
        {releases && coverage.releases.GOOD.map((pt, i) => dot(pt, i, H.good))}
        {releases && coverage.releases.DEFECTIVE.map((pt, i) => dot(pt, i, H.reject))}
        {grasps && coverage.grasps.map((pt, i) => dot(pt, i, H.strong, 2.8))}
        {trials.map((t, i) => {
          const [cx, cy] = fr.px(t.x, t.y);
          const c = t.ok === false ? H.p1 : H.text;
          return (
            <g key={`t${i}`}>
              <circle cx={cx} cy={cy} r={11} fill="none" stroke={c} strokeWidth={3} />
              <text x={cx + 14} y={cy + 6} fontFamily={SANS} fontSize={18} fontWeight={700} fill={c}>
                {t.ok === false ? '✗' : t.ok ? '✓' : '?'}
              </text>
            </g>
          );
        })}
      </svg>
      <div style={{position: 'absolute', right: 10, top: 8, display: 'flex', flexDirection: 'column', gap: 4, fontSize: 15, color: H.muted, background: 'rgba(242,242,242,.9)', padding: '4px 8px'}}>
        {grasps && (
          <span style={{display: 'flex', gap: 8, alignItems: 'center'}}>
            <Swatch colour={H.strong} size={11} /> grasp ({coverage.grasps.length})
          </span>
        )}
        {releases && (
          <>
            <span style={{display: 'flex', gap: 8, alignItems: 'center'}}>
              <Swatch colour={H.good} size={11} /> release, green plate ({coverage.releases.GOOD.length})
            </span>
            <span style={{display: 'flex', gap: 8, alignItems: 'center'}}>
              <Swatch colour={H.reject} size={11} /> release, orange plate ({coverage.releases.DEFECTIVE.length})
            </span>
          </>
        )}
        {trials.length > 0 && <span>rings: test positions · ✗ = not on the correct plate</span>}
      </div>
    </div>
  );
};

interface Layout {
  round: number;
  bricks: {n: number; x: number; y: number; rotation: number; defective: boolean}[];
  plates: {green: [number, number]; orange: [number, number]};
}

export const LayoutPlot: React.FC<{w: number; h: number}> = ({w, h}) => {
  const layout = (data as unknown as {layout: Layout | null}).layout;
  const fr = frameFor(w, h);
  return (
    <div style={{position: 'relative', width: w, height: h, background: H.display, border: '1px solid', borderColor: '#9a9a9a #f7f7f7 #f7f7f7 #9a9a9a'}}>
      <svg width={w} height={h} style={{display: 'block'}}>
        <Grid fr={fr} />
        {layout &&
          ([
            [H.good, layout.plates.green],
            [H.reject, layout.plates.orange],
          ] as [string, [number, number]][]).map(([c, [x, y]], i) => {
            const [cx, cy] = fr.px(x, y);
            return <circle key={i} cx={cx} cy={cy} r={7 * fr.s} fill={`${c}40`} stroke={c} strokeWidth={3} />;
          })}
        {layout?.bricks.map((b) => {
          const [cx, cy] = fr.px(b.x, b.y);
          const c = b.defective ? H.reject : H.text;
          return (
            <g key={b.n}>
              <rect x={cx - 3.2 * fr.s} y={cy - 1.6 * fr.s} width={6.4 * fr.s} height={3.2 * fr.s} fill="none" stroke={c} strokeWidth={2.5} transform={`rotate(${-b.rotation} ${cx} ${cy})`} />
              <text x={cx + 4 * fr.s} y={cy - 2 * fr.s} fontFamily={MONO} fontSize={16} fontWeight={700} fill={c}>
                B{b.n}
              </text>
            </g>
          );
        })}
      </svg>
      {!layout && (
        <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
          <span style={{background: H.p2, color: '#111', fontFamily: MONO, fontSize: 18, padding: '4px 10px'}}>NO ROUND LOADED · python3 tools/random_layout.py</span>
        </div>
      )}
    </div>
  );
};

// ── Process mimic pieces ──────────────────────────────────────────────────────────────────

export const Equip: React.FC<{x: number; y: number; w: number; h: number; title: string; sub?: string; on?: boolean; dashed?: boolean; icon?: React.ReactNode}> = ({
  x,
  y,
  w,
  h,
  title,
  sub,
  on,
  dashed,
  icon,
}) => (
  <g>
    <rect x={x} y={y} width={w} height={h} fill={on ? H.on : H.panel} stroke={H.strong} strokeWidth={2} strokeDasharray={dashed ? '8 6' : undefined} />
    <text x={x + w / 2} y={y + 32} textAnchor="middle" fontFamily={SANS} fontSize={20} fontWeight={700} fill={on ? '#fff' : H.text}>
      {title}
    </text>
    {sub && (
      <text x={x + w / 2} y={y + 56} textAnchor="middle" fontFamily={SANS} fontSize={16} fill={on ? '#d0d0d0' : H.muted}>
        {sub}
      </text>
    )}
    {icon}
  </g>
);

export const Pipe: React.FC<{d: string; arrow?: boolean}> = ({d, arrow = true}) => (
  <path d={d} fill="none" stroke={H.strong} strokeWidth={3} markerEnd={arrow ? 'url(#arrow)' : undefined} />
);

export const ArrowDefs: React.FC = () => (
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill={H.strong} />
    </marker>
  </defs>
);

/** A small data box under a mimic element, like the HMI's tag fields. */
export const TagBox: React.FC<{x: number; y: number; w: number; k: string; v: string}> = ({x, y, w, k, v}) => (
  <g>
    <rect x={x} y={y} width={w} height={30} fill={H.display} stroke="#9a9a9a" />
    <text x={x + 8} y={y + 20} fontFamily={SANS} fontSize={13} fontWeight={700} fill={H.muted} letterSpacing=".05em">
      {k}
    </text>
    <text x={x + w - 8} y={y + 21} fontFamily={MONO} fontSize={16} fill={H.text} textAnchor="end">
      {v}
    </text>
  </g>
);
