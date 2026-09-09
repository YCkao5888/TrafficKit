"""Sphinx 設定。

本目錄同時是文件原始碼與 Sphinx 的 source dir：
既有的 catalog.md、工作單等 Markdown 會一起收進網站。

本機建置（專案根目錄）：
    .\\.venv\\Scripts\\python.exe -m sphinx -b html -W --keep-going \
        -d docs/_build/doctrees docs docs/_build/html

版號：預設取已安裝的 traffickit 版本。CI 會用環境變數指定要建置成哪一版：
    DOCS_VERSION=latest   → 版本切換器顯示「latest」
    DOCS_VERSION=0.1.0    → 版本切換器顯示「0.1.0」
"""

import os
from importlib import metadata

project = "TrafficKit"
author = "TrafficKit 開發團隊"
copyright = "2026, " + author

release = metadata.version("traffickit")
version = release

# 網站上這一份文件對應的版本標籤，決定版本切換器要把哪一項標成目前所在位置。
docs_version = os.environ.get("DOCS_VERSION", "latest")

# GitHub Pages 的站台根目錄。改 repo 名稱或改用自訂網域時要一起改。
site_root = os.environ.get(
    "DOCS_SITE_ROOT", "https://yckao5888.github.io/TrafficKit"
)

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "numpydoc",
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "README.md"]
language = "zh_TW"

# -- autodoc / autosummary ---------------------------------------------------

autosummary_generate = True
autodoc_typehints = "none"          # 型別已寫在 numpydoc 的 Parameters 表裡
autodoc_member_order = "bysource"
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": False,
}

# numpydoc 會自己列出 class 成員，關掉以免與 autosummary 重複。
numpydoc_show_class_members = False
numpydoc_class_members_toctree = False
# 契約寫在 docstring 裡，缺段落應該被看見而不是靜靜通過。
numpydoc_validation_checks = set()

# -- MyST --------------------------------------------------------------------

myst_enable_extensions = ["colon_fence", "deflist"]
myst_heading_anchors = 3

# -- intersphinx -------------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable", None),
    "pandas": ("https://pandas.pydata.org/docs", None),
}

# -- HTML --------------------------------------------------------------------

html_theme = "pydata_sphinx_theme"
html_title = f"TrafficKit {release}"
html_static_path = ["_static"]
html_css_files = ["custom.css"]

html_theme_options = {
    "github_url": "https://github.com/YCkao5888/TrafficKit",
    "navbar_end": ["version-switcher", "theme-switcher", "navbar-icon-links"],
    "switcher": {
        # switcher.json 放在站台根目錄，由所有版本共用，
        # 因此新增版本時只要更新根目錄那一份。
        "json_url": f"{site_root}/switcher.json",
        "version_match": docs_version,
    },
    "show_version_warning_banner": True,
    "navigation_with_keys": False,
}

html_context = {
    "github_user": "YCkao5888",
    "github_repo": "TrafficKit",
    "github_version": "master",
    "doc_path": "docs",
}
