"""Exact deterministic regional quotas over fixed customer IDs."""
from __future__ import annotations
from logiroute.algorithms.ordering import ordered_strings
from logiroute.scenario_generator.random_source import RandomSource


def sample_regions(groups: dict[str,list[str]],quotas: dict[str,int],count: int,rng: RandomSource) -> list[str]:
    """Validate then sample without replacement. Time O(N²+R²), Space O(N).

    Pseudocode: check disjoint pools and exact quota sum; visit stable region order;
    choose an index from the remaining pool; remove that ID; append each selection.
    """
    if not isinstance(quotas,dict) or not quotas or set(quotas)-set(groups): raise ValueError('invalid destination quota regions')
    if any(isinstance(q,bool) or not isinstance(q,int) or q<0 for q in quotas.values()) or sum(quotas.values())!=count: raise ValueError('destination quotas must sum to order count')
    seen=set()
    for values in groups.values():
        for key in values:
            if key in seen: raise ValueError('overlapping candidate regions')
            seen.add(key)
    if any(q>len(groups[zone]) for zone,q in quotas.items()): raise ValueError('regional quota exceeds candidate pool')
    result=[]
    for zone in ordered_strings(quotas):
        available=ordered_strings(groups[zone])
        for _ in range(quotas[zone]):
            value=rng.choice(available); available.remove(value); result.append(value)
    return result
