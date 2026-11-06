"""Явні OLS-специфікації та діагностика за зафіксованим протоколом."""

import json

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.outliers_influence import variance_inflation_factor


def build_design(frame, definition, config):
    """Побудувати X/y без видалення або перестановки рядків."""
    controls = definition["controls"]
    allowed = {"age", "sex", "school", "guardian"}
    if len(set(controls)) != len(controls) or not set(controls) <= allowed:
        raise ValueError("Невідомі або повторені controls")
    required = ["record_id", "subject", "Medu", "Fedu", config["replication"]["outcome"]]
    required += controls
    if not set(required) <= set(frame):
        raise ValueError("Відсутні обов'язкові колонки")
    if frame[required].isna().any().any():
        raise ValueError("Пропуски: silent dropping заборонено")
    subject = definition["subject"]
    if not frame["subject"].eq(subject).all() or frame["record_id"].duplicated().any():
        raise ValueError("Невірний subject або повторені record_id")
    if len(frame) != config["expected_sample"][subject]:
        raise ValueError("N не відповідає зафіксованій вибірці")
    if not config["replication"]["intercept"]:
        raise ValueError("Протокол вимагає intercept")
    X = pd.DataFrame({"intercept": np.ones(len(frame))}, index=frame.index)
    levels = config["replication"]["education_levels"]
    reference = config["replication"]["education_reference"]
    for parent in ("Medu", "Fedu"):
        if set(frame[parent].unique()) != set(levels):
            raise ValueError(f"Неповні або невідомі категорії {parent}")
        for level in levels:
            if level != reference:
                X[f"{parent}_{level}"] = frame[parent].eq(level).astype(float)
    categories = {
        "sex": ["M", "F"],
        "school": ["MS", "GP"],
        "guardian": ["other", "mother", "father"],
    }
    for control in controls:
        if control == "age":
            X[control] = pd.to_numeric(frame[control], errors="raise").astype(float)
        else:
            values = categories[control]
            if set(frame[control].unique()) != set(values):
                raise ValueError(f"Неповні або невідомі категорії {control}")
            reference = config["reference_categories"][control]
            for value in values:
                if value != reference:
                    X[f"{control}_{value}"] = frame[control].eq(value).astype(float)
    y = pd.to_numeric(frame[config["replication"]["outcome"]], errors="raise").astype(float)
    if not np.isfinite(X.to_numpy()).all() or not np.isfinite(y.to_numpy()).all():
        raise ValueError("Нескінченні або нечислові X/y")
    return X, y


def fit_model(frame, definition, config):
    """OLS з HC3/normal inference та обмеженою covariance-чутливістю."""
    X, y = build_design(frame, definition, config)
    matrix = X.to_numpy()
    n, p = matrix.shape
    rank = int(np.linalg.matrix_rank(matrix))
    if rank != p:
        raise ValueError("Матриця X не має повного рангу")
    if n - rank <= 0:
        raise ValueError("Непозитивні залишкові df")
    leverage = np.einsum("ij,ji->i", matrix, np.linalg.pinv(matrix))
    if leverage.max() >= config["robustness"]["max_leverage"]:
        raise ValueError("Leverage перевищує допустиму межу")
    covariances = {}
    for covariance in ("HC3", "nonrobust", "HC1"):
        result = sm.OLS(y, X, missing="raise").fit(cov_type=covariance, use_t=False)
        for values in (
            result.params,
            result.bse,
            result.cov_params(),
            result.conf_int(),
            result.pvalues,
        ):
            if not np.isfinite(np.asarray(values)).all():
                raise ValueError("Нескінченні результати inference")
        covariances[covariance] = result
    result = covariances["HC3"]
    influence = covariances["nonrobust"].get_influence()
    cooks = influence.cooks_distance[0]
    if not np.isfinite(cooks).all():
        raise ValueError("Нескінченний Cook distance")
    summary = {
        "nobs": n,
        "n_parameters": p,
        "rank": rank,
        "df_resid": n - rank,
        "r_squared": result.rsquared,
        "adjusted_r2": result.rsquared_adj,
        "terms": json.dumps(list(X.columns)),
        "formula": f"{y.name} ~ " + " + ".join(X.columns),
    }
    vif = pd.DataFrame(
        [
            {"term": term, "vif": variance_inflation_factor(matrix, index)}
            for index, term in enumerate(X.columns)
            if term != "intercept"
        ]
    )
    vif["flag"] = vif["vif"] > config["diagnostics"]["vif_flag"]
    vif["status"] = np.where(np.isfinite(vif["vif"]), "available", "not_finite")
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
        "max_vif": float(vif["vif"].max()),
        "vif_flag_count": int(vif["flag"].sum()),
    }
    rows = pd.DataFrame(
        {
            "record_id": frame["record_id"].to_numpy(),
            "fitted": np.asarray(result.fittedvalues),
            "residual": np.asarray(result.resid),
            "leverage": leverage,
            "cooks_distance": cooks,
        }
    )
    return {
        "X": X,
        "y": y,
        "result": result,
        "covariance_results": covariances,
        "summary": summary,
        "diagnostics": diagnostics,
        "vif": vif,
        "row_diagnostics": rows,
    }


def smoke_check_m1(frame, config):
    """Незалежно перевірити M1 через lstsq до решти моделей."""
    definition = next(model for model in config["models"] if model["id"] == "M1")
    fitted = fit_model(frame, definition, config)
    X, y = fitted["X"], fitted["y"]
    beta = np.linalg.lstsq(X.to_numpy(), y.to_numpy(), rcond=None)[0]
    np.testing.assert_allclose(fitted["result"].params, beta, rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose(fitted["result"].fittedvalues, X @ beta, atol=1e-10)
    np.testing.assert_allclose(fitted["result"].resid, y - X @ beta, atol=1e-10)
    return fitted


def contrast_test(result, weights, confidence_level=0.95, distribution="chi2"):
    """Прямий контраст із повною covariance, без припущення незалежності beta."""
    vector = np.array([weights.get(term, 0.0) for term in result.model.exog_names])
    if set(weights) - set(result.model.exog_names):
        raise ValueError("Контраст містить відсутній терм")
    estimate = float(vector @ np.asarray(result.params))
    variance = float(vector @ np.asarray(result.cov_params()) @ vector)
    if not np.isfinite(variance) or variance <= 0:
        raise ValueError("Контраст неоцінюваний")
    se = np.sqrt(variance)
    z = estimate / se
    critical = stats.norm.ppf((1 + confidence_level) / 2)
    statistic = z * z if distribution == "chi2" else z
    p_value = stats.chi2.sf(statistic, 1) if distribution == "chi2" else 2 * stats.norm.sf(abs(z))
    return {
        "estimate": estimate,
        "std_error": se,
        "ci_low": estimate - critical * se,
        "ci_high": estimate + critical * se,
        "statistic": statistic,
        "distribution": distribution,
        "p_value": p_value,
    }


def adjust_hypotheses(table, alpha=0.05):
    """Holm окремо в кожному наперед заданому сімействі."""
    table = table.copy()
    for indices in table.groupby("family", sort=False).groups.values():
        table.loc[indices, "p_holm"] = multipletests(table.loc[indices, "p_value"], method="holm")[
            1
        ]
    significant = table["p_holm"] < alpha
    table["verdict"] = np.select(
        [significant & (table["estimate"] > 0), significant & (table["estimate"] < 0)],
        ["expected_supported", "opposite_evidence"],
        default="insufficient_evidence",
    )
    return table


def build_model_tables(frames, config):
    """Повернути таблиці в пам'яті; жодного запису артефактів."""
    smoke = smoke_check_m1(frames["mat"], config)
    collected = {
        name: []
        for name in (
            "coefficients",
            "models",
            "diagnostics",
            "vif",
            "hypotheses",
            "row_diagnostics",
        )
    }
    for definition in config["models"]:
        subject, model_id = definition["subject"], definition["id"]
        fitted = smoke if model_id == "M1" else fit_model(frames[subject], definition, config)
        keys = {"subject": subject, "model_id": model_id}
        for kind in ("summary", "diagnostics"):
            collected["models" if kind == "summary" else kind].append({**keys, **fitted[kind]})
        for kind in ("vif", "row_diagnostics"):
            collected[kind].extend(fitted[kind].assign(**keys).to_dict("records"))
        for covariance, result in fitted["covariance_results"].items():
            ci = result.conf_int(alpha=1 - config["inference"]["confidence_level"])
            for term in fitted["X"]:
                collected["coefficients"].append(
                    {
                        **keys,
                        "variant": "baseline",
                        "term": term,
                        "estimate": result.params[term],
                        "std_error": result.bse[term],
                        "ci_low": ci.loc[term, 0],
                        "ci_high": ci.loc[term, 1],
                        "p_value": result.pvalues[term],
                        "nobs": int(result.nobs),
                        "adjusted_r2": result.rsquared_adj,
                        "covariance_type": covariance,
                        "use_t": bool(result.use_t),
                    }
                )
        if model_id in ("M4", "M10"):
            for family, weights, label, distribution in (
                ("H1", {"Medu_4": 1}, "Medu_4=0", "normal"),
                ("H2", {"Medu_4": 1, "Fedu_4": -1}, "Medu_4-Fedu_4=0", "chi2"),
            ):
                test = contrast_test(
                    fitted["result"], weights, config["inference"]["confidence_level"], distribution
                )
                collected["hypotheses"].append(
                    {
                        **keys,
                        "family": family,
                        "contrast": label,
                        "covariance_type": "HC3",
                        "use_t": False,
                        **test,
                    }
                )
    tables = {name: pd.DataFrame(rows) for name, rows in collected.items()}
    tables["hypotheses"] = adjust_hypotheses(tables["hypotheses"], config["inference"]["alpha"])
    return tables
