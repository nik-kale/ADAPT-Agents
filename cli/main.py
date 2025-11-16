#!/usr/bin/env python3
"""
ADAPT-Agents CLI
Command-line interface for agent operations
"""

import click
import json
import sys
from pathlib import Path
from typing import Optional


@click.group()
@click.version_option(version="2.0.0")
def cli():
    """ADAPT-Agents - Modular Diagnostic Agents Library"""
    pass


@cli.command()
@click.argument('incident_file', type=click.Path(exists=True))
@click.option('--agent', '-a', multiple=True, help='Specific agents to run (log, metrics, change, topology, hypothesis, remediation)')
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--format', '-f', type=click.Choice(['json', 'yaml', 'text']), default='text', help='Output format')
@click.option('--async', 'use_async', is_flag=True, help='Use async execution')
def analyze(incident_file: str, agent: tuple, output: Optional[str], format: str, use_async: bool):
    """Run RCA analysis on incident data"""
    # Load incident data
    with open(incident_file) as f:
        if incident_file.endswith('.json'):
            incident_data = json.load(f)
        elif incident_file.endswith(('.yaml', '.yml')):
            import yaml
            incident_data = yaml.safe_load(f)
        else:
            click.echo("Error: Unsupported file format. Use .json or .yaml", err=True)
            sys.exit(1)

    # Run analysis
    if agent:
        # Run specific agents
        results = run_specific_agents(list(agent), incident_data, use_async)
    else:
        # Run full chain
        from chains.orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator(error_strategy="continue")
        results = orchestrator.execute_rca_chain(incident_data)

    # Output results
    if output:
        output_results(results, output, format)
    else:
        if format == 'json':
            click.echo(json.dumps(results, indent=2, default=str))
        elif format == 'text':
            from chains.orchestrator import AgentOrchestrator
            orchestrator = AgentOrchestrator()
            orchestrator.print_results(results)


def run_specific_agents(agent_names: list, incident_data: dict, use_async: bool):
    """Run specific agents only"""
    from agents import (
        LogAnalyzerAgent, MetricsAnalyzerAgent, ChangeCorrelatorAgent,
        TopologyInferenceAgent, HypothesisGeneratorAgent, RemediationPlannerAgent
    )
    from schemas import BaseAgentInput

    agent_map = {
        'log': LogAnalyzerAgent,
        'metrics': MetricsAnalyzerAgent,
        'change': ChangeCorrelatorAgent,
        'topology': TopologyInferenceAgent,
        'hypothesis': HypothesisGeneratorAgent,
        'remediation': RemediationPlannerAgent
    }

    results = {}
    for agent_name in agent_names:
        if agent_name not in agent_map:
            click.echo(f"Warning: Unknown agent '{agent_name}'", err=True)
            continue

        agent_class = agent_map[agent_name]
        agent = agent_class()

        # Prepare input based on agent type
        input_data = BaseAgentInput(
            context=incident_data,
            parameters=incident_data.get('parameters', {})
        )

        # Execute
        result = agent.execute(input_data)
        results[agent_name] = result

    return results


def output_results(results: dict, output_path: str, format: str):
    """Write results to file"""
    with open(output_path, 'w') as f:
        if format == 'json':
            json.dump(results, f, indent=2, default=str)
        elif format == 'yaml':
            import yaml
            yaml.dump(results, f, default_flow_style=False)
        elif format == 'text':
            # Write human-readable text
            f.write("ADAPT-Agents Analysis Results\n")
            f.write("=" * 80 + "\n\n")
            f.write(str(results))


@cli.command()
@click.option('--scenario', type=click.Choice(['memory_leak', 'db_pool', 'cascade']), required=True)
@click.option('--output', '-o', required=True, help='Output file path')
def generate_test_data(scenario: str, output: str):
    """Generate synthetic test data"""
    from examples import synthetic_data

    if scenario == 'memory_leak':
        data = synthetic_data.create_memory_leak_incident()
    elif scenario == 'db_pool':
        data = synthetic_data.create_database_pool_incident()
    else:
        click.echo(f"Scenario '{scenario}' not implemented yet", err=True)
        sys.exit(1)

    # Write to file
    with open(output, 'w') as f:
        json.dump(data, f, indent=2)

    click.echo(f"Generated {scenario} test data → {output}")


@cli.command()
@click.option('--host', default='0.0.0.0', help='API host')
@click.option('--port', default=8000, type=int, help='API port')
@click.option('--workers', default=4, type=int, help='Number of workers')
@click.option('--reload', is_flag=True, help='Enable auto-reload (development)')
def serve(host: str, port: int, workers: int, reload: bool):
    """Start API server"""
    try:
        import uvicorn
        from api.server import app

        click.echo(f"Starting ADAPT-Agents API server on {host}:{port}")
        uvicorn.run(
            "api.server:app",
            host=host,
            port=port,
            workers=workers if not reload else 1,
            reload=reload
        )
    except ImportError:
        click.echo("Error: uvicorn and fastapi not installed", err=True)
        click.echo("Install with: pip install 'adapt-agents[api]'", err=True)
        sys.exit(1)


@cli.command()
@click.option('--port', default=9090, type=int, help='Metrics port')
def metrics(port: int):
    """Start metrics server"""
    from utils.metrics import start_metrics_server
    import time

    click.echo(f"Starting metrics server on port {port}")
    click.echo("Metrics available at http://localhost:{port}/metrics")

    start_metrics_server(port)

    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        click.echo("\nShutting down metrics server")


@cli.command()
def version():
    """Show version information"""
    click.echo("ADAPT-Agents v2.0.0")
    click.echo("Modular Diagnostic Agents Library")


@cli.command()
@click.argument('config_file', type=click.Path(), required=False)
def validate_config(config_file: Optional[str]):
    """Validate configuration file"""
    if config_file:
        # Load and validate specific file
        config_path = Path(config_file)
        if not config_path.exists():
            click.echo(f"Error: Config file not found: {config_file}", err=True)
            sys.exit(1)

        from config.settings import load_config_from_file
        config = load_config_from_file(config_path)
        click.echo(f"✓ Configuration valid: {config_file}")
        click.echo(json.dumps(config, indent=2))
    else:
        # Validate current settings
        from config.settings import get_settings
        settings = get_settings()
        click.echo("✓ Current configuration valid")
        click.echo(f"LLM Provider: {settings.llm_provider}")
        click.echo(f"Cache Backend: {settings.cache_backend}")
        click.echo(f"Log Level: {settings.log_level}")


if __name__ == '__main__':
    cli()
