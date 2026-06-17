"""
PathAdapter — Provider 特定路径归一化。

禁止在 Router 层使用 replace() 做字符串替换式路径修正。
每个 Provider 独立实现自己的 PathAdapter。

Router 负责: Provider Detection
PathAdapter 负责: Provider Specific Path Normalization
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("token_monitor.proxy.path_adapter")


class PathAdapter(ABC):
    """Provider 特定路径归一化的抽象基类。

    将来自 Gateway 的请求路径（含 provider 前缀）归一化为
    上游 API 的标准路径格式（不含 provider 前缀）。
    """

    @abstractmethod
    def normalize(self, path: str) -> str | None:
        """归一化请求路径。

        Args:
            path: Gateway 接收到的完整请求路径（如 /openai/v1/chat/completions）。

        Returns:
            归一化后的路径（如 /v1/chat/completions），可直拼接 base_url。
            如果路径不匹配此 Adapter 的预期格式，返回 None。
        """
        ...


class OpenAIPathAdapter(PathAdapter):
    """OpenAI 路径归一化。

    处理规则:
    1. 剥离 provider 前缀 /openai
    2. 检测 /v1 前缀: 有则保留，无则补全

    示例:
    - /openai/v1/chat/completions → /v1/chat/completions
    - /openai/chat/completions    → /v1/chat/completions  (补全 /v1)
    - /openai/v1/embeddings       → /v1/embeddings
    - /openai/embeddings          → /v1/embeddings         (补全 /v1)
    """

    PROVIDER_PREFIX = "/openai"

    def normalize(self, path: str) -> str | None:
        if not path.startswith(self.PROVIDER_PREFIX):
            return None

        # 剥离 provider 前缀
        target = path[len(self.PROVIDER_PREFIX):]

        # 确保以 / 开头
        if not target.startswith("/"):
            target = "/" + target

        # 补全 /v1 前缀（如果缺失）
        if not target.startswith("/v1/") and target != "/v1":
            # /chat/completions → /v1/chat/completions
            # /embeddings       → /v1/embeddings
            target = "/v1" + target

        logger.debug("OpenAI path normalized: %s → %s", path, target)
        return target


class AnthropicPathAdapter(PathAdapter):
    """Anthropic 路径归一化。

    处理规则:
    1. 剥离 provider 前缀 /anthropic
    2. 检测并去重 double /v1

    示例:
    - /anthropic/v1/messages      → /v1/messages
    - /anthropic/v1/v1/messages   → /v1/messages  (去重)
    - /anthropic/v1/messages/count→ /v1/messages/count
    """

    PROVIDER_PREFIX = "/anthropic"

    def normalize(self, path: str) -> str | None:
        if not path.startswith(self.PROVIDER_PREFIX):
            return None

        # 剥离 provider 前缀
        target = path[len(self.PROVIDER_PREFIX):]

        # 确保以 / 开头
        if not target.startswith("/"):
            target = "/" + target

        # 去重 double /v1
        if target.startswith("/v1/v1"):
            target = target[3:]  # 去掉多余的 "/v1"，保留 "/v1/..."
            logger.debug("Anthropic path dedup: %s → %s", path, target)

        logger.debug("Anthropic path normalized: %s → %s", path, target)
        return target


# Provider → PathAdapter 注册表
# 通过此注册表查找 Provider 对应的 PathAdapter
# 新增 Provider 时在此注册即可，无需修改 PathAdapter 或 Router 代码
PROVIDER_PATH_ADAPTERS: dict[str, PathAdapter] = {
    "openai": OpenAIPathAdapter(),
    "anthropic": AnthropicPathAdapter(),
    # 未来扩展:
    # "gemini": GeminiPathAdapter(),
    # "deepseek": DeepSeekPathAdapter(),
    # "openrouter": OpenRouterPathAdapter(),
    # "ccswitch": CCSwitchPathAdapter(),
}


def get_path_adapter(provider: str) -> PathAdapter | None:
    """获取指定 Provider 的 PathAdapter。

    Args:
        provider: Provider 名称（如 "openai"、"anthropic"）。

    Returns:
        对应的 PathAdapter 实例，如果不存在返回 None。
    """
    return PROVIDER_PATH_ADAPTERS.get(provider)
