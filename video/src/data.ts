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
  inspect?: {
    scores: number[];
    labels: string[];
    verdict: string;
    rechecked?: boolean;
    second_look?: boolean;
    anomaly_ms: number[];
    bands: number[];
    stops?: {deg: number; median: number; label: string; scores: number[]}[];
  };
  inspect_s?: number;
  sort?: {result: string; sentence: string; s: number};
  total_s?: number;
}

/** An inspection example chosen in facts.json, with its photos per wrist stop. */
export interface Example {
  kind: string;
  cycle: number;
  what: string;
  verdict: string;
  second_look: boolean;
  stops: {deg: number; median: number; label: string; photo: string; heat: string}[];
}

export interface Results {
  runs: string[];
  model: string;
  bricks_through_loop: number;
  verdicts_correct: number;
  defective_rejected: [number, number];
  clean_accepted: [number, number];
  picks_ok: number;
  pick_attempts: number;
  pick_timeouts: number;
  picks_stopped_by_operator: number;
  median_cycle_s: number;
  median_pick_s: number;
  median_inspect_s: number;
  median_sort_s: number;
  thermal: string;
  failures: string[];
  verdicts_checked: string;
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
    results?: Results;
    policy?: {family: string; training: string; chunk_ms_gpu: number};
    inspection?: {crop: string; bands: number[]; train_photos: number; train_photos_at_show_pose: number; held_out: string; ms_gpu_loop: number; ms_gpu_loop_p95: number; ms_cpu: number; ms_npu: number; fp32_mb: number; int8_mb: number; int8_diff_max: number; train_time: string; first_live_failure: string};
  };
  numbers: Record<string, Num>;
  bench: {
    policy: {model: string; device: string; median_ms: number; chunk: number}[];
    anomaly: {precision: string; device: string; median_ms: number; size_mb: number; score_diff_max: number}[];
    contended: string[];
  };
  run: {folder: string | null; cycles: Cycle[]; images: {photo: string; heat: string | null}[]; sim: boolean; scores: number[]; examples: Example[]};
  footage: Record<string, boolean>;
  loop: {stops_deg: number[]; frames_per_stop: number; pick_timeout_s: number | null; sort_timeout_s: number | null; fps: number};
  evaluation: {rounds: Num; cycles: Num; failures: string[]};
  draft: string[];
}

export const data = rawData as unknown as Data;
export const timings = rawTimings as unknown as {voice: string | null; scenes: Record<string, VoScene>};

export const FPS = 30;

// Scene order, the script's planned length (s), and which narration it carries.
export const SCENES = [
  {id: 's1', base: 6, vo: null},
  {id: 's2', base: 13, vo: 's2'},
  {id: 's3', base: 13, vo: 's3'},
  {id: 's4', base: 13, vo: 's4'},
  {id: 's5', base: 8, vo: 's5'},
  {id: 's6', base: 35, vo: null},
  {id: 's7', base: 12, vo: 's7'},
  {id: 's8', base: 10, vo: 's8', tail: 3.5}, // the end card follows the narration
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
