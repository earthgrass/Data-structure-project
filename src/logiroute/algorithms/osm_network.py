"""Handwritten directed components and topology-preserving OSM chain extraction."""
from __future__ import annotations
import math
from typing import Any
from logiroute.algorithms.ordering import ordered_strings


def largest_component(adjacency: dict[str,list[str]]) -> list[str]:
    """Iterative Kosaraju. Time O(V+E+V² ordering), Space O(V+E).

    Pseudocode: postorder DFS; transpose; reverse postorder DFS; retain largest SCC.
    Equal size components retain the first found in deterministic vertex order.
    """
    reverse={k:[] for k in adjacency}; seen=set(); finish=[]
    for key,targets in adjacency.items():
        for target in targets: reverse[target].append(key)
    for root in ordered_strings(adjacency):
        if root in seen: continue
        seen.add(root); stack=[(root,0)]
        while stack:
            node,index=stack[-1]
            if index==len(adjacency[node]): finish.append(node); stack.pop(); continue
            target=adjacency[node][index]; stack[-1]=(node,index+1)
            if target not in seen: seen.add(target); stack.append((target,0))
    seen=set(); best=[]
    for root in reversed(finish):
        if root in seen: continue
        seen.add(root); group=[]; stack=[root]
        while stack:
            node=stack.pop(); group.append(node)
            for target in reverse[node]:
                if target not in seen: seen.add(target); stack.append(target)
        if len(group)>len(best): best=group
    return ordered_strings(best)


def compile_roads(nodes: dict[str,dict[str,Any]],ways: list[dict[str,Any]],settings: dict[str,Any]) -> dict[str,Any]:
    """Split ways at intersections, preserve geometry/direction, retain SCC.

    Time O(V²+E+G+(P+L)*V*B), Space O(V+E+G). G counts geometry points,
    P candidates, L configured landmarks, B campus boundary size (1 without campus).

    No invented reverse edges. Parallel endpoint pairs retain the shortest actual
    directed chain; discarded alternatives are counted, never merged geometrically.
    """
    west,south,east,north=settings['bbox']; radius=settings['earth_radius_m']
    def point(lon: float,lat: float) -> list[float]:
        return [radius*math.radians(lon-west),-radius*math.log(math.tan(math.pi/4+math.radians(lat)/2))+radius*math.log(math.tan(math.pi/4+math.radians(north)/2))]
    def inside(key: str) -> bool:
        n=nodes[key]; return west<=n['lon']<=east and south<=n['lat']<=north
    valid=[]; usage={}; names={}; background=[]; features=[]
    for w in ways:
        t=w['tags']; refs=w['nodes']
        coords=[point(nodes[k]['lon'],nodes[k]['lat']) for k in refs if k in nodes]
        if len(coords)<2: continue
        if t.get('building') or t.get('landuse') or t.get('leisure') or t.get('natural')=='water':
            features.append({'kind':'building' if t.get('building') else 'water' if t.get('natural')=='water' else 'land','name':t.get('name',''),'geometry':coords})
        if t.get('highway'): background.append({'name':t.get('name',''),'kind':t['highway'],'geometry':coords})
        if t.get('highway') not in settings['speed_kmh'] or t.get('access') in ('no','private') or t.get('vehicle')=='no' or t.get('motor_vehicle')=='no': continue
        for k in refs:
            if k in nodes and inside(k): usage[k]=usage.get(k,0)+1; names.setdefault(k,t.get('name','道路'))
        valid.append(w)
    adjacency={k:[] for k in usage}; raw=[]
    for w in valid:
        t=w['tags']; refs=w['nodes']; oneway=t.get('oneway','yes' if t.get('junction')=='roundabout' else 'no')
        for a,b in zip(refs,refs[1:]):
            if a not in adjacency or b not in adjacency or a==b: continue
            if oneway not in ('yes','1','true'): adjacency[b].append(a)
            if oneway!='-1': adjacency[a].append(b)
    component=set(largest_component(adjacency))
    landmarks={}; campus=None
    if settings.get('campus'):
        from logiroute.algorithms.campus_locations import place_landmarks
        landmarks,campus=place_landmarks(nodes,ways,settings,component)
    anchors=set(landmarks)
    for w in valid:
        refs=w['nodes']
        for i,k in enumerate(refs):
            if k in component and (i==0 or i==len(refs)-1 or usage[k]>1 or refs[i-1] not in component or refs[i+1] not in component): anchors.add(k)
    for w in valid:
        t=w['tags']; chain=[]; speed=settings['speed_kmh'][t['highway']]
        # maxspeed is used only for a simple numeric km/h tag; otherwise explicit defaults.
        tag=t.get('maxspeed','')
        if tag.replace('.','',1).isdigit() and float(tag)>0: speed=float(tag)
        oneway=t.get('oneway','yes' if t.get('junction')=='roundabout' else 'no')
        for k in w['nodes']:
            if k not in component: chain=[]; continue
            chain.append(k)
            if k not in anchors: continue
            if len(chain)>1 and chain[0]!=k:
                geometry=[point(nodes[j]['lon'],nodes[j]['lat']) for j in chain]
                distance=0.0
                for a,b in zip(chain,chain[1:]):
                    a=nodes[a]; b=nodes[b]; p1=math.radians(a['lat']); p2=math.radians(b['lat'])
                    h=math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(math.radians(b['lon']-a['lon'])/2)**2
                    distance+=2*radius*math.asin(min(1,math.sqrt(h)))/1000
                row={'source':chain[0],'target':k,'distance':distance,'travel_time':distance/speed*60,'cost':distance*settings['cost_per_km'],'geometry':geometry,'osm_way':w['id'],'name':t.get('name','未命名道路'),'highway':t['highway']}
                if oneway!='-1': raw.append(row)
                if oneway not in ('yes','1','true'): raw.append({**row,'source':k,'target':chain[0],'geometry':list(reversed(geometry))})
            chain=[k]
    edges={}; duplicates=0
    for e in raw:
        key=(e['source'],e['target'])
        if key in edges:
            duplicates+=1
            if edges[key]['distance']<=e['distance']: continue
        edges[key]=e
    adjacency={k:[] for k in ordered_strings(anchors)}
    for a,b in edges: adjacency[a].append(b)
    kept=largest_component(adjacency); allowed=set(kept); selected=dict(landmarks); reserved=set(selected)
    if any(k not in allowed for k in selected): raise ValueError('configured landmark lost during road compression')
    def nearest(lon: float,lat: float) -> str:
        p=point(lon,lat); best=None; score=math.inf
        for k in kept:
            if k in reserved: continue
            q=point(nodes[k]['lon'],nodes[k]['lat']); d=(p[0]-q[0])**2+(p[1]-q[1])**2
            if d<score: score=d; best=k
        if best is None: raise ValueError('not enough distinct real road locations')
        return best
    for base in ([] if landmarks else settings['bases']):
        k=nearest(base['lon'],base['lat']); reserved.add(k); selected[k]=base
    # Farthest-first spatial coverage over actual road anchors, stable ID tie order.
    distances={k:min((nodes[k]['lon']-nodes[b]['lon'])**2*math.cos(math.radians(nodes[k]['lat']))**2+(nodes[k]['lat']-nodes[b]['lat'])**2 for b in reserved) for k in kept}
    initial_candidates=sum(r['type']=='customer' for r in selected.values())
    if initial_candidates>settings['candidate_count']: raise ValueError('named pool exceeds configured candidate count')
    for i in range(initial_candidates,settings['candidate_count']):
        best=None; score=-1
        for k in kept:
            if campus:
                from logiroute.algorithms.campus_locations import in_polygon
                p=nodes[k]; w,s,e,n=campus['outside_bounds']
                if not w<=p['lon']<=e or not s<=p['lat']<=n or in_polygon(p['lon'],p['lat'],campus['polygon']): continue
            if k not in reserved and distances[k]>score: best=k; score=distances[k]
        if best is None: raise ValueError('candidate pool exceeds road anchors')
        reserved.add(best); selected[best]={'id':f'P{i+1:02}','type':'customer','name':names.get(best,'道路')+' · 候选点 '+str(i+1)}
        if campus: selected[best]['metadata']={'zone':'surrounding','location_source':'osm_road_anchor','approximate':True}
        for k in kept:
            d=(nodes[k]['lon']-nodes[best]['lon'])**2*math.cos(math.radians(nodes[k]['lat']))**2+(nodes[k]['lat']-nodes[best]['lat'])**2
            distances[k]=min(distances[k],d)
    ids={k:selected[k]['id'] if k in selected else 'R'+k for k in kept}
    output_nodes=[]
    for k in kept:
        n=nodes[k]; role=selected.get(k,{'type':'customer','name':names.get(k,'道路')})
        output_nodes.append({'id':ids[k],'type':role['type'],'name':role['name'],'x':point(n['lon'],n['lat'])[0],'y':point(n['lon'],n['lat'])[1],
                             'metadata':{'osm_id':k,'lon':n['lon'],'lat':n['lat'],'routing_only':k not in selected,**role.get('metadata',{})}})
    output={'nodes':output_nodes,'edges':[{**e,'source':ids[e['source']],'target':ids[e['target']]} for e in edges.values() if e['source'] in allowed and e['target'] in allowed],
            'features':features,'background_roads':background,'bounds':[0,0,*point(east,south)],'candidate_ids':[r['id'] for r in selected.values() if r['type']=='customer'],
            'discarded_parallel_directions':duplicates,'discarded_road_nodes':len(adjacency)-len(kept)}
    if campus:
        outline=[point(*p) for p in campus['polygon']]; pad=campus['map_padding_m']/math.cos(math.radians((south+north)/2))
        output['bounds']=[min(p[0] for p in outline)-pad,min(p[1] for p in outline)-pad,max(p[0] for p in outline)+pad,max(p[1] for p in outline)+pad]
        output['campus']={'outline':outline,'campus_profile':True,'location_note':'快递站与外卖柜按用户描述近似定位，可依据实际柜位进一步校准'}
        output['candidate_groups']={zone:[r['id'] for r in selected.values() if r['type']=='customer' and r['metadata']['zone']==zone] for zone in ('campus','surrounding')}
    return output
