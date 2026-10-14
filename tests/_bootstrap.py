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
from typing import Optional

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


def 注册napcat平台() -> None:
    """把 napcat 注册进 platform_registry,让 `Platform("napcat")` 能解析。

    Platform 的动态成员由 Enum 的 `_missing_` 在 `platform_registry.is_registered(name)`
    为真时按需创建(注释原话:"Plugin platforms are dynamic members created on demand")。
    真实运行时的顺序是「先加载插件(register_platform) → 再建适配器」,测试里要自己
    补这一步 —— 否则构造适配器时会 ValueError: 'napcat' is not a valid Platform。
    """
    if getattr(注册napcat平台, "_已注册", False):
        return
    from gateway.platform_registry import PlatformEntry, platform_registry

    try:
        platform_registry.register(PlatformEntry(
            name="napcat", label="NapCat (QQ)",
            adapter_factory=lambda cfg: None, check_fn=lambda: True, source="plugin",
        ))
    except Exception:
        pass  # 已注册过就跳过
    注册napcat平台._已注册 = True  # type: ignore[attr-defined]


def 建立临时媒体策略(允许目录: Path, 父目录: Optional[Path] = None) -> Path:
    """造一个带「严格媒体白名单」的临时 profile,并把 HERMES_HOME override 指过去。

    ⚠️ 必须用 set_hermes_home_override 而不是 HERMES_HOME 环境变量:media_policy 读的
    是进程内 ContextVar 路由到的 profile 配置(multiplex 每个 profile turn 设置),
    只设环境变量会读回空值、把「策略没生效」误判成代码有问题。
    """
    档案 = (父目录 or 允许目录.parent) / "profile"
    档案.mkdir(parents=True, exist_ok=True)
    (档案 / "config.yaml").write_text(
        "gateway:\n"
        "  strict: true\n"
        "  trust_recent_files: false\n"
        "  media_delivery_allow_dirs:\n"
        f"    - {允许目录}\n",
        encoding="utf-8",
    )
    from hermes_constants import set_hermes_home_override

    set_hermes_home_override(str(档案))
    return 档案
