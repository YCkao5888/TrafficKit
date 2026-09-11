"""traffickit-viz 的骨架測試。

套件還沒有公開函式，所以這裡驗的是**結構**：裝得起來、相依方向正確、
公開名單與實際匯出一致。功能搬進來之後，每一項再各自加規格測試。

這份測試不在核心的 `tests/` 底下，因此 `unittest discover -s tests` 不會
跑到——沒裝 OpenCV 的環境仍然可以跑核心測試。
"""

import re
import unittest
from pathlib import Path

import traffickit_viz

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _dependency_names(key: str) -> list[str]:
    """讀 pyproject 裡某個相依清單，回傳套件名稱（不含版本條件）。

    不用 tomllib：它是 3.11 才進標準庫，而本專案支援到 3.10。
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    block = text.split(f"\n{key} = [", 1)[1].split("]", 1)[0]
    names = []
    for line in block.splitlines():
        line = line.strip().strip(",").strip('"')
        if not line or line.startswith("#"):
            continue
        names.append(re.split(r"[<>=!~\[ ]", line, maxsplit=1)[0])
    return names


class TestPackageSkeleton(unittest.TestCase):
    def test_package_imports_and_declares_a_version(self):
        self.assertRegex(traffickit_viz.__version__, r"^\d+\.\d+\.\d+")

    def test_public_names_actually_exist(self):
        # __all__ 目前是空的；有東西時這一條會擋下「登記了卻沒匯出」。
        missing = [
            name for name in traffickit_viz.__all__
            if not hasattr(traffickit_viz, name)
        ]
        self.assertEqual(missing, [], "__all__ 列出的名稱必須真的匯出")

    def test_the_core_package_is_available(self):
        # 相依方向：這個套件可以用核心，反過來不行（核心那邊有對應的測試）。
        from traffickit.formats import read_motc_su_vehicles

        self.assertTrue(callable(read_motc_su_vehicles))


class TestDependencies(unittest.TestCase):
    def test_opencv_is_installed_and_importable(self):
        # 把 OpenCV 隔離在這個套件是整個拆分的目的；裝不起來就沒有意義了。
        import cv2

        self.assertTrue(hasattr(cv2, "VideoCapture"))

    def test_required_dependencies_are_the_expected_three(self):
        self.assertEqual(
            sorted(_dependency_names("dependencies")),
            ["numpy", "opencv-python-headless", "traffickit"],
        )

    def test_progress_bar_and_image_helpers_stay_optional(self):
        # tqdm 只用在命令列進度條、Pillow 只用在預覽的加速路徑，
        # 兩者缺了都要還能跑，所以不可以出現在必要相依裡。
        required = sorted(_dependency_names("dependencies"))
        optional = sorted(_dependency_names("extras"))
        self.assertEqual(optional, ["Pillow", "tqdm"])
        for name in optional:
            self.assertNotIn(name, required)


if __name__ == "__main__":
    unittest.main()
