"""测试公共引导:定位 Hermes workspace,并把本仓库当包加载。

仓库目录名带连字符(hermes-qq-onebot),不能直接 `import`,所以用 importlib 按文件
加载并注册成 `napcat_plugin` 包 —— 插件内部用的是相对 import(`from .tools import`),
必须是个真包才能加载。
"""
import importlib.util
import os
import sys
import types
from pathlib import Path

仓库根 = Path(__file__).resolve().parent.parent


def 定位工作区() -> str:
    """找到 Hermes 的 workspace(python 包根),用来 import gateway / tools / websockets。"""
    候选 = [os.environ.get("HERMES_WORKSPACE", "")]
    候选 += [str(p) for p in sorted(Path.home().glob(".hermes/installs/*/environments/*/workspace"))]
    for 路径 in 候选:
        if 路径 and (Path(路径) / "gateway" / "config.py").is_file():
            return 路径
    print("找不到 Hermes workspace,请设置环境变量 HERMES_WORKSPACE", file=sys.stderr)
    raise SystemExit(2)


def 加载包(*模块: str) -> types.ModuleType:
    """把仓库注册成包,并按需加载指定子模块。返回包对象。"""
    if "napcat_plugin" not in sys.modules:
        工作区 = 定位工作区()
        if 工作区 not in sys.path:
            sys.path.insert(0, 工作区)
        包 = types.ModuleType("napcat_plugin")
        包.__path__ = [str(仓库根)]  # type: ignore[attr-defined]
        sys.modules["napcat_plugin"] = 包
    for 名 in 模块:
        全名 = f"napcat_plugin.{名}"
        if 全名 in sys.modules:
            continue
        spec = importlib.util.spec_from_file_location(全名, 仓库根 / f"{名}.py")
        if spec is None or spec.loader is None:
            raise ImportError(f"加载 {全名} 失败")
        m = importlib.util.module_from_spec(spec)
        sys.modules[全名] = m
        spec.loader.exec_module(m)
    return sys.modules["napcat_plugin"]
