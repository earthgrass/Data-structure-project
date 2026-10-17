/**
 * 北京市行政区划示意 GeoJSON 数据 —— Phase 5 验收整改版。
 *
 * ⚠️ 重要声明（已更新）：
 *   本数据为「示意底板」，用于 Phase 5 Dashboard 可视化演示。
 *   多边形顶点为**人工近似手绘**，**不**代表官方精确行政区划边界。
 *
 *   优先考虑的真实数据源：
 *     - 北京市民政局全市全市地图 PDF（官方）https://mzj.beijing.gov.cn/art/2026/9/15/art_11098_693242.html
 *     - Wikimedia: Districts_of_Beijing.svg（CC BY-SA 4.0）
 *       https://commons.wikimedia.org/wiki/File:Districts_of_Beijing.svg
 *
 *   由于本环境离线、无法核实许可边界，未直接采用上述矢量数据；保留
 *   示意图状态。如需替换为真实数据，须先确认：
 *     1. 来源与版本号；
 *     2. 许可证（CC BY-SA 4.0 需署名 + 相同方式共享）；
 *     3. 坐标系（WGS84 经度 / 纬度）；
 *     4. 与现有节点 metadata.lng/lat 投影一致性。
 *
 * 改进（vs Phase 5 初版）：
 *   1. 每个区添加 categorical.color（CSS 十六进制）—— 16 区差异化低饱
 *      和度彩色填充，避免"几个灰色块拼接"的观感；
 *   2. 顶点增加；相邻区边界线对齐更自然；
 *   3. centroid 位置微调，让标签与货车节点尽量不重叠；
 *   4. 分类字段保留 central / suburb / mountain；
 *   5. 边界框略微收紧到 [115.7, 39.5, 117.3, 40.7]。
 *
 * 数据来源 / 许可：本文件**未**采集自任何外部数据源；坐标基于公开
 * 地图近似位置人工手绘。仅用于课程设计与算法演示。**不得**用于任何
 * 真实决策或公开发布。
 */

export interface BeijingDistrictProperties {
  /** 行政区中文名 */
  name: string;
  /** 拼音 / ID（与 Node 区域标签对接时使用） */
  id: string;
  /** 区中心（用于标签定位） */
  centroid: [number, number];
  /** 分类标签：central / suburb / mountain */
  category: 'central' | 'suburb' | 'mountain';
  /** 低饱和度彩色填充（CSS hex） */
  color: string;
}

export interface BeijingDistrictFeature {
  type: 'Feature';
  properties: BeijingDistrictProperties;
  geometry: {
    type: 'Polygon';
    coordinates: [number, number][][];
  };
}

export interface BeijingDistrictsGeoJSON {
  type: 'FeatureCollection';
  metadata: {
    description: string;
    coordinate_system: 'WGS84';
    disclaimer: string;
    bbox: [number, number, number, number];
  };
  features: BeijingDistrictFeature[];
}

const BBOX: [number, number, number, number] = [115.7, 39.5, 117.3, 40.7];

/** 16 区差异化低饱和度彩色填充。色相差异保证区划感，
 *  饱和度统一压低避免抢眼。
 */
const COLORS = {
  // 中心 4 区：偏冷
  dongcheng: '#fde2e4',      // 粉
  xicheng:   '#e2eafc',      // 浅蓝
  chaoyang:  '#dde7c7',      // 浅绿
  haidian:   '#ffe8c2',      // 米黄
  // 城区
  fengtai:        '#f7d6c4',  // 橙粉
  shijingshan:    '#e6cfe2',  // 浅紫
  // 远郊平原
  tongzhou:   '#cfe5d3',      // 绿
  shunyi:     '#cdd9c0',      // 灰绿
  changping:  '#d4d2b0',      // 黄绿
  daxing:     '#f6dfb1',      // 浅黄
  fangshan:   '#ead6a7',      // 米
  // 山区
  mentougou: '#cfd1c4',      // 灰
  huairou:    '#b8c6b0',      // 深绿
  pinggu:     '#b5cdb8',      // 青绿
  miyun:      '#a4b8a8',      // 深灰绿
  yanqing:    '#a3a8b0',      // 蓝灰
} as const;

export const BEIJING_DISTRICTS: BeijingDistrictsGeoJSON = {
  type: 'FeatureCollection',
  metadata: {
    description: '北京市 16 区示意边界（手绘，非官方）',
    coordinate_system: 'WGS84',
    disclaimer:
      '本数据为示意底板，顶点为人工近似手绘，不代表官方行政区划。' +
      '坐标系统：WGS84（经度 / 纬度）。',
    bbox: BBOX,
  },
  features: [
    // ===== 中心四区（与外围更细颗粒对齐） =====
    {
      type: 'Feature',
      properties: {
        name: '东城区', id: 'dongcheng',
        centroid: [116.418, 39.928],
        category: 'central', color: COLORS.dongcheng,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.395, 39.948],
          [116.418, 39.952],
          [116.435, 39.945],
          [116.448, 39.928],
          [116.440, 39.916],
          [116.425, 39.905],
          [116.408, 39.902],
          [116.390, 39.910],
          [116.385, 39.928],
          [116.388, 39.940],
          [116.395, 39.948],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '西城区', id: 'xicheng',
        centroid: [116.366, 39.913],
        category: 'central', color: COLORS.xicheng,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.340, 39.948],
          [116.395, 39.948],
          [116.388, 39.940],
          [116.385, 39.928],
          [116.390, 39.910],
          [116.408, 39.902],
          [116.398, 39.890],
          [116.378, 39.880],
          [116.350, 39.882],
          [116.338, 39.895],
          [116.335, 39.918],
          [116.340, 39.948],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '朝阳区', id: 'chaoyang',
        centroid: [116.490, 39.920],
        category: 'central', color: COLORS.chaoyang,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.435, 39.945],
          [116.448, 39.928],
          [116.580, 39.935],
          [116.650, 39.950],
          [116.700, 39.965],
          [116.730, 39.940],
          [116.740, 39.880],
          [116.700, 39.840],
          [116.620, 39.825],
          [116.520, 39.820],
          [116.470, 39.840],
          [116.440, 39.875],
          [116.430, 39.910],
          [116.425, 39.905],
          [116.435, 39.945],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '海淀区', id: 'haidian',
        centroid: [116.300, 39.965],
        category: 'central', color: COLORS.haidian,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.220, 40.080],
          [116.330, 40.085],
          [116.380, 40.060],
          [116.398, 40.000],
          [116.398, 39.948],
          [116.395, 39.948],
          [116.340, 39.948],
          [116.335, 39.918],
          [116.338, 39.895],
          [116.350, 39.882],
          [116.310, 39.870],
          [116.260, 39.880],
          [116.230, 39.910],
          [116.220, 39.950],
          [116.220, 40.080],
        ]],
      },
    },

    // ===== 城区 =====
    {
      type: 'Feature',
      properties: {
        name: '石景山区', id: 'shijingshan',
        centroid: [116.222, 39.910],
        category: 'suburb', color: COLORS.shijingshan,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.180, 39.945],
          [116.220, 39.950],
          [116.230, 39.910],
          [116.260, 39.880],
          [116.220, 39.870],
          [116.180, 39.880],
          [116.170, 39.910],
          [116.180, 39.945],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '丰台区', id: 'fengtai',
        centroid: [116.286, 39.858],
        category: 'suburb', color: COLORS.fengtai,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.220, 39.870],
          [116.260, 39.880],
          [116.310, 39.870],
          [116.378, 39.880],
          [116.398, 39.890],
          [116.408, 39.870],
          [116.430, 39.840],
          [116.400, 39.800],
          [116.330, 39.770],
          [116.230, 39.790],
          [116.180, 39.830],
          [116.170, 39.870],
          [116.180, 39.880],
          [116.220, 39.870],
        ]],
      },
    },

    // ===== 远郊平原 =====
    {
      type: 'Feature',
      properties: {
        name: '通州区', id: 'tongzhou',
        centroid: [116.660, 39.910],
        category: 'suburb', color: COLORS.tongzhou,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.700, 39.965],
          [116.830, 39.985],
          [116.900, 39.960],
          [116.930, 39.900],
          [116.900, 39.850],
          [116.820, 39.825],
          [116.740, 39.840],
          [116.730, 39.880],
          [116.740, 39.940],
          [116.700, 39.965],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '顺义区', id: 'shunyi',
        centroid: [116.660, 40.135],
        category: 'suburb', color: COLORS.shunyi,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.650, 40.220],
          [116.840, 40.225],
          [116.960, 40.180],
          [117.000, 40.100],
          [116.930, 40.020],
          [116.830, 39.985],
          [116.700, 39.965],
          [116.580, 39.935],
          [116.500, 39.990],
          [116.500, 40.080],
          [116.550, 40.180],
          [116.650, 40.220],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '昌平区', id: 'changping',
        centroid: [116.235, 40.225],
        category: 'suburb', color: COLORS.changping,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.100, 40.430],
          [116.330, 40.440],
          [116.420, 40.380],
          [116.450, 40.260],
          [116.430, 40.140],
          [116.398, 40.060],
          [116.380, 40.060],
          [116.330, 40.085],
          [116.220, 40.080],
          [116.130, 40.140],
          [116.080, 40.260],
          [116.100, 40.430],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '大兴区', id: 'daxing',
        centroid: [116.340, 39.730],
        category: 'suburb', color: COLORS.daxing,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.180, 39.830],
          [116.430, 39.840],
          [116.530, 39.780],
          [116.560, 39.700],
          [116.500, 39.640],
          [116.380, 39.620],
          [116.220, 39.660],
          [116.150, 39.740],
          [116.180, 39.830],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '房山区', id: 'fangshan',
        centroid: [115.970, 39.720],
        category: 'suburb', color: COLORS.fangshan,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [115.700, 39.920],
          [116.130, 39.900],
          [116.170, 39.870],
          [116.180, 39.830],
          [116.150, 39.740],
          [116.220, 39.660],
          [116.080, 39.620],
          [115.800, 39.650],
          [115.700, 39.780],
          [115.700, 39.920],
        ]],
      },
    },

    // ===== 山区 =====
    {
      type: 'Feature',
      properties: {
        name: '门头沟区', id: 'mentougou',
        centroid: [116.105, 39.945],
        category: 'mountain', color: COLORS.mentougou,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [115.850, 40.130],
          [116.130, 40.140],
          [116.220, 40.080],
          [116.220, 39.950],
          [116.180, 39.945],
          [116.180, 39.880],
          [116.170, 39.870],
          [116.130, 39.900],
          [116.060, 39.920],
          [115.900, 39.940],
          [115.850, 40.020],
          [115.850, 40.130],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '怀柔区', id: 'huairou',
        centroid: [116.640, 40.320],
        category: 'mountain', color: COLORS.huairou,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.450, 40.260],
          [116.430, 40.380],
          [116.420, 40.500],
          [116.550, 40.560],
          [116.750, 40.560],
          [116.870, 40.480],
          [116.920, 40.380],
          [116.840, 40.225],
          [116.650, 40.220],
          [116.550, 40.180],
          [116.500, 40.080],
          [116.500, 39.990],
          [116.450, 40.140],
          [116.450, 40.260],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '平谷区', id: 'pinggu',
        centroid: [117.120, 40.140],
        category: 'mountain', color: COLORS.pinggu,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.960, 40.180],
          [117.150, 40.220],
          [117.250, 40.150],
          [117.270, 40.000],
          [117.200, 39.920],
          [117.050, 39.940],
          [116.960, 40.020],
          [116.960, 40.180],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '密云区', id: 'miyun',
        centroid: [116.860, 40.380],
        category: 'mountain', color: COLORS.miyun,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.870, 40.480],
          [117.020, 40.500],
          [117.150, 40.450],
          [117.180, 40.320],
          [117.150, 40.220],
          [116.960, 40.180],
          [116.840, 40.225],
          [116.920, 40.380],
          [116.870, 40.480],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '延庆区', id: 'yanqing',
        centroid: [115.970, 40.470],
        category: 'mountain', color: COLORS.yanqing,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [115.700, 40.450],
          [115.700, 40.620],
          [115.850, 40.700],
          [116.080, 40.720],
          [116.330, 40.660],
          [116.420, 40.560],
          [116.430, 40.500],
          [116.430, 40.380],
          [116.420, 40.260],
          [116.330, 40.440],
          [116.100, 40.430],
          [115.850, 40.450],
          [115.700, 40.450],
        ]],
      },
    },
  ],
};

/** 工具函数：给定经纬度返回所在区 ID（点在多边形内 — 射线法）。 */
export function findDistrict(
  lng: number,
  lat: number,
): BeijingDistrictProperties | null {
  for (const f of BEIJING_DISTRICTS.features) {
    if (pointInPolygon([lng, lat], f.geometry.coordinates[0])) {
      return f.properties;
    }
  }
  return null;
}

function pointInPolygon(
  point: [number, number],
  ring: [number, number][],
): boolean {
  const [x, y] = point;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    const intersect =
      yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}