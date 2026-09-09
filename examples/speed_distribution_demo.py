"""車速分布統計的最小呼叫範例。

執行方式（專案根目錄）：
    Windows : .\\.venv\\Scripts\\python.exe examples/speed_distribution_demo.py
    Linux   : ./.venv/bin/python examples/speed_distribution_demo.py
"""

import pandas as pd

from traffickit.speed import speed_bin_edges, summarise_speed_distribution

MPS_TO_KMH = 3.6


def make_tracks() -> pd.DataFrame:
    """教學用的四台車資料，速度單位為 m/s。"""
    return pd.DataFrame({
        "vehicle_id": ["A"] * 3 + ["B"] * 3 + ["C"] * 3 + ["D"] * 2,
        "time_s": [0.0, 1.0, 2.0] * 3 + [0.0, 1.0],
        "speed_smooth_mps": [
            8.0, 9.0, 10.0,
            9.0, 11.0, 12.0,
            11.0, 11.0, 9.0,
            0.5, 1.5,
        ],
    })


def main() -> None:
    tracks = make_tracks()
    edges = speed_bin_edges(width_mps=5.0, upper_mps=15.0)

    result = summarise_speed_distribution(
        tracks,
        bin_edges_mps=edges,
        statistic="mean",
    )

    print("分箱邊界 (m/s)：", edges)
    print()
    print("每車代表速度：")
    print(result.vehicle_speeds.to_string(index=False))
    print()
    print("分箱結果：")
    print(result.bins.to_string(index=False))
    print()
    print(f"移動門檻前車輛數：{result.input_vehicle_count}")
    print(f"納入統計車輛數　：{result.summary.vehicle_count}")
    print(f"落入分箱車輛數　：{result.binned_vehicle_count}")
    print(
        f"超出分箱範圍　　：低於 {result.below_range_count} 台、"
        f"高於 {result.above_range_count} 台"
    )
    print()
    summary = result.summary
    print(
        "整體統計 (m/s)："
        f" 平均 {summary.mean_mps:.3f}"
        f"、中位數 {summary.median_mps:.3f}"
        f"、P85 {summary.p85_mps:.3f}"
        f"、最大 {summary.max_mps:.3f}"
    )
    # 顯示單位換算屬於呼叫端的責任，核心函式一律使用 m/s。
    print(f"整體平均 (km/h)：{summary.mean_mps * MPS_TO_KMH:.2f}")

    # 只看有在移動的車：門檻 2 m/s（7.2 km/h）會整台排除慢速的 D。
    moving = summarise_speed_distribution(
        tracks,
        bin_edges_mps=edges,
        statistic="mean",
        moving_threshold_mps=2.0,
    )
    print()
    print(
        "套用 2 m/s 移動門檻後："
        f" {moving.input_vehicle_count} 台中保留 "
        f"{moving.summary.vehicle_count} 台，"
        f"各箱車輛數 {moving.bins['vehicle_count'].tolist()}"
    )


if __name__ == "__main__":
    main()
