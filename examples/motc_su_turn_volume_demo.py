"""從 MOTC_SU 軌跡檔算出轉向流量的完整流程。

執行方式（專案根目錄）：
    .\\.venv\\Scripts\\python.exe examples/motc_su_turn_volume_demo.py [CSV路徑]

不給路徑時會找 data/ 底下的 *_CSV_SU.csv；找不到就自動產生一份很小的
示範檔（順便當成格式說明）。
"""

import sys
import tempfile
from pathlib import Path

from traffickit.formats import MOTC_SU_VEHICLE_CLASSES, read_motc_su_vehicles
from traffickit.volume import (
    DEFAULT_PCU_WEIGHTS,
    clockwise_movements,
    summarise_turn_volume,
)

# 路口分支代號，順時針從左側路口起算——MOTC_SU 的既定規則。
GATES = ["A", "B", "C", "D"]

# 車種分組。聯結車車身 g 刻意不放進任何一組：它與車頭 h 是同一輛車的兩列，
# 兩列都算會把一輛聯結車計成兩輛。留在組外，它會出現在 unassigned_classes。
VEHICLE_GROUPS = {
    "大型車": ["b", "t", "h"],
    "小型車": ["c"],
    "機車": ["m"],
}

SAMPLE_LINES = [
    # ID, 進入frame, 離開frame, 進入代號, 離開代號, 車種, 每個 frame 八個座標值
    "1,0,1,BI,AO,c," + ",".join(["10", "10", "20", "10", "20", "20", "10", "20"] * 2),
    "2,0,1,BI,CO,m," + ",".join(["30", "30", "40", "30", "40", "40", "30", "40"] * 2),
    "3,2,2,AI,CO,c," + ",".join(["50", "50", "60", "50", "60", "60", "50", "60"]),
    "4,2,2,X,CO,m," + ",".join(["70", "70", "80", "70", "80", "70", "70", "80"]),
]


def resolve_path() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    found = sorted(Path("data").glob("*_CSV_SU.csv"))
    if found:
        return found[0]
    sample = Path(tempfile.mkdtemp()) / "sample_CSV_SU.csv"
    sample.write_text("\n".join(SAMPLE_LINES) + "\n", encoding="utf-8")
    return sample


def main() -> None:
    path = resolve_path()
    print(f"讀取：{path.name}")

    # 1. 格式轉換層：只把檔案轉成表格，不做任何交通判定。
    vehicles = read_motc_su_vehicles(path)   # fps 預設 9.99
    incomplete = int((~vehicles["is_complete"]).sum())
    print(
        f"共 {len(vehicles)} 台車；不完整軌跡（代號 X）{incomplete} 台。"
    )
    print(vehicles.head(5).to_string(index=False))
    print()

    counts = vehicles["vehicle_class"].value_counts()
    print("車種組成：")
    for code, number in counts.items():
        print(f"  {code} {MOTC_SU_VEHICLE_CLASSES[code]}：{number}")
    print()

    # 2. 交通判定由呼叫端決定：官方定義說 X 要忽略，所以在這裡濾掉。
    complete = vehicles.query("is_complete")

    # 3. 轉向對照表。順時針編號可推導轉向類別，但**合法性要自己填**。
    #    這裡把迴轉全部設為不允許，只是示範；實際請依現場標誌標線調整。
    movements = clockwise_movements(
        GATES, disallowed=[(gate, gate) for gate in GATES]
    )

    result = summarise_turn_volume(
        complete,
        movements=movements,
        vehicle_groups=VEHICLE_GROUPS,
        pcu_weights=DEFAULT_PCU_WEIGHTS,
    )

    print("轉向流量（車輛數）：")
    table = result.by_turn.pivot_table(
        index="entry_gate",
        columns=["turn", "vehicle_group"],
        values="vehicle_count",
        aggfunc="sum",
        fill_value=0,
    )
    order = [
        (turn, group)
        for turn in result.turns
        for group in result.vehicle_groups
        if (turn, group) in table.columns
    ]
    print(table.loc[:, order].to_string())
    print()

    summary = result.summary
    print(f"納入統計車輛數：{summary.counted_vehicle_count}")
    print(
        f"未分組車輛數　：{summary.unassigned_vehicle_count}"
        f"（車種 {list(summary.unassigned_classes)}）"
    )
    print(f"總 PCU　　　　：{summary.total_pcu:.2f}")
    print(
        f"標記為不允許卻有車：{summary.disallowed_vehicle_count} 台"
        "（本例把迴轉全設為不允許，數字代表迴轉車次，不代表真的違規）"
    )


if __name__ == "__main__":
    main()
