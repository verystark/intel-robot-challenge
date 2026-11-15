import React from 'react';
import {
  AbsoluteFill,
  Easing,
  Img,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {Num, Word, data, timings, VO_LEAD_S} from '../data';
import {C, font, monoFont} from '../theme';

const ease = Easing.bezier(0.33, 0, 0.2, 1);

/** Fades and slides its children in, starting `delay` seconds into the scene. */
export const Appear: React.FC<{delay?: number; dy?: number; children: React.ReactNode; style?: React.CSSProperties}> = ({
  delay = 0,
  dy = 16,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = interpolate(frame, [delay * fps, delay * fps + 0.45 * fps], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: ease,
  });
  return <div style={{opacity: t, transform: `translateY(${(1 - t) * dy}px)`, ...style}}>{children}</div>;
};

/** A measured number, or a visibly marked placeholder while it isn't measured yet. */
export const Value: React.FC<{v: Num | string | undefined; name: string; digits?: number; unit?: string}> = ({
  v,
  name,
  digits = 0,
  unit = '',
}) => {
  if (v === null || v === undefined || v === '') {
    return <span style={{color: C.placeholder, borderBottom: `2px dotted ${C.placeholder}`}}>[{name}]</span>;
  }
  const text = typeof v === 'number' ? v.toLocaleString('en-GB', {maximumFractionDigits: digits, minimumFractionDigits: digits}) : v;
  return (
    <span>
      {text}
      {unit}
    </span>
  );
};

export const Badge: React.FC<{text: string; colour?: string; corner?: 'tr' | 'tl' | 'bl' | 'br'}> = ({
  text,
  colour = C.text,
  corner = 'tr',
}) => {
  const pos: React.CSSProperties = {
    tr: {top: 40, right: 48},
    tl: {top: 40, left: 48},
    bl: {bottom: 40, left: 48},
    br: {bottom: 40, right: 48},
  }[corner];
  return (
    <div
      style={{
        position: 'absolute',
        ...pos,
        fontFamily: monoFont,
        fontSize: 26,
        color: colour,
        background: 'rgba(24,24,28,0.82)',
        border: `1.5px solid ${colour}55`,
        padding: '8px 16px',
        borderRadius: 8,
        letterSpacing: 0.5,
      }}
    >
      {text}
    </div>
  );
};

/** Real footage if the file is there; a labelled box until it is filmed. */
export const Footage: React.FC<{
  id: string;
  label: string;
  startFrom?: number; // seconds into the clip
  speed?: number;
  volume?: number;
  style?: React.CSSProperties;
}> = ({id, label, startFrom = 0, speed = 1, volume = 1, style}) => {
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
    <AbsoluteFill
      style={{
        background: `repeating-linear-gradient(135deg, ${C.panel}, ${C.panel} 24px, #2B2B32 24px, #2B2B32 48px)`,
        border: `2px dashed ${C.line}`,
        alignItems: 'center',
        justifyContent: 'center',
        ...style,
      }}
    >
      <div style={{fontFamily: monoFont, color: C.dim, fontSize: 30, textAlign: 'center', lineHeight: 1.5}}>
        {id.toUpperCase()} · footage to film
        <br />
        <span style={{fontSize: 24}}>{label}</span>
      </div>
    </AbsoluteFill>
  );
};

export const Photo: React.FC<{src: string; style?: React.CSSProperties}> = ({src, style}) => (
  <Img src={staticFile(src)} style={{width: '100%', height: '100%', objectFit: 'cover', ...style}} />
);

export const Title: React.FC<{children: React.ReactNode; size?: number; colour?: string}> = ({children, size = 54, colour = C.text}) => (
  <div style={{fontFamily: font, fontWeight: 700, fontSize: size, color: colour, lineHeight: 1.15}}>{children}</div>
);

export const Line: React.FC<{children: React.ReactNode; size?: number; colour?: string; mono?: boolean}> = ({
  children,
  size = 34,
  colour = C.text,
  mono = false,
}) => (
  <div style={{fontFamily: mono ? monoFont : font, fontWeight: 400, fontSize: size, color: colour, lineHeight: 1.35}}>{children}</div>
);

/** Word-timed captions for a scene's narration, at most 7 words at a time, split at sentence ends. */
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
    <div style={{position: 'absolute', bottom: 64, left: 0, right: 0, display: 'flex', justifyContent: 'center'}}>
      <div
        style={{
          fontFamily: font,
          fontSize: 38,
          fontWeight: 600,
          color: C.text,
          background: 'rgba(16,16,20,0.78)',
          padding: '10px 22px',
          borderRadius: 10,
          maxWidth: 1500,
          textAlign: 'center',
        }}
      >
        {chunk.map((w, i) => (
          <span key={i} style={{opacity: t >= w.start - 0.05 ? 1 : 0.45}}>
            {w.text}{' '}
          </span>
        ))}
      </div>
    </div>
  );
};

/** Marks a draft render so nobody mistakes it for the final video. */
export const DraftMark: React.FC = () =>
  data.draft.length ? (
    <div
      style={{
        position: 'absolute',
        top: 14,
        left: '50%',
        transform: 'translateX(-50%)',
        fontFamily: monoFont,
        fontSize: 18,
        color: C.placeholder,
        opacity: 0.85,
        whiteSpace: 'nowrap',
      }}
    >
      DRAFT · {data.draft.join(' · ')}
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
  <div style={{background: C.panel, border: `2px solid ${colour}`, borderRadius: 12, padding: '14px 20px', ...style}}>{children}</div>
);

export const Arrow: React.FC<{length?: number; colour?: string}> = ({length = 60, colour = C.dim}) => (
  <svg width={length} height={24} viewBox={`0 0 ${length} 24`} style={{flexShrink: 0}}>
    <line x1={0} y1={12} x2={length - 12} y2={12} stroke={colour} strokeWidth={3} />
    <polygon points={`${length - 14},4 ${length},12 ${length - 14},20`} fill={colour} />
  </svg>
);
