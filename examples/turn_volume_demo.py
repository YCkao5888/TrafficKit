"""轉向流量統計的最小呼叫範例。

同時示範兩件屬於**呼叫端**的事：
1. 把專案設定裡的 TurnDirection 轉成 movements DataFrame。
2. 用回傳結果組出報表版面與百分比。

執行方式（專案根目錄）：
    Windows : .\\.venv\\Scripts\\python.exe examples/turn_volume_demo.py
    Linux   : ./.venv/bin/python examples/turn_volume_demo.py
"""

import pandas as pd

from traffickit.volume import DEFAULT_PCU_WEIGHTS, summarise_turn_volume

# 專案設定裡的原始格式（對應舊版 projectTurnConfig[zone].movements）。
ZONE_CONFIG = {
    "name": "測試路口",
    "movements": [
        {"from": "N", "to": "E",  "category": "left",     "is_allowed": True},
        {"from": "N", "to": "S",  "category": "straight", "is_allowed": True},
        {"from": "N", "to": "W",  "category": "right",    "is_allowed": True},
        {"from": "N", "to": "NE", "category": "right",    "is_allowed": True},
        {"from": "E", "to": "N",  "category": "right",    "is_allowed": True},
        {"from": "E", "to": "W",  "category": "straight", "is_allowed": True},
        {"from": "E", "to": "E",  "category": "u_turn",   "is_allowed": False},
    ],
}


def load_movements(zone_config: dict) -> pd.DataFrame:
    """把客戶端設定格式轉成套件契約的欄位名稱。這是整合端的責任。"""
    return pd.DataFrame([
        {
            "entry_gate": item["from"],
            "exit_gate": item["to"],
            "turn": item["category"],
            "is_allowed": item["is_allowed"],
        }
        for item in zone_config["movements"]
    ])


def make_vehicles() -> pd.DataFrame:
    """一列一台車的通過紀錄。V7 是行人，未列入車種分組。"""
    return pd.DataFrame(
        [
            ("V1", "N", "S",  "c"),
            ("V2", "N", "S",  "c"),
            ("V3", "N", "S",  "m"),
            ("V4", "N", "E",  "c"),
            ("V5", "E", "W",  "m"),
            ("V6", "E", "E",  "m"),
            ("V7", "N", "S",  "p"),
            ("V8", "N", "NE", "c"),
        ],
        columns=["vehicle_id", "entry_gate", "exit_gate", "vehicle_class"],
    )


def build_report(result) -> pd.DataFrame:
    """把 by_turn 轉成舊版報表版面：進入方向 × (轉向 × 分組)。"""
    table = result.by_turn.pivot_table(
        index="entry_gate",
        columns=["turn", "vehicle_group"],
        values="vehicle_count",
        aggfunc="sum",
        fill_value=0,
    )
    # 還原套件給的順序，pivot_table 會自行字典排序。
    order = [
        (turn, group)
        for turn in result.turns
        for group in result.vehicle_groups
        if (turn, group) in table.columns
    ]
    return table.loc[:, order]


def main() -> None:
    movements = load_movements(ZONE_CONFIG)
    vehicles = make_vehicles()

    vehicle_groups = {"小型車": ["c"], "機車": ["m"]}
    pcu_weights = {name: DEFAULT_PCU_WEIGHTS[name] for name in vehicle_groups}

    result = summarise_turn_volume(
        vehicles,
        movements=movements,
        vehicle_groups=vehicle_groups,
        pcu_weights=pcu_weights,
    )

    print("最細粒度（進入 × 駛出 × 轉向 × 分組）：")
    print(result.movements.to_string(index=False))
    print()
    print("報表彙整（進入 × 轉向 × 分組）：")
    print(result.by_turn.to_string(index=False))
    print()

    summary = result.summary
    print(f"輸入車輛數　　：{summary.input_vehicle_count}")
    print(f"納入統計車輛數：{summary.counted_vehicle_count}")
    print(
        f"未分組車輛數　：{summary.unassigned_vehicle_count}"
        f"（車種 {list(summary.unassigned_classes)}）"
    )
    print(f"違規轉向車輛數：{summary.disallowed_vehicle_count}")
    print(f"總 PCU　　　　：{summary.total_pcu:.2f}")
    print()

    # 版面與百分比屬於呼叫端；套件只回傳車輛數與 PCU。
    print("報表版面（車輛數）：")
    report = build_report(result)
    print(report.to_string())
    print()
    print("各進入方向的轉向佔比（%）：")
    entry_total = report.sum(axis=1)
    percent = report.div(entry_total.replace(0, pd.NA), axis=0) * 100
    print(percent.round(1).to_string())
    print()

    # 合法但沒有車的轉向，與不允許的轉向，兩者可以分開。
    empty_allowed = result.movements.query(
        "is_allowed and vehicle_count == 0"
    )[["entry_gate", "exit_gate", "turn", "vehicle_group"]]
    print(f"合法但本次 0 台的組合共 {len(empty_allowed)} 筆，例如：")
    print(empty_allowed.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
