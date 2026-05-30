from app.models import ModelConfig
from app.services.adapter_config_factory import build_adapter_config_from_model


def _make_model_config(**overrides):
    model_config = ModelConfig(
        id="mc-1",
        provider="moonshot",
        model="kimi-k2",
        display_name="Kimi K2",
        api_format="openai_chat",
        base_url="https://api.moonshot.cn/v1",
        use_full_url=False,
        capabilities={},
        status="available",
    )
    model_config.api_key_encrypted = ""
    for key, value in overrides.items():
        setattr(model_config, key, value)
    return model_config


def test_build_adapter_config_chat_source_includes_status():
    cfg = build_adapter_config_from_model(_make_model_config(), source="model_config")

    assert cfg.provider == "moonshot"
    assert cfg.model == "kimi-k2"
    assert cfg.metadata["source"] == "model_config"
    assert cfg.metadata["status"] == "available"
    assert cfg.metadata["model_config_id"] == "mc-1"


def test_build_adapter_config_validation_source_no_status():
    cfg = build_adapter_config_from_model(
        _make_model_config(),
        source="model_config_validation",
    )

    assert cfg.metadata["source"] == "model_config_validation"
    assert "status" not in cfg.metadata
