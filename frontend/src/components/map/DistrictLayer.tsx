// Phase 5 —— 北京行政区划底板。
// 渲染顺序：先区填充 → 后区边界 → 区名标签。

import { BEIJING_DISTRICTS } from '../../data/beijing-districts';

interface DistrictLayerProps {
  project: (lng: number, lat: number) => { x: number; y: number };
}

export function DistrictLayer({ project }: DistrictLayerProps) {
  return (
    <g aria-label="行政区划">
      {BEIJING_DISTRICTS.features.map((f) => {
        const ring = f.geometry.coordinates[0];
        const points = ring
          .map(([lng, lat]) => {
            const p = project(lng, lat);
            return `${p.x.toFixed(2)},${p.y.toFixed(2)}`;
          })
          .join(' ');
        const c = project(f.properties.centroid[0], f.properties.centroid[1]);
        return (
          <g key={`district-${f.properties.id}`}>
            <polygon
              points={points}
              fill="var(--identity-district-fill)"
              stroke="var(--identity-district-stroke)"
              strokeWidth={1}
              strokeOpacity={0.7}
            />
            <text
              x={c.x}
              y={c.y}
              textAnchor="middle"
              fontSize={10}
              fill="var(--identity-district-text)"
              fontWeight={500}
              pointerEvents="none"
            >
              {f.properties.name}
            </text>
          </g>
        );
      })}
    </g>
  );
}