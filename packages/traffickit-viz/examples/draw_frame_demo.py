"""把一個影格的車輛框畫出來並存成 PNG。

執行方式（專案根目錄）：
    .\\.venv\\Scripts\\python.exe packages/traffickit-viz/examples/draw_frame_demo.py [CSV路徑]

不給路徑時會找 data/ 底下的 *_CSV_SU.csv；找不到就自動產生一份很小的
示範檔。輸出寫到暫存目錄，路徑會印出來。

這支範例示範的是**接縫**：軌跡由核心的 traffickit.formats 讀，
畫面由 traffickit_viz 畫，兩者之間傳的就是一般的 DataFrame。
真正要疊到影片上時，把這裡的空白影像換成 cv2 解出來的影格即可。
"""

import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from traffickit.formats import read_motc_su_tracks, read_motc_su_vehicles

from traffickit_viz import BoxStyle, add_headings, assign_colors, draw_boxes

SAMPLE_LINES = [
    # ID, 進入frame, 離開frame, 進入代號, 離開代號, 車種, 每個 frame 八個座標值
    "1,0,2,BI,AO,c,"
    + "60,40,60,80,140,80,140,40,"
    + "80,40,80,80,160,80,160,40,"
    + "100,40,100,80,180,80,180,40",
    "2,0,2,AI,CO,m,"
    + "200,150,200,180,250,180,250,150,"
    + "210,150,210,180,260,180,260,150,"
    + "220,150,220,180,270,180,270,150",
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

    # 1. 核心負責讀檔，回傳一般的 DataFrame。
    tracks = read_motc_su_tracks(path)
    print(f"軌跡列數：{len(tracks)}")

    # 逐影格的表沒有車種（那是整台車的屬性，在 *_vehicles 那張表），
    # 標籤要顯示車種就自己接上來。
    vehicles = read_motc_su_vehicles(path)
    tracks = tracks.merge(
        vehicles[["vehicle_id", "vehicle_class"]], on="vehicle_id", how="left"
    )

    # 2. 車頭方向要沿時間平滑，否則箭頭會一直晃。這是逐車計算，
    #    所以整份算一次就好，不要每個影格重算。
    tracks = add_headings(tracks, window=5)

    # 3. 挑一個有車的影格。
    busiest = tracks["frame"].value_counts().idxmax()
    frame_boxes = tracks.query("frame == @busiest")
    print(f"畫第 {busiest} 格，共 {len(frame_boxes)} 台車")

    # 4. 配色對整段影片一次算好。若改成每個影格依當下出現的車輛配色，
    #    同一台車的顏色會隨著別的車進出畫面而改變，畫面就會閃爍。
    style = BoxStyle(
        assign_colors(sorted(tracks["vehicle_id"].unique())),
        label="both",
        front="arrow",
        fill_alpha=0.15,
    )

    # 5. 真正要用時這裡是 cv2 解出來的影格；沒有影片就先畫在空白底上。
    width = int(np.ceil(tracks[["x1_px", "x2_px", "x3_px", "x4_px"]].max().max())) + 20
    height = int(np.ceil(tracks[["y1_px", "y2_px", "y3_px", "y4_px"]].max().max())) + 20
    canvas = np.zeros((height, width, 3), dtype=np.uint8)

    draw_boxes(canvas, frame_boxes, style=style)   # canvas 就地被改

    output = Path(tempfile.mkdtemp()) / f"frame_{busiest}.png"
    cv2.imwrite(str(output), canvas)
    painted = int(np.count_nonzero(canvas.any(axis=2)))
    print(f"畫面尺寸：{width}x{height}，上色像素 {painted}")
    print(f"輸出：{output}")

    unknown = int(frame_boxes["heading_x"].isna().sum())
    if unknown:
        print(f"注意：{unknown} 台車這一格算不出車頭方向，箭頭略過不畫。")


if __name__ == "__main__":
    main()
