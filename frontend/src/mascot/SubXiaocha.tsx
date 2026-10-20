import { useId, type CSSProperties } from 'react';
import { BODY, LEFT_EYE, RIGHT_EYE } from './core/geometry';
import { XIAOCHA_STATES, type XiaochaState } from './core/states';
import { XIAOCHA_ROLES, type XiaochaRole, type XiaochaAngle, type XiaochaPose } from './roles';
import './core/xiacha.css';
import './family-tokens.css';
import './family.css';

export interface SubXiaochaProps {
  role: XiaochaRole;
  /** Host task state. Defaults to idle; role identity never starts a task. */
  state?: XiaochaState;
  angle?: XiaochaAngle;
  pose?: XiaochaPose | 'signature';
  tone?: 'paper' | 'scan' | 'inherit';
  size?: number;
  showMaterials?: boolean;
  paused?: boolean;
  animated?: boolean;
  replayKey?: string | number;
  decorative?: boolean;
  label?: string;
  className?: string;
  style?: CSSProperties;
}

/** Role identity and task state are orthogonal; this component does no collection. */
export function SubXiaocha({role, state: stateInput, angle: angleInput, pose: poseInput = 'signature',
  tone = 'paper', size = 96, showMaterials = true, paused = false, animated = true, replayKey = 0,
  decorative = false, label, className = '', style,
}: SubXiaochaProps) {
  const identity = XIAOCHA_ROLES[role];
  const state = stateInput ?? 'idle';
  const angle = angleInput ?? identity.angle;
  const pose = poseInput === 'signature' ? identity.pose : poseInput;
  const instance = `sub-xiacha-${useId().replace(/[^a-zA-Z0-9_-]/g,'-')}`;
  const maskId = `${instance}-eyes`;
  const titleId = `${instance}-title`;
  return <svg key={`${role}-${state}-${replayKey}`} xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 112 112" className={`xiacha sub-xiacha ${className}`.trim()}
    data-role={role} data-state={state} data-angle={angle} data-pose={pose} data-tone={tone}
    data-paused={paused} data-static={!animated} data-compact={size < 48}
    data-materials={showMaterials}
    style={{width:size,height:size,...style}} role={decorative ? undefined : 'img'}
    aria-hidden={decorative ? true : undefined} aria-labelledby={decorative ? undefined : titleId} focusable="false">
    {!decorative && <title id={titleId}>{label ?? `${identity.label}：${XIAOCHA_STATES[state].label}`}</title>}
    <defs><mask id={maskId} maskUnits="userSpaceOnUse" x="0" y="0" width="112" height="112" style={{maskType:'luminance'}}>
      <rect width="112" height="112" fill="white" />
      <g className="sc-face-offset"><g className="xc-gaze">
        <g className="xc-open-eyes" fill="black">
          <g className="sc-eye-left"><path className="xc-eye xc-eye-left" d={LEFT_EYE}/></g>
          <g className="sc-eye-right"><path className="xc-eye xc-eye-right" d={RIGHT_EYE}/></g>
        </g>
        <g className="xc-smile-eyes" fill="none" stroke="black" strokeWidth="4.2" strokeLinecap="round">
          <path d="M41 59Q45.5 50 50 59"/><path d="M62 57Q67 48 72 57"/>
        </g>
      </g></g>
      <path className="sc-back-mark" d="M55 49Q59 56 56 63" fill="none" stroke="black" strokeOpacity=".3" strokeWidth="2.2" strokeLinecap="round"/>
    </mask></defs>
    <ellipse className="xc-shadow" cx="55" cy="101" rx="24" ry="2.8" fill="currentColor"/>
      <g className="sc-angle"><g className="sc-stance"><g className="xc-head">
        <path d={BODY} fill="var(--xiacha-eye-fill, transparent)"/>
        <path className="xc-body" d={BODY} fill="currentColor" mask={`url(#${maskId})`}/>
      </g></g></g>
    <g className="sc-planning xc-notes xc-prop" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
      <path className="xc-note-one" d="M84 24H97"/><path className="xc-note-two" d="M88 31H101"/><path className="xc-note-three" d="M91 38H100"/>
    </g>
    <g className="sc-tool" transform="translate(94 69)" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
      {role === 'quant' && <g><path d="M0 0V19H15"/><path className="sc-tool-detail" d="M3 13L7 8L10 11L15 3"/><path d="M4 8V16M11 5V13" strokeWidth="1.2"/></g>}
      {role === 'finance' && <g><path d="M0 0H13V19H0Z M5 0V19"/><path className="sc-tool-detail" d="M8 5H10M8 10H10M8 15H10"/></g>}
      {role === 'news' && <g><path d="M2 0H12Q14 0 14 2V12Q14 14 12 14H7L3 18V14H2Q0 14 0 12V2Q0 0 2 0Z"/><path className="sc-tool-detail" d="M4 5H10M4 9H8"/></g>}
      {role === 'legal' && <g><path d="M0 -4H9V14H0M4 18H13V0"/><path className="sc-tool-detail" d="M3 2H6M3 7H6"/></g>}
      {role === 'registry' && <g><path d="M0 0H13V19H0Z"/><path className="sc-tool-detail" d="M5 4H8V8H5Z M3 13H10M3 16H8"/></g>}
      {role === 'filings' && <g><path d="M0 0H13V19H0Z"/><path className="sc-tool-detail" d="M4 5H9M3 10H9M3 15H7"/></g>}
    </g>
  </svg>;
}
