// Phase 5.3 —— 场景 x/y 坐标 → SVG 视口投影工具。
// 仅用标准数学（线性映射），无任何 GIS 库依赖。
//
// 重构说明：
//   * v2 之前依赖 lng/lat 投影 + 北京 16 区示意 GeoJSON；
//   * v3 起仅用 NodeData.x / NodeData.y 抽象坐标（[0, 100]），
//     不再绑定北京行政区划，便于后续切换真实路网或随机测试场景。

import type { NodeData } from '../../types';

export interface ViewportBox {
  /** 抽象坐标 x 范围 [minX, maxX] */
  minX: number;
  maxX: number;
  /** 抽象坐标 y 范围 [minY, maxY] */
  minY: number;
  maxY: number;
}

export interface SvgPoint {
  x: number;
  y: number;
}

/**
 * 给定节点 bbox + SVG 视口尺寸，返回投影函数。
 * 投影保持比例（不扭曲）；padding 用于节点标签与外圈边距。
 */
export function makeProjection(
  bbox: ViewportBox,
  viewW: number,
  viewH: number,
  padX: number = 30,
  padY: number = 30,
): (x: number, y: number) => SvgPoint {
  const xRange = bbox.maxX - bbox.minX || 1e-9;
  const yRange = bbox.maxY - bbox.minY || 1e-9;
  const usableW = viewW - 2 * padX;
  const usableH = viewH - 2 * padY;
  return (x: number, y: number) => ({
    x: padX + ((x - bbox.minX) / xRange) * usableW,
    // y 轴朝下：bbox.minY 对应 SVG 顶部（small y）
    y: padY + (1 - (y - bbox.minY) / yRange) * usableH,
  });
}

/**
 * 节点直接用 x/y 投影（不再有 lng/lat fallback）。
 * 调用方应已校验 Number.isFinite(n.x) && Number.isFinite(n.y)。
 */
export function projectNode(
  n: NodeData,
  project: (x: number, y: number) => SvgPoint,
): SvgPoint {
  return project(n.x, n.y);
}

/** 计算一组节点的 x/y 范围。 */
export function computeNodeBBox(
  nodes: NodeData[],
): ViewportBox {
  if (nodes.length === 0) {
    return { minX: 0, maxX: 1, minY: 0, maxY: 1 };
  }
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const n of nodes) {
    if (!Number.isFinite(n.x) || !Number.isFinite(n.y)) continue;
    if (n.x < minX) minX = n.x;
    if (n.x > maxX) maxX = n.x;
    if (n.y < minY) minY = n.y;
    if (n.y > maxY) maxY = n.y;
  }
  if (!Number.isFinite(minX)) {
    return { minX: 0, maxX: 1, minY: 0, maxY: 1 };
  }
  return { minX, maxX, minY, maxY };
}