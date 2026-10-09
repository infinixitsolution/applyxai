"""Tests for Windows agent packaging functionality."""

import subprocess
import sys
from pathlib import Path


def test_agent_imports():
    """Test that agent modules can be imported."""
    import agent
    assert hasattr(agent, 'AGENT_VERSION')
    assert agent.AGENT_VERSION == "1.1.2"

    from agent import config
    assert hasattr(config, 'default_home')

    from agent import client
    assert hasattr(client, 'ApiClient')

    from agent import supervisor
    assert hasattr(supervisor, 'Supervisor')


def test_agent_cli_help():
    """Test that agent CLI help works."""
    result = subprocess.run(
        [sys.executable, "-m", "agent", "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "pair" in result.stdout
    assert "run" in result.stdout
    assert "status" in result.stdout
    assert "unpair" in result.stdout


def test_agent_cli_status():
    """Test that agent CLI status command works."""
    result = subprocess.run(
        [sys.executable, "-m", "agent", "status"],
        capture_output=True,
        text=True
    )
    # Status should work even if not paired (just shows not connected)
    assert result.returncode in [0, 2]  # 0 if paired, 2 if not


def test_config_default_home():
    """Test that default home directory is correctly set."""
    from agent import config
    home = config.default_home()
    assert isinstance(home, Path)
    # On Windows, should use LOCALAPPDATA
    if sys.platform == "win32":
        assert "ApplyXAI" in str(home)


def test_config_check_server_url():
    """Test server URL validation."""
    from agent import config

    # Valid HTTPS URLs
    assert config.check_server_url("https://app.applyxai.com") == "https://app.applyxai.com"
    assert config.check_server_url("https://app.applyxai.com/") == "https://app.applyxai.com"

    # Valid localhost HTTP
    assert config.check_server_url("http://localhost:8000") == "http://localhost:8000"
    assert config.check_server_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"

    # Invalid URLs
    try:
        config.check_server_url("http://192.168.1.1:8000")
        assert False, "Should reject non-localhost HTTP"
    except ValueError:
        pass

    try:
        config.check_server_url("app.applyxai.com")
        assert False, "Should reject URL without scheme"
    except ValueError:
        pass


def test_config_round_trip(tmp_path):
    """Test config save/load round trip."""
    from agent import config

    cfg = config.AgentConfig(
        server="https://test.example.com",
        token="test_token_123",
        device_id="device_456",
        user_id="user_789",
        name="Test PC"
    )

    config.save(tmp_path, cfg)
    loaded = config.load(tmp_path)

    assert loaded.server == cfg.server
    assert loaded.token == cfg.token
    assert loaded.device_id == cfg.device_id
    assert loaded.user_id == cfg.user_id
    assert loaded.name == cfg.name

    # Token should not be in repr
    assert "test_token_123" not in repr(cfg)
    assert "test_token_123" not in repr(loaded)

    config.forget(tmp_path)
    assert config.load(tmp_path) is None


def test_runner_is_frozen():
    """Test that _is_frozen returns correct value."""
    from automation.runner import _is_frozen
    # In development, should be False
    assert _is_frozen() == False


def test_runner_get_python_exe():
    """Test that _get_python_exe returns a valid path."""
    from automation.runner import _get_python_exe
    python_exe = _get_python_exe()
    assert Path(python_exe).exists()
    assert python_exe.endswith("python.exe") or python_exe.endswith("python")


def test_automation_modules_import():
    """Test that automation modules can be imported."""
    import automation
    import automation.events
    import automation.run_config
    import automation.runner

    assert hasattr(automation.events, 'APPLIED')
    assert hasattr(automation.run_config, 'build_run_config')
    assert hasattr(automation.runner, 'EngineRun')


def test_modules_import():
    """Test that modules can be imported."""
    import modules
    import modules.run_hooks
    import modules.open_chrome
    import modules.helpers

    assert hasattr(modules.run_hooks, 'emit')
    assert hasattr(modules.open_chrome, 'createChromeSession')


def test_gui_imports():
    """Test that GUI module can be imported."""
    try:
        from agent import gui
        assert hasattr(gui, 'AgentGUI')
    except ImportError:
        # GUI imports tkinter which may not be available in all environments
        # This is acceptable
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
