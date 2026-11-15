import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
import {loadFont as loadMono} from '@remotion/google-fonts/JetBrainsMono';

const inter = loadInter('normal', {weights: ['400', '600', '700'], subsets: ['latin']});
const mono = loadMono('normal', {weights: ['400', '600'], subsets: ['latin']});

export const font = inter.fontFamily;
export const monoFont = mono.fontFamily;

// Dark grey like the loop's demo screen; plate colours for the verdicts.
export const C = {
  bg: '#18181C',
  panel: '#26262C',
  line: '#3A3A42',
  text: '#EBEBEB',
  dim: '#96969B',
  good: '#2EC4A6', // the teal "green" plate
  defective: '#FF7A1A', // the orange plate
  unsure: '#E8C547',
  stage: '#3D8BD9', // active stage, as on the loop screen
  placeholder: '#E8C547',
};

export const verdictColour = (v: string | undefined) =>
  v === 'GOOD' ? C.good : v === 'DEFECTIVE' ? C.defective : v === 'UNSURE' ? C.unsure : C.dim;
