"""Deterministic source-referenced campus service anchors; no synthetic road edges."""
from __future__ import annotations
import math
from typing import Any
from logiroute.algorithms.ordering import ordered_strings


def in_polygon(x: float,y: float,polygon: list[list[float]]) -> bool:
    """Handwritten ray crossing; Time/Space O(boundary vertices)."""
    result=False
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]: result=not result
    return result


def place_landmarks(nodes: dict[str,dict[str,Any]],ways: list[dict[str,Any]],settings: dict[str,Any],component: set[str]) -> tuple[dict[str,dict[str,Any]],dict[str,Any]]:
    """Match configured references to distinct existing road nodes; O(L*V*B+V²).

    Pseudocode: resolve OSM reference; apply documented offset; scan eligible road
    nodes in handwritten stable order; reject distant match; reserve real node.
    B is boundary size. Space O(V+L+B+W), W source ways. No invented road edges.
    """
    spec=settings['campus']; index={w['id']:w for w in ways}; boundary=index[spec['boundary_way']]['nodes']
    polygon=[[nodes[k]['lon'],nodes[k]['lat']] for k in boundary]
    roads=ordered_strings(component); selected={}; used_ids=set(); radius=settings['earth_radius_m']
    for row in settings['bases']+spec['candidate_landmarks']:
        if row['id'] in used_ids: raise ValueError('duplicate configured location ID')
        used_ids.add(row['id']); reference=row.get('reference',{}); metadata={}
        if 'osm_node' in reference:
            p=nodes[reference['osm_node']]; lon=p['lon']; lat=p['lat']; metadata['reference_osm_node']=reference['osm_node']
        elif 'osm_way' in reference:
            refs=index[reference['osm_way']]['nodes']
            if refs[0]==refs[-1]: refs=refs[:-1]
            lon=sum(nodes[k]['lon'] for k in refs)/len(refs)
            lat=max(nodes[k]['lat'] for k in refs) if reference.get('anchor')=='north' else sum(nodes[k]['lat'] for k in refs)/len(refs)
            metadata['reference_osm_way']=reference['osm_way']
        else: lon=row['lon']; lat=row['lat']
        lat+=math.degrees(reference.get('north_offset_m',0)/radius)
        lon+=math.degrees(reference.get('east_offset_m',0)/(radius*math.cos(math.radians(lat))))
        best=None; distance=math.inf
        for key in roads:
            if key in selected: continue
            p=nodes[key]
            if row.get('zone')=='campus' and not in_polygon(p['lon'],p['lat'],polygon): continue
            d=math.hypot(math.radians(p['lon']-lon)*math.cos(math.radians(lat)),math.radians(p['lat']-lat))*radius
            if d<distance: best=key; distance=d
        if best is None or distance>spec['max_snap_distance_m']: raise ValueError('no nearby reachable anchor for '+row['id'])
        selected[best]={**row,'metadata':{**metadata,'zone':row.get('zone','base'),'display_name':row['name'],
                       'reference_lon':lon,'reference_lat':lat,'snap_distance_m':distance,
                       'location_source':row['location_source'],'approximate':True,'location_note':row.get('location_note','楼栋附近道路接驳点，非楼门精确坐标')}}
    return selected,{'polygon':polygon,'outside_bounds':spec['outside_bounds'],'map_padding_m':spec['map_padding_m']}
