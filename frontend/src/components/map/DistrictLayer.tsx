// Phase 5 —— 北京行政区划底板。
// 渲染顺序：先区填充（每区差异化彩色）→ 区边界 → 区名标签。

import { BEIJING_DISTRICTS, BeijingDistrictFeature } from '../../data/beijing-districts';

interface DistrictLayerProps {
  project: (lng: number, lat: number) => { x: number; y: number };
}

export function DistrictLayer({ project }: DistrictLayerProps) {
  return (
    <g aria-label="行政区划">
      {BEIJING_DISTRICTS.features.map((f: BeijingDistrictFeature) => {
        const ring = f.geometry.coordinates[0];
        const points = ring
          .map(([lng, lat]: [number, number]) => {
            const p = project(lng, lat);
            return `${p.x.toFixed(2)},${p.y.toFixed(2)}`;
          })
          .join(' ');
        const c = project(f.properties.centroid[0], f.properties.centroid[1]);
        return (
          <g key={`district-${f.properties.id}`}>
            <polygon
              points={points}
              fill={f.properties.color}
              stroke="#94a3b8"
              strokeWidth={1.2}
              strokeOpacity={0.6}
            />
            <text
              x={c.x}
              y={c.y}
              textAnchor="middle"
              fontSize={11}
              fill="#334155"
              fontWeight={f.properties.category === 'central' ? 700 : 500}
              pointerEvents="none"
              style={{ paintOrder: 'stroke', stroke: '#ffffff',
                       strokeWidth: 2, strokeLinejoin: 'round' }}
            >
              {f.properties.name}
            </text>
          </g>
        );
      })}
    </g>
  );
}