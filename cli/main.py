"""Command line interface for quant plugin framework."""

from __future__ import annotations

from datetime import datetime

import click


@click.group()
@click.version_option(version="0.1.0", prog_name="quant")
def cli() -> None:
    """Quant Plugin Framework CLI"""


@cli.group()
def run() -> None:
    """Run commands"""


@run.command()
@click.option("--config", "-c", type=click.Path(exists=True), help="Config file path")
@click.option("--strategy", "-s", default="double_low", help="Strategy name")
@click.option("--start", type=click.DateTime(), help="Start date")
@click.option("--end", type=click.DateTime(), help="End date")
def backtest(
    config: str | None,
    strategy: str,
    start: datetime | None,
    end: datetime | None,
) -> None:
    """Run backtest with specified strategy"""
    click.echo("Backtest started")
    click.echo(f"strategy={strategy}")
    if config is not None:
        click.echo(f"config={config}")
    if start is not None:
        click.echo(f"start={start.isoformat()}")
    if end is not None:
        click.echo(f"end={end.isoformat()}")


if __name__ == "__main__":
    cli()
