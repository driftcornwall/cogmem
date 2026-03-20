"""Tests for CogMem CLI commands."""
import pytest
from click.testing import CliRunner
from cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "CogMem" in result.output or "cogmem" in result.output.lower()


def test_create_agent(runner, tmp_path):
    result = runner.invoke(cli, ["create-agent", "Nova", "--path", str(tmp_path / "Nova")])
    assert result.exit_code == 0
    assert (tmp_path / "Nova" / "cogmem.yaml").exists()


def test_list_agents_empty(runner, tmp_path):
    result = runner.invoke(cli, ["list-agents", "--agents-dir", str(tmp_path)])
    assert result.exit_code == 0


def test_create_then_list(runner, tmp_path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    runner.invoke(cli, ["create-agent", "Nova", "--path", str(agents_dir / "Nova")])
    result = runner.invoke(cli, ["list-agents", "--agents-dir", str(agents_dir)])
    assert result.exit_code == 0
    assert "Nova" in result.output
