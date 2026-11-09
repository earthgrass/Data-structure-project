import {useState} from 'react';
import type {Plan} from '../types';
import {fmt} from '../presentation';
type Demo={title:string;cost_note:string;runs:{objective:string;input_fingerprint:string;distance:number;cost:number;travel_time:number;final_return:number;plan:Plan;audit:{valid:boolean;complete_all:boolean}}[];reference:{scope:string;enumerated_closed_routes:number;minimum_distance:number;minimum_cost:number}};

export function ControlledExperiment(){
  const [data,setData]=useState<Demo|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  async function run(){setBusy(true);setError('');try{
    const response=await fetch('/api/v2/experiments/objective-demo');
    if(!response.ok)throw new Error(`实验请求失败（${response.status}），请检查后端连接。`);
    setData(await response.json());
  }catch(e){setError(e instanceof Error?e.message:'实验未完成');}finally{setBusy(false);}}
  return <section className="d-card"><div className="d-card-head"><div><h2>受控双目标实验</h2><p>独立教学输入；不使用或修改当前校园会话</p></div><button disabled={busy} onClick={()=>void run()}>{busy?'真实算法运行中…':'运行受控实验'}</button></div>
    <div className="d-pad"><p>校园初始成本与距离成比例，两目标可能相同。本实验比较模拟高服务成本直达通道与普通绕行通道；保留相同道路、订单、容量与时间窗。</p>
      {error&&<p role="alert">{error}</p>}
      {data&&<><p>{data.cost_note}</p><div className="d-table-scroll"><table><thead><tr><th>目标 / 覆盖</th><th>距离 km</th><th>模拟成本 元</th><th>行驶时间 分</th><th>最终返仓 分</th></tr></thead><tbody>{data.runs.map(r=><tr key={r.objective}><td>{r.objective} · {r.audit.valid&&r.audit.complete_all?'独立审计完整':'非完整结果'}</td><td>{fmt(r.distance)}</td><td>{fmt(r.cost)}</td><td>{fmt(r.travel_time)}</td><td>{fmt(r.final_return)}</td></tr>)}</tbody></table></div>
        {data.runs.map(r=><p key={r.objective}><b>{r.objective} 末端道路：</b>{r.plan.routes.filter(v=>v.vehicle==='LAST').map(v=>v.actions.filter(a=>a.kind==='drive').map(a=>`${a.source}→${a.target}`).join(' · '))}</p>)}
        <p>独立枚举 {data.reference.enumerated_closed_routes} 种闭环道路组合，最小距离 {fmt(data.reference.minimum_distance)}、最小成本 {fmt(data.reference.minimum_cost)}。基准仅适用于本例的一单一中转站固定干线，不证明一般多车贪心最优。</p>
      </>}
    </div></section>;
}
