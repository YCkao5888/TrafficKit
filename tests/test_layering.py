"""核心套件的相依邊界。

`traffickit` 只依賴 pandas 與 numpy，所以後端服務、CI 與 Jupyter 都裝得動。
視覺化那一層（`traffickit_viz`）需要 OpenCV，安裝後數百 MB。

這條線一旦反過來——核心 import 了視覺化套件、或核心多了一個重量級相依——
**所有功能測試仍然會通過**，問題要到別人安裝時才會發現。所以由這一支守。
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "src" / "traffickit"
PYPROJECT = ROOT / "pyproject.toml"

#: 這些一旦出現在核心，就代表分層被打破了。
FORBIDDEN_MODULES = ("traffickit_viz", "cv2", "tkinter", "PIL", "matplotlib")

_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(?P<module>[A-Za-z_][\w.]*)", re.MULTILINE
)


def core_modules() -> list[Path]:
    return sorted(CORE.rglob("*.py"))


def imported_roots(source: str) -> set[str]:
    """回傳這份原始碼 import 的最上層模組名稱。"""
    return {
        match.group("module").split(".", 1)[0]
        for match in _IMPORT.finditer(source)
    }


def declared_dependencies() -> list[str]:
    """讀 pyproject 的 [project] dependencies，回傳套件名稱（不含版本條件）。

    不用 tomllib：它是 3.11 才進標準庫，而本專案支援到 3.10。
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    block = text.split("\ndependencies = [", 1)[1].split("]", 1)[0]
    names = []
    for line in block.splitlines():
        line = line.strip().strip(",").strip('"')
        if not line or line.startswith("#"):
            continue
        names.append(re.split(r"[<>=!~\[ ]", line, maxsplit=1)[0])
    return names


class TestCoreDependencyBoundary(unittest.TestCase):
    def test_core_has_modules_to_check(self):
        # 避免路徑寫錯時，下面的測試全部變成掃 0 個檔案而永遠通過。
        self.assertGreater(len(core_modules()), 5)

    def test_core_never_imports_the_visualisation_layer(self):
        offenders = []
        for path in core_modules():
            roots = imported_roots(path.read_text(encoding="utf-8"))
            for name in FORBIDDEN_MODULES:
                if name in roots:
                    offenders.append(f"{path.relative_to(ROOT)} → {name}")
        self.assertEqual(
            offenders,
            [],
            "核心不可以依賴視覺化或 GUI 套件；這些屬於 traffickit_viz",
        )

    def test_core_declares_only_pandas_and_numpy(self):
        self.assertEqual(sorted(declared_dependencies()), ["numpy", "pandas"])

    def test_viz_package_is_not_bundled_into_the_core_distribution(self):
        # 根目錄的 pyproject 只從 src/ 找套件，packages/ 底下的東西是另一個
        # distribution。設定被改成掃整個專案的話，OpenCV 會跟著跑進核心。
        text = PYPROJECT.read_text(encoding="utf-8")
        self.assertIn('where = ["src"]', text)
        self.assertIn('include = ["traffickit*"]', text)


if __name__ == "__main__":
    unittest.main()
