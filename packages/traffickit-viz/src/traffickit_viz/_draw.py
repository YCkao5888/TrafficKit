"""把車身框畫到影像上。

這一層只負責畫，不負責決定要畫誰、也不負責讀寫影片檔。
"""

from __future__ import annotations

import cv2
import numpy as np
import pandas as pd

from ._heading import CORNER_COLUMNS
from ._style import BoxStyle

_FONT = cv2.FONT_HERSHEY_SIMPLEX


def draw_boxes(
    image: np.ndarray,
    boxes: pd.DataFrame,
    *,
    style: BoxStyle,
) -> np.ndarray:
    """在一張影像上畫出這個影格所有車輛的框。

    Parameters
    ----------
    image : numpy.ndarray
        BGR 影像，形狀 ``(高, 寬, 3)``、dtype 為 ``uint8``，
        也就是 :func:`cv2.VideoCapture.read` 給的東西。
    boxes : pandas.DataFrame
        **這一個影格**要畫的車輛，一列一台。必要欄位：``vehicle_id``
        與四角點 ``x1_px``…``y4_px``。依 ``style`` 另外可能需要
        ``vehicle_class``（標籤含車種時）或 ``heading_x``／``heading_y``
        （車頭標示含箭頭時）。
    style : BoxStyle
        外觀設定，含涵蓋所有車輛的顏色表。

    Returns
    -------
    numpy.ndarray
        就是傳進來的那個 ``image``。

    Raises
    ------
    TypeError
        image 不是 ndarray，或 boxes 不是 DataFrame。
    ValueError
        影像形狀或 dtype 不對、缺必要欄位、座標含非有限值，
        或顏色表沒有涵蓋某台車。

    Notes
    -----
    **本函式就地修改 ``image``**，這是整個套件唯一會修改輸入的地方。
    核心套件的慣例是不修改輸入，但那是給表格用的：影片一秒有數十張
    4K 影像，每張都複製一份只為了遵守慣例，會讓輸出慢到不能用。
    需要保留原圖時請自己傳 ``image.copy()``。

    畫超出畫面的框**不是錯誤**：車輛進出畫面邊緣時本來就會有一部分在外面，
    露出的部分照畫。**完全**在畫面外的車則整台跳過——標籤的位置會夾進畫面內
    以免靠邊的車標籤被裁掉，若不跳過，畫面邊緣會浮著一個沒有框的標籤。

    繪製順序是：填色 → 外框 → 標籤 → 車頭標示。車頭標示畫在最後，
    因此在框線與標籤之上。
    """
    _check_image(image)
    _check_boxes(boxes, style)

    if boxes.empty:
        return image

    corners = boxes.loc[:, list(CORNER_COLUMNS)].to_numpy(dtype="float64")
    if not np.isfinite(corners).all():
        raise ValueError("boxes 的角點座標含有非有限值（NaN 或 inf）")
    corners = corners.reshape(-1, 4, 2)

    vehicle_ids = boxes["vehicle_id"].to_numpy()
    classes = (
        boxes["vehicle_class"].to_numpy()
        if "vehicle_class" in boxes.columns else None
    )
    headings = (
        boxes.loc[:, ["heading_x", "heading_y"]].to_numpy(dtype="float64")
        if style.needs_heading else None
    )

    height, width = image.shape[:2]
    for row, vehicle_id in enumerate(vehicle_ids):
        color = style.color_for(vehicle_id)
        if not _intersects_image(corners[row], height, width):
            # 完全在畫面外的車整台跳過。OpenCV 本來就會裁掉框線，但標籤的
            # 位置是夾進畫面內的，不跳過的話畫面邊緣會浮著一個沒有框的標籤。
            continue
        vehicle_class = classes[row] if classes is not None else None
        _draw_one(
            image,
            corners[row],
            color=color,
            text=_label_text(vehicle_id, vehicle_class, style.label),
            style=style,
        )
        if style.front != "none":
            _draw_front(
                image,
                corners[row],
                heading=headings[row] if headings is not None else None,
                style=style,
            )
    return image


def _intersects_image(corners, height: int, width: int) -> bool:
    """這個框有沒有任何一部分落在畫面內。"""
    low = corners.min(axis=0)
    high = corners.max(axis=0)
    return bool(
        high[0] >= 0 and high[1] >= 0 and low[0] <= width - 1 and low[1] <= height - 1
    )


def _draw_one(image, corners, *, color, text, style: BoxStyle) -> None:
    points = np.rint(corners).astype(np.int32).reshape(-1, 1, 2)

    if style.fill_alpha > 0:
        overlay = image.copy()
        cv2.fillPoly(overlay, [points], color)
        cv2.addWeighted(
            overlay, style.fill_alpha, image, 1 - style.fill_alpha, 0, dst=image
        )

    cv2.polylines(
        image, [points], isClosed=True, color=color,
        thickness=style.thickness, lineType=cv2.LINE_AA,
    )

    if text:
        _draw_label(image, corners, color=color, text=text, style=style)


def _draw_label(image, corners, *, color, text, style: BoxStyle) -> None:
    weight = max(1, style.thickness - 1)
    (width, height), baseline = cv2.getTextSize(
        text, _FONT, style.font_scale, weight
    )

    # 貼在框的最上緣，並夾在畫面內，否則靠邊的車標籤會被裁掉看不到。
    anchor = corners[int(np.argmin(corners[:, 1]))]
    x = int(min(max(anchor[0], 0), max(0, image.shape[1] - width - 4)))
    y = int(max(anchor[1] - 6, height + 4))

    cv2.rectangle(
        image, (x, y - height - baseline // 2), (x + width + 4, y + baseline),
        color, thickness=-1,
    )
    cv2.putText(
        image, text, (x + 2, y), _FONT, style.font_scale,
        (0, 0, 0), weight, cv2.LINE_AA,
    )


def _draw_front(image, corners, *, heading, style: BoxStyle) -> None:
    if style.front in ("edge", "both"):
        start = tuple(np.rint(corners[0]).astype(int))
        end = tuple(np.rint(corners[1]).astype(int))
        cv2.line(
            image, start, end, style.front_color,
            style.thickness + 1, cv2.LINE_AA,
        )

    if style.front in ("arrow", "both"):
        if heading is None or not np.isfinite(heading).all():
            return  # 這一格算不出方向，不畫箭頭；別畫一個指向任意方向的
        center = corners.mean(axis=0)
        body = np.linalg.norm(corners[:2].mean(axis=0) - corners[2:].mean(axis=0))
        # 箭頭長度取車身長的一半，尖端大約落在車頭邊上；車身太短時給個下限，
        # 否則機車與行人的箭頭會短到看不見。
        tip = center + np.asarray(heading) * max(body * 0.5, 6.0)
        cv2.arrowedLine(
            image,
            tuple(np.rint(center).astype(int)),
            tuple(np.rint(tip).astype(int)),
            style.front_color,
            max(1, style.thickness),
            cv2.LINE_AA,
            tipLength=0.35,
        )


def _label_text(vehicle_id, vehicle_class, mode: str) -> str:
    if mode == "none":
        return ""
    if mode == "id":
        return f"ID {vehicle_id}"
    if mode == "class":
        return str(vehicle_class) if vehicle_class else "-"
    return f"ID {vehicle_id} {vehicle_class or ''}".strip()


def _check_image(image) -> None:
    if not isinstance(image, np.ndarray):
        raise TypeError(f"image 必須是 numpy.ndarray，收到 {type(image).__name__}")
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(
            f"image 必須是 (高, 寬, 3) 的 BGR 影像，收到形狀 {image.shape}"
        )
    if image.dtype != np.uint8:
        raise ValueError(f"image 的 dtype 必須是 uint8，收到 {image.dtype}")


def _check_boxes(boxes, style: BoxStyle) -> None:
    if not isinstance(boxes, pd.DataFrame):
        raise TypeError(
            f"boxes 必須是 pandas.DataFrame，收到 {type(boxes).__name__}"
        )

    required = ["vehicle_id", *CORNER_COLUMNS]
    if style.needs_vehicle_class:
        required.append("vehicle_class")
    if style.needs_heading:
        required.extend(("heading_x", "heading_y"))

    missing = [name for name in required if name not in boxes.columns]
    if missing:
        raise ValueError(
            f"boxes 缺少必要欄位：{missing}"
            + ("（車頭標示含箭頭時需要，見 add_headings）"
               if style.needs_heading
               and {"heading_x", "heading_y"} & set(missing) else "")
        )
