// Phase 5.3 —— PlaybackStrip：实时回放累计指标条。
//
// 数据归属：
//   - OWN：当前 stop / 累计 distance · time · cost / 进度条
//   - NOT OWN：不调用任何 API；全部由 playback prop 驱动
//   - DISPLAY：受控展示
//
// 不变量：
//   * 单车辆：永远只有一个「当前位置」；
//   * 不重算路径 —— 累计值来自 route_plan.cross_metrics 的线性插值。

import type { PlaybackView } from '../../state/usePlayback';

interface PlaybackStripProps {
  playback: PlaybackView;
}

function fmt(n: number, digits = 2): string {
  return n.toFixed(digits);
}

export function PlaybackStrip({ playback }: PlaybackStripProps) {
  const { currentStopId, cumulative, progress, isDone, isPlaying } = playback;
  const stateLabel = isDone
    ? '回放完成'
    : isPlaying
      ? playback.state.kind === 'playing' && playback.state.mode === 'manual'
        ? '单段演示中'
        : '自动播放中'
      : playback.isPaused
        ? '已暂停 · 可播放下一段'
        : '准备就绪';

  return (
    <div className="playback-strip" role="region" aria-label="实时回放指标">
      <div className="playback-strip-row playback-strip-stats">
        <div className="playback-cell">
          <div className="playback-cell-label">状态</div>
          <div className="playback-cell-val">{stateLabel}</div>
        </div>
        <div className="playback-cell">
          <div className="playback-cell-label">当前站点</div>
          <div className="playback-cell-val playback-cell-stop">
            {currentStopId ?? '—'}
          </div>
        </div>
        <div className="playback-cell">
          <div className="playback-cell-label">累计距离</div>
          <div className="playback-cell-val">
            {fmt(cumulative.distance)}
            <span className="playback-cell-unit">km</span>
          </div>
        </div>
        <div className="playback-cell">
          <div className="playback-cell-label">累计时间</div>
          <div className="playback-cell-val">
            {fmt(cumulative.time)}
            <span className="playback-cell-unit">min</span>
          </div>
        </div>
        <div className="playback-cell">
          <div className="playback-cell-label">累计成本</div>
          <div className="playback-cell-val">
            {fmt(cumulative.cost)}
            <span className="playback-cell-unit">¥</span>
          </div>
        </div>
      </div>

      <div className="playback-progress">
        <div
          className="playback-progress-fill"
          style={{ width: `${Math.min(100, Math.max(0, progress * 100))}%` }}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress * 100)}
          role="progressbar"
        />
      </div>
    </div>
  );
}
