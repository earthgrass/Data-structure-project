// Phase 5 —— 前端 TypeScript 类型
// 直接镜像 src/logiroute/api/schemas.py 与 Phase 3 ScheduleResult 的 to_dict() 输出。

export type NodeType = 'warehouse' | 'customer' | 'transfer';

export interface NodeData {
  id: string;
  name: string;
  type: NodeType;
  x: number;
  y: number;
  /** Phase 5 可视化经度（WGS84）；null 时回退到 x/y 投影 */
  lng: number | null;
  /** Phase 5 可视化纬度（WGS84）；null 时回退到 x/y 投影 */
  lat: number | null;
  /** 节点 metadata（如 viz_source 等） */
  metadata?: Record<string, unknown>;
}

export interface EdgeData {
  source: string;
  target: string;
  distance: number;
  travel_time: number;
  cost: number;
  traffic_status: string;
}

export interface VehicleData {
  id: string;
  capacity: number;
  current_load: number;
  current_node_id: string;
  status: string;
}

export interface CourierData {
  id: string;
  name: string;
  vehicle_id: string;
  status: string;
}

export interface OrderData {
  id: string;
  destination_id: string;
  demand: number;
  time_window_start: number;
  time_window_end: number;
  priority: string;
  status: string;
}

export interface GraphData {
  directed: boolean;
  node_count: number;
  edge_count: number;
  nodes: NodeData[];
  edges: EdgeData[];
}

export interface ScenarioData {
  name: string;
  mode: string;
  random_seed: number;
  graph: GraphData;
  vehicles: VehicleData[];
  couriers: CourierData[];
  orders: OrderData[];
  simulation: Record<string, unknown>;
  optimization: Record<string, unknown>;
  metadata: Record<string, unknown>;
  backbone: string[] | null;
}

export interface ValidationReport {
  feasible: boolean;
  scenario_name: string;
  nodes: number;
  edges: number;
  warehouses: number;
  customers: number;
  transfers: number;
  orders: number;
  total_demand: number;
  capacity: number;
  backbone_length: number;
  all_orders_covered: boolean;
  capacity_ok: boolean;
  time_windows_ok: boolean;
  all_legs_reachable: boolean;
  closed_route_ok: boolean;
  service_time: number;
  initial_time: number;
  violations: { check: string; message: string }[];
}

/** Phase 5 统一规划器响应——比较接口的双目标结构 */
export interface CompareResponse {
  objectives: string[];
  results: Record<string, ScheduleResult>;
}

export interface ScenarioResponse {
  scenario: ScenarioData;
  validation: ValidationReport;
  config_name: string;
}

export interface LegData {
  source: string;
  target: string;
  metric: string;
  path: string[];
  total_weight: number;
  reachable: boolean;
  cross_metrics: Record<string, number>;
}

export interface StopData {
  sequence_index: number;
  node_id: string;
  arrival_time: number;
  service_start: number;
  service_end: number;
  waiting_time: number;
}

export interface RoutePlanData {
  algorithm: string;
  objective: string;
  vehicle_id: string;
  courier_id: string | null;
  depot_id: string;
  stop_sequence: string[];
  road_node_sequence: string[];
  legs: LegData[];
  stops: StopData[];
  total_distance: number;
  total_travel_time: number;
  total_cost: number;
  main_objective_total: number;
  departure_time: number;
  return_time: number;
  capacity: number;
  served_order_ids: string[];
  is_feasible: boolean;
}

export interface PlanningStats {
  cache_hits: number;
  cache_misses: number;
  dijkstra_calls: number;
  paths_evaluated: number;
  feasibility_checks: number;
  iterations: number;
  runtime_seconds: number;
}

export interface ViolationData {
  order_id: string;
  kind: string;
  message: string;
}

export interface ScheduleResult {
  scenario_name: string;
  algorithm: string;
  objective: string;
  depot_id: string;
  vehicle_id: string;
  courier_id: string | null;
  route_plan: RoutePlanData;
  served_order_ids: string[];
  unserved_orders: ViolationData[];
  total_distance: number;
  total_travel_time: number;
  total_cost: number;
  main_objective_total: number;
  planning_stats: PlanningStats;
  is_feasible: boolean;
}

export interface PlanResponse {
  objective: string;
  result: ScheduleResult;
}

export interface CompareResponse {
  objective: string;
  results: Record<string, ScheduleResult>;
}

export type Algorithm = 'nearest_neighbor' | 'insertion' | 'two_opt';
export type Objective = 'distance' | 'cost';

export interface HealthResponse {
  status: string;
  version: string;
  objectives: string[];
}

export interface ApiError {
  error: {
    kind: string;
    message: string;
    details?: Record<string, unknown>;
  };
}