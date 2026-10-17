// Phase 5 —— 经纬度 → SVG 视口投影工具。
// 仅用标准数学（线性映射），无任何 GIS 库依赖。

import type { NodeData } from '../../types';

export interface ViewportBox {
  /** 经度范围 [minLng, maxLng] */
  minLng: number;
  maxLng: number;
  /** 纬度范围 [minLat, maxLat] */
  minLat: number;
  maxLat: number;
}

export interface SvgPoint {
  x: number;
  y: number;
}

/**
 * 给定经纬度边界 + SVG 视口尺寸，返回投影函数。
 * 投影保持地理比例（不扭曲）；上下 padding 用于区名标签。
 */
export function makeProjection(
  bbox: ViewportBox,
  viewW: number,
  viewH: number,
  padX: number = 30,
  padY: number = 30,
): (lng: number, lat: number) => SvgPoint {
  const lngRange = bbox.maxLng - bbox.minLng || 1e-9;
  const latRange = bbox.maxLat - bbox.minLat || 1e-9;
  const usableW = viewW - 2 * padX;
  const usableH = viewH - 2 * padY;
  return (lng: number, lat: number) => ({
    x: padX + ((lng - bbox.minLng) / lngRange) * usableW,
    // 纬度越高 → y 越小（SVG y 轴朝下）
    y: padY + (1 - (lat - bbox.minLat) / latRange) * usableH,
  });
}

/** 节点优先用 lng/lat，缺失时回退到 x/y 归一化到 [pad, view-pad]。 */
export function projectNode(
  n: NodeData,
  project: (lng: number, lat: number) => SvgPoint,
  fallbackBBox: { minX: number; maxX: number; minY: number; maxY: number },
  viewW: number,
  viewH: number,
  padX: number = 30,
  padY: number = 30,
): SvgPoint {
  if (n.lng != null && n.lat != null) {
    return project(n.lng, n.lat);
  }
  const { minX, maxX, minY, maxY } = fallbackBBox;
  const xRange = maxX - minX || 1e-9;
  const yRange = maxY - minY || 1e-9;
  return {
    x: padX + ((n.x - minX) / xRange) * (viewW - 2 * padX),
    y: padY + (1 - (n.y - minY) / yRange) * (viewH - 2 * padY),
  };
}

/** 计算一组节点的经纬度范围（lng/lat 缺失时回退到 x/y）。 */
export function computeNodeBBox(
  nodes: NodeData[],
): { minLng: number; maxLng: number; minLat: number; maxLat: number;
     minY: number; maxY: number; minX: number; maxX: number } {
  const lngs = nodes.map((n) => n.lng ?? n.x);
  const lats = nodes.map((n) => n.lat ?? n.y);
  const xs = nodes.map((n) => n.x);
  const ys = nodes.map((n) => n.y);
  return {
    minLng: Math.min(...lngs),
    maxLng: Math.max(...lngs),
    minLat: Math.min(...lats),
    maxLat: Math.max(...lats),
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minY: Math.min(...ys),
    maxY: Math.max(...ys),
  };
}