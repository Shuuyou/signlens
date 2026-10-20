import type {Report} from '../types'
import type {ProgressEvent,ScanState} from '../design/scan'
import {Xiaocha} from './core/Xiaocha'
import SpecialistWorkbench from '../SpecialistWorkbench'
import '../design/xiacha-workspace.css'

import {mascotState} from './observations'
export function MainMascot({events=[],busy=false,report=null,waiting=false,state='idle'}:{events?:ProgressEvent[];busy?:boolean;report?:Report|null;waiting?:boolean;state?:ScanState}){
 const current=mascotState(events,busy,report,waiting,state)
 return <Xiaocha state={current} size={40} animated={current!=='waiting'} decorative/>
}
export default function XiachaWorkspace({events,busy,report,waiting=false,state='idle'}:{events:ProgressEvent[];busy:boolean;report:Report|null;waiting?:boolean;state?:ScanState}){
 const current=mascotState(events,busy,report,waiting,state)
 const text=waiting?'先确认是哪家公司，我在这里等你。':state==='cancelled'?'这次核查已暂停。':report?report.task_plan.next_action==='need_more_information'?'小察已整理公开信号，仍有材料未覆盖。':'小察已把这次核查整理成下面的卡片。':busy?'小察在为你核实公开材料。':'小察准备好了，先说说你想查什么。'
 return <details className="xiacha-workspace" aria-label="小察工作区"><summary><Xiaocha state={current} size={32} animated={current!=='waiting'} decorative/><span>{text}</span><small>{report?'这次查了这些':'查看分工与回执'}</small></summary><SpecialistWorkbench events={events} busy={busy}/><p className="xiacha-boundary">角色状态来自实际工作回执，不代表已经读到正文；未覆盖的材料仍保留缺口。</p></details>
}
