// Phase 5.1 —— 地图图例（独立组件，可放置于地图角落）。
// 视觉编码：色相 + 形状 双通道，避免只靠颜色区分。

interface MapLegendProps {
  /** 是否显示"非路线边"项 */
  showNetworkEdges?: boolean;
}

const ROLE_LABELS: Record<string, string> = {
  warehouse: '仓库',
  customer: '客户',
  transfer: '中转',
};

export function MapLegend({ showNetworkEdges = true }: MapLegendProps) {
  return (
    <div className="map-legend" role="region" aria-label="地图图例">
      <div className="map-legend-title">图例</div>

      <div className="legend-row">
        <span
          className="legend-swatch square"
          style={{ background: 'var(--identity-warehouse)' }}
        />
        <span>{ROLE_LABELS.warehouse}</span>
      </div>

      <div className="legend-row">
        <span
          className="legend-swatch circle"
          style={{ background: 'var(--identity-customer)' }}
        />
        <span>{ROLE_LABELS.customer}</span>
      </div>

      <div className="legend-row">
        <span className="legend-swatch triangle" />
        <span>{ROLE_LABELS.transfer}</span>
      </div>

      <div className="legend-row">
        <span
          className="legend-line"
          style={{ background: 'var(--identity-route-active)' }}
        />
        <span>当前配送路线</span>
      </div>

      {showNetworkEdges && (
        <div className="legend-row">
          <span
            className="legend-line"
            style={{
              background: 'var(--identity-route-edge)',
              opacity: 0.6,
            }}
          />
          <span>网络普通边</span>
        </div>
      )}
    </div>
  );
}
