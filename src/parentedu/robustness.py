"""Наперед визначені перевірки стійкості; функції не записують артефактів."""

import hashlib
import json

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

from parentedu.models import fit_model


class NotEstimableError(ValueError):
    """Очікувана технічна відмова фіксованої шкільної матриці."""


def select_variant_frame(layers, subject, variant, school=""):
    """Кожний варіант починається з власного незмінного шару."""
    frame = layers["validated" if variant == "R1" else "replication"][subject]
    if variant == "R2":
        frame = frame.loc[frame.G3.ne(0)]
    elif variant == "R4":
        if school not in ("MS", "GP"):
            raise ValueError("R4 потребує школу MS/GP")
        frame = frame.loc[frame.school.eq(school)]
    elif variant not in ("baseline", "R1", "R3", "R5", "placebo"):
        raise ValueError("Невідомий варіант")
    return frame.copy(deep=True)


def build_variant_design(frame, definition, config, variant, noise=None):
    """Явні фіксовані категорії; відсутні рівні не перекодовуються."""
    controls = list(definition["controls"])
    if variant == "R4":
        controls.remove("school")
    if variant == "R5":
        controls.append("studytime")
    required = ["record_id", "subject", "Medu", "Fedu", "G3", *controls]
    if not set(required) <= set(frame) or frame[required].isna().any().any():
        raise ValueError("Відсутні колонки або пропуски")
    if frame.record_id.duplicated().any() or not frame.subject.eq(definition["subject"]).all():
        raise ValueError("Невірні record_id/subject")
    X = pd.DataFrame({"intercept": np.ones(len(frame))}, index=frame.index)
    levels = [0, 1, 2, 3, 4] if variant == "R1" else [1, 2, 3, 4]
    for parent in ("Medu", "Fedu"):
        if not frame[parent].isin(levels).all():
            raise ValueError("Невідомі коди освіти")
        if variant == "R3":
            X[f"{parent}_ordinal"] = frame[parent].astype(float)
        else:
            for level in levels:
                if level != 1:
                    X[f"{parent}_{level}"] = frame[parent].eq(level).astype(float)
    categories = {
        "sex": ["M", "F"],
        "school": ["MS", "GP"],
        "guardian": ["other", "mother", "father"],
        "studytime": [1, 2, 3, 4],
    }
    for control in controls:
        if control == "age":
            X[control] = pd.to_numeric(frame[control], errors="raise").astype(float)
        else:
            values = categories[control]
            if not frame[control].isin(values).all():
                raise ValueError(f"Невідомі коди {control}")
            reference = 1 if control == "studytime" else config["reference_categories"][control]
            for value in values:
                if value != reference:
                    X[f"{control}_{value}"] = frame[control].eq(value).astype(float)
    if variant == "placebo":
        if noise is None or len(noise) != len(frame):
            raise ValueError("Потрібен noise у порядку baseline")
        X["noise"] = np.asarray(noise)
    y = pd.to_numeric(frame.G3, errors="raise").astype(float)
    if not np.isfinite(X.to_numpy()).all() or not np.isfinite(y).all():
        raise ValueError("Нескінченні X/y")
    return X, y


def fit_variant(frame, definition, config, variant, noise=None):
    """OLS HC3/normal з перевіркою технічної оцінюваності до fit."""
    X, y = build_variant_design(frame, definition, config, variant, noise)
    matrix = X.to_numpy()
    n, p = matrix.shape
    rank = int(np.linalg.matrix_rank(matrix))
    if rank != p:
        raise NotEstimableError("rank_deficient")
    if n - rank <= 0:
        raise NotEstimableError("nonpositive_residual_df")
    leverage = np.einsum("ij,ji->i", matrix, np.linalg.pinv(matrix))
    if leverage.max() >= config["robustness"]["max_leverage"]:
        raise NotEstimableError("max_leverage")
    result = sm.OLS(y, X, missing="raise").fit(cov_type="HC3", use_t=False)
    for values in (
        result.params,
        result.bse,
        result.cov_params(),
        result.conf_int(),
        result.pvalues,
    ):
        if not np.isfinite(np.asarray(values)).all():
            raise NotEstimableError("nonfinite_inference")
    influence = sm.OLS(y, X, missing="raise").fit().get_influence()
    cooks = influence.cooks_distance[0]
    if not np.isfinite(cooks).all():
        raise NotEstimableError("nonfinite_cooks_distance")
    vif = pd.DataFrame(
        [
            {"term": term, "vif": variance_inflation_factor(matrix, i)}
            for i, term in enumerate(X)
            if term != "intercept"
        ]
    )
    vif["flag"] = vif.vif > config["diagnostics"]["vif_flag"]
    vif["status"] = np.where(np.isfinite(vif.vif), "available", "not_finite")
    diagnostics = {
        "nobs": n,
        "n_parameters": p,
        "rank": rank,
        "df_resid": n - rank,
        "max_leverage": float(leverage.max()),
        "leverage_threshold": 2 * p / n,
        "leverage_flag_count": int((leverage > 2 * p / n).sum()),
        "max_cooks_distance": float(cooks.max()),
        "cooks_threshold": 4 / n,
        "cooks_flag_count": int((cooks > 4 / n).sum()),
        "max_vif": float(vif.vif.max()),
        "vif_flag_count": int(vif.flag.sum()),
    }
    rows = pd.DataFrame(
        {
            "record_id": frame.record_id.to_numpy(),
            "fitted": result.fittedvalues,
            "residual": result.resid,
            "leverage": leverage,
            "cooks_distance": cooks,
        }
    )
    return {
        "X": X,
        "y": y,
        "result": result,
        "vif": vif,
        "diagnostics": diagnostics,
        "row_diagnostics": rows,
        "summary": {"nobs": n, "adjusted_r2": result.rsquared_adj},
    }


def h3_change(beta_base, beta_augmented):
    """Описова зміна абсолютної оцінки, без тесту різниці."""
    return {
        "delta_abs": abs(beta_augmented) - abs(beta_base),
        "sign_change": bool(np.sign(beta_base) != np.sign(beta_augmented)),
    }


def _coefficient(result, term, config):
    ci = result.conf_int(alpha=1 - config["inference"]["confidence_level"])
    return {
        "term": term,
        "estimate": result.params[term],
        "std_error": result.bse[term],
        "ci_low": ci.loc[term, 0],
        "ci_high": ci.loc[term, 1],
        "p_value": result.pvalues[term],
        "nobs": int(result.nobs),
        "adjusted_r2": result.rsquared_adj,
        "covariance_type": "HC3",
        "use_t": False,
    }


def build_robustness_tables(layers, config):
    """Повернути 16 кандидатів та всі таблиці в пам'яті, без зміни входів."""
    collected = {
        key: []
        for key in (
            "specifications",
            "coefficients",
            "summary",
            "diagnostics",
            "vif",
            "h3",
            "placebo",
            "membership",
            "row_diagnostics",
            "noise",
        )
    }
    changes = {
        "baseline": "unchanged",
        "R1": "include_education_zero",
        "R2": "exclude_G3_zero",
        "R3": "ordinal_education",
        "R4": "separate_schools",
        "R5": "add_studytime",
        "placebo": "add_independent_normal_noise",
    }
    for subject in config["replication"]["subjects"]:
        definition = next(
            d
            for d in config["models"]
            if d["subject"] == subject and d["id"] in config["robustness"]["base_models"]
        )
        base = fit_model(layers["replication"][subject], definition, config)
        for variant, school in [
            ("baseline", ""),
            ("R1", ""),
            ("R2", ""),
            ("R3", ""),
            ("R4", "MS"),
            ("R4", "GP"),
            ("R5", ""),
            ("placebo", ""),
        ]:
            keys = {
                "subject": subject,
                "base_model_id": definition["id"],
                "variant": variant,
                "school": school,
            }
            frame = select_variant_frame(layers, subject, variant, school)
            noise, noise_meta = None, {}
            if variant == "placebo":
                i = config["placebo"]["subject_order"].index(subject)
                seed = config["project"]["seed"] + config["placebo"]["seed_offsets"][i]
                noise = np.random.default_rng(seed).normal(size=len(frame))
                local = pd.DataFrame(
                    {"record_id": frame.record_id.to_numpy(), "noise": noise, "seed": seed}
                )
                digest = hashlib.sha256(
                    local[["record_id", "noise"]]
                    .to_csv(index=False, float_format="%.17g", lineterminator="\n")
                    .encode()
                ).hexdigest()
                noise_meta = {
                    "seed": seed,
                    "rng": "numpy.random.default_rng/PCG64",
                    "order_noise_sha256": digest,
                }
                collected["noise"].extend(local.assign(**keys).to_dict("records"))
            counts = {
                parent: (int(frame[parent].eq(1).sum()), int(frame[parent].eq(4).sum()))
                for parent in ("Medu", "Fedu")
            }
            reason = ""
            if variant == "R4":
                if len(frame) < config["robustness"]["min_subgroup_n"]:
                    reason = "min_subgroup_n"
                elif all(
                    min(c) < config["robustness"]["min_compared_category_n"]
                    for c in counts.values()
                ):
                    reason = "min_compared_category_n"
            X, _y = build_variant_design(frame, definition, config, variant, noise)
            fitted = None
            if not reason:
                if variant == "baseline":
                    fitted = base
                else:
                    try:
                        fitted = fit_variant(frame, definition, config, variant, noise)
                    except NotEstimableError as exc:
                        if variant != "R4":
                            raise
                        reason = str(exc)
            status = "available" if fitted is not None else "not_estimable"
            spec = {
                **keys,
                "input_layer": "validated" if variant == "R1" else "replication",
                "change": changes[variant],
                "nobs": len(frame),
                "model_status": status,
                "reason": reason,
                "terms": json.dumps(list(X)),
                "formula": "G3 ~ " + " + ".join(X),
                "estimand": "ordinal_per_level" if variant == "R3" else "categorical_4_vs_1",
            }
            if fitted is not None:
                spec["adjusted_r2"] = fitted["result"].rsquared_adj
            collected["specifications"].append(spec)
            collected["membership"].extend(
                frame[["record_id"]]
                .assign(**keys, row_order=np.arange(len(frame)), model_status=status)
                .to_dict("records")
            )
            diagnostic = {
                "nobs": len(frame),
                "n_parameters": X.shape[1],
                "rank": int(np.linalg.matrix_rank(X.to_numpy())) if len(frame) else 0,
                "df_resid": len(frame) - int(np.linalg.matrix_rank(X.to_numpy()))
                if len(frame)
                else 0,
            }
            diagnostic.update(
                {
                    f"{parent}_{level}_n": int(frame[parent].eq(level).sum())
                    for parent in ("Medu", "Fedu")
                    for level in range(5)
                }
            )
            if fitted is not None:
                diagnostic.update(fitted["diagnostics"])
                for kind in ("vif", "row_diagnostics"):
                    collected[kind].extend(fitted[kind].assign(**keys).to_dict("records"))
                for term in fitted["X"]:
                    collected["coefficients"].append(
                        {**keys, **_coefficient(fitted["result"], term, config)}
                    )
            collected["diagnostics"].append(
                {**keys, **diagnostic, "model_status": status, "reason": reason}
            )
            if variant == "placebo":
                collected["placebo"].append(
                    {
                        **keys,
                        **_coefficient(fitted["result"], "noise", config),
                        **noise_meta,
                        "model_status": status,
                    }
                )
                continue
            for parent in ("Medu", "Fedu"):
                term = f"{parent}_ordinal" if variant == "R3" else f"{parent}_4"
                contrast_reason = reason
                if (
                    fitted is not None
                    and variant == "R4"
                    and min(counts[parent]) < config["robustness"]["min_compared_category_n"]
                ):
                    contrast_reason = "min_compared_category_n"
                row = {
                    **keys,
                    "parent": parent,
                    "term": term,
                    "estimand": spec["estimand"],
                    "nobs": len(frame),
                    "reference_n": counts[parent][0],
                    "target_n": counts[parent][1],
                    "model_status": status,
                    "status": "not_estimable" if contrast_reason else "available",
                    "reason": contrast_reason,
                    "comparison_reason": "incomparable_estimand" if variant == "R3" else "",
                    "baseline_estimate": base["result"].params[f"{parent}_4"],
                    "delta_beta": np.nan,
                }
                row.update(
                    dict.fromkeys(("estimate", "std_error", "ci_low", "ci_high", "p_value"), np.nan)
                )
                if not contrast_reason:
                    row.update(_coefficient(fitted["result"], term, config))
                    if variant != "R3":
                        row["delta_beta"] = row["estimate"] - row["baseline_estimate"]
                collected["summary"].append(row)
            if variant == "R5":
                before = _coefficient(base["result"], "Medu_4", config)
                after = _coefficient(fitted["result"], "Medu_4", config)
                collected["h3"].append(
                    {
                        **keys,
                        "beta_base": before["estimate"],
                        "beta_augmented": after["estimate"],
                        "base_ci_low": before["ci_low"],
                        "base_ci_high": before["ci_high"],
                        "augmented_ci_low": after["ci_low"],
                        "augmented_ci_high": after["ci_high"],
                        "nobs": len(frame),
                        **h3_change(before["estimate"], after["estimate"]),
                    }
                )
    return {key: pd.DataFrame(rows) for key, rows in collected.items()}
