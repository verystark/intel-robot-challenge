// Everything the video shows comes from these two generated files:
// public/data.json (scripts/build_data.py) and public/vo/timings.json (tts/make_voice.py).
import rawData from '../public/data.json';
import rawTimings from '../public/vo/timings.json';

export type Num = number | null;

export interface Word {
  text: string;
  start: number;
  end: number;
}

export interface VoScene {
  file: string;
  duration: number;
  draft: boolean;
  words: Word[];
}

export interface Cycle {
  cycle: number;
  pick?: {result: string; s: number};
  show_s?: number;
  inspect?: {scores: number[]; labels: string[]; verdict: string; rechecked: boolean; anomaly_ms: number[]; bands: number[]};
  sort?: {result: string; sentence: string; s: number};
  total_s?: number;
}

export interface Data {
  facts: {
    dataset: {name: string; episodes: number; picks: number; sorts: number; labels_checked: string};
    models: Record<'pick' | 'sort' | 'anomaly', {name: string; device: string}>;
    sentences: Record<'pick' | 'GOOD' | 'DEFECTIVE', string>;
    laptop: string;
    repo_url: string | null;
    team: string[];
    run_take: {loop_run: string | null; footage_offset_s: number; result_line: string | null; plate_swap_shown: boolean};
  };
  numbers: Record<'EPISODES' | 'PICKS' | 'SORTS' | 'PICK_MS' | 'SORT_MS' | 'INSPECT_MS' | 'R' | 'M' | 'P' | 'I' | 'S' | 'E' | 'X', Num>;
  bench: {
    policy: {model: string; device: string; median_ms: number; chunk: number}[];
    anomaly: {precision: string; device: string; median_ms: number; size_mb: number; score_diff_max: number}[];
    contended: string[];
  };
  run: {folder: string | null; cycles: Cycle[]; images: {photo: string; heat: string | null}[]; sim: boolean; scores: number[]};
  footage: Record<string, boolean>;
  evaluation: {rounds: Num; cycles: Num; failures: string[]};
  draft: string[];
}

export const data = rawData as unknown as Data;
export const timings = rawTimings as unknown as {voice: string | null; scenes: Record<string, VoScene>};

export const FPS = 30;

// Scene order, the script's planned length (s), and which narration it carries.
export const SCENES = [
  {id: 's1', base: 8, vo: null},
  {id: 's2', base: 13, vo: 's2'},
  {id: 's3', base: 13, vo: 's3'},
  {id: 's4', base: 13, vo: 's4'},
  {id: 's5', base: 8, vo: 's5'},
  {id: 's6', base: 40, vo: null},
  {id: 's7', base: 12, vo: 's7'},
  {id: 's8', base: 10, vo: 's8', tail: 4.5}, // the end card follows the narration
] as const;

export type SceneId = (typeof SCENES)[number]['id'];

export const VO_LEAD_S = 0.4; // narration starts this long after the scene does
const VO_TAIL_S = 0.8;

export const sceneFrames = (id: SceneId): number => {
  const scene = SCENES.find((s) => s.id === id)!;
  const vo = scene.vo ? timings.scenes[scene.vo] : undefined;
  const tail = 'tail' in scene ? scene.tail : VO_TAIL_S;
  const seconds = Math.max(scene.base, vo ? vo.duration + VO_LEAD_S + tail : 0);
  return Math.round(seconds * FPS);
};

export const totalFrames = (): number => SCENES.reduce((sum, s) => sum + sceneFrames(s.id), 0);
