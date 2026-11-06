"""Pure synthesis of frozen P05/P06 aggregate exports; no model estimation."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from parentedu.robustness_reporting import _read_summary

BASE = {"mat": "M4", "por": "M10"}
MODEL_KEYS = [("mat", f"M{i}") for i in range(1, 5)] + [("por", f"M{i}") for i in range(7, 11)]
SUMMARY_KEYS = ["subject", "base_model_id", "variant", "school", "parent", "term"]
KEYS = {
    "replication_hypotheses": ["subject", "model_id", "family"],
    "replication_verdicts": ["subject", "model_id"],
    "replication_comparison": ["subject", "model_id", "term", "metric"],
    "replication_coefficients": ["subject", "model_id", "variant", "term", "covariance_type"],
    "replication_se_comparison": ["subject", "model_id", "term", "metric", "covariance_type"],
    "robustness_summary": SUMMARY_KEYS,
    "robustness_h3": ["subject", "base_model_id", "variant", "school"],
    "robustness_placebo": ["subject", "base_model_id", "variant", "school", "term"],
    "robustness_specifications": ["subject", "base_model_id", "variant", "school"],
    "robustness_diagnostics": ["subject", "base_model_id", "variant", "school"],
    "robustness_baseline_check": ["subject", "base_model_id", "metric", "term"],
}


def format_value(value, metric="", unit=""):
    """Presentation only; preserve every original CSV token separately."""
    if value is None or str(value) in ("", "nan", "<NA>"):
        return "NA"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(number):
        return "NA"
    if metric.startswith("p_") or metric == "p_value":
        return f"{number:.6g}"
    if unit == "count" or metric in ("nobs", "matched_cells", "total_cells"):
        return str(int(number))
    return f"{number:.3f}"


def _bool(value):
    if value not in ("True", "False"):
        raise ValueError(f"Invalid boolean token: {value}")
    return value == "True"


def _close(actual, expected, message):
    if not np.allclose(
        np.asarray(actual, float),
        np.asarray(expected, float),
        atol=1e-10,
        rtol=1e-10,
        equal_nan=True,
    ):
        raise ValueError(message)


def build_conclusion_tables(table_dir: Path, root: Path) -> dict[str, pd.DataFrame]:
    """Read, validate and synthesize existing exports without writing any files."""
    table_dir, root = Path(table_dir), Path(root)
    raw, hashes = {}, {}
    for name, keys in KEYS.items():
        path = table_dir / f"{name}.csv"
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        if not set(keys).issubset(frame) or frame.duplicated(keys).any():
            raise ValueError(f"Missing/duplicate keys: {name}")
        for column in ("matches", "use_t", "sign_change", "sample_match", "specification_match"):
            if column in frame:
                frame.loc[frame[column].ne(""), column].map(_bool)
        raw[name] = frame
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    summary = _read_summary(table_dir)
    if len(raw["robustness_specifications"]) != 16:
        raise ValueError("Expected complete 16-candidate specification registry")
    expected_specs = {
        (s, BASE[s], v, school)
        for s in BASE
        for v, school in [
            ("baseline", ""),
            ("R1", ""),
            ("R2", ""),
            ("R3", ""),
            ("R4", "GP"),
            ("R4", "MS"),
            ("R5", ""),
            ("placebo", ""),
        ]
    }
    spec_keys = KEYS["robustness_specifications"]
    if (
        set(raw["robustness_specifications"][spec_keys].itertuples(index=False, name=None))
        != expected_specs
    ):
        raise ValueError("Incomplete specification keys")
    verdicts = raw["replication_verdicts"].copy()
    if set(verdicts[["subject", "model_id"]].itertuples(index=False, name=None)) != set(
        MODEL_KEYS + [("all", "global")]
    ):
        raise ValueError("Incomplete model/global verdict keys")
    hypotheses = raw["replication_hypotheses"].copy()
    if set(hypotheses[["subject", "model_id", "family"]].itertuples(index=False, name=None)) != {
        (s, m, h) for s, m in BASE.items() for h in ("H1", "H2")
    }:
        raise ValueError("Incomplete hypothesis keys")
    h3 = raw["robustness_h3"]
    if set(h3[KEYS["robustness_h3"]].itertuples(index=False, name=None)) != {
        (s, m, "R5", "") for s, m in BASE.items()
    }:
        raise ValueError("Incomplete H3 keys")
    placebo = raw["robustness_placebo"]
    if set(placebo[KEYS["robustness_placebo"]].itertuples(index=False, name=None)) != {
        (s, m, "placebo", "", "noise") for s, m in BASE.items()
    }:
        raise ValueError("Incomplete placebo keys")
    checks = raw["robustness_baseline_check"]
    if len(checks) != 4390 or not checks.matches.map(_bool).all():
        raise ValueError("Baseline checks incomplete or failed")
    for check in checks.itertuples():
        try:
            a, b = float(check.expected), float(check.actual)
        except ValueError:
            if check.expected != check.actual:
                raise ValueError("Baseline check values conflict") from None
        else:
            _close([a], [b], "Baseline check values conflict")
    for s, model in BASE.items():
        baseline = summary[(summary.subject == s) & (summary.variant == "baseline")]
        for row in baseline.itertuples():
            source = raw["replication_coefficients"]
            source = source[
                (source.subject == s)
                & (source.model_id == model)
                & (source.term == row.term)
                & (source.variant == "baseline")
                & (source.covariance_type == "HC3")
            ]
            if len(source) != 1:
                raise ValueError("Missing P05 baseline coefficient")
            fields = [
                "estimate",
                "std_error",
                "ci_low",
                "ci_high",
                "p_value",
                "nobs",
                "adjusted_r2",
            ]
            _close(
                [getattr(row, f) for f in fields],
                source.iloc[0][fields],
                "P05/P06 baseline conflict",
            )
        b = baseline[baseline.parent == "Medu"].iloc[0]
        a = summary[
            (summary.subject == s) & (summary.variant == "R5") & (summary.parent == "Medu")
        ].iloc[0]
        h = h3[h3.subject == s].iloc[0]
        fields = [
            "beta_base",
            "beta_augmented",
            "base_ci_low",
            "base_ci_high",
            "augmented_ci_low",
            "augmented_ci_high",
            "nobs",
            "delta_abs",
        ]
        _close(
            h[fields],
            [
                b.estimate,
                a.estimate,
                b.ci_low,
                b.ci_high,
                a.ci_low,
                a.ci_high,
                a.nobs,
                abs(a.estimate) - abs(b.estimate),
            ],
            "H3/summary conflict",
        )
        if _bool(h.sign_change) != bool(np.sign(a.estimate) != np.sign(b.estimate)):
            raise ValueError("H3 sign_change conflict")
    comparison = raw["replication_comparison"]
    if len(comparison) != 84:
        raise ValueError("Incomplete numerical comparison")
    for row in verdicts.itertuples():
        cells = (
            comparison
            if row.subject == "all"
            else comparison[
                (comparison.subject == row.subject) & (comparison.model_id == row.model_id)
            ]
        )
        if len(cells) != int(row.total_cells) or cells.matches.map(_bool).sum() != int(
            row.matched_cells
        ):
            raise ValueError("Verdict/comparison count conflict")
    verdicts["numeric_status"] = verdicts.verdict
    verdicts["inference_status"] = verdicts.original_method
    verdicts["numeric_semantics"] = (
        "N, coefficients and adjusted R2 within original print tolerance; excludes SE"
    )
    verdicts["inference_semantics"] = "Author covariance method not identified; own HC3 is separate"
    verdicts["substantive_semantics"] = (
        "Subject H1/H2 use frozen separate Holm families; H3 descriptive"
    )
    hypotheses["status"] = hypotheses.verdict
    hypotheses["p_delta"] = np.nan
    hypotheses["limitation"] = "Conditional association; separate Holm family; CI not simultaneous"
    h3rows = []
    for row in h3.to_dict("records"):
        delta = float(row["delta_abs"])
        h3rows.append(
            {
                **row,
                "model_id": row["base_model_id"],
                "family": "H3",
                "contrast": "abs(beta_R5)-abs(beta_baseline)",
                "estimate": row["delta_abs"],
                "status": "descriptive_"
                + ("decrease" if delta < 0 else "increase" if delta > 0 else "unchanged"),
                "verdict": "descriptive_only",
                "p_delta": np.nan,
                "limitation": "No test of nested-model difference; no mediation identification",
            }
        )
    hypotheses = pd.concat([hypotheses, pd.DataFrame(h3rows)], ignore_index=True)
    robustness = summary.copy()
    for column in ("baseline_estimate", "delta_beta"):
        robustness[column] = pd.to_numeric(robustness[column], errors="coerce")
    robustness["unit"] = np.where(
        robustness.variant == "R3", "G3 points per education level", "G3 points: education 4 vs 1"
    )
    robustness["direction_denominator"] = (
        robustness.parent.eq("Medu")
        & robustness.variant.isin(["R1", "R2", "R4", "R5"])
        & robustness.status.eq("available")
    )
    claims, evidence = [], []

    def claim(
        cid,
        text,
        kind="result",
        scope="",
        status="reported",
        limitations="association_limits;scope_limits",
    ):
        claims.append(
            {
                "claim_id": cid,
                "text_uk": text,
                "kind": kind,
                "scope": scope,
                "status": status,
                "limitation_ids": limitations,
            }
        )

    def ev(cid, name, row, metric, unit="", **extra):
        value = str(row[metric])
        key = {k: str(row[k]) for k in KEYS[name]}
        display = format_value(value, metric, unit)
        evidence.append(
            dict(
                claim_id=cid,
                evidence_id=f"{cid}:{len(evidence) + 1}",
                source_table=f"outputs/tables/{name}.csv",
                source_hash=hashes[name],
                row_key_json=json.dumps(key, sort_keys=True),
                metric=metric,
                raw_value=value,
                display_value=display,
                unit=unit,
                source_kind="csv",
                filter_json="",
                numerator_rule="",
                denominator_rule="",
                **extra,
            )
        )
        return display

    global_row = verdicts[verdicts.subject == "all"].iloc[0]
    cid = "numeric_replication"
    matched = ev(cid, "replication_verdicts", global_row, "matched_cells", "count")
    total = ev(cid, "replication_verdicts", global_row, "total_cells", "count")
    ev(cid, "replication_verdicts", global_row, "verdict")
    claim(
        cid,
        f"Числова реплікація: {matched}/{total} клітинок; статус {global_row.verdict}. SE не входять до цього вердикту.",
        scope="Table 8",
    )
    failures = comparison[~comparison.matches.map(_bool)]
    for row in failures.to_dict("records"):
        cid = f"mismatch_{row['model_id']}_{row['term']}_{row['metric']}"
        orig = ev(cid, "replication_comparison", row, "original_value", "G3 points")
        ours = ev(cid, "replication_comparison", row, "replicated_value", "G3 points")
        claim(
            cid,
            f"{row['model_id']} {row['term']}: опубліковано {orig}, у нас {ours}; незбіг лишається невирішеним, можлива перестановка підписів не встановлена.",
            scope=row["model_id"],
            status="unresolved",
        )
    for row in raw["replication_hypotheses"].to_dict("records"):
        cid = f"{row['family']}_{row['subject']}"
        ev(cid, "replication_hypotheses", row, "verdict")
        vals = {
            m: ev(
                cid,
                "replication_hypotheses",
                row,
                m,
                "G3 points" if m in ("estimate", "ci_low", "ci_high") else "probability",
            )
            for m in ("estimate", "ci_low", "ci_high", "p_value", "p_holm")
        }
        nrow = raw["robustness_summary"]
        nrow = nrow[
            (nrow.subject == row["subject"])
            & (nrow.variant == "baseline")
            & (nrow.parent == "Medu")
        ].iloc[0]
        n = ev(cid, "robustness_summary", nrow, "nobs", "count")
        outcome = (
            "очікування підтримано"
            if row["verdict"] == "expected_supported"
            else "недостатньо доказів очікуваної різниці"
            if row["verdict"] == "insufficient_evidence"
            else row["verdict"]
        )
        interpretation = (
            "Вища проти початкової освіти матері за однакової освіти батька й контролів."
            if row["family"] == "H1"
            else "Різниця материнського та батьківського контрастів вищої проти початкової освіти; прямий тест рівності коефіцієнтів."
        )
        claim(
            cid,
            f"{row['subject']} {row['family']}: {outcome}; оцінка {vals['estimate']}, CI [{vals['ci_low']}; {vals['ci_high']}], raw p={vals['p_value']}, Holm p={vals['p_holm']}, N={n}. {interpretation}",
            scope=row["subject"],
            status=row["verdict"],
        )
    for row in h3.to_dict("records"):
        cid = f"H3_{row['subject']}"
        vals = {
            m: ev(cid, "robustness_h3", row, m, "G3 points")
            for m in (
                "beta_base",
                "beta_augmented",
                "delta_abs",
                "base_ci_low",
                "base_ci_high",
                "augmented_ci_low",
                "augmented_ci_high",
            )
        }
        claim(
            cid,
            f"{row['subject']} H3: beta {vals['beta_base']} → {vals['beta_augmented']}; Δ|beta|={vals['delta_abs']}; CI бази [{vals['base_ci_low']}; {vals['base_ci_high']}], R5 [{vals['augmented_ci_low']}; {vals['augmented_ci_high']}]. Це описова зміна після studytime, без p зміни та висновку про медіацію.",
            scope=row["subject"],
            status="descriptive_only",
        )
    mask = robustness.direction_denominator
    eligible = robustness[mask]
    cid = "robustness_direction"
    keys = []
    for row in raw["robustness_summary"].to_dict("records"):
        if (
            row["parent"] == "Medu"
            and row["variant"] in ("R1", "R2", "R4", "R5")
            and row["status"] == "available"
        ):
            ev(cid, "robustness_summary", row, "estimate", "G3 points")
            keys.append({k: row[k] for k in SUMMARY_KEYS})
    numerator, denominator = int((eligible.estimate > 0).sum()), len(eligible)
    for metric, value in (("positive_count", numerator), ("available_count", denominator)):
        evidence.append(
            {
                "claim_id": cid,
                "evidence_id": f"{cid}:{len(evidence) + 1}",
                "source_table": "outputs/tables/robustness_summary.csv",
                "source_hash": hashes["robustness_summary"],
                "row_key_json": json.dumps(keys, sort_keys=True),
                "metric": metric,
                "raw_value": str(value),
                "display_value": str(value),
                "unit": "count",
                "source_kind": "csv_aggregate",
                "filter_json": json.dumps(
                    {"parent": "Medu", "variant": ["R1", "R2", "R4", "R5"], "status": "available"},
                    sort_keys=True,
                ),
                "numerator_rule": "count(estimate > 0)",
                "denominator_rule": "count(available categorical maternal R1/R2/R4/R5 rows); exclude baseline,R3,placebo,refusals",
            }
        )
    claim(
        cid,
        f"Додатний знак Medu_4 у {numerator}/{denominator} оцінюваних категоріальних R1/R2/R4/R5; це не незалежні підтвердження та не вимога значущості кожного варіанта.",
        scope="categorical sensitivity",
    )
    for row in raw["robustness_summary"].to_dict("records"):
        if row["status"] == "not_estimable":
            cid = f"refusal_{row['subject']}_{row['school']}_{row['parent']}"
            n = ev(cid, "robustness_summary", row, "nobs", "count")
            reason = ev(cid, "robustness_summary", row, "reason")
            claim(
                cid,
                f"{row['subject']}/{row['school']} {row['parent']}: N={n}, not_estimable: {reason}. Відмова не свідчить про відсутність зв'язку.",
                scope="R4",
                status="not_estimable",
            )
        elif row["variant"] == "R3":
            cid = f"ordinal_{row['subject']}_{row['parent']}"
            vals = {
                m: ev(cid, "robustness_summary", row, m, "G3 points per education level")
                for m in ("estimate", "ci_low", "ci_high")
            }
            claim(
                cid,
                f"R3 {row['subject']} {row['parent']}: {vals['estimate']} бала G3 на рівень освіти, CI [{vals['ci_low']}; {vals['ci_high']}]. Інший estimand; delta до категоріальної бази відсутня.",
                scope="R3",
            )
        elif row["variant"] == "R4" and row["school"] == "MS":
            cid = f"subgroup_{row['subject']}_{row['parent']}"
            low, high = [
                ev(cid, "robustness_summary", row, m, "G3 points") for m in ("ci_low", "ci_high")
            ]
            claim(
                cid,
                f"{row['subject']}/MS {row['parent']}: широкий CI [{low}; {high}]; точність підгруп обмежена, рівність шкіл не перевірялася.",
                scope="R4",
            )
    for row in raw["robustness_diagnostics"].to_dict("records"):
        if row["max_vif"] and float(row["max_vif"]) > 5:
            cid = f"vif_{row['subject']}_{row['variant']}_{row['school']}"
            v = ev(cid, "robustness_diagnostics", row, "max_vif", "VIF")
            claim(
                cid,
                f"{row['subject']} {row['variant']} {row['school']}: max VIF={v}; корельовані предиктори обмежують точність, це сигнал огляду.",
                kind="diagnostic",
                scope="sensitivity",
            )
    for subject in BASE:
        cid = f"R2_{subject}"
        rows = raw["robustness_summary"]
        values = {}
        for variant in ("baseline", "R2"):
            row = rows[
                (rows.subject == subject) & (rows.variant == variant) & (rows.parent == "Medu")
            ].iloc[0]
            values[variant] = {
                m: ev(cid, "robustness_summary", row, m, "count" if m == "nobs" else "G3 points")
                for m in ("nobs", "estimate", "ci_low", "ci_high")
            }
        b, a = values["baseline"], values["R2"]
        claim(
            cid,
            f"R2 {subject}: після виключення нульових G3 N {b['nobs']} → {a['nobs']}; Medu_4 {b['estimate']} → {a['estimate']}, CI R2 [{a['ci_low']}; {a['ci_high']}]. Змінюється склад вибірки, це окрема чутливість.",
            scope="R2",
        )
        row = raw["robustness_diagnostics"]
        row = row[(row.subject == subject) & (row.variant == "R1")].iloc[0]
        cid = f"rare_zero_{subject}"
        lev = ev(cid, "robustness_diagnostics", row, "max_leverage", "leverage")
        counts = {
            m: ev(cid, "robustness_diagnostics", row, m, "count") for m in ("Medu_0_n", "Fedu_0_n")
        }
        claim(
            cid,
            f"R1 {subject}: категорія без освіти рідкісна (Medu: {counts['Medu_0_n']}, Fedu: {counts['Fedu_0_n']}); max leverage={lev}. Рідкісні категорії можуть створювати впливові спостереження; це не автоматичне правило виключення.",
            kind="diagnostic",
            scope="R1",
        )
    registry = raw["robustness_specifications"]
    cid = "candidate_registry"
    for row in registry.to_dict("records"):
        ev(cid, "robustness_specifications", row, "model_status")
    available = int(registry.model_status.eq("available").sum())
    claim(
        cid,
        f"Реєстр містить {len(registry)} кандидатів, оцінено {available}; відмови збережено явно. База й placebo не входять у знаменник напряму категоріальної стійкості.",
        scope="P06 registry",
    )
    for metric, value in (("candidate_count", len(registry)), ("available_count", available)):
        evidence.append(
            {
                "claim_id": cid,
                "evidence_id": f"{cid}:{metric}",
                "source_table": "outputs/tables/robustness_specifications.csv",
                "source_hash": hashes["robustness_specifications"],
                "row_key_json": json.dumps(
                    registry[KEYS["robustness_specifications"]].to_dict("records"), sort_keys=True
                ),
                "metric": metric,
                "raw_value": str(value),
                "display_value": str(value),
                "unit": "count",
                "source_kind": "csv_aggregate",
                "filter_json": "{}",
                "numerator_rule": "count(model_status == available)",
                "denominator_rule": "count(all specification candidates)",
            }
        )
    for row in placebo.to_dict("records"):
        cid = f"placebo_{row['subject']}"
        vals = {
            m: ev(
                cid,
                "robustness_placebo",
                row,
                m,
                "probability" if m == "p_value" else "G3 points per noise unit",
            )
            for m in ("estimate", "ci_low", "ci_high", "p_value")
        }
        claim(
            cid,
            f"{row['subject']} noise: beta={vals['estimate']}, CI [{vals['ci_low']}; {vals['ci_high']}], raw p={vals['p_value']}. Один фіксований вектор на предмет; це не доказ відсутності confounding або коректності всього дизайну.",
            scope="placebo",
        )
    protocol = root / "docs/replication_protocol.md"
    policies = {
        "author_inference": "Авторський SE/inference: not_identified. Числові збіги SE під HC3/nonrobust/HC1 не встановлюють авторський метод.",
        "association_limits": "Це умовні асоціації: невиміряні здібності, ресурси, очікування, шкільний відбір і помилки самозвітів залишають альтернативні пояснення. Контролі та studytime не усувають їх повністю.",
        "scope_limits": "Узагальнення обмежене двома школами Португалії та історичним набором; учні між предметами можуть перетинатися. N предметів не додаються як кількість різних людей.",
        "inference_limits": "Власний inference умовний щодо відібраної автором специфікації. Holm контролює окремі сімейства H1/H2; p/CI стійкості описові, CI не одночасні. Незначущість не доводить рівності або відсутності зв'язку.",
    }
    for cid, text in policies.items():
        claim(
            cid,
            text,
            kind="limitation",
            scope="protocol",
            status="not_identified" if cid == "author_inference" else "applies",
        )
        if cid == "author_inference":
            ev(cid, "replication_verdicts", global_row, "original_method")
        section = {
            "author_inference": "Власний inference та невідомі SE оригіналу",
            "association_limits": "Гіпотези й альтернативні пояснення",
            "scope_limits": "Джерело, вибірка й одиниця спостереження",
            "inference_limits": "Власний inference та невідомі SE оригіналу",
        }[cid]
        protocol_section = (
            protocol.read_text(encoding="utf-8")
            .split(f"## {section}\n", 1)[1]
            .split("\n## ", 1)[0]
            .strip()
        )
        evidence.append(
            {
                "claim_id": cid,
                "evidence_id": f"{cid}:policy",
                "source_table": "docs/replication_protocol.md",
                "source_hash": hashlib.sha256(protocol.read_bytes()).hexdigest(),
                "row_key_json": json.dumps(
                    {
                        "section": {
                            "author_inference": "Власний inference та невідомі SE оригіналу",
                            "association_limits": "Гіпотези й альтернативні пояснення",
                            "scope_limits": "Джерело, вибірка й одиниця спостереження",
                            "inference_limits": "Власний inference та невідомі SE оригіналу",
                        }[cid]
                    }
                ),
                "metric": "section_interpretation",
                "raw_value": protocol_section,
                "display_value": text,
                "unit": "",
                "source_kind": "protocol_interpretation",
                "filter_json": "",
                "numerator_rule": "",
                "denominator_rule": "",
            }
        )
    literature_csv = root / "docs/literature.csv"
    literature_rows = pd.read_csv(literature_csv, dtype=str, keep_default_na=False)
    if literature_rows.id.duplicated().any() or set(literature_rows.id) != {
        "L01",
        "L02",
        "L03",
        "L04",
    }:
        raise ValueError("Incomplete literature registry")
    for row in literature_rows.to_dict("records"):
        cid = f"literature_{row['id']}"
        text = (
            f"{row['authors']} ({row['year']}): {row['verified_result']} "
            f"Дизайн: {row['method']} Популяція: {row['population_data']} "
            f"Зіставлення з нами: {row['relevance_to_design']} "
            f"Межі: {row['limitations_for_our_design']} Статус зв’язку: {row['relation_to_original']}. "
            f"DOI: {row['doi']}; доступ: {row['access_status']}"
        )
        claim(cid, text, kind="literature", scope=row["id"], status=row["relation_to_original"])
        for metric in (
            "authors",
            "year",
            "verified_result",
            "method",
            "population_data",
            "relevance_to_design",
            "limitations_for_our_design",
            "relation_to_original",
            "doi",
            "access_status",
        ):
            value = row[metric]
            evidence.append(
                {
                    "claim_id": cid,
                    "evidence_id": f"{cid}:{metric}",
                    "source_table": "docs/literature.csv",
                    "source_hash": hashlib.sha256(literature_csv.read_bytes()).hexdigest(),
                    "row_key_json": json.dumps({"id": row["id"]}),
                    "metric": metric,
                    "raw_value": value,
                    "display_value": value,
                    "unit": "",
                    "source_kind": "csv",
                    "filter_json": "",
                    "numerator_rule": "",
                    "denominator_rule": "",
                    "evidence_location": row["evidence_location"],
                    "evidence_url": row["evidence_url"],
                }
            )
    literature_path = root / "docs/evidence/literature_followup/summary.json"
    literature = json.loads(literature_path.read_text(encoding="utf-8"))
    cid = "literature_gap"
    count, required = literature["verified_direct_count"], literature["required_min"]
    claim(
        cid,
        f"Перевірено прямих цитувань (це не перевірки освітнього результату): {count}; мінімальна вимога citing/checking: {required}; статус {literature['status']}. Пошук обмежений доступними індексами/текстами; це не доказ відсутності праць у світі. Тематичні роботи не замінюють прямих перевірок; країни, вік, дизайн і шкали не дають підстав об'єднувати ефекти.",
        kind="literature",
        scope=str(literature["search_scope"]),
        status=literature["status"],
    )
    if "substantive_checking_count" in literature:
        cid = "literature_checking"
        checking = literature["substantive_checking_count"]
        claim(
            cid,
            f"Підтверджених змістових перевірок результатів Da в цьому пошуку: {checking}. Саме цитування в іншій предметній області не є освітньою реплікацією.",
            kind="literature",
            scope=str(literature["search_scope"]),
            status="unresolved",
        )
        evidence.append(
            {
                "claim_id": cid,
                "evidence_id": f"{cid}:count",
                "source_table": "docs/evidence/literature_followup/summary.json",
                "source_hash": hashlib.sha256(literature_path.read_bytes()).hexdigest(),
                "row_key_json": json.dumps({"field": "substantive_checking_count"}),
                "metric": "substantive_checking_count",
                "raw_value": str(checking),
                "display_value": str(checking),
                "unit": "count",
                "source_kind": "json",
                "filter_json": "",
                "numerator_rule": "",
                "denominator_rule": "",
            }
        )
    cid = "literature_gap"
    for metric in ("verified_direct_count", "required_min", "status", "search_scope"):
        value = str(literature[metric])
        evidence.append(
            {
                "claim_id": cid,
                "evidence_id": f"{cid}:{metric}",
                "source_table": "docs/evidence/literature_followup/summary.json",
                "source_hash": hashlib.sha256(literature_path.read_bytes()).hexdigest(),
                "row_key_json": json.dumps({"field": metric}),
                "metric": metric,
                "raw_value": value,
                "display_value": value,
                "unit": "count" if metric in ("verified_direct_count", "required_min") else "",
                "source_kind": "json",
                "filter_json": "",
                "numerator_rule": "",
                "denominator_rule": "",
            }
        )
    return {
        "hypotheses": hypotheses,
        "verdicts": verdicts,
        "robustness": robustness,
        "claims": pd.DataFrame(claims),
        "claim_evidence": pd.DataFrame(evidence),
    }
