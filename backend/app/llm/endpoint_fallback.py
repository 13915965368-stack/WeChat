from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, TypeVar

from app.llm.provider_aliases import normalize_provider_alias
from app.llm.schemas import AdapterConfig
from app.llm.validator import LLMStreamInterruptedError, LLMValidationError

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class EndpointOption:
    label: str
    base_url: str


class EndpointFallbackError(ValueError):
    pass


PROVIDER_ENDPOINT_OPTIONS: dict[str, tuple[EndpointOption, ...]] = {
    "moonshot": (
        EndpointOption(label="国内地址", base_url="https://api.moonshot.cn/v1"),
        EndpointOption(label="国外地址", base_url="https://api.moonshot.ai/v1"),
    ),
    "minimax": (
        EndpointOption(label="国内地址", base_url="https://api.minimaxi.com/v1"),
        EndpointOption(label="国外地址", base_url="https://api.minimax.io/v1"),
    ),
    "qwen": (
        EndpointOption(label="国内地址", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"),
        EndpointOption(label="国外地址", base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
    ),
}


def get_provider_endpoint_options(provider: str) -> tuple[EndpointOption, ...]:
    return PROVIDER_ENDPOINT_OPTIONS.get(normalize_provider_alias(provider), ())


def resolve_endpoint_candidates(config: AdapterConfig) -> list[tuple[str, AdapterConfig]]:
    options = get_provider_endpoint_options(config.provider)
    configured_base_url = (config.base_url or "").strip()

    if config.use_full_url or not options:
        return [("已配置地址", config)]

    official_urls = {_canonicalize_url(option.base_url) for option in options}
    if configured_base_url and _canonicalize_url(configured_base_url) not in official_urls:
        return [("手填地址", config)]

    return [
        (
            option.label,
            replace(
                config,
                base_url=option.base_url,
                metadata={**config.metadata, "endpoint_label": option.label},
            ),
        )
        for option in options
    ]


def run_with_endpoint_fallback(
    config: AdapterConfig,
    operation: Callable[[AdapterConfig], T],
) -> T:
    candidates = resolve_endpoint_candidates(config)
    if len(candidates) == 1:
        return operation(candidates[0][1])

    attempts: list[tuple[str, str, str]] = []
    for label, candidate_config in candidates:
        try:
            return operation(candidate_config)
        except LLMValidationError:
            raise
        except LLMStreamInterruptedError:
            raise
        except Exception as exc:
            attempts.append(
                (
                    label,
                    (candidate_config.base_url or "").strip(),
                    str(exc).strip() or exc.__class__.__name__,
                )
            )

    raise EndpointFallbackError(_format_attempt_errors(attempts))


def _canonicalize_url(value: str) -> str:
    return value.strip().rstrip("/").lower()


def _format_attempt_errors(attempts: list[tuple[str, str, str]]) -> str:
    lines = ["国内和国外地址都调用失败："]
    for index, (label, base_url, detail) in enumerate(attempts, start=1):
        lines.append(f"{index}. {label} {base_url}")
        lines.append(f"   {detail}")
    return "\n".join(lines)
