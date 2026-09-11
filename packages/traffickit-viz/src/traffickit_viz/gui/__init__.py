"""TrafficKit 車輛標註的圖形介面（PySide6 / Qt 6）。

啟動方式：

.. code-block:: console

    traffickit-viz
    python -m traffickit_viz.gui

介面背後的狀態與計算集中在 :mod:`._session`，**完全不依賴 Qt**，
因此那一層可以直接寫測試；視窗只負責把動作轉成呼叫、把結果畫出來。

``traffickit_viz`` 本身不 import 這個子套件，所以只要繪製與影片輸出的
場合（後端、批次、CI）不會載入 Qt。
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """開啟視窗，回傳行程結束碼。"""
    from PySide6.QtWidgets import QApplication

    from ._window import MainWindow

    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName("TrafficKit 車輛標註")
    window = MainWindow()
    window.show()
    return app.exec()


__all__ = ["main"]
