import pytest
import asyncio
from agent.exceptions import ConfigError
from agent.runner import _validate_startup

@pytest.mark.asyncio
async def test_config_error_message(capsys, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    
    with pytest.raises(SystemExit) as exc:
        await _validate_startup()
        
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "❌ Configuration error:" in captured.out
