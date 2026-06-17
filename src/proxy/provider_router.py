"""
ProviderRouter — URL 路径前缀 → Provider 检测。

仅负责 Provider 识别，不负责路径修正。
路径归一化通过 resolve_and_normalize() 委托给 PathAdapter。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.proxy.path_adapter import get_path_adapter, PathAdapter

logger = logging.getLogger("token_monitor.proxy.provider_router")


@dataclass
class RouteResult:
    """Gateway URL 前缀解析结果。"""
    provider: str           # Provider 名称: "openai", "anthropic", ...
    target_path: str        # PathAdapter 归一化后的路径: "/v1/chat/completions"
    matched: bool           # 是否为有效的 Gateway 路由


# Provider 前缀定义
# 基于 P0 SDK Path Discovery 真实抓包结果确定
# 匹配规则: 路径以这些前缀之一开头 → 识别为该 Provider
_PROVIDER_PREFIXES: dict[str, list[str]] = {
    "openai": ["/openai"],
    "anthropic": ["/anthropic"],
    # M2+ 扩展:
    # "deepseek": ["/deepseek"],
    # "gemini": ["/gemini"],
    # "openrouter": ["/openrouter"],
    # "ccswitch": ["/ccswitch"],
}


class ProviderRouter:
    """URL 路径 → Provider 检测。

    仅负责 Provider 识别，路径归一化通过 resolve_and_normalize()
    委托给 PathAdapter 层处理。

    用法:
        router = ProviderRouter()
        result = router.resolve_and_normalize("/openai/v1/chat/completions")
        if result and result.matched:
            # result.provider = "openai"
            # result.target_path = "/v1/chat/completions"
            ...
    """

    def resolve(self, path: str) -> str | None:
        """仅检测 Provider，不归一化路径。

        Args:
            path: 请求路径（如 /openai/v1/chat/completions）。

        Returns:
            Provider 名称，如果不是 Gateway 请求则返回 None。
        """
        # 确保 path 以 / 开头
        if not path or not path.startswith("/"):
            return None

        for provider, prefixes in _PROVIDER_PREFIXES.items():
            for prefix in prefixes:
                # 宽松前缀匹配: /openai、/openai/、/openai/v1 均匹配
                # 路径必须正好以 prefix 开头，且 prefix 后是 / 或路径结束
                if path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + "?"):
                    logger.debug("Router: %s → provider=%s", path, provider)
                    return provider

        return None

    def resolve_and_normalize(self, path: str) -> RouteResult | None:
        """解析 Provider 并委托 PathAdapter 归一化路径。

        流程:
        1. resolve(path) → 检测 Provider
        2. get_path_adapter(provider) → 获取对应的 PathAdapter
        3. adapter.normalize(path) → 归一化 target_path
        4. 返回 RouteResult

        Args:
            path: 请求路径。

        Returns:
            RouteResult，如果不是 Gateway 请求则返回 None。
        """
        provider = self.resolve(path)
        if provider is None:
            return None

        # 获取 PathAdapter 进行归一化
        adapter = get_path_adapter(provider)
        if adapter is None:
            # Provider 已注册但无 PathAdapter → 回退到简单剥离前缀
            logger.warning(
                "No PathAdapter registered for provider '%s', "
                "falling back to simple prefix strip", provider
            )
            target_path = self._strip_prefix(path, provider)
        else:
            target_path = adapter.normalize(path)
            if target_path is None:
                logger.error(
                    "PathAdapter.normalize() returned None for '%s' "
                    "(provider=%s)", path, provider
                )
                # 回退到简单剥离
                target_path = self._strip_prefix(path, provider)

        result = RouteResult(
            provider=provider,
            target_path=target_path,
            matched=True,
        )
        logger.info(
            "Gateway route: %s → provider=%s, target=%s",
            path, provider, target_path,
        )
        return result

    def is_gateway_request(self, path: str) -> bool:
        """判断是否为 Gateway 模式的请求。

        如果路径以任何已注册的 Provider 前缀开头，则为 Gateway 请求。
        否则为 Proxy 模式请求（完整 URL）。

        Args:
            path: 请求路径。

        Returns:
            True 如果是 Gateway 请求。
        """
        return self.resolve(path) is not None

    @staticmethod
    def _strip_prefix(path: str, provider: str) -> str:
        """简单剥离 provider 前缀（回退逻辑，不推荐）。

        仅在 PathAdapter 缺失时使用。

        Args:
            path: 原始路径。
            provider: Provider 名称。

        Returns:
            剥离前缀后的路径。
        """
        prefix = "/" + provider
        target = path
        if target.startswith(prefix):
            target = target[len(prefix):]
        if not target.startswith("/"):
            target = "/" + target
        return target
