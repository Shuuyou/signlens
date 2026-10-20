export const XIAOCHA_STATES = {
  "idle": {
    "label": "准备开始",
    "detail": "轻轻呼吸，偶尔眨眼。",
    "motion": "loop"
  },
  "planning": {
    "label": "梳理核查重点",
    "detail": "抬眼想一想，把要查的事理顺。",
    "motion": "loop"
  },
  "searching": {
    "label": "查找公开材料",
    "detail": "左右寻找，视线带着小幅转头。",
    "motion": "loop"
  },
  "reading": {
    "label": "阅读材料",
    "detail": "逐行往下看，身旁是一页材料。",
    "motion": "loop"
  },
  "thinking": {
    "label": "整理线索",
    "detail": "歪头思考，一只眼睛轻轻眯起。",
    "motion": "loop"
  },
  "verifying": {
    "label": "复核出处",
    "detail": "对照两份材料，来回确认。",
    "motion": "loop"
  },
  "waiting": {
    "label": "等你确认",
    "detail": "停下工作，看向你；不转圈催促。",
    "motion": "ambient"
  },
  "done": {
    "label": "本次核查已整理",
    "detail": "轻点一下头，露出弯弯的眼睛。",
    "motion": "once"
  },
  "insufficient": {
    "label": "还需要补充材料",
    "detail": "轻轻歪头，留着尚未填满的一页。",
    "motion": "once"
  },
  "error": {
    "label": "这次查询没有完成",
    "detail": "小幅摇头一次，然后安静停下。",
    "motion": "once"
  }
} as const;
export type XiaochaState = keyof typeof XIAOCHA_STATES;

/** Semantic observations supplied by the host; these are NOT SSE event names. */
export type XiaochaObservation =
  | { kind: 'idle' | 'planning' | 'searching' | 'reading' | 'thinking' | 'verifying' }
  | { kind: 'needs_confirmation' }
  | { kind: 'settled'; outcome: 'prepared' | 'insufficient' | 'request_failed' };

export function stateFromObservation(observation: XiaochaObservation): XiaochaState {
  if (observation.kind === 'needs_confirmation') return 'waiting';
  if (observation.kind === 'settled') {
    return { prepared: 'done', insufficient: 'insufficient', request_failed: 'error' }[observation.outcome] as XiaochaState;
  }
  return observation.kind;
}
