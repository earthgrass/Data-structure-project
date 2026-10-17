/**
 * 北京市行政区划示意 GeoJSON 数据。
 *
 * ⚠️ 重要声明：
 *   本数据为「示意底板」，用于 Phase 5 Dashboard 可视化演示。
 *   多边形顶点为手绘近似，**不**代表官方精确行政区划边界。
 *   坐标系：WGS84（经度 / 纬度，单位：度）。
 *   覆盖范围：约 39.5°N–40.7°N / 115.5°E–117.3°E。
 *
 * 北京市辖区 16 个：
 *   中心区：东城区、西城区、朝阳区、海淀区
 *   城区：丰台区、石景山区
 *   近郊区：通州区、顺义区、昌平区、大兴区、房山区
 *   山区：门头沟区、怀柔区、平谷区、密云区、延庆区
 *
 * 数据来源 / 许可：
 *   本文件**未**采集自任何官方 / 商业数据源；顶点坐标基于公开地图的近似位置手绘，
 *   仅用于课程设计与算法演示。**不得**用于任何真实决策或公开发布。
 */

export interface BeijingDistrictProperties {
  /** 行政区中文名 */
  name: string;
  /** 拼音 / ID（与 Node 区域标签对接时使用） */
  id: string;
  /** 区中心（用于标签定位） */
  centroid: [number, number]; // [lng, lat]
  /** 分类标签：central / suburb / mountain */
  category: 'central' | 'suburb' | 'mountain';
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
    bbox: [number, number, number, number]; // [minLng, minLat, maxLng, maxLat]
  };
  features: BeijingDistrictFeature[];
}

/** 经度范围 [115.7, 117.2]，纬度范围 [39.5, 40.7]（含 16 区边界） */
const BBOX: [number, number, number, number] = [115.7, 39.5, 117.2, 40.7];

export const BEIJING_DISTRICTS: BeijingDistrictsGeoJSON = {
  type: 'FeatureCollection',
  metadata: {
    description: '北京市 16 区示意边界（手绘，非官方）',
    coordinate_system: 'WGS84',
    disclaimer:
      '本数据为示意底板，顶点为手绘近似，不代表官方行政区划。' +
      '坐标系统：WGS84（经度 / 纬度）。',
    bbox: BBOX,
  },
  features: [
    // -------- 中心四区 --------
    {
      type: 'Feature',
      properties: {
        name: '东城区',
        id: 'dongcheng',
        centroid: [116.418, 39.928],
        category: 'central',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.385, 39.945],
          [116.430, 39.945],
          [116.450, 39.928],
          [116.430, 39.910],
          [116.395, 39.908],
          [116.380, 39.922],
          [116.385, 39.945],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '西城区',
        id: 'xicheng',
        centroid: [116.366, 39.913],
        category: 'central',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.340, 39.945],
          [116.385, 39.945],
          [116.380, 39.922],
          [116.395, 39.908],
          [116.380, 39.890],
          [116.345, 39.890],
          [116.330, 39.910],
          [116.340, 39.945],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '朝阳区',
        id: 'chaoyang',
        centroid: [116.485, 39.92],
        category: 'central',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.430, 39.985],
          [116.580, 39.985],
          [116.620, 39.940],
          [116.640, 39.880],
          [116.550, 39.830],
          [116.450, 39.855],
          [116.430, 39.910],
          [116.450, 39.928],
          [116.430, 39.945],
          [116.430, 39.985],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '海淀区',
        id: 'haidian',
        centroid: [116.30, 39.96],
        category: 'central',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.220, 40.060],
          [116.350, 40.080],
          [116.395, 40.040],
          [116.395, 39.985],
          [116.395, 39.945],
          [116.340, 39.945],
          [116.330, 39.910],
          [116.345, 39.890],
          [116.260, 39.890],
          [116.220, 39.940],
          [116.220, 40.060],
        ]],
      },
    },

    // -------- 城区 --------
    {
      type: 'Feature',
      properties: {
        name: '丰台区',
        id: 'fengtai',
        centroid: [116.286, 39.858],
        category: 'suburb',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.260, 39.890],
          [116.345, 39.890],
          [116.380, 39.890],
          [116.395, 39.890],
          [116.380, 39.855],
          [116.400, 39.820],
          [116.330, 39.790],
          [116.230, 39.820],
          [116.220, 39.870],
          [116.260, 39.890],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '石景山区',
        id: 'shijingshan',
        centroid: [116.222, 39.906],
        category: 'suburb',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.180, 39.940],
          [116.260, 39.940],
          [116.260, 39.890],
          [116.220, 39.890],
          [116.180, 39.905],
          [116.180, 39.940],
        ]],
      },
    },

    // -------- 近郊 / 远郊（平原） --------
    {
      type: 'Feature',
      properties: {
        name: '通州区',
        id: 'tongzhou',
        centroid: [116.66, 39.91],
        category: 'suburb',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.550, 39.985],
          [116.720, 39.985],
          [116.780, 39.930],
          [116.780, 39.860],
          [116.700, 39.830],
          [116.640, 39.880],
          [116.620, 39.940],
          [116.580, 39.985],
          [116.550, 39.985],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '顺义区',
        id: 'shunyi',
        centroid: [116.65, 40.13],
        category: 'suburb',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.550, 40.220],
          [116.760, 40.220],
          [116.780, 40.130],
          [116.780, 39.985],
          [116.720, 39.985],
          [116.550, 39.985],
          [116.550, 40.130],
          [116.550, 40.220],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '昌平区',
        id: 'changping',
        centroid: [116.23, 40.22],
        category: 'suburb',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.080, 40.400],
          [116.350, 40.400],
          [116.395, 40.250],
          [116.395, 40.080],
          [116.350, 40.080],
          [116.220, 40.060],
          [116.080, 40.200],
          [116.080, 40.400],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '大兴区',
        id: 'daxing',
        centroid: [116.33, 39.73],
        category: 'suburb',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.180, 39.830],
          [116.450, 39.830],
          [116.500, 39.770],
          [116.500, 39.660],
          [116.380, 39.620],
          [116.220, 39.660],
          [116.150, 39.760],
          [116.180, 39.830],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '房山区',
        id: 'fangshan',
        centroid: [115.97, 39.72],
        category: 'suburb',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [115.700, 39.900],
          [116.150, 39.870],
          [116.180, 39.830],
          [116.150, 39.760],
          [116.220, 39.660],
          [116.080, 39.620],
          [115.800, 39.650],
          [115.700, 39.780],
          [115.700, 39.900],
        ]],
      },
    },

    // -------- 山区 --------
    {
      type: 'Feature',
      properties: {
        name: '门头沟区',
        id: 'mentougou',
        centroid: [116.10, 39.94],
        category: 'mountain',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [115.850, 40.100],
          [116.180, 40.080],
          [116.220, 40.060],
          [116.180, 39.940],
          [116.180, 39.905],
          [116.080, 39.870],
          [115.850, 39.900],
          [115.850, 40.100],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '怀柔区',
        id: 'huairou',
        centroid: [116.63, 40.32],
        category: 'mountain',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.350, 40.500],
          [116.800, 40.500],
          [116.850, 40.350],
          [116.760, 40.220],
          [116.550, 40.220],
          [116.350, 40.400],
          [116.350, 40.500],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '平谷区',
        id: 'pinggu',
        centroid: [117.12, 40.14],
        category: 'mountain',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.900, 40.300],
          [117.300, 40.280],
          [117.300, 40.050],
          [117.100, 39.980],
          [116.900, 40.050],
          [116.900, 40.300],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '密云区',
        id: 'miyun',
        centroid: [116.85, 40.38],
        category: 'mountain',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [116.760, 40.620],
          [117.100, 40.620],
          [117.100, 40.350],
          [116.800, 40.500],
          [116.760, 40.620],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        name: '延庆区',
        id: 'yanqing',
        centroid: [115.97, 40.47],
        category: 'mountain',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [115.700, 40.620],
          [116.350, 40.620],
          [116.350, 40.500],
          [116.350, 40.400],
          [116.080, 40.400],
          [115.700, 40.450],
          [115.700, 40.620],
        ]],
      },
    },
  ],
};

/** 工具函数：给定经纬度返回所在区 ID（点 in polygon 简化射线法）。 */
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