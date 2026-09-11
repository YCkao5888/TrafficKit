"""確保 README 的程式碼真的能跑，而且輸出與文件寫的一致。

README 的範例是多數人接觸這個套件的第一件事，壞掉了沒人會發現——
實際發生過三次：函式呼叫裡留著 `...`、範例沒有 print 所以跑起來沒輸出、
以及少 import 一個常數導致 NameError。

本測試把 README 裡每個 ```python 區塊抽出來執行；若該區塊後面緊接著一個
沒有語言標記的 ``` 區塊，就把它當成預期的標準輸出逐字比對。
要更新輸出時請實際跑一次再貼上，不要用手改。
"""

import io
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"

# 需要本機 MOTC 軌跡檔的區塊無法在這裡執行，
# 該路徑改由 examples/ 底下的示範程式與 tests/test_motc_*.py 覆蓋。
_NEEDS_LOCAL_FILE = ("_CSV_SU.csv", "_CSV_SSAM.csv")

_FENCE = re.compile(r"^```([^\n]*)\n(.*?)^```", re.DOTALL | re.MULTILINE)


def fenced_blocks(text: str) -> list[tuple[str, str]]:
    """回傳 (語言標記, 內容) 的清單，順序與文件相同。"""
    return [
        (match.group(1).strip(), match.group(2))
        for match in _FENCE.finditer(text)
    ]


def python_examples(text: str) -> list[tuple[int, str, str | None]]:
    """挑出 python 區塊，並附上緊接其後、沒有語言標記的預期輸出。"""
    blocks = fenced_blocks(text)
    examples = []
    for index, (language, body) in enumerate(blocks):
        if language != "python":
            continue
        expected = None
        if index + 1 < len(blocks) and blocks[index + 1][0] == "":
            expected = blocks[index + 1][1]
        examples.append((index, body, expected))
    return examples


def normalise(text: str) -> str:
    """比對前去掉每行尾端空白與整體前後空行。"""
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


class TestReadmeExamples(unittest.TestCase):
    def setUp(self):
        self.text = README.read_text(encoding="utf-8")
        self.examples = python_examples(self.text)

    def test_readme_has_examples_to_check(self):
        # 避免抽取邏輯壞掉時測試變成永遠通過。
        self.assertGreaterEqual(len(self.examples), 3)

    def test_every_example_runs_and_prints_what_readme_claims(self):
        checked_output = 0
        for index, source, expected in self.examples:
            if any(marker in source for marker in _NEEDS_LOCAL_FILE):
                continue
            with self.subTest(block=index):
                captured = io.StringIO()
                namespace: dict = {"__name__": "__readme__"}
                with redirect_stdout(captured):
                    exec(compile(source, f"README.md#block{index}", "exec"), namespace)
                if expected is not None:
                    self.assertEqual(
                        normalise(captured.getvalue()),
                        normalise(expected),
                        "README 標示的輸出與實際執行結果不同",
                    )
                    checked_output += 1
        self.assertGreaterEqual(checked_output, 2)

    def test_examples_are_complete_snippets(self):
        """省略號會讓複製貼上的人拿到不能跑的程式碼。"""
        for index, source, _ in self.examples:
            with self.subTest(block=index):
                self.assertNotIn("...", source)

    def test_examples_import_what_they_use(self):
        """常見的漏 import：用了模組常數卻只 import 函式。"""
        names = ("DEFAULT_PCU_WEIGHTS", "DEFAULT_VEHICLE_GROUPS", "TURNS")
        for index, source, _ in self.examples:
            for name in names:
                if name in source:
                    with self.subTest(block=index, name=name):
                        imports = re.findall(
                            r"^from .+ import \(?(.+?)\)?$",
                            source,
                            re.MULTILINE | re.DOTALL,
                        )
                        self.assertTrue(
                            any(name in chunk for chunk in imports),
                            f"{name} 被使用但沒有 import",
                        )


if __name__ == "__main__":
    unittest.main()
