"""Rebuild the offline map from the preserved OSM extract; no network on app startup."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from logiroute.algorithms.osm_network import compile_roads


def main() -> None:
    """Parse OSM XML and persist reproducible derived data. O(source bytes+compiler)."""
    folder=Path(__file__).resolve().parents[1]/'data/bjut'
    settings=json.loads((folder/'build-config.json').read_text(encoding='utf-8'))
    source=folder/'source.osm'; root=ET.parse(source).getroot()
    nodes={n.attrib['id']:{'lon':float(n.attrib['lon']),'lat':float(n.attrib['lat'])} for n in root.findall('node')}
    ways=[{'id':w.attrib['id'],'nodes':[n.attrib['ref'] for n in w.findall('nd')],'tags':{t.attrib['k']:t.attrib['v'] for t in w.findall('tag')}} for w in root.findall('way')]
    data=compile_roads(nodes,ways,settings)
    data['provenance']={'source':'OpenStreetMap','source_url':settings['source_url'],'download_date':settings['download_date'],'license':'ODbL-1.0','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'bbox':settings['bbox'],'osm_base':root.attrib.get('timestamp','')}
    target=folder/'network.json'; target.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(len(data['nodes']),'nodes',len(data['edges']),'directed roads',len(data['candidate_ids']),'candidate stops',target.stat().st_size,'bytes')


if __name__=='__main__': main()
