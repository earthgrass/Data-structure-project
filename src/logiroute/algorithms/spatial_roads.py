"""Handwritten Euclidean Prim backbone and bounded nearest-neighbor selection."""
from __future__ import annotations
from collections.abc import Sequence


def local_road_pairs(points: Sequence[tuple[str,float,float]],k: int) -> list[tuple[int,int]]:
    """Tree first, then union of each vertex's k nearest neighbors.

    Prim: repeatedly take the closest unvisited vertex, update its best parent.
    Neighbors: maintain a bounded insertion list by squared distance, then ID.
    Time O(V²*k), Space O(V*k+V); no library graph, heap or sorting algorithm.
    First V-1 pairs form a deterministic tree. Sets are membership-only.
    """
    n=len(points)
    if not 1<=k<n or len({p[0] for p in points})!=n: raise ValueError('invalid nearest-neighbor inputs')
    def distance(a: int,b: int) -> float:
        return (points[a][1]-points[b][1])**2+(points[a][2]-points[b][2])**2
    used=[False]*n; best=[float('inf')]*n; parent=[-1]*n; best[0]=0.0
    result=[]; seen=set()
    for _ in range(n):
        chosen=-1
        for i in range(n):
            if not used[i] and (chosen<0 or best[i]<best[chosen] or best[i]==best[chosen] and points[i][0]<points[chosen][0]): chosen=i
        used[chosen]=True
        if parent[chosen]>=0:
            a,b=parent[chosen],chosen; pair=(a,b) if a<b else (b,a)
            result.append(pair); seen.add(pair)
        for j in range(n):
            if used[j]: continue
            d=distance(chosen,j)
            if d<best[j] or d==best[j] and (parent[j]<0 or points[chosen][0]<points[parent[j]][0]):
                best[j]=d; parent[j]=chosen
    for i in range(n):
        nearest: list[tuple[float,str,int]]=[]
        for j in range(n):
            if j==i: continue
            d=distance(i,j); position=0
            while position<len(nearest) and (nearest[position][0]<d or nearest[position][0]==d and nearest[position][1]<points[j][0]): position+=1
            nearest.insert(position,(d,points[j][0],j))
            if len(nearest)>k: nearest.pop()
        for _,_,j in nearest:
            pair=(i,j) if i<j else (j,i)
            if pair not in seen: result.append(pair); seen.add(pair)
    return result
