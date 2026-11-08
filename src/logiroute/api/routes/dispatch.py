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
from logiroute.dispatch.session import Session,ConflictError
from logiroute.graph.logistics_graph import GraphError


class DispatchService:
    """One-process session store. All reads/writes serialized. O(total retained state)."""
    def __init__(self) -> None:
        self.lock=RLock(); self.sessions: dict[str,Session]={}; self.attempts={}; self.counter=0

    def snapshot(self,key: str,session: Session) -> dict[str,Any]:
        return {'id':key,**session.snapshot(),'generation':self.attempts[key]}


router=APIRouter(prefix='/api/v2')


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
        if set(data)-{'seed','profile'}: raise ValueError('unknown create fields')
        profile=data.get('profile','random')
        if profile not in ('random','bjut'): raise ValueError('unknown map profile')
        if profile=='bjut':
            from logiroute.dispatch.real_map import map_config
            config=map_config()
        else: config=load_config()
        seed=data.get('seed',config['default_seed']); state,attempts=generate_state(seed,config)
        service=request.app.state.dispatch_service
        with service.lock:
            service.counter+=1; key=config['session_prefix']+str(service.counter); session=Session(state)
            service.sessions[key]=session; service.attempts[key]=attempts
            return service.snapshot(key,session)
    except GenerationError as exc: return failure(422,'generation_exhausted',str(exc),attempts=exc.attempts)
    except (ValueError,TypeError,GraphError,KeyError) as exc: return failure(422,'invalid_input',str(exc))


@router.get('/sessions/{key}')
def read(key: str,request: Request) -> Any:
    service=request.app.state.dispatch_service
    with service.lock:
        if key not in service.sessions: return failure(404,'not_found','unknown session')
        return service.snapshot(key,service.sessions[key])


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
            if kind not in fields or set(data)-fields[kind]-{'revision','command'}: raise ValueError('unknown command/fields')
            session=deepcopy(original); comparison=None
            if kind=='plan':
                proposal=session.prepare(data.get('objective','distance'))
                if proposal.report.safe_to_apply: session.apply(proposal)
                else: return failure(422,'unsafe_plan','protected cargo has no accepted continuation',report=proposal.to_dict())
            elif kind=='compare': comparison=[session.prepare(mode).to_dict() for mode in ('distance','cost')]
            elif kind=='depart': session.depart()
            elif kind=='step': session.step()
            elif kind=='pause': session.pause()
            elif kind=='add': session.add_order(data['id'],data['destination'],Decimal(data['demand']) if isinstance(data['demand'],str) else data['demand'],number(data['earliest']),number(data['deadline']),data['priority'])
            elif kind=='automatic': session.automatic(data['count'],data['seed'],data.get('priority','normal'))
            elif kind in ('cancel','expire'): session.cancel(data['id'],expired=kind=='expire')
            elif kind=='priority': session.priority(data['id'],data['priority'])
            elif kind=='traffic': session.traffic(data['source'],data['target'],data['status'])
            snapshot=service.snapshot(key,session)
            if comparison is not None: snapshot['comparison']=comparison
            service.sessions[key]=session
            return snapshot
    except ConflictError as exc: return failure(409,'conflict',str(exc))
    except (ValueError,TypeError,KeyError,GraphError,OverflowError,InvalidOperation) as exc: return failure(422,'invalid_input',str(exc))
