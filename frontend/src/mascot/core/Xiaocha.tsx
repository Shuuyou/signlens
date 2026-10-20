import { useId, type CSSProperties } from 'react';
import { BODY, LEFT_EYE, RIGHT_EYE } from './geometry';
import { XIAOCHA_STATES, type XiaochaState } from './states';
import './xiacha.css';

export interface XiaochaProps {
  state?: XiaochaState;
  /** CSS pixels. Recommended: 32/48 for avatars, 96/144 for workspaces. */
  size?: number;
  /** Pause at the current frame; does not change the actual task state. */
  paused?: boolean;
  /** A static pose, independent of the user's reduced-motion preference. */
  animated?: boolean;
  /** Increment to replay a one-shot reaction when another operation ends. */
  replayKey?: string | number;
  decorative?: boolean;
  label?: string;
  className?: string;
  style?: CSSProperties;
}

/** Pure presentation: the caller owns state changes, SSE and task semantics. */
export function Xiaocha({
  state = 'idle', size = 64, paused = false, animated = true,
  replayKey = 0, decorative = false, label, className = '', style,
}: XiaochaProps) {
  const instance = `xiacha-${useId().replace(/[^a-zA-Z0-9_-]/g, '-')}`;
  const maskId = `${instance}-eyes`;
  const titleId = `${instance}-title`;
  return (
    <svg
      key={`${state}-${replayKey}`}
      xmlns="http://www.w3.org/2000/svg" viewBox="0 0 112 112"
      className={`xiacha ${className}`.trim()}
      data-state={state} data-paused={paused} data-static={!animated}
      data-compact={size < 48}
      style={{ width: size, height: size, ...style }}
      role={decorative ? undefined : 'img'}
      aria-hidden={decorative ? true : undefined}
      aria-labelledby={decorative ? undefined : titleId}
      focusable="false"
    >
      {!decorative && <title id={titleId}>{label ?? XIAOCHA_STATES[state].label}</title>}
      <defs>
        <mask id={maskId} maskUnits="userSpaceOnUse" x="0" y="0" width="112" height="112" style={{ maskType: 'luminance' }}>
          <rect width="112" height="112" fill="white" />
          <g className="xc-gaze">
            <g className="xc-open-eyes" fill="black">
              <path className="xc-eye xc-eye-left" d={LEFT_EYE} />
              <path className="xc-eye xc-eye-right" d={RIGHT_EYE} />
            </g>
            <g className="xc-smile-eyes" fill="none" stroke="black" strokeWidth="4.2" strokeLinecap="round">
              <path d="M41 59Q45.5 50 50 59" />
              <path d="M62 57Q67 48 72 57" />
            </g>
          </g>
        </mask>
      </defs>
      <ellipse className="xc-shadow" cx="55" cy="101" rx="24" ry="2.8" fill="currentColor" />
      <g className="xc-head">
        <path d={BODY} fill="var(--xiacha-eye-fill, transparent)" />
        <path className="xc-body" d={BODY} fill="currentColor" mask={`url(#${maskId})`} />
      </g>
      <g className="xc-notes xc-prop" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
        <path className="xc-note-one" d="M84 24H97" />
        <path className="xc-note-two" d="M88 31H101" />
        <path className="xc-note-three" d="M91 38H100" />
      </g>
      <g className="xc-paper xc-prop" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
        <path d="M91 68H105V89H91" />
        <path className="xc-paper-line-one" d="M97 75H101" />
        <path className="xc-paper-line-two" d="M95 81H101" />
      </g>
      <g className="xc-compare xc-prop" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
        <path d="M92 64H101V82H92M96 86H105V68" />
        <path className="xc-compare-line" d="M95 70H98M95 75H98" />
      </g>
      <g className="xc-missing xc-prop" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
        <path d="M90 68H103V89H90M95 77H98" />
      </g>
    </svg>
  );
}
