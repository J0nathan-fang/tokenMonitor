"""
EndpointResolver — Provider 名称 → 目标 Base URL + API Key 解析。

接收 ProviderRouter 解析的 provider + PathAdapter 归一化的 path，
拼接为完整的 upstream URL。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("token_monitor.proxy.endpoint_resolver")


@dataclass
class EndpointConfig:
    """单个 Provider 的端点配置。"""
    provider: str                            # 路由键 / client_type ("openai", ...)
    base_url: str                            # 上游 API Base URL（可指向 DeepSeek 等）
    enabled: bool = True
    api_key_header: str = "Authorization"    # 上游 API 期望的 Auth Header 名称
    api_key_prefix: str = "Bearer "          # Auth Header 值的前缀
    actual_provider: str = ""                # 真实后端 Provider（默认同 provider）
    pricing_version: str = ""                # 定价版本标识（如 "2026-06-deepseek"）

    def __post_init__(self):
        if not self.actual_provider:
            self.actual_provider = self.provider


# 默认 Provider 配置
# 基于 P0 SDK Path Discovery 结果:
# - OpenAI SDK 使用 Authorization: Bearer <key>
# - Anthropic SDK 使用 x-api-key: <key>
_DEFAULT_PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {
        "base_url": "https://api.deepseek.com",
        "api_key_header": "Authorization",
        "api_key_prefix": "Bearer ",
        "actual_provider": "deepseek",
        "pricing_version": "2026-06-deepseek",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com",
        "api_key_header": "x-api-key",
        "api_key_prefix": "",
    },
    # M2+ 扩展:
    # "deepseek": {
    #     "base_url": "https://api.deepseek.com",
    #     "api_key_header": "Authorization",
    #     "api_key_prefix": "Bearer ",
    # },
    # "gemini": {
    #     "base_url": "https://generativelanguage.googleapis.com",
    #     "api_key_header": "x-goog-api-key",
    #     "api_key_prefix": "",
    # },
    # "openrouter": {
    #     "base_url": "https://openrouter.ai/api",
    #     "api_key_header": "Authorization",
    #     "api_key_prefix": "Bearer ",
    # },
}


class EndpointResolver:
    """Provider 名称 → 目标 Base URL + API Key 解析。

    从默认配置加载 Provider 配置，支持运行时注册/注销。
    配合 PathAdapter 归一化后的路径拼接完整 upstream URL。

    用法:
        resolver = EndpointResolver()
        config = resolver.resolve("openai")
        url = resolver.build_target_url("openai", "/v1/chat/completions")
        # → "https://api.openai.com/v1/chat/completions"
    """

    def __init__(self) -> None:
        self._providers: dict[str, EndpointConfig] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        """从内置默认配置加载 Provider。"""
        for name, cfg in _DEFAULT_PROVIDERS.items():
            self._providers[name] = EndpointConfig(
                provider=name,
                base_url=cfg["base_url"],
                enabled=True,
                api_key_header=cfg["api_key_header"],
                api_key_prefix=cfg["api_key_prefix"],
                actual_provider=cfg.get("actual_provider", name),
                pricing_version=cfg.get("pricing_version", ""),
            )
        logger.info(
            "Loaded %d default providers: %s",
            len(self._providers),
            ", ".join(self._providers.keys()),
        )

    def resolve(self, provider: str) -> EndpointConfig | None:
        """获取 Provider 的端点配置。

        Args:
            provider: Provider 名称（如 "openai"）。

        Returns:
            EndpointConfig，如果 provider 不存在或未启用返回 None。
        """
        config = self._providers.get(provider)
        if config is None:
            logger.warning("Unknown provider: %s", provider)
            return None
        if not config.enabled:
            logger.warning("Provider disabled: %s", provider)
            return None
        return config

    def build_target_url(self, provider: str, normalized_path: str) -> str | None:
        """拼接完整的上游 API URL。

        Args:
            provider: Provider 名称。
            normalized_path: PathAdapter 归一化后的路径（如 /v1/chat/completions）。

        Returns:
            完整 URL（如 https://api.openai.com/v1/chat/completions），
            如果 provider 无效返回 None。
        """
        config = self.resolve(provider)
        if config is None:
            return None

        # 确保 path 以 / 开头
        target_path = normalized_path if normalized_path.startswith("/") else "/" + normalized_path

        # 拼接 base_url + path
        # base_url 不应包含尾部 /
        base = config.base_url.rstrip("/")
        url = base + target_path
        logger.debug("Target URL: %s", url)
        return url

    def get_api_key_headers(
        self,
        provider: str,
        client_auth_header: str | None = None,
    ) -> dict[str, str] | None:
        """构建上游 API 所需的 Auth Headers。

        当前阶段（透传模式）:
        - 如果客户端发送了 auth header，剥离前缀后转译为上游 API 期望的 header 格式
        - 如果客户端未发送 auth header，返回 None（上游 API 会返回 401）

        未来阶段（管理模式）:
        - 从 keyring/Windows Credential Manager 读取存储的 Key 注入

        Args:
            provider: Provider 名称。
            client_auth_header: 客户端发送的 Authorization header 值（如果有）。

        Returns:
            Auth header 字典（如 {"Authorization": "Bearer sk-xxx"}），
            如果没有可用的 API Key 则返回 None。
        """
        config = self.resolve(provider)
        if config is None:
            return None

        if not client_auth_header:
            # 透传模式: 无 Key → 不注入
            logger.debug("No client auth header for %s, forwarding without auth", provider)
            return None

        # 透传模式: 剥离客户端 header 的前缀，用上游 API 的格式重新包装
        key_value = client_auth_header
        # 尝试剥离常见前缀 (Bearer, Basic 等)
        if " " in key_value:
            prefix, _, key_value = key_value.partition(" ")
            logger.debug("Stripped auth prefix '%s' from client header", prefix)

        # 构建上游 API 期望的 header
        prefix = config.api_key_prefix
        header_name = config.api_key_header
        header_value = prefix + key_value if prefix else key_value

        return {header_name: header_value}

    def register_provider(self, config: EndpointConfig) -> None:
        """注册或更新一个 Provider。

        Args:
            config: Provider 的端点配置。
        """
        self._providers[config.provider] = config
        logger.info("Provider registered: %s → %s", config.provider, config.base_url)

    def remove_provider(self, provider: str) -> None:
        """移除一个 Provider。

        Args:
            provider: Provider 名称。
        """
        self._providers.pop(provider, None)
        logger.info("Provider removed: %s", provider)

    @property
    def providers(self) -> list[str]:
        """获取所有已注册的 Provider 名称。"""
        return list(self._providers.keys())

    @property
    def enabled_providers(self) -> list[str]:
        """获取所有已启用的 Provider 名称。"""
        return [k for k, v in self._providers.items() if v.enabled]
