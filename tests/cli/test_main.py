"""CLI tests for quant command line entry (Day 11, TDD)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from cli.main import cli


def test_cli_help_output() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "Quant Plugin Framework CLI" in result.output
    assert "run" in result.output


def test_cli_version_output() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert "quant, version 0.1.0" in result.output


def test_run_backtest_command() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["run", "backtest"])

    assert result.exit_code == 0
    assert "backtest started" in result.output.lower()
    assert "strategy=double_low" in result.output


def test_run_backtest_with_config() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        config_path = Path("config.toml")
        config_path.write_text("[strategy]\nname='double_low'\n", encoding="utf-8")

        result = runner.invoke(
            cli,
            ["run", "backtest", "--config", str(config_path)],
        )

    assert result.exit_code == 0
    assert "config=config.toml" in result.output


def test_run_backtest_with_missing_config_file() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["run", "backtest", "--config", "missing.toml"])

    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_run_backtest_strategy_parameter_passthrough() -> None:
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["run", "backtest", "--strategy", "mean_reversion"],
    )

    assert result.exit_code == 0
    assert "strategy=mean_reversion" in result.output
