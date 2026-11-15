import React from 'react';
import {AbsoluteFill} from 'remotion';
import {data} from './data';
import {C, font} from './theme';
import {Footage} from './components/ui';
import {CoverageMap} from './components/CoverageMap';

// YouTube thumbnail, 1280×720: a frame of the run if it's filmed, else the coverage map.
export const Thumbnail: React.FC = () => (
  <AbsoluteFill style={{background: C.bg, flexDirection: 'row'}}>
    <div style={{width: 560, padding: '70px 0 0 60px', display: 'flex', flexDirection: 'column', gap: 26}}>
      <div style={{fontFamily: font, fontWeight: 700, fontSize: 64, color: C.text, lineHeight: 1.05}}>
        Random bricks.
        <br />
        Movable plates.
      </div>
      <div style={{fontFamily: font, fontSize: 30, color: C.dim, lineHeight: 1.35}}>
        A VLA picks and sorts.
        <br />
        <span style={{color: C.defective}}>Anomalib</span> finds the defects.
        <br />
        All on one Intel laptop.
      </div>
      <div style={{fontFamily: font, fontWeight: 700, fontSize: 34, color: C.text, marginTop: 20}}>Jenssenit</div>
    </div>
    <div style={{flex: 1, position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
      {data.footage.a1 ? (
        <Footage id="a1" label="" startFrom={data.facts.run_take.footage_offset_s + 2} volume={0} />
      ) : (
        <CoverageMap size={660} delay={-10} />
      )}
    </div>
  </AbsoluteFill>
);
