"""Versioned transactional adapter. No algorithms or physical state in the UI."""
from __future__ import annotations
from copy import deepcopy
from decimal import Decimal,InvalidOperation
import json
import math
from threading import RLock
from typing import Any
from fastapi import APIRouter,Request
from fastapi.responses import JSONResponse
from logiroute.dispatch.scenario import load_config
from logiroute.dispatch.generation import generate_state,GenerationError
from logiroute.dispatch.time_windows import WindowGenerationError
from logiroute.dispatch.session import Session,ConflictError
from logiroute.dispatch.admission import admit_critical,CriticalAdmissionError
from logiroute.graph.logistics_graph import GraphError


class DispatchService:
    """One-process session store. All reads/writes serialized. O(total retained state)."""
    def __init__(self) -> None:
        self.lock=RLock(); self.sessions: dict[str,Session]={}; self.attempts={}; self.counter=0

    def snapshot(self,key: str,session: Session) -> dict[str,Any]:
        return {'id':key,**session.snapshot(),'generation':self.attempts[key]}


router=APIRouter(prefix='/api/v2')


@router.get('/experiments/objective-demo')
def controlled_objective_demo() -> dict[str,Any]:
    """Read-only isolated small experiment; never writes session state."""
    from logiroute.dispatch.controlled_demo import objective_demo
    return objective_demo()


def failure(status: int,kind: str,message: str,**details: Any) -> JSONResponse:
    return JSONResponse(status_code=status,content={'error':{'kind':kind,'message':message,**details}})


async def body(request: Request) -> dict[str,Any]:
    """Parse original single quantities exactly, before a float DTO can lose digits."""
    def reject_constant(value: str) -> None: raise ValueError('nonfinite JSON number: '+value)
    def pairs(items: list[tuple[str,Any]]) -> dict[str,Any]:
        result={}
        for k,v in items:
            if k in result: raise ValueError('duplicate JSON field: '+k)
            result[k]=v
        return result
    value=json.loads(await request.body(),parse_float=Decimal,parse_constant=reject_constant,object_pairs_hook=pairs)
    if not isinstance(value,dict): raise ValueError('JSON object required')
    return value


def number(value: Any) -> float:
    if isinstance(value,bool) or not isinstance(value,(int,float,Decimal)) or not math.isfinite(float(value)): raise ValueError('finite number required')
    return float(value)


@router.post('/sessions')
async def create(request: Request) -> Any:
    try:
        data=await body(request)
        if set(data)-{'seed','profile','window_mode','auto_replan'}: raise ValueError('unknown create fields')
        if 'auto_replan' in data and not isinstance(data['auto_replan'],bool):raise ValueError('boolean auto_replan required')
        profile=data.get('profile','random')
        if profile not in ('random','bjut','bjut-campus','bjut-studio','bjut-studio-operational'): raise ValueError('unknown map profile')
        if profile in ('bjut','bjut-campus','bjut-studio','bjut-studio-operational'):
            from logiroute.dispatch.real_map import map_config
            config=map_config('bjut-campus' if profile in ('bjut-studio','bjut-studio-operational') else profile)
        else: config=load_config()
        seed=data.get('seed',config['default_seed'])
        if profile in ('bjut-studio','bjut-studio-operational'):
            from logiroute.dispatch.studio import studio_state,defaults
            state=studio_state(seed,defaults(),data.get('window_mode','pressure' if profile=='bjut-studio-operational' else 'strict'),operational=profile=='bjut-studio-operational');attempts=[]
        else: state,attempts=generate_state(seed,config,window_mode=data.get('window_mode'))
        service=request.app.state.dispatch_service
        with service.lock:
            service.counter+=1; key=config['session_prefix']+str(service.counter); session=Session(state)
            if data.get('auto_replan',False):session.enable_auto_replan()
            service.sessions[key]=session; service.attempts[key]=attempts
            return service.snapshot(key,session)
    except GenerationError as exc: return failure(422,'generation_exhausted',str(exc),attempts=exc.attempts)
    except WindowGenerationError as exc: return failure(422,'generation_exhausted',str(exc),attempts=exc.attempts)
    except (ValueError,TypeError,GraphError,KeyError) as exc: return failure(422,'invalid_input',str(exc))


@router.get('/sessions/{key}')
def read(key: str,request: Request) -> Any:
    service=request.app.state.dispatch_service
    with service.lock:
        if key not in service.sessions: return failure(404,'not_found','unknown session')
        return service.snapshot(key,service.sessions[key])


@router.post('/sessions/{key}/trial')
async def parameter_trial(key: str,request: Request) -> Any:
    """Fresh fork, original IDs/windows retained; no entered-action reset."""
    from logiroute.dispatch.studio import trial_session
    from logiroute.algorithms.window_calibration import route_structure
    try:
        data=await body(request);service=request.app.state.dispatch_service
        with service.lock:
            if key not in service.sessions:return failure(404,'not_found','unknown session')
            original=service.sessions[key]
            if set(data)-{'revision','parameters','objective'}:raise ValueError('unknown trial fields')
            if isinstance(data.get('revision'),bool) or not isinstance(data.get('revision'),int):raise ValueError('integer revision required')
            if data['revision']!=original.state.revision:raise ConflictError('stale revision; refresh session')
            session=trial_session(original,data['parameters']);objective=data.get('objective','cost')
            baseline=original.prepare(objective)
            session.state.config['studio_trial']={'original_session':key,'objective':objective,
                'before':{'distance':sum(r.total_distance for r in baseline.routes),'cost':sum(r.total_cost for r in baseline.routes),'accepted':len(baseline.accepted),'complete_all':baseline.report.complete_all},
                'before_routes':json.loads(json.dumps(route_structure(baseline)))}
            proposal=session.prepare(objective)
            if not proposal.report.valid or not proposal.report.safe_to_apply:return failure(422,'unsafe_plan','parameter trial failed independent verification')
            session.apply(proposal);service.counter+=1;new_key=session.state.config['session_prefix']+str(service.counter)
            service.sessions[new_key]=session;service.attempts[new_key]=[]
            return service.snapshot(new_key,session)
    except ConflictError as exc:return failure(409,'conflict',str(exc))
    except (ValueError,TypeError,KeyError,GraphError,InvalidOperation) as exc:return failure(422,'invalid_input',str(exc))


@router.post('/sessions/{key}/commands')
async def command(key: str,request: Request) -> Any:
    try:
        data=await body(request); service=request.app.state.dispatch_service
        with service.lock:
            if key not in service.sessions: return failure(404,'not_found','unknown session')
            original=service.sessions[key]
            if isinstance(data.get('revision'),bool) or not isinstance(data.get('revision'),int): raise ValueError('integer revision required')
            if data['revision']!=original.state.revision: raise ConflictError('stale revision; refresh session')
            kind=data['command']; fields={
                'plan':{'objective'},'compare':set(),'depart':set(),'step':set(),'pause':set(),
                'add':{'id','destination','demand','earliest','deadline','priority'},
                'automatic':{'count','seed','priority'},'cancel':{'id'},'expire':{'id'},
                'priority':{'id','priority'},'traffic':{'source','target','status'}}
            mutations={'add','automatic','cancel','expire','priority','traffic'}
            optional={'auto_replan'} if kind in mutations else set()
            if kind=='add':optional.update({'protect_critical','allow_late'})
            if kind not in fields or set(data)-fields[kind]-{'revision','command'}-optional: raise ValueError('unknown command/fields')
            if 'auto_replan' in data and not isinstance(data['auto_replan'],bool):raise ValueError('boolean auto_replan required')
            if 'protect_critical' in data and (not isinstance(data['protect_critical'],bool) or data['priority']!='critical'):raise ValueError('protect_critical requires a critical order and boolean value')
            if 'allow_late' in data and (not isinstance(data['allow_late'],bool) or data['priority']!='critical' or not data.get('protect_critical',False)):raise ValueError('allow_late requires protected critical admission')
            session=deepcopy(original); comparison=None
            if data.get('auto_replan',False):session.enable_auto_replan()
            if kind=='plan':
                proposal=session.prepare(data.get('objective','distance'))
                if proposal.report.safe_to_apply: session.apply(proposal)
                else: return failure(422,'unsafe_plan','protected cargo has no accepted continuation',report=proposal.to_dict())
            elif kind=='compare': comparison=[session.prepare(mode).to_dict() for mode in ('distance','cost')]
            elif kind=='depart': session.depart()
            elif kind=='step': session.step()
            elif kind=='pause': session.pause()
            elif kind=='add':
                args=(data['id'],data['destination'],Decimal(data['demand']) if isinstance(data['demand'],str) else data['demand'],number(data['earliest']),number(data['deadline']))
                if data.get('protect_critical',False):admit_critical(session,*args,allow_late=data.get('allow_late',False))
                else:session.add_order(*args,data['priority'])
            elif kind=='automatic': session.automatic(data['count'],data['seed'],data.get('priority','normal'))
            elif kind in ('cancel','expire'): session.cancel(data['id'],expired=kind=='expire')
            elif kind=='priority': session.priority(data['id'],data['priority'])
            elif kind=='traffic':
                old_time=session.state.graph.get_edge(data['source'],data['target']).travel_time
                session.traffic(data['source'],data['target'],data['status'])
                if not session.auto_replan_enabled and 'studio' in session.state.config and (data['status']=='blocked' or session.state.graph.get_edge(data['source'],data['target']).travel_time>=old_time*1.2):
                    session._studio_auto_replan_pending=True
                    session._studio_auto_replan_status='等待已进入动作完成后自动重规划'
            if session.auto_replan_enabled:
                session._studio_auto_replan_pending=False
                session.process_auto_replan()
            elif getattr(session,'_studio_auto_replan_pending',False) and not session.running:
                session._studio_auto_replan_pending=False
                proposal=session.prepare(session.plan.objective if session.plan else 'cost')
                if proposal.report.safe_to_apply:
                    session.apply(proposal);session._studio_auto_replan_status='已自动独立验证并应用续程；等待确认出发'
                else:session._studio_auto_replan_status='自动续程无法安全应用；保留实际货物与旧历史，请人工检查'
            snapshot=service.snapshot(key,session)
            if kind=='add' and data.get('protect_critical',False):snapshot['critical_admission']=session._critical_admission
            if comparison is not None: snapshot['comparison']=comparison
            service.sessions[key]=session
            return snapshot
    except CriticalAdmissionError as exc: return failure(422,'critical_unavailable',str(exc),report=exc.report)
    except ConflictError as exc: return failure(409,'conflict',str(exc))
    except (ValueError,TypeError,KeyError,GraphError,OverflowError,InvalidOperation) as exc: return failure(422,'invalid_input',str(exc))
