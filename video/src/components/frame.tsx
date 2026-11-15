// The frame every scene sits in: the cell HMI's top bar, and camera tiles with on-screen labels.
import React from 'react';
import {AbsoluteFill} from 'remotion';
import {data} from '../data';
import {H, MONO, SANS} from './hmi';

const HBox: React.FC<{k: string; v: React.ReactNode; tone?: 'normal' | 'p2' | 'on'}> = ({k, v, tone = 'normal'}) => (
  <div style={{display: 'flex', alignItems: 'stretch', border: '1px solid #6a6a6a', background: '#2c2c2c', height: 38}}>
    <div style={{padding: '0 10px', color: '#a8a8a8', fontSize: 15, display: 'flex', alignItems: 'center', borderRight: '1px solid #555', letterSpacing: '.06em', fontFamily: SANS}}>{k}</div>
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

export interface Field {
  k: string;
  v: React.ReactNode;
  tone?: 'normal' | 'p2';
}

/** Grey HMI screen with the CELL 01 top bar. `fields` are the boxes on the right of the bar. */
export const Frame: React.FC<{title: string; fields?: Field[]; children: React.ReactNode; dark?: boolean}> = ({title, fields = [], children, dark}) => {
  const top = 58 + (data.draft.length ? 30 : 0); // room for the draft strip (components/ui DraftMark)
  return (
    <AbsoluteFill style={{background: dark ? '#111' : H.bg, color: H.text, fontFamily: SANS}}>
      <div style={{position: 'absolute', top, left: 0, right: 0, bottom: 0, padding: dark ? 0 : 10, display: 'flex', gap: 10}}>{children}</div>
      <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 58, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 14px', background: H.top, color: '#e8e8e8', borderBottom: '1px solid #222'}}>
        <div style={{fontSize: 24, letterSpacing: '.04em', whiteSpace: 'nowrap'}}>
          <b>CELL 01</b>
          <span style={{color: '#8a8a8a', margin: '0 14px'}}>|</span>BRICK QC &amp; SORT
          <span style={{color: '#8a8a8a', margin: '0 14px'}}>|</span>
          {title}
        </div>
        <div style={{display: 'flex', gap: 10}}>
          {fields.map((f) => (
            <HBox key={f.k} k={f.k} v={f.v} tone={f.tone} />
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** A camera tile like the HMI's: header bar, black picture, on-screen label. */
export const Cam: React.FC<{title: string; osd?: string; children: React.ReactNode; style?: React.CSSProperties}> = ({title, osd, children, style}) => (
  <div style={{background: H.panel, border: `1px solid ${H.line}`, display: 'flex', flexDirection: 'column', minWidth: 0, minHeight: 0, ...style}}>
    <div style={{fontSize: 16, fontWeight: 700, letterSpacing: '.05em', padding: '5px 10px', background: H.head, borderBottom: `1px solid ${H.line}`, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>
      {title}
    </div>
    <div style={{position: 'relative', background: '#111', flex: 1, minHeight: 0, overflow: 'hidden'}}>
      {children}
      {osd && (
        <div style={{position: 'absolute', left: 10, top: 8, font: `17px ${MONO}`, color: '#fff', textShadow: '1px 1px 0 #000, -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000', whiteSpace: 'pre'}}>{osd}</div>
      )}
    </div>
  </div>
);
