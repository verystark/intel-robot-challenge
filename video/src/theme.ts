// The video uses the cell's operator-screen look (loop/dashboard, after ISA-101): grey when
// normal, colour only for plate identity and abnormal states. Colours come from the dashboard's
// palette.json; fonts are the HMI's (Arial / Liberation Sans, DejaVu Sans Mono), installed locally.
import palette from '../../loop/dashboard/palette.json';

const p = palette.hmi;

export const font = 'Arial, "Liberation Sans", Helvetica, "DejaVu Sans", sans-serif';
export const monoFont = '"DejaVu Sans Mono", "Liberation Mono", "Courier New", monospace';

export const C = {
  bg: p.background,
  panel: p.panel,
  display: p.display,
  line: p.line,
  strong: p.equipment_on,
  text: p.text,
  dim: p.muted,
  head: '#cfcfcf',
  top: '#3e3e3e',
  good: p.plate_good, // the teal "green" plate
  defective: p.plate_reject, // the orange plate
  unsure: p.alarm_medium,
  alarm: p.alarm_high,
  stage: p.equipment_on, // an active stage is filled dark grey, as on the HMI
  placeholder: p.alarm_medium,
};

export const verdictColour = (v: string | undefined) =>
  v === 'GOOD' ? C.good : v === 'DEFECTIVE' ? C.defective : v === 'UNSURE' ? C.unsure : C.dim;
