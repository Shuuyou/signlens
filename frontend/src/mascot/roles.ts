export const XIAOCHA_ROLES = {
  "quant": {
    "label": "量化分察", "colorName": "鸢尾蓝", "light": "#5b67a6", "dark": "#b5bdef",
    "angle": "right", "pose": "desk", "state": "verifying",
    "detail": "观察价格，核对每一次预测。", "tool": "chart"
  },
  "finance": {
    "label": "财报分察",
    "colorName": "松针绿",
    "light": "#35695a",
    "dark": "#8bc7b0",
    "angle": "right",
    "pose": "desk",
    "state": "reading",
    "detail": "低头看账，逐行核对。",
    "tool": "ledger"
  },
  "news": {
    "label": "舆情分察",
    "colorName": "陶土橙",
    "light": "#b85c41",
    "dark": "#e9a98d",
    "angle": "left",
    "pose": "listen",
    "state": "searching",
    "detail": "侧耳听线索，转头找出处。",
    "tool": "messages"
  },
  "legal": {
    "label": "司法分察",
    "colorName": "麦穗金",
    "light": "#996b2e",
    "dark": "#e1bd79",
    "angle": "front",
    "pose": "upright",
    "state": "verifying",
    "detail": "正面复核，把两份材料一起看。",
    "tool": "files"
  },
  "registry": {
    "label": "工商分察",
    "colorName": "雾青蓝",
    "light": "#4c7084",
    "dark": "#a3c7da",
    "angle": "left",
    "pose": "lean",
    "state": "reading",
    "detail": "探身辨认，先确认材料里的主体。",
    "tool": "profile"
  },
  "filings": {
    "label": "公告分察",
    "colorName": "橄榄绿",
    "light": "#757848",
    "dark": "#c9d093",
    "angle": "right",
    "pose": "carry",
    "state": "reading",
    "detail": "俯身看材料，再慢慢整理。",
    "tool": "scrolls"
  }
} as const;
export type XiaochaRole = keyof typeof XIAOCHA_ROLES;
export type XiaochaAngle = 'front' | 'left' | 'right' | 'back';
export const XIAOCHA_POSES = ["neutral", "desk", "listen", "upright", "lean", "carry"] as const;
export type XiaochaPose = typeof XIAOCHA_POSES[number];
