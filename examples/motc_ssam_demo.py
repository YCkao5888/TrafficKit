"""從 MOTC_SSAM 軌跡檔算出轉向流量，並示範公尺座標的用法。

執行方式（專案根目錄）：
    .\\.venv\\Scripts\\python.exe examples/motc_ssam_demo.py [CSV路徑]

不給路徑時會找 data/ 底下的 *_CSV_SSAM.csv；找不到就自動產生一份很小的
示範檔（順便當成格式說明）。

SSAM 版與 Pixel Frame 版（見 motc_su_turn_volume_demo.py）是同一批分析
成果的兩種輸出：路口代號與車種代號相同，差別在 SSAM 版一列一台車一個
時間步、座標是公尺，車身以車頭中點、車尾中點與車寬表示。
"""

import sys
import tempfile
from pathlib import Path

from traffickit.formats import (
    MOTC_SU_VEHICLE_CLASSES,
    read_motc_ssam_tracks,
    read_motc_ssam_vehicles,
)
from traffickit.volume import (
    DEFAULT_PCU_WEIGHTS,
    clockwise_movements,
    summarise_turn_volume,
)

# 路口分支代號，順時針從左側路口起算——MOTC 空拍軌跡格式的既定規則。
GATES = ["A", "B", "C", "D"]

VEHICLE_GROUPS = {
    "大型車": ["b", "t", "h"],
    "小型車": ["c"],
    "機車": ["m"],
}

SAMPLE_LINES = [
    "FORMAT,SSAM Trajectory",
    "DIMENSIONS,Scale,1,MaxX,1000,MaxY,1000",
    "Timestep,Vehicle ID,Link ID,Lane ID,Front X,Front Y,Rear X,Rear Y,"
    "Length,Width,Speed,class,intersection in,intersection out",
    # 每個時間步前有一列只有 Timestep 的分隔列，讀取器會略過。
    "0.0",
    "0.0,1,1,1,10.0,5.0,6.0,5.0,4.0,1.8,10.0,c,BI,AO",
    "0.0,2,1,1,10.0,20.0,8.0,20.0,2.0,0.8,8.0,m,BI,CO",
    "0.1",
    "0.1,1,1,1,11.0,5.0,7.0,5.0,4.0,1.8,10.0,c,BI,AO",
    "0.1,2,1,1,10.8,20.0,8.8,20.0,2.0,0.8,8.0,m,BI,CO",
    "0.1,3,1,1,40.0,30.0,36.0,30.0,4.0,1.8,9.0,c,AI,CO",
    # 行人走行穿線：代號是兩個路口字母，不是 AI／AO。
    "0.1,4,1,1,25.0,25.0,24.5,25.0,0.5,0.5,1.2,p,AB,AB",
    # 不完整軌跡。
    "0.1,5,1,1,60.0,60.0,56.0,60.0,4.0,1.8,7.0,m,X,CO",
]


def resolve_path() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    found = sorted(Path("data").glob("*_CSV_SSAM.csv"))
    if found:
        return found[0]
    sample = Path(tempfile.mkdtemp()) / "sample_CSV_SSAM.csv"
    sample.write_text("\n".join(SAMPLE_LINES) + "\n", encoding="utf-8")
    return sample


def main() -> None:
    path = resolve_path()
    print(f"讀取：{path.name}")

    # 1. 格式轉換層：只把檔案轉成表格，不做任何交通判定。
    vehicles = read_motc_ssam_vehicles(path)
    incomplete = int((~vehicles["is_complete"]).sum())
    crosswalk = int(vehicles["is_crosswalk"].sum())
    print(
        f"共 {len(vehicles)} 台車；不完整軌跡（代號 X）{incomplete} 台、"
        f"行穿線（例如 AB）{crosswalk} 台。"
    )
    print(vehicles.head(5).to_string(index=False))
    print()

    counts = vehicles["vehicle_class"].value_counts()
    print("車種組成：")
    for code, number in counts.items():
        print(f"  {code} {MOTC_SU_VEHICLE_CLASSES[code]}：{number}")
    print()

    # 2. 逐時間步的位置。座標是公尺，直接就能算距離，不需要比例尺。
    tracks = read_motc_ssam_tracks(path)
    print(f"軌跡列數：{len(tracks)}（一列 = 一台車一個時間步）")
    moved = (
        tracks.sort_values(["vehicle_id", "time_s"])
        .groupby("vehicle_id")[["center_x_m", "center_y_m"]]
        .agg(lambda values: values.iloc[-1] - values.iloc[0])
    )
    span = (moved["center_x_m"] ** 2 + moved["center_y_m"] ** 2) ** 0.5
    print(
        f"首末位移（公尺）：中位數 {span.median():.1f}、"
        f"最大 {span.max():.1f}；位移不到 1 公尺的有 {int((span < 1).sum())} 台"
    )
    print("（座標單位就是公尺，不需要比例尺就能算距離。"
          "位移極小的多半是停等或誤偵測，本套件不替你濾掉。）")
    print()

    # 3. 交通判定由呼叫端決定：X 與行穿線都不是路口代號，在這裡濾掉。
    usable = vehicles.query("is_complete and not is_crosswalk")

    movements = clockwise_movements(
        GATES, disallowed=[(gate, gate) for gate in GATES]
    )
    result = summarise_turn_volume(
        usable,
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
    print(f"總 PCU　　　　：{summary.total_pcu:.2f}")


if __name__ == "__main__":
    main()
