import React from 'react';
import {data} from './data';
import {Cam, Frame} from './components/frame';
import {Footage, Photo} from './components/ui';
import {H, MONO, Swatch} from './components/hmi';

// YouTube thumbnail, 1280×720, as an HMI screen: the claim on the left, a real inspection
// heatmap of a marked brick (or a frame of the run, once it's filmed) on the right.
export const Thumbnail: React.FC = () => {
  const bad = data.run.examples.find((e) => e.kind === 'defective');
  const view = bad?.stops[0];
  return (
    <Frame title="INSPECTION" fields={[{k: 'VLA', v: 'PI0.5'}]}>
      <div style={{width: 560, display: 'flex', flexDirection: 'column', gap: 18, padding: '24px 10px 0 14px'}}>
        <div style={{fontSize: 52, fontWeight: 700, lineHeight: 1.05, letterSpacing: '.01em'}}>
          RANDOM BRICKS.
          <br />
          MOVABLE PLATES.
        </div>
        <div style={{fontSize: 27, lineHeight: 1.35, color: H.muted}}>
          A pi0.5 VLA picks and sorts.
          <br />
          Anomalib checks every brick.
          <br />
          All on one Intel laptop.
        </div>
        <div style={{marginTop: 8, fontSize: 30, fontWeight: 700}}>JENSSENIT</div>
      </div>
      <Cam title={data.footage.a1 ? 'CAM 04 · SIDE VIEW' : 'CAM 03 · INSPECTION · ANOMALIB OVERLAY'} osd={view ? `+90°  score ${view.median.toFixed(2)}` : undefined} style={{flex: 1}}>
        {data.footage.a1 ? (
          <Footage id="a1" label="" startFrom={data.facts.run_take.footage_offset_s + 2} volume={0} />
        ) : view ? (
          <Photo src={view.heat} />
        ) : null}
        {!data.footage.a1 && bad && (
          <div style={{position: 'absolute', left: 14, bottom: 14, display: 'flex', alignItems: 'center', gap: 10, background: 'rgba(227,227,227,.95)', border: `1px solid ${H.line}`, padding: '6px 12px'}}>
            <Swatch colour={H.reject} size={20} />
            <b style={{fontSize: 30}}>{bad.verdict}</b>
            <span style={{font: `18px ${MONO}`, color: H.muted}}>{bad.what}</span>
          </div>
        )}
      </Cam>
    </Frame>
  );
};
