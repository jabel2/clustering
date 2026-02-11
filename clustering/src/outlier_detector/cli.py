"""CLI interface for outlier detection tool."""

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from .pipeline import load_data, clean_data, engineer_features, FeatureConfig
from .clustering import HDBSCANClusterer, OutlierScorer, ClusterProfiler
from .explanation import ContextBuilder, ExplanationAgent
from .recommendation import DatasetAnalyzer, SettingsRecommender

app = typer.Typer(
    name="outlier-detector",
    help="Clustering-based outlier detection with LLM explanations.",
    add_completion=False,
)
console = Console()


@app.command()
def analyze(
    file_path: Path = typer.Argument(..., help="Path to CSV or JSON data file"),
    id_column: Optional[str] = typer.Option(
        None, "--id-column", "-i", help="Column to use as row identifier"
    ),
    categorical: Optional[str] = typer.Option(
        None, "--categorical", "-c", help="Comma-separated categorical column names"
    ),
    numerical: Optional[str] = typer.Option(
        None, "--numerical", "-n", help="Comma-separated numerical column names"
    ),
    min_cluster_size: int = typer.Option(
        5, "--min-cluster-size", "-m", help="Minimum cluster size for HDBSCAN (ignored if --auto-cluster-size)"
    ),
    auto_cluster_size: bool = typer.Option(
        False, "--auto-cluster-size", "-a", help="Automatically determine optimal min_cluster_size"
    ),
    auto_method: str = typer.Option(
        "dbcv", "--auto-method", help="Method for auto cluster size: dbcv, balanced, heuristic"
    ),
    outlier_threshold: float = typer.Option(
        0.8, "--outlier-threshold", "-t", help="Outlier score threshold (0-1)"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output JSON file path"
    ),
):
    """Analyze a dataset for outliers using HDBSCAN clustering."""
    console.print(f"\n[bold blue]Loading data from {file_path}...[/bold blue]")

    # Load data
    try:
        df = load_data(file_path)
    except FileNotFoundError:
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"  Loaded {len(df)} records with {len(df.columns)} columns")

    # Clean data
    exclude = [id_column] if id_column else []
    cleaned_df, ids = clean_data(df, id_column=id_column, exclude_columns=exclude)
    console.print(f"  Cleaned data: {len(cleaned_df.columns)} features")

    # Parse column specifications
    cat_cols = categorical.split(",") if categorical else []
    num_cols = numerical.split(",") if numerical else []

    # Engineer features
    feature_config = FeatureConfig(
        categorical_columns=[c.strip() for c in cat_cols],
        numerical_columns=[c.strip() for c in num_cols],
    )
    feature_result = engineer_features(cleaned_df, feature_config)
    console.print(f"  Engineered {len(feature_result.feature_names)} features")

    # Cluster
    console.print("\n[bold blue]Clustering...[/bold blue]")

    # Auto-detect min_cluster_size if requested
    if auto_cluster_size:
        console.print(f"  Auto-detecting min_cluster_size (method: {auto_method})...")
        optimal_size, details = HDBSCANClusterer.auto_min_cluster_size(
            feature_result.features, method=auto_method
        )
        console.print(f"  Selected min_cluster_size: {optimal_size}")
        if "scores" in details and details["scores"]:
            # Show top 3 candidates sorted by adjusted score (if available) or dbcv
            sorted_scores = sorted(
                details["scores"].items(),
                key=lambda x: x[1].get("adjusted_score", x[1].get("dbcv", 0)),
                reverse=True
            )[:3]
            for size, info in sorted_scores:
                if "effective_outlier_pct" in info:
                    console.print(
                        f"    size={size}: score={info['adjusted_score']:.3f}, "
                        f"clusters={info['n_clusters']}, outliers={info['effective_outlier_pct']:.1f}%"
                    )
                elif "adjusted_score" in info:
                    console.print(
                        f"    size={size}: score={info['adjusted_score']:.3f} (DBCV={info['dbcv']:.3f}), "
                        f"clusters={info['n_clusters']}, noise={info['noise_pct']:.1f}%"
                    )
                else:
                    console.print(
                        f"    size={size}: DBCV={info['dbcv']:.3f}, "
                        f"clusters={info['n_clusters']}, noise={info['noise_pct']:.1f}%"
                    )
        min_cluster_size = optimal_size

    clusterer = HDBSCANClusterer(min_cluster_size=min_cluster_size)
    cluster_result = clusterer.fit(feature_result.features)
    console.print(f"  Found {cluster_result.n_clusters} clusters")
    console.print(f"  Noise points: {cluster_result.n_noise}")

    # Score outliers
    scorer = OutlierScorer(outlier_threshold=outlier_threshold)
    outlier_info = scorer.score(cluster_result, ids)

    # Profile clusters
    profiler = ClusterProfiler(
        categorical_columns=feature_result.categorical_columns,
        numerical_columns=feature_result.numerical_columns,
    )
    profile_result = profiler.profile(cleaned_df, cluster_result)

    # Display results
    _display_results(
        outlier_info, profile_result, cleaned_df, scorer, cluster_result, ids
    )

    # Save output
    if output:
        _save_results(
            output, outlier_info, profile_result, cleaned_df, scorer, ids
        )
        console.print(f"\n[green]Results saved to {output}[/green]")


@app.command()
def explain(
    file_path: Path = typer.Argument(..., help="Path to CSV or JSON data file"),
    id_column: Optional[str] = typer.Option(
        None, "--id-column", "-i", help="Column to use as row identifier"
    ),
    categorical: Optional[str] = typer.Option(
        None, "--categorical", "-c", help="Comma-separated categorical column names"
    ),
    numerical: Optional[str] = typer.Option(
        None, "--numerical", "-n", help="Comma-separated numerical column names"
    ),
    context: str = typer.Option(
        "", "--context", help="Dataset description (e.g., 'AD group: Finance-Admins')"
    ),
    min_cluster_size: int = typer.Option(
        5, "--min-cluster-size", "-m", help="Minimum cluster size for HDBSCAN (ignored if --auto-cluster-size)"
    ),
    auto_cluster_size: bool = typer.Option(
        False, "--auto-cluster-size", "-a", help="Automatically determine optimal min_cluster_size"
    ),
    auto_method: str = typer.Option(
        "dbcv", "--auto-method", help="Method for auto cluster size: dbcv, balanced, heuristic"
    ),
    outlier_threshold: float = typer.Option(
        0.8, "--outlier-threshold", "-t", help="Outlier score threshold (0-1)"
    ),
    model: str = typer.Option(
        "gpt-oss:20b", "--model", help="Ollama model to use"
    ),
    max_outliers_llm: int = typer.Option(
        25, "--max-outliers-llm", help="Max outliers to send to LLM (prevents prompt overflow)"
    ),
    include_recommendations: bool = typer.Option(
        False, "--recommend", "-r", help="Include LLM recommendations in the report"
    ),
    output_format: str = typer.Option(
        "json,terminal,markdown,csv",
        "--output-format", "-f",
        help="Output formats (comma-separated: json,terminal,markdown,csv)"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Base output file path (extensions added automatically)"
    ),
):
    """Analyze outliers and generate LLM explanations."""
    # Run analysis first
    console.print(f"\n[bold blue]Loading data from {file_path}...[/bold blue]")

    try:
        df = load_data(file_path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"  Loaded {len(df)} records")

    # Clean and process
    exclude = [id_column] if id_column else []
    cleaned_df, ids = clean_data(df, id_column=id_column, exclude_columns=exclude)

    cat_cols = categorical.split(",") if categorical else []
    num_cols = numerical.split(",") if numerical else []

    feature_config = FeatureConfig(
        categorical_columns=[c.strip() for c in cat_cols],
        numerical_columns=[c.strip() for c in num_cols],
    )
    feature_result = engineer_features(cleaned_df, feature_config)

    # Cluster
    console.print("\n[bold blue]Clustering...[/bold blue]")

    # Auto-detect min_cluster_size if requested
    if auto_cluster_size:
        console.print(f"  Auto-detecting min_cluster_size (method: {auto_method})...")
        optimal_size, details = HDBSCANClusterer.auto_min_cluster_size(
            feature_result.features, method=auto_method
        )
        console.print(f"  Selected min_cluster_size: {optimal_size}")
        if "scores" in details and details["scores"]:
            sorted_scores = sorted(
                details["scores"].items(),
                key=lambda x: x[1].get("adjusted_score", x[1].get("dbcv", 0)),
                reverse=True
            )[:3]
            for size, info in sorted_scores:
                if "effective_outlier_pct" in info:
                    console.print(
                        f"    size={size}: score={info['adjusted_score']:.3f}, "
                        f"clusters={info['n_clusters']}, outliers={info['effective_outlier_pct']:.1f}%"
                    )
                elif "adjusted_score" in info:
                    console.print(
                        f"    size={size}: score={info['adjusted_score']:.3f} (DBCV={info['dbcv']:.3f}), "
                        f"clusters={info['n_clusters']}, noise={info['noise_pct']:.1f}%"
                    )
                else:
                    console.print(
                        f"    size={size}: DBCV={info['dbcv']:.3f}, "
                        f"clusters={info['n_clusters']}, noise={info['noise_pct']:.1f}%"
                    )
        min_cluster_size = optimal_size

    clusterer = HDBSCANClusterer(min_cluster_size=min_cluster_size)
    cluster_result = clusterer.fit(feature_result.features)
    console.print(f"  Found {cluster_result.n_clusters} clusters, {cluster_result.n_noise} noise points")

    # Score and profile
    scorer = OutlierScorer(outlier_threshold=outlier_threshold)
    outlier_info = scorer.score(cluster_result, ids)

    if outlier_info.outlier_count == 0:
        console.print("\n[green]No outliers detected![/green]")
        raise typer.Exit(0)

    profiler = ClusterProfiler(
        categorical_columns=feature_result.categorical_columns,
        numerical_columns=feature_result.numerical_columns,
    )
    profile_result = profiler.profile(cleaned_df, cluster_result)

    # Get outlier data and deviations
    outlier_df = scorer.get_outlier_data(cleaned_df, outlier_info)
    deviation_df = profiler.compute_deviation_scores(
        cleaned_df, outlier_info.indices, cluster_result
    )

    # Build context for LLM
    console.print("\n[bold blue]Generating LLM explanation...[/bold blue]")
    if outlier_info.outlier_count > max_outliers_llm:
        console.print(f"  [yellow]Note: {outlier_info.outlier_count} outliers found, sending top {max_outliers_llm} to LLM[/yellow]")
    context_builder = ContextBuilder(
        dataset_description=context,
        id_column=id_column,
        max_outliers=max_outliers_llm,
    )
    explanation_context = context_builder.build(
        cleaned_df, profile_result, outlier_df, deviation_df, outlier_info.ids
    )

    # Check Ollama connection
    agent = ExplanationAgent(model=model)
    if not agent.check_connection():
        console.print(f"\n[yellow]Warning: Model '{model}' not found in Ollama.[/yellow]")
        available = agent.list_available_models()
        if available:
            console.print(f"Available models: {', '.join(available)}")
        else:
            console.print("[red]Ollama not running. Start with 'ollama serve'[/red]")
        raise typer.Exit(1)

    # Generate explanation
    try:
        result = agent.explain(explanation_context)
    except ConnectionError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    # Get recommendations if requested
    recommendation_result = None
    if include_recommendations:
        console.print("\n[bold blue]Getting LLM recommendations...[/bold blue]")
        analyzer = DatasetAnalyzer()
        profile = analyzer.analyze(df)
        recommender = SettingsRecommender(model=model)
        try:
            recommendation_result = recommender.recommend(
                profile=profile,
                domain_context=context,
                file_path=str(file_path),
            )
            console.print("  Recommendations generated")
        except Exception as e:
            console.print(f"  [yellow]Warning: Could not get recommendations: {e}[/yellow]")

    # Output results
    formats = [f.strip().lower() for f in output_format.split(",")]

    if "terminal" in formats:
        console.print("\n")
        console.print(Panel(
            Markdown(result.explanation),
            title="[bold]Outlier Explanation[/bold]",
            border_style="green",
        ))

    base_path = output or Path(file_path.stem + "_analysis")

    if "json" in formats:
        json_path = Path(str(base_path) + ".json")
        _save_explanation_json(
            json_path, outlier_info, profile_result, result, cleaned_df, scorer, ids
        )
        console.print(f"\n[green]JSON saved to {json_path}[/green]")

    if "markdown" in formats:
        md_path = Path(str(base_path) + ".md")
        _save_explanation_markdown(
            md_path, context, outlier_info, profile_result, result, recommendation_result
        )
        console.print(f"[green]Markdown saved to {md_path}[/green]")

    if "csv" in formats:
        csv_path = Path(str(base_path) + ".csv")
        _save_annotated_csv(
            csv_path, df, outlier_info, result
        )
        console.print(f"[green]Annotated CSV saved to {csv_path}[/green]")


@app.command()
def recommend(
    file_path: Path = typer.Argument(..., help="Path to CSV or JSON data file"),
    context: str = typer.Option(
        "", "--context", help="Domain context (e.g., 'Active Directory group for Finance team')"
    ),
    model: str = typer.Option(
        "gpt-oss:20b", "--model", help="Ollama model to use"
    ),
):
    """Use LLM to recommend optimal settings for outlier detection."""
    console.print(f"\n[bold blue]Analyzing dataset structure...[/bold blue]")

    # Load data
    try:
        df = load_data(file_path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"  Loaded {len(df)} records with {len(df.columns)} columns")

    # Analyze dataset
    analyzer = DatasetAnalyzer()
    profile = analyzer.analyze(df)

    # Display profile summary
    console.print("\n[bold]Dataset Profile:[/bold]")
    for col in profile.columns:
        type_str = f"[cyan]{col.dtype}[/cyan]"
        null_str = f" [yellow]({col.null_pct:.1f}% null)[/yellow]" if col.null_pct > 0 else ""
        console.print(f"  - {col.name}: {type_str}, {col.unique_count} unique{null_str}")

    if profile.id_column_candidates:
        console.print(f"\n  [green]Likely ID columns:[/green] {', '.join(profile.id_column_candidates)}")

    # Get LLM recommendations
    console.print(f"\n[bold blue]Consulting LLM for recommendations...[/bold blue]")

    recommender = SettingsRecommender(model=model)

    if not recommender.check_connection():
        console.print("[red]Ollama not running. Start with 'ollama serve'[/red]")
        raise typer.Exit(1)

    try:
        result = recommender.recommend(
            profile=profile,
            domain_context=context,
            file_path=str(file_path),
        )
    except ConnectionError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    # Display recommendations
    settings = result.settings

    console.print("\n[bold green]LLM Recommendations:[/bold green]")

    if settings.id_column:
        console.print(f"  [bold]ID Column:[/bold] {settings.id_column}")

    if settings.categorical_columns:
        console.print(f"  [bold]Categorical:[/bold] {', '.join(settings.categorical_columns)}")

    if settings.numerical_columns:
        console.print(f"  [bold]Numerical:[/bold] {', '.join(settings.numerical_columns)}")

    if settings.exclude_columns:
        console.print(f"  [bold]Exclude:[/bold] {', '.join(settings.exclude_columns)}")

    if settings.expected_outlier_pct:
        console.print(f"  [bold]Expected Outliers:[/bold] ~{settings.expected_outlier_pct}%")

    console.print(f"  [bold]Auto Method:[/bold] {settings.auto_method}")

    if settings.column_weights:
        weights_str = ", ".join(f"{k}: {v}x" for k, v in settings.column_weights.items())
        console.print(f"  [bold]Column Weights:[/bold] {weights_str}")

    if settings.outlier_signals:
        console.print("\n  [bold]Outlier Signals to Watch:[/bold]")
        for signal in settings.outlier_signals:
            console.print(f"    - {signal}")

    if settings.reasoning:
        console.print(f"\n  [bold]Reasoning:[/bold] {settings.reasoning}")

    # Display suggested CLI command
    console.print("\n" + "=" * 60)
    console.print("[bold]Suggested CLI Commands:[/bold]")
    console.print("=" * 60)

    console.print("\n[cyan]# Basic analysis:[/cyan]")
    console.print(result.cli_command)

    console.print("\n[cyan]# With LLM explanation:[/cyan]")
    explain_cmd = result.cli_command.replace("analyze", "explain")
    if context:
        explain_cmd += f' \\\n  --context "{context}"'
    console.print(explain_cmd)


def _display_results(
    outlier_info, profile_result, df, scorer, cluster_result, ids
):
    """Display analysis results in terminal."""
    # Summary
    console.print("\n[bold green]Analysis Complete[/bold green]")
    console.print(f"  Total records: {outlier_info.total_count}")
    console.print(f"  Outliers found: {outlier_info.outlier_count} ({outlier_info.outlier_percentage:.1f}%)")

    # Cluster table
    table = Table(title="\nCluster Summary")
    table.add_column("Cluster", style="cyan")
    table.add_column("Size", justify="right")
    table.add_column("Percentage", justify="right")

    for cluster in profile_result.clusters:
        label = "Noise" if cluster.label == -1 else str(cluster.label)
        table.add_row(label, str(cluster.size), f"{cluster.percentage:.1f}%")

    console.print(table)

    # Outliers table
    if outlier_info.outlier_count > 0:
        outlier_df = scorer.get_outlier_data(df, outlier_info)

        table = Table(title="\nTop Outliers")
        table.add_column("ID/Index", style="cyan")
        table.add_column("Score", justify="right")

        # Add first few feature columns
        feature_cols = [c for c in outlier_df.columns if not c.startswith("_")][:4]
        for col in feature_cols:
            table.add_column(col)

        for i, row in outlier_df.iterrows():
            identifier = str(outlier_info.ids.iloc[i]) if outlier_info.ids is not None else str(i)
            score = f"{row['_outlier_score']:.2f}"
            values = [str(row[c])[:20] for c in feature_cols]
            table.add_row(identifier, score, *values)

        console.print(table)


def _save_results(output_path, outlier_info, profile_result, df, scorer, ids):
    """Save analysis results to JSON."""
    outlier_df = scorer.get_outlier_data(df, outlier_info)

    result = {
        "summary": {
            "total_records": outlier_info.total_count,
            "outlier_count": outlier_info.outlier_count,
            "outlier_percentage": outlier_info.outlier_percentage,
            "n_clusters": profile_result.n_clusters,
        },
        "clusters": [
            {
                "label": c.label,
                "size": c.size,
                "percentage": c.percentage,
                "profile": {
                    col.name: {
                        "type": col.dtype,
                        "mode": col.mode,
                        "distribution": col.distribution,
                    }
                    for col in c.columns
                },
            }
            for c in profile_result.clusters
        ],
        "outliers": [
            {
                "id": str(outlier_info.ids.iloc[i]) if outlier_info.ids is not None else i,
                "score": float(row["_outlier_score"]),
                "values": {k: str(v) for k, v in row.items() if not k.startswith("_")},
            }
            for i, row in outlier_df.iterrows()
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)


def _save_explanation_json(
    output_path, outlier_info, profile_result, explanation_result, df, scorer, ids
):
    """Save explanation results to JSON."""
    outlier_df = scorer.get_outlier_data(df, outlier_info)

    result = {
        "summary": {
            "total_records": outlier_info.total_count,
            "outlier_count": outlier_info.outlier_count,
            "outlier_percentage": outlier_info.outlier_percentage,
            "n_clusters": profile_result.n_clusters,
        },
        "outliers": [
            {
                "id": str(outlier_info.ids.iloc[i]) if outlier_info.ids is not None else i,
                "score": float(row["_outlier_score"]),
                "values": {k: str(v) for k, v in row.items() if not k.startswith("_")},
            }
            for i, row in outlier_df.iterrows()
        ],
        "explanation": {
            "model": explanation_result.model,
            "content": explanation_result.explanation,
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)


def _save_explanation_markdown(
    output_path, context, outlier_info, profile_result, explanation_result,
    recommendation_result=None
):
    """Save explanation results to Markdown."""
    lines = [
        f"# Outlier Analysis Report",
        "",
        f"**Dataset**: {context}" if context else "",
        f"**Total Records**: {outlier_info.total_count}",
        f"**Outliers Found**: {outlier_info.outlier_count} ({outlier_info.outlier_percentage:.1f}%)",
        f"**Clusters**: {profile_result.n_clusters}",
        "",
    ]

    # Add LLM recommendations section if available
    if recommendation_result and recommendation_result.settings:
        settings = recommendation_result.settings
        lines.extend([
            "## LLM Recommendations",
            "",
        ])

        if settings.expected_outlier_pct:
            lines.append(f"**Expected Outlier Rate**: ~{settings.expected_outlier_pct}%")

        if settings.column_weights:
            weights_str = ", ".join(f"{k} ({v}x)" for k, v in settings.column_weights.items())
            lines.append(f"**Important Columns**: {weights_str}")

        if settings.outlier_signals:
            lines.extend(["", "### Outlier Signals to Watch", ""])
            for signal in settings.outlier_signals:
                lines.append(f"- {signal}")

        if settings.reasoning:
            lines.extend([
                "",
                "### Analysis Reasoning",
                "",
                settings.reasoning,
            ])

        lines.extend(["", "---", ""])

    lines.extend([
        "## Cluster Summary",
        "",
        "| Cluster | Size | Percentage |",
        "|---------|------|------------|",
    ])

    for cluster in profile_result.clusters:
        label = "Noise" if cluster.label == -1 else str(cluster.label)
        lines.append(f"| {label} | {cluster.size} | {cluster.percentage:.1f}% |")

    # Add detailed cluster profiles
    lines.extend(["", "## Cluster Profiles", ""])

    for cluster in profile_result.clusters:
        if cluster.label == -1:
            lines.append(f"### Noise/Outliers ({cluster.size} records)")
        else:
            lines.append(f"### Cluster {cluster.label} ({cluster.size} records, {cluster.percentage:.1f}%)")
        lines.append("")

        # Build a description of key characteristics
        categorical_desc = []
        numerical_desc = []

        for col in cluster.columns:
            if col.dtype == "categorical":
                # Show the dominant value and its percentage
                if col.mode_percentage >= 50:
                    categorical_desc.append(
                        f"- **{col.name}**: {col.mode} ({col.mode_percentage:.0f}%)"
                    )
                else:
                    # Mixed cluster - show top values
                    top_vals = ", ".join(
                        f"{k} ({v:.0f}%)" for k, v in list(col.distribution.items())[:3]
                    )
                    categorical_desc.append(f"- **{col.name}**: {top_vals}")
            else:
                # Numerical - show median and range
                dist = col.distribution
                numerical_desc.append(
                    f"- **{col.name}**: median {dist['median']}, range [{dist['min']} - {dist['max']}]"
                )

        if categorical_desc:
            lines.extend(categorical_desc)
        if numerical_desc:
            lines.extend(numerical_desc)
        lines.append("")

    lines.extend([
        "## LLM Explanation",
        "",
        f"*Model: {explanation_result.model}*",
        "",
        explanation_result.explanation,
    ])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _save_annotated_csv(output_path, original_df, outlier_info, explanation_result):
    """Save original CSV with analysis columns appended for outliers."""
    # Create a copy of the original dataframe
    df = original_df.copy()

    # Add analysis columns (empty by default)
    df["_is_outlier"] = False
    df["_outlier_score"] = 0.0
    df["_why_outlier"] = ""
    df["_unusual_attributes"] = ""
    df["_risk_level"] = ""
    df["_recommended_action"] = ""

    # Mark outliers
    for i, idx in enumerate(outlier_info.indices):
        df.loc[idx, "_is_outlier"] = True
        df.loc[idx, "_outlier_score"] = float(outlier_info.scores[i])

    # Add structured analysis if available
    if explanation_result.structured_analysis:
        # Create lookup by ID
        analysis_lookup = {
            a.id: a for a in explanation_result.structured_analysis
        }

        # Match analysis to rows
        for i, idx in enumerate(outlier_info.indices):
            # Get the ID for this outlier
            if outlier_info.ids is not None and i < len(outlier_info.ids):
                outlier_id = str(outlier_info.ids.iloc[i])
            else:
                outlier_id = str(idx)

            # Look up analysis
            analysis = analysis_lookup.get(outlier_id)
            if analysis:
                df.loc[idx, "_why_outlier"] = analysis.why_outlier
                df.loc[idx, "_unusual_attributes"] = analysis.unusual_attributes
                df.loc[idx, "_risk_level"] = analysis.risk_level
                df.loc[idx, "_recommended_action"] = analysis.recommended_action

    # Save to CSV
    df.to_csv(output_path, index=False, encoding="utf-8")


if __name__ == "__main__":
    app()
