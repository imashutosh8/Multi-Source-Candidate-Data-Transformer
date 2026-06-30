import json
import logging
from pathlib import Path
from typing import Optional
import typer
from candidate_transformer.config import PipelineConfig
from candidate_transformer.orchestrator import CandidateTransformerOrchestrator, PipelineError
from candidate_transformer.validators.validator import ValidationError

# Setup typer application
app = typer.Typer(
    name="candidate-transformer",
    help="CLI tool to ingest, clean, normalize, merge, and project candidate profile datasets.",
    no_args_is_help=True
)

# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("candidate_transformer")

@app.command()
def transform(
    csv: Optional[Path] = typer.Option(None, "--csv", help="Path to recruiter candidate CSV file"),
    ats: Optional[Path] = typer.Option(None, "--ats", help="Path to ATS candidate JSON file"),
    resume: Optional[Path] = typer.Option(None, "--resume", help="Path to candidate resume PDF file"),
    notes: Optional[Path] = typer.Option(None, "--notes", help="Path to recruiter notes TXT file"),
    config: Optional[Path] = typer.Option(None, "--config", help="Path to projection and validation configuration JSON"),
    output: Path = typer.Option(Path("candidate.json"), "--output", "-o", help="Output path for the projected candidate profile JSON")
):
    """
    Ingests and merges candidate details from structured and unstructured sources,
    resolves source conflicts, calculates profile confidence, and outputs projected JSON.
    """
    logger.info("Initializing Candidate Profile Transformation Engine.")
    
    # Verify at least one input file is provided
    if not (csv or ats or resume or notes):
        typer.secho("Error: At least one input source (--csv, --ats, --resume, --notes) must be specified.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Load configuration JSON if provided
    config_dict = None
    if config:
        if not config.exists():
            typer.secho(f"Error: Configuration file not found at '{config}'", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        try:
            with open(config, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
            logger.info(f"Loaded schema projection configuration from '{config}'")
        except json.JSONDecodeError as jde:
            typer.secho(f"Error: Config JSON is malformed: {jde}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        except Exception as e:
            typer.secho(f"Error: Failed to read configuration file: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

    # Load pipeline configuration if present
    pipeline_cfg = None
    if config_dict and "pipeline" in config_dict:
        try:
            pipeline_cfg = PipelineConfig.model_validate(config_dict["pipeline"])
            logger.info("Loaded custom pipeline configuration parameters from config file.")
        except Exception as pce:
            typer.secho(f"Error: Pipeline config section is invalid: {pce}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

    # Initialize orchestrator
    orchestrator = CandidateTransformerOrchestrator(config=pipeline_cfg)

    try:
        # Run pipeline
        result = orchestrator.run(
            csv_path=csv,
            ats_path=ats,
            resume_path=resume,
            notes_path=notes,
            config=config_dict
        )
    except ValidationError as ve:
        typer.secho("\nValidation Failures in Projected Schema:", fg=typer.colors.RED, bold=True, err=True)
        for error_msg in ve.errors:
            typer.secho(f" - {error_msg}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except PipelineError as pe:
        typer.secho(f"\nPipeline Error: {pe}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        logger.exception("Transformation pipeline run encountered an unhandled exception.")
        typer.secho(f"Unhandled Exception: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Write output JSON to disk
    try:
        # Ensure parent directories exist
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as out_file:
            json.dump(result, out_file, indent=2, ensure_ascii=False)
        
        logger.info(f"Canonical projected candidate profile written successfully to '{output}'")
        typer.secho(f"\nSuccess! Merged candidate output written to '{output}'", fg=typer.colors.GREEN, bold=True)
    except Exception as e:
        typer.secho(f"Error: Failed to write output JSON to '{output}': {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command()
def info():
    """
    Prints information about the Multi-Source Candidate Data Transformer.
    """
    typer.echo("Multi-Source Candidate Data Transformer v0.1.0")
    typer.echo("Eightfold Engineering Assignment Implementation")

if __name__ == "__main__":
    app()
