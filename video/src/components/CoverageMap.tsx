import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import rawCoverage from '../../public/coverage.json';
import {data} from '../data';
import {C, font, monoFont} from '../theme';

// Training grasp and release points from forward kinematics (scripts/coverage.py), in cm:
// origin on the shoulder-pan axis, x forward, y to the robot's left.
type Pt = [number, number, number, number]; // x, y, z, episode
const coverage = rawCoverage as unknown as {grasps: Pt[]; releases: {GOOD: Pt[]; DEFECTIVE: Pt[]}};

export interface Trial {
  x: number;
  y: number;
  ok: boolean | null;
}

/** Top view of the workspace: the robot at the bottom, forward is up. */
export const CoverageMap: React.FC<{
  size: number;
  delay?: number; // s before the points start appearing
  show?: {grasps?: boolean; releases?: boolean};
  trials?: Trial[];
}> = ({size, delay = 0, show = {grasps: true, releases: true}, trials = []}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps - delay;
  const reach = 50; // cm shown from the base to the top edge
  const s = size / reach; // px per cm
  const px = (x: number, y: number) => [size / 2 - y * s, size - 14 - x * s] as const;
  const appear = (i: number, n: number, start: number, span: number) =>
    interpolate(t, [start + (i / n) * span, start + (i / n) * span + 0.25], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const dots = (pts: Pt[], colour: string, start: number) =>
    pts.map((p, i) => {
      const [cx, cy] = px(p[0], p[1]);
      return <circle key={`${colour}${i}`} cx={cx} cy={cy} r={3.2} fill={colour} opacity={0.9 * appear(i, pts.length, start, 1.6)} />;
    });
  const [bx, by] = px(0, 0);
  const legend: [string, string, boolean | undefined][] = [
    ['grasps (picks)', C.text, show.grasps],
    ['released on the green plate', C.good, show.releases],
    ['released on the orange plate', C.defective, show.releases],
  ];
  return (
    <div style={{position: 'relative', width: size, height: size}}>
      <svg width={size} height={size}>
        {[10, 20, 30, 40].map((r) => (
          <g key={r}>
            <circle cx={bx} cy={by} r={r * s} fill="none" stroke={C.line} strokeWidth={1} />
            <text x={bx + 4} y={by - r * s - 4} fill={C.dim} fontSize={14} fontFamily={monoFont}>
              {r} cm
            </text>
          </g>
        ))}
        {show.releases && dots(coverage.releases.GOOD, C.good, 1.2)}
        {show.releases && dots(coverage.releases.DEFECTIVE, C.defective, 1.2)}
        {show.grasps && dots(coverage.grasps, C.text, 0)}
        {trials.map((tr, i) => {
          const [cx, cy] = px(tr.x, tr.y);
          const o = appear(i, trials.length, 0.5, 1.5);
          const colour = tr.ok === null ? C.unsure : tr.ok ? C.good : C.defective;
          return (
            <g key={`t${i}`} opacity={o}>
              <circle cx={cx} cy={cy} r={11} fill="none" stroke={colour} strokeWidth={3} />
              <text x={cx + 14} y={cy + 6} fill={colour} fontSize={18} fontFamily={font} fontWeight={700}>
                {tr.ok === null ? '?' : tr.ok ? '✓' : '✗'}
              </text>
            </g>
          );
        })}
        <circle cx={bx} cy={by} r={10} fill={C.stage} />
      </svg>
      <div style={{position: 'absolute', left: 8, top: 4, display: 'flex', flexDirection: 'column', gap: 4}}>
        {legend
          .filter(([, , on]) => on)
          .map(([label, colour]) => (
            <div key={label} style={{fontFamily: font, fontSize: 18, color: C.dim, display: 'flex', alignItems: 'center', gap: 8}}>
              <span style={{width: 10, height: 10, borderRadius: 5, background: colour, display: 'inline-block'}} />
              {label}
            </div>
          ))}
        {trials.length > 0 && (
          <div style={{fontFamily: font, fontSize: 18, color: C.dim}}>rings: test positions, ✓ correct plate / ✗ not</div>
        )}
      </div>
    </div>
  );
};

export const coverageCounts = {grasps: coverage.grasps.length, good: coverage.releases.GOOD.length, defective: coverage.releases.DEFECTIVE.length};

/** Trial positions with outcomes, from the evaluation rounds (scripts/build_data.py). */
export const trials = (): Trial[] => (data as unknown as {trials?: Trial[]}).trials ?? [];

interface Layout {
  round: number;
  bricks: {n: number; x: number; y: number; rotation: number; defective: boolean}[];
  plates: {green: [number, number]; orange: [number, number]};
}

/** The random draw for a round: bricks (numbered, rotated) and plates, top view. */
export const LayoutMap: React.FC<{size: number; delay?: number}> = ({size, delay = 0}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const layout = (data as unknown as {layout: Layout | null}).layout;
  const t = frame / fps - delay;
  const s = size / 58; // cm across: room for plates at the far edge
  const px = (x: number, y: number) => [size / 2 - y * s, size - 10 - x * s] as const;
  const [bx, by] = px(0, 0);
  if (!layout) {
    return (
      <div style={{width: size, height: size, border: `2px dashed ${C.line}`, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(24,24,28,0.85)'}}>
        <span style={{fontFamily: monoFont, fontSize: 18, color: C.placeholder, textAlign: 'center', padding: 12}}>[map of the round's random draw: tools/random_layout.py]</span>
      </div>
    );
  }
  const plates: [string, [number, number]][] = [
    [C.good, layout.plates.green],
    [C.defective, layout.plates.orange],
  ];
  return (
    <div style={{width: size, height: size, background: 'rgba(24,24,28,0.88)', borderRadius: 10, border: `1.5px solid ${C.line}`, position: 'relative'}}>
      <svg width={size} height={size}>
        {[10, 20, 30, 40].map((r) => (
          <circle key={r} cx={bx} cy={by} r={r * s} fill="none" stroke={C.line} strokeWidth={1} />
        ))}
        {plates.map(([colour, [x, y]], i) => {
          const [cx, cy] = px(x, y);
          const o = interpolate(t, [1.6 + i * 0.3, 1.9 + i * 0.3], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          return <circle key={i} cx={cx} cy={cy} r={7 * s} fill={`${colour}33`} stroke={colour} strokeWidth={2.5} opacity={o} />;
        })}
        {layout.bricks.map((b, i) => {
          const [cx, cy] = px(b.x, b.y);
          const o = interpolate(t, [0.2 + i * 0.2, 0.45 + i * 0.2], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const colour = b.defective ? C.defective : C.text;
          return (
            <g key={b.n} opacity={o}>
              <rect x={cx - 3.2 * s} y={cy - 1.6 * s} width={6.4 * s} height={3.2 * s} fill="none" stroke={colour} strokeWidth={2} transform={`rotate(${-b.rotation} ${cx} ${cy})`} />
              <text x={cx + 4 * s} y={cy - 2 * s} fill={colour} fontSize={14} fontFamily={font} fontWeight={700}>
                {b.n}
              </text>
            </g>
          );
        })}
        <circle cx={bx} cy={by} r={6} fill={C.stage} />
      </svg>
      <div style={{position: 'absolute', left: 8, bottom: 6, fontFamily: font, fontSize: 16, color: C.dim}}>Round {layout.round} · random draw</div>
    </div>
  );
};
