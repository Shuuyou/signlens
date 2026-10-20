import type {Report} from '../types'
import type {ProgressEvent,ScanState} from '../design/scan'
import type {XiaochaRole} from './roles'
import type {XiaochaState} from './core/states'

const roleDomains:Record<XiaochaRole,string>={registry:'profile',finance:'filings',filings:'filings',legal:'public_records',news:'news',quant:'market'}
const missing=new Set(['unsupported','unavailable','unconfigured','blocked','rate_limited','schema_unverified','deferred','empty','budget_exhausted','call_budget_exhausted'])
export function mascotState(events:ProgressEvent[],busy:boolean,report:Report|null,waiting=false,state:ScanState='idle'):XiaochaState{
 if(waiting||state==='cancelled')return 'waiting'
 if(state==='error')return 'error'
 if(report)return report.task_plan.next_action==='need_more_information'?'insufficient':'done'
 const latest=events.at(-1)
 if(!busy)return 'idle'
 if(latest?.task_state==='awaiting_entity')return 'waiting'
 if(latest?.raw_role==='Skeptic')return 'verifying'
 if(latest?.raw_role==='Analyst')return 'thinking'
 if(latest?.tool==='read_public_filing'&&(latest.task_state==='tool_action'||latest.tool_state==='started'||latest.status==='started'))return 'reading'
 if(latest?.task_state==='tool_action')return 'searching'
 if(latest?.domain&&latest.status)return 'thinking'
 return 'planning'
}
export function roleObservation(role:XiaochaRole,events:ProgressEvent[],report:Report|null,busy:boolean,state:ScanState='idle'){
 const domain=roleDomains[role],receipt=[...events].reverse().find(e=>e.domain===domain&&e.tool!=='read_public_filing'&&(e.status||e.task_state==='tool_action'))
 const documentEvent=[...events].reverse().find(e=>e.tool==='read_public_filing')
 const coverage=report?.coverage[domain]
 const profiles=report?.evidence.filter(e=>e.kind==='profile')||[]
 const facts=report?.evidence.filter(e=>e.kind==='filing'||e.kind==='financial').some(e=>Object.entries(e.facts).some(([k,v])=>/^(revenue_current|revenue_previous|operating_cashflow)$/.test(k)&&typeof v==='number'&&Number.isFinite(v)))
 const status=coverage?.status||receipt?.status
 const planned=events.some(e=>e.plan?.some(p=>p.domains.includes(domain)))
 const label=role==='quant'?'行情与预测':role==='finance'?'财务数字':role==='filings'?'公告材料':role==='registry'?'公司身份':role==='legal'?'司法记录':'新闻线索'
 let taskState:XiaochaState='idle',detail=planned?'等待实际查询回执':'本次尚未启动这项查询'
 if(role==='registry'&&report&&profiles.length>0&&profiles.every(e=>e.provider==='cninfo')){
  taskState='insufficient';detail='只核对了证券简称，工商登记未覆盖'
 }else if(role==='finance'){
  if(facts){taskState=report?'done':'verifying';detail='已取得财务材料，提示仍以原文为准'}
  else if(report){taskState='insufficient';detail='尚未取得可核验的财务数字，不能据目录判断现金流'}
 }else if(role==='filings'&&documentEvent&&(documentEvent.task_state==='tool_action'||documentEvent.tool_state==='started'||documentEvent.status==='started')){
  taskState='reading';detail='正在提取公开公告正文页'
 }else if(role==='filings'&&((coverage?.pages_read||0)>0||documentEvent?.status==='ok')){
  taskState=coverage?.document_status&&coverage.document_status!=='ok'?'insufficient':'done';detail=`已提取 ${coverage?.pages_read||documentEvent?.pages_read||0} 页正文，数字尚未核验${coverage?.partial?'；仅覆盖部分页面':''}${coverage?.document_status&&coverage.document_status!=='ok'?'；仍有正文未取得':''}`
 }else if(receipt?.task_state==='tool_action'||receipt?.tool_state==='started'||receipt?.status==='started'){taskState='searching';detail='正在查询公开材料'
 }else if(status){
  taskState=status==='error'||status==='timeout'?'error':missing.has(status)?'insufficient':'done'
  detail=role==='filings'&&status==='ok'&&report?.evidence.some(e=>e.content_level==='directory'||e.provider==='cninfo'&&e.kind==='filing'&&e.content_level!=='document')?'已找到公告目录；正文尚未取得':status==='ok'?'本次查询已返回材料':status==='rate_limited'?'来源限制访问，已停止本路查询':status==='empty'?'这次未查到材料，不代表没有问题':'公开渠道暂未覆盖，保留缺口'
 }
 if(state==='cancelled'&&!status){taskState='waiting';detail='本次已取消，未返回的查询停止展示'}
 if(!busy&&taskState==='reading'){taskState='insufficient';detail='正文提取尚未确认完成'}
 return {state:taskState,detail,label}
}
