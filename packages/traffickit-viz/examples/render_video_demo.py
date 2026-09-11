"""把軌跡疊到影片上輸出，示範完整的流程。

執行方式（專案根目錄）：
    .\\.venv\\Scripts\\python.exe packages/traffickit-viz/examples/render_video_demo.py
    .\\.venv\\Scripts\\python.exe packages/traffickit-viz/examples/render_video_demo.py 影片 軌跡檔

不給參數時會自己合成一小段影片與對應的軌跡：兩台車橫越畫面，軌跡刻意
**每 3 格才取樣一次**，用來示範 `resample_tracks` 補中間影格的效果。
合成出來的影片可以直接打開看，框應該穩穩貼在移動的方塊上。

給參數時，軌跡檔要是 MOTC_SU 格式，且其 frame 編號要對得上影片；
對不上時用 --frame-offset 那類的整體平移（這裡用 FRAME_OFFSET 常數）。
"""

import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from traffickit.formats import read_motc_su_tracks, read_motc_su_vehicles

from traffickit_viz import (
    BoxStyle,
    add_headings,
    assign_colors,
    frame_span,
    probe_video,
    render_video,
    resample_tracks,
)

FRAME_OFFSET = 0          # 軌跡與影片不同步時的整體平移
SAMPLE_FRAMES = 60
SAMPLE_SIZE = (320, 240)
SAMPLE_FPS = 10.0
SAMPLE_STEP = 3           # 合成軌跡每幾格取樣一次


def synthesise(directory: Path) -> tuple[Path, pd.DataFrame]:
    """造一段影片與完全對得上的軌跡，讓輸出結果可以目視檢查。"""
    width, height = SAMPLE_SIZE
    path = directory / "synthetic.avi"
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), SAMPLE_FPS, (width, height)
    )
    if not writer.isOpened():
        raise RuntimeError("無法建立合成影片，請確認 OpenCV 安裝正常")

    # 兩台「車」：一台往右、一台往左，尺寸不同。
    movers = [
        {"vehicle_id": "1", "size": (40, 24), "y": 70,
         "x0": 10.0, "dx": 4.0, "class": "c"},
        {"vehicle_id": "2", "size": (24, 16), "y": 150,
         "x0": float(width - 40), "dx": -3.0, "class": "m"},
    ]

    rows = []
    for frame in range(SAMPLE_FRAMES):
        image = np.full((height, width, 3), 40, dtype=np.uint8)
        cv2.line(image, (0, 110), (width, 110), (70, 70, 70), 2)   # 假的車道線
        for mover in movers:
            box_width, box_height = mover["size"]
            x = mover["x0"] + mover["dx"] * frame
            y = mover["y"]
            cv2.rectangle(
                image,
                (int(x), int(y)),
                (int(x + box_width), int(y + box_height)),
                (200, 200, 200), thickness=-1,
            )
            # 軌跡刻意比影片稀疏，之後靠 resample_tracks 補回來。
            if frame % SAMPLE_STEP == 0:
                # 車頭在行進方向那一側；角點順序與 traffickit.formats 相同：
                # 車頭兩角在前，順時針。
                if mover["dx"] > 0:
                    corners = [(x + box_width, y), (x + box_width, y + box_height),
                               (x, y + box_height), (x, y)]
                else:
                    corners = [(x, y + box_height), (x, y),
                               (x + box_width, y), (x + box_width, y + box_height)]
                rows.append({
                    "vehicle_id": mover["vehicle_id"],
                    "frame": frame,
                    "vehicle_class": mover["class"],
                    **{f"{axis}{index}_px": value
                       for index, point in enumerate(corners, start=1)
                       for axis, value in zip(("x", "y"), point)},
                })
        writer.write(image)
    writer.release()
    return path, pd.DataFrame(rows)


def load_real(video_path: Path, csv_path: Path) -> pd.DataFrame:
    tracks = read_motc_su_tracks(csv_path)
    vehicles = read_motc_su_vehicles(csv_path)
    return tracks.merge(
        vehicles[["vehicle_id", "vehicle_class"]], on="vehicle_id", how="left"
    )


def main() -> None:
    workspace = Path(tempfile.mkdtemp())

    if len(sys.argv) > 2:
        video_path, tracks = Path(sys.argv[1]), load_real(
            Path(sys.argv[1]), Path(sys.argv[2])
        )
        print(f"影片：{video_path.name}")
    else:
        video_path, tracks = synthesise(workspace)
        print(f"沒有給參數，改用合成影片：{video_path.name}")

    info = probe_video(video_path)
    print(f"{info.frame_count} 格、{info.fps:.2f} fps、{info.width}x{info.height}")
    print(f"軌跡取樣列數：{len(tracks)}")

    # 1. 補上影片有、軌跡沒有的影格。不補的話框會一閃一閃。
    #    max_gap 讓被遮蔽或已離開的車不要被連成一條直線。
    span = frame_span(tracks, pad=0)
    if span is None:
        raise SystemExit("軌跡是空的，沒有東西可以畫")
    start, end = span[0], min(span[1], info.frame_count - 1)
    dense = resample_tracks(tracks, range(start, end + 1), max_gap=30)
    print(f"補到每一格後：{len(dense)} 列（影格 {start}–{end}）")

    # 2. 車頭方向要沿時間平滑，否則箭頭一直晃。順序是先補格再算方向。
    dense = add_headings(dense, window=5)

    # 3. 配色對整段影片一次算好。
    style = BoxStyle(
        assign_colors(sorted(dense["vehicle_id"].unique())),
        label="both",
        front="arrow",
        fill_alpha=0.12,
        thickness=2,
    )

    # 4. 輸出。progress 只是回呼，本套件不會自己 print。
    def progress(done: int, total: int) -> None:
        if done % 20 == 0 or done == total:
            print(f"  已寫入 {done}/{total} 格", end="\r")

    result = render_video(
        video_path,
        dense,
        style=style,
        output_path=workspace / "annotated",
        start_frame=start,
        end_frame=end,
        frame_offset=FRAME_OFFSET,
        codec="MJPG",
        show_frame_number=True,
        progress=progress,
    )
    print()
    print(f"輸出：{result.output_path}")
    print(
        f"影格 {result.start_frame}–{result.end_frame}，"
        f"寫入 {result.frames_written} 格，完成={result.is_complete}"
    )
    print(f"畫到的車輛：{len(result.drawn_vehicle_ids)} 台")
    if result.missing_vehicle_ids:
        print(f"這段時間沒有軌跡的車輛：{result.missing_vehicle_ids}")


if __name__ == "__main__":
    main()
