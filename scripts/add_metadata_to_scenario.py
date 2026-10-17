"""一次性脚本：给 ``config/scenario.json`` 中的节点补 ``metadata.lng/lat``。

不修改其它任何字段（边 / 订单 / 时间窗 / 车辆 / 配送员保持原样）。

依据节点 ID 模式分配经纬度（北京 16 区示意）：

* W1 / W2 —— 朝阳 / 海淀
* T1..T4 —— 北京城区/近郊
* C1..C29 —— 12 中心+近郊区域循环 + 微抖动（确定性 SEED=42）

使用：``python scripts/add_metadata_to_scenario.py [--force]``
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIO_PATH = ROOT / "config" / "scenario.json"
SEED = 42

# 北京城区/近郊 12 区示意经纬度（中心位置）
DISTRICTS_LNG_LAT = [
    (116.42, 39.92),  # 东城
    (116.37, 39.91),  # 西城
    (116.49, 39.93),  # 朝阳
    (116.30, 39.97),  # 海淀
    (116.29, 39.86),  # 丰台
    (116.22, 39.91),  # 石景山
    (116.66, 39.91),  # 通州
    (116.65, 40.13),  # 顺义
    (116.23, 40.22),  # 昌平
    (116.33, 39.73),  # 大兴
    (115.97, 39.72),  # 房山
    (116.10, 39.94),  # 门头沟
]

# 仓库 / 中转固定位置
SPECIAL_LNG_LAT = {
    "W1": (116.485, 39.92),   # 朝阳
    "W2": (116.30, 39.96),    # 海淀
    "T1": (116.42, 39.88),    # 西城南
    "T2": (116.55, 39.86),    # 朝阳东
    "T3": (116.20, 39.78),    # 丰台西
    "T4": (116.66, 39.78),    # 通州西
}


def customer_lng_lat(idx: int, rng: random.Random) -> tuple[float, float]:
    """第 idx（1-based）个客户的经纬度。"""
    base_lng, base_lat = DISTRICTS_LNG_LAT[(idx - 1) % len(DISTRICTS_LNG_LAT)]
    return (
        round(base_lng + rng.uniform(-0.02, 0.02), 5),
        round(base_lat + rng.uniform(-0.02, 0.02), 5),
    )


def add_metadata(node: dict, rng: random.Random) -> None:
    nid = node["id"]
    if nid in SPECIAL_LNG_LAT:
        lng, lat = SPECIAL_LNG_LAT[nid]
    elif nid.startswith("C"):
        # 提取数字部分（id 形如 "C1" / "C29"）
        try:
            num = int(nid[1:])
        except ValueError:
            num = 1
        lng, lat = customer_lng_lat(num, rng)
    else:
        # 兜底：中心区
        lng, lat = 116.40, 39.90
    existing = node.get("metadata") or {}
    existing.setdefault("lng", lng)
    existing.setdefault("lat", lat)
    existing.setdefault("viz_source", "beijing_schematic")
    node["metadata"] = existing


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="覆盖已存在的 scenario.json")
    args = parser.parse_args()

    if SCENARIO_PATH.exists() and not args.force:
        print(f"{SCENARIO_PATH} 已存在，传 --force 以覆盖。")
        return

    with SCENARIO_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    rng = random.Random(SEED)
    for node in data["network"]["nodes"]:
        add_metadata(node, rng)

    with SCENARIO_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已写入 {SCENARIO_PATH}（仅添加 metadata，未改其它字段）")


if __name__ == "__main__":
    main()