"""Presentation-only exports from frozen aggregate tables; no model estimation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

COLUMNS = [
    "value_id",
    "claim_id",
    "source_table",
    "source_hash",
    "row_key_json",
    "metric",
    "raw_value",
    "display_report",
    "display_slide",
    "unit",
    "scope",
]
BLUE = "#2474b5"
GREY = "#7d8790"
SUBJECTS = {"mat": "Математика", "por": "Португальська"}


def format_value(value, metric="", unit="", decimals=3):
    """Format missing values explicitly and retain small nonzero p-values."""
    if pd.isna(value) or (isinstance(value, str) and value.strip() in {"", "NA", "NaN", "nan"}):
        return "—"
    try:
        number = float(value)
    except (ValueError, TypeError):
        return str(value)
    if metric.startswith("p_"):
        return "<1e-300" if number == 0 else f"{number:.6g}"
    if unit == "count" or metric in {"nobs", "count", "n"}:
        return str(int(number))
    return f"{number:.{decimals}f}"


def collect_report_values(root):
    """Return traceable values, preserving K3 evidence pointers and hashes."""
    root = Path(root)
    evidence = pd.read_csv(root / "outputs/tables/final_claim_evidence.csv", keep_default_na=False)
    claims = pd.read_csv(root / "outputs/tables/final_claims.csv").set_index("claim_id")
    rows = []

    def add(value_id, claim, source, key, metric, value, unit="", source_hash=None):
        path = root / source
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if source_hash and digest != source_hash:
            raise ValueError(f"Stale evidence: {source}")
        rows.append(
            {
                "value_id": value_id,
                "claim_id": claim,
                "source_table": source,
                "source_hash": digest,
                "row_key_json": key
                if isinstance(key, str)
                else json.dumps(key, ensure_ascii=False, sort_keys=True),
                "metric": metric,
                "raw_value": value,
                "display_report": format_value(value, metric, unit, 3),
                "display_slide": format_value(value, metric, unit, 2),
                "unit": unit,
                "scope": claims.loc[claim, "scope"] if claim in claims.index else "sample",
            }
        )

    for e in evidence.to_dict("records"):
        claim, metric = e["claim_id"], e["metric"]
        value_id = f"{claim}.{metric}"
        if claim == "numeric_replication":
            value_id = f"global.{metric}"
        elif claim == "robustness_direction" and metric.endswith("_count"):
            value_id = "robustness." + metric.removesuffix("_count")
        elif claim == "candidate_registry" and metric.endswith("_count"):
            value_id = "candidate." + ("total" if metric == "candidate_count" else "available")
        elif claim.startswith("ordinal_"):
            value_id = f"R3_{claim.removeprefix('ordinal_')}.{metric}"
        elif claim == "vif_por_R4_MS":
            value_id = "VIF.por_MS"
        elif claim == "literature_gap":
            value_id = f"literature.{metric}"
        elif claim.startswith("mismatch_M10_"):
            parent = claim.removeprefix("mismatch_M10_").removesuffix("_estimate")
            value_id = f"M10.{parent}." + ("original" if metric == "original_value" else "ours")
        elif claim.startswith("R2_"):
            key = json.loads(e["row_key_json"])
            if key.get("variant") == "baseline":
                value_id = f"{claim}.baseline_{metric}"
        # Multiple source rows supporting one claim retain unique identifiers.
        if any(r["value_id"] == value_id for r in rows):
            value_id += f".evidence_{len(rows)}"
        add(
            value_id,
            claim,
            e["source_table"],
            e["row_key_json"],
            metric,
            e["raw_value"],
            e["unit"],
            e["source_hash"],
        )

    def table(name):
        return pd.read_csv(root / f"outputs/tables/{name}.csv", keep_default_na=False)

    verdict = table("final_verdicts")
    global_row = verdict.loc[verdict.model_id == "global"].iloc[0]
    for short, metric in [
        ("complete_models", "complete_match_models"),
        ("partial_models", "partial_match_models"),
    ]:
        add(
            f"global.{short}",
            "numeric_replication",
            "outputs/tables/final_verdicts.csv",
            {"model_id": "global"},
            metric,
            global_row[metric],
            "count",
        )
    for s, row in table("sample_flow").set_index("subject").iterrows():
        for name, metric in [
            ("validated_n", "n_before"),
            ("replication_n", "n_after"),
            ("zero_g3", "g3_zero_after"),
        ]:
            add(
                f"sample.{s}.{name}",
                "scope_limits",
                "outputs/tables/sample_flow.csv",
                {"subject": s, "stage": row.stage},
                metric,
                row[metric],
                "count",
            )
    specs = table("robustness_specifications")
    add(
        "candidate.refused",
        "candidate_registry",
        "outputs/tables/robustness_specifications.csv",
        {"filter": "model_status != available", "aggregation": "count"},
        "refused_count",
        int((specs.model_status != "available").sum()),
        "count",
    )
    summary_path = "docs/evidence/literature_followup/summary.json"
    summary = json.loads((root / summary_path).read_text(encoding="utf-8"))
    add(
        "literature.primary_metadata_direct_count",
        "literature_gap",
        summary_path,
        {"field": "primary_metadata_direct_count"},
        "primary_metadata_direct_count",
        summary["primary_metadata_direct_count"],
        "count",
    )
    add(
        "subgroup.mat_MS.nobs",
        "refusal_mat_MS_Medu",
        "outputs/tables/final_robustness.csv",
        {"subject": "mat", "variant": "R4", "school": "MS", "parent": "Medu"},
        "nobs",
        table("final_robustness")
        .query("subject == 'mat' and variant == 'R4' and school == 'MS' and parent == 'Medu'")
        .iloc[0]
        .nobs,
        "count",
    )
    result = pd.DataFrame(rows, columns=COLUMNS)
    if result.value_id.duplicated().any():
        raise ValueError("Duplicate report value identifiers")
    return result


def create_report_figures(root, assets_dir):
    """Export paired Plotly fragments/static SVG from identical aggregate rows."""
    import matplotlib

    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "parentedu-p08"
    import matplotlib.pyplot as plt
    import plotly.graph_objects as go

    root, assets_dir = Path(root), Path(assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)
    read = lambda name: pd.read_csv(root / f"outputs/tables/{name}.csv")
    hypotheses = read("final_hypotheses")
    robustness = read("final_robustness")
    charts = {}
    for family in ("H1", "H2"):
        charts[family.lower()] = [
            (SUBJECTS[r.subject], r.estimate, r.ci_low, r.ci_high, BLUE)
            for r in hypotheses.loc[hypotheses.family == family].itertuples()
        ]
    charts["robustness"] = []
    selected = robustness.loc[
        (robustness.parent == "Medu") & robustness.variant.isin(["R1", "R2", "R4", "R5"])
    ]
    for r in selected.itertuples():
        label = f"{SUBJECTS[r.subject]} · {r.variant}"
        if pd.notna(r.school):
            label += f" {r.school}"
        label += f" · N={int(r.nobs)}"
        charts["robustness"].append((label, r.estimate, r.ci_low, r.ci_high, BLUE))
    charts["h3"] = []
    for r in hypotheses.loc[hypotheses.family == "H3"].itertuples():
        for name, beta, lo, hi, color in [
            ("База", r.beta_base, r.base_ci_low, r.base_ci_high, GREY),
            ("+ час навчання", r.beta_augmented, r.augmented_ci_low, r.augmented_ci_high, BLUE),
        ]:
            charts["h3"].append((f"{SUBJECTS[r.subject]} · {name}", beta, lo, hi, color))
    charts["placebo"] = [
        (SUBJECTS[r.subject], r.estimate, r.ci_low, r.ci_high, GREY)
        for r in read("robustness_placebo").itertuples()
    ]
    titles = {
        "h1": "Вища проти початкової освіти матері",
        "h2": "Різниця материнського та батьківського контрастів",
        "robustness": "Материнський контраст у перевірках стійкості",
        "h3": "Материнський контраст до та після врахування часу навчання",
        "placebo": "Коефіцієнт фіксованого випадкового noise",
        "education": "Освіта матері: кількість записів у вибірці реплікації",
    }
    outputs = {}
    for stem in (*charts, "education"):
        fig = go.Figure()
        mpl, ax = plt.subplots(figsize=(12.8, 5.2), constrained_layout=True)
        if stem == "education":
            data = read("eda_category_counts")
            data = data.loc[(data.layer == "replication") & (data.variable == "Medu")]
            for subject, color in [("mat", BLUE), ("por", GREY)]:
                part = data.loc[data.subject == subject].sort_values("level")
                labels = part.label.tolist()
                fig.add_bar(x=labels, y=part["count"], name=SUBJECTS[subject], marker_color=color)
                positions = list(range(len(part)))
                shift = -0.2 if subject == "mat" else 0.2
                ax.bar(
                    [p + shift for p in positions],
                    part["count"],
                    0.4,
                    label=SUBJECTS[subject],
                    color=color,
                )
            ax.set_xticks(positions, labels)
            ax.set_ylabel("Кількість записів")
            ax.legend()
            fig.update_layout(yaxis_title="Кількість записів", barmode="group")
        else:
            records = charts[stem]
            for i, (label, beta, low, high, color) in enumerate(records):
                if pd.isna(beta):
                    ax.text(
                        0.02,
                        i,
                        "Не оцінено",
                        transform=ax.get_yaxis_transform(),
                        va="center",
                        color=GREY,
                    )
                    fig.add_annotation(
                        x=0.02,
                        xref="paper",
                        y=label,
                        text="Не оцінено",
                        showarrow=False,
                        xanchor="left",
                    )
                    continue
                fig.add_trace(
                    go.Scatter(
                        x=[beta],
                        y=[label],
                        mode="markers",
                        marker={"color": color, "size": 14},
                        showlegend=False,
                        error_x={
                            "type": "data",
                            "symmetric": False,
                            "array": [high - beta],
                            "arrayminus": [beta - low],
                            "thickness": 3,
                            "width": 8,
                        },
                        hovertemplate="%{y}: %{x:.3f}<extra></extra>",
                    )
                )
                ax.errorbar(
                    beta,
                    i,
                    xerr=[[beta - low], [high - beta]],
                    fmt="o",
                    color=color,
                    capsize=5,
                    linewidth=3,
                    markersize=8,
                )
            labels = [r[0] for r in records]
            ax.set_yticks(range(len(labels)), labels)
            ax.invert_yaxis()
            ax.axvline(0, color=GREY, linestyle="--", linewidth=1.5)
            ax.set_xlabel("Бали G3 · оцінка та 95% CI (HC3)")
            fig.update_yaxes(categoryorder="array", categoryarray=labels[::-1])
            fig.add_vline(x=0, line_dash="dash", line_color=GREY)
            fig.update_xaxes(title="Бали G3 · оцінка та 95% CI (HC3)")
        ax.set_title(titles[stem], fontsize=15, pad=14)
        ax.tick_params(labelsize=11)
        ax.spines[["top", "right"]].set_visible(False)
        fig.update_layout(
            width=1100,
            height=410 if stem == "robustness" else 390,
            template="plotly_white",
            font={"family": "Arial", "size": 20, "color": "#182b3a"},
            margin={"l": 435 if stem == "robustness" else 180, "r": 30, "t": 30, "b": 90},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        paths = {
            kind: assets_dir / f"{stem}.{suffix}"
            for kind, suffix in [("html", "plotly.html"), ("svg", "svg"), ("json", "json")]
        }
        paths["html"].write_text(
            fig.to_html(full_html=False, include_plotlyjs=False, div_id=f"chart-{stem}"),
            encoding="utf-8",
        )
        paths["json"].write_text(fig.to_json(), encoding="utf-8")
        mpl.savefig(paths["svg"], format="svg", metadata={"Date": None})
        plt.close(mpl)
        outputs[stem] = paths
    return outputs
