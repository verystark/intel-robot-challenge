import React from 'react';
import {AbsoluteFill, Easing, Img, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Num, Word, data, timings, VO_LEAD_S} from '../data';
import {C, font, monoFont} from '../theme';

const ease = Easing.bezier(0.33, 0, 0.2, 1);

/** Fades its children in, starting `delay` seconds into the scene. No sliding: the HMI doesn't move. */
export const Appear: React.FC<{delay?: number; dy?: number; children: React.ReactNode; style?: React.CSSProperties}> = ({
  delay = 0,
  dy = 0,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = interpolate(frame, [delay * fps, delay * fps + 0.3 * fps], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  return <div style={{opacity: t, transform: dy ? `translateY(${(1 - t) * dy}px)` : undefined, ...style}}>{children}</div>;
};

/** A measured number, or an amber "not measured" badge (a bad-quality value, in HMI terms). */
export const Value: React.FC<{v: Num | string | undefined; name: string; digits?: number; unit?: string}> = ({v, name, digits = 0, unit = ''}) => {
  if (v === null || v === undefined || v === '') {
    return <span style={{background: C.placeholder, color: '#111', padding: '0 8px', fontFamily: monoFont}}>{name}</span>;
  }
  const text = typeof v === 'number' ? v.toLocaleString('en-GB', {maximumFractionDigits: digits, minimumFractionDigits: digits}) : v;
  return (
    <span>
      {text}
      {unit}
    </span>
  );
};

/** Real footage if the file is there; an HMI "no signal" camera tile until it is filmed. */
export const Footage: React.FC<{id: string; label: string; startFrom?: number; speed?: number; volume?: number; style?: React.CSSProperties}> = ({
  id,
  label,
  startFrom = 0,
  speed = 1,
  volume = 1,
  style,
}) => {
  const {fps} = useVideoConfig();
  if (data.footage[id]) {
    return (
      <OffthreadVideo
        src={staticFile(`footage/${id}.mp4`)}
        startFrom={Math.round(startFrom * fps)}
        playbackRate={speed}
        volume={volume}
        style={{width: '100%', height: '100%', objectFit: 'cover', ...style}}
      />
    );
  }
  return (
    <AbsoluteFill style={{background: '#111', alignItems: 'center', justifyContent: 'center', ...style}}>
      <div style={{fontFamily: monoFont, color: '#e0e0e0', fontSize: 28, textAlign: 'center', lineHeight: 1.6}}>
        <span style={{background: C.placeholder, color: '#111', padding: '2px 10px'}}>{id.toUpperCase()} · NO SIGNAL · FOOTAGE TO FILM</span>
        <br />
        <span style={{fontSize: 22, color: '#a8a8a8'}}>{label}</span>
      </div>
    </AbsoluteFill>
  );
};

export const Photo: React.FC<{src: string; style?: React.CSSProperties}> = ({src, style}) => (
  <Img src={staticFile(src)} style={{width: '100%', height: '100%', objectFit: 'cover', display: 'block', ...style}} />
);

export const Title: React.FC<{children: React.ReactNode; size?: number; colour?: string}> = ({children, size = 54, colour = C.text}) => (
  <div style={{fontFamily: font, fontWeight: 700, fontSize: size, color: colour, lineHeight: 1.15}}>{children}</div>
);

export const Line: React.FC<{children: React.ReactNode; size?: number; colour?: string; mono?: boolean}> = ({children, size = 30, colour = C.text, mono = false}) => (
  <div style={{fontFamily: mono ? monoFont : font, fontSize: size, color: colour, lineHeight: 1.35}}>{children}</div>
);

/** Word-timed captions for a scene's narration, at most 7 words at a time, in a dark HMI bar. */
export const Captions: React.FC<{vo: string}> = ({vo}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const scene = timings.scenes[vo];
  if (!scene) return null;
  const t = frame / fps - VO_LEAD_S;
  const chunks: Word[][] = [];
  let current: Word[] = [];
  for (const w of scene.words) {
    current.push(w);
    if (current.length >= 7 || /[.;:!?]$/.test(w.text)) {
      chunks.push(current);
      current = [];
    }
  }
  if (current.length) chunks.push(current);
  const chunk = chunks.find((c) => t >= c[0].start - 0.05 && t <= c[c.length - 1].end + 0.25);
  if (!chunk) return null;
  return (
    <div style={{position: 'absolute', bottom: 46, left: 0, right: 0, display: 'flex', justifyContent: 'center'}}>
      <div style={{fontFamily: font, fontSize: 36, color: '#f0f0f0', background: 'rgba(44,44,44,0.94)', border: '1px solid #6a6a6a', padding: '8px 22px', maxWidth: 1500, textAlign: 'center'}}>
        {chunk.map((w, i) => (
          <span key={i} style={{opacity: t >= w.start - 0.05 ? 1 : 0.5}}>
            {w.text}{' '}
          </span>
        ))}
      </div>
    </div>
  );
};

/** While anything is missing, a P2 alarm strip under the top bar says what (as on the deck). */
export const DraftMark: React.FC = () =>
  data.draft.length ? (
    <div
      style={{
        position: 'absolute',
        top: 58,
        left: 0,
        right: 0,
        height: 30,
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '0 16px',
        background: C.placeholder,
        color: '#111',
        fontFamily: monoFont,
        fontSize: 16,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
      }}
    >
      <b>P2</b>
      <span>DATA.DRAFT</span>
      <span>{data.draft.join(' · ')}</span>
    </div>
  ) : null;

/** Types `text` out over `seconds`, starting at `delay`. */
export const Typewriter: React.FC<{text: string; delay?: number; seconds?: number}> = ({text, delay = 0, seconds = 2}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const n = Math.floor(interpolate(frame, [delay * fps, (delay + seconds) * fps], [0, text.length], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const caret = n < text.length && Math.floor(frame / 8) % 2 === 0 ? '▍' : '';
  return (
    <span>
      {text.slice(0, n)}
      <span style={{color: C.dim}}>{caret}</span>
    </span>
  );
};

export const Box: React.FC<{children: React.ReactNode; colour?: string; style?: React.CSSProperties}> = ({children, colour = C.line, style}) => (
  <div style={{background: C.panel, border: `1px solid ${colour}`, padding: '12px 18px', ...style}}>{children}</div>
);

export const Arrow: React.FC<{length?: number; colour?: string}> = ({length = 60, colour = C.strong}) => (
  <svg width={length} height={24} viewBox={`0 0 ${length} 24`} style={{flexShrink: 0}}>
    <line x1={0} y1={12} x2={length - 12} y2={12} stroke={colour} strokeWidth={3} />
    <polygon points={`${length - 14},4 ${length},12 ${length - 14},20`} fill={colour} />
  </svg>
);

export const Badge: React.FC<{text: string; colour?: string; corner?: 'tr' | 'tl' | 'bl' | 'br'}> = ({text, corner = 'tr'}) => {
  const pos: React.CSSProperties = {tr: {top: 110, right: 24}, tl: {top: 110, left: 24}, bl: {bottom: 24, left: 24}, br: {bottom: 24, right: 24}}[corner];
  return (
    <div style={{position: 'absolute', ...pos, fontFamily: monoFont, fontSize: 22, color: '#f0f0f0', background: 'rgba(44,44,44,0.92)', border: '1px solid #6a6a6a', padding: '6px 12px'}}>
      {text}
    </div>
  );
};
