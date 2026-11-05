"""Check frozen protocol/reference integrity without reading student data or fitting models."""

import csv
import hashlib
import json
import re
import tomllib
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def number(text: str) -> Decimal:
    return Decimal(re.sub(r"\s", "", text.replace("−", "-")))


def main() -> None:
    with (ROOT / "configs/analysis.toml").open("rb") as handle:
        config = tomllib.load(handle)
    reference = ROOT / "data/reference"
    coefficients = rows(reference / "table8_coefficients.csv")
    models = rows(reference / "table8_models.csv")
    definitions = {model["id"]: model for model in config["models"]}
    expected_ids = {"M1", "M2", "M3", "M4", "M7", "M8", "M9", "M10"}
    require(set(definitions) == expected_ids, "Wrong model definitions")
    require(len(models) == 8 and len(coefficients) == 68, "Incomplete reference tables")
    keys = [(r["subject"], r["model_id"], r["term"]) for r in coefficients]
    require(len(keys) == len(set(keys)), "Duplicate coefficient keys")
    require(len({r["model_id"] for r in models}) == 8, "Duplicate model rows")
    epsilon = Decimal(config["comparison"]["rounding_epsilon"])
    for row in coefficients:
        definition = definitions[row["model_id"]]
        require(row["subject"] == definition["subject"], "Subject mismatch")
        require(int(row["source_column"]) == definition["source_column"], "Column mismatch")
        require(row["verified"] == "true", "Unreviewed coefficient")
        require(row["significance_marker"] in ("", "*", "**", "***"), "Invalid stars")
        require(number(row["std_error"]) > 0, "Nonpositive standard error")
        for value_field, printed_field, tolerance_field in (
            ("estimate", "estimate_printed", "estimate_tolerance"),
            ("std_error", "se_printed", "se_tolerance"),
        ):
            printed = number(row[printed_field])
            require(number(row[value_field]) == printed, "Printed/numeric mismatch")
            tolerance = Decimal("0.5") * Decimal(10) ** printed.as_tuple().exponent + epsilon
            require(number(row[tolerance_field]) == tolerance, "Wrong rounding tolerance")
        require((reference / row["source_snapshot"]).is_file(), "Missing source snapshot")
    base_terms = {f"{parent}_{level}" for parent in ("Medu", "Fedu") for level in (2, 3, 4)}
    for model_id, definition in definitions.items():
        expected = set(base_terms)
        controls = definition["controls"]
        if "age" in controls:
            expected.add("age")
        if "sex" in controls:
            expected.add("sex_F")
        if "school" in controls:
            expected.add("school_GP")
        if "guardian" in controls:
            expected.update(("guardian_mother", "guardian_father"))
        actual = {r["term"] for r in coefficients if r["model_id"] == model_id}
        require(actual == expected, f"Wrong published terms: {model_id}")
    for row in models:
        definition = definitions[row["model_id"]]
        require(row["subject"] == definition["subject"], "Model subject mismatch")
        require(int(row["source_column"]) == definition["source_column"], "Model column mismatch")
        require(row["outcome"] == config["replication"]["outcome"], "Wrong outcome")
        require(int(row["nobs"]) == config["expected_sample"][row["subject"]], "Wrong N")
        require(row["verified"] == "true", "Unreviewed model row")
        printed = number(row["adjusted_r2_printed"])
        require(number(row["adjusted_r2"]) == printed, "Wrong adjusted R-squared")
        tolerance = Decimal("0.5") * Decimal(10) ** printed.as_tuple().exponent + epsilon
        require(number(row["adjusted_r2_tolerance"]) == tolerance, "Wrong R-squared tolerance")
    source_root = reference / "sources"
    manifest = json.loads((source_root / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest:
        path = (source_root / item["file"]).resolve()
        require(path.is_relative_to(source_root.resolve()), "Invalid manifest path")
        content = path.read_bytes()
        require(hashlib.sha256(content).hexdigest() == item["sha256"], "Source hash mismatch")
        if "bytes" in item:
            require(len(content) == item["bytes"], "Source length mismatch")
    course = ROOT / "docs/evidence/course_requirements_source.txt"
    provenance = json.loads(course.with_name("course_requirements_provenance.json").read_text())
    require(not provenance["missing_child_blocks"], "Incomplete course snapshot")
    require(hashlib.sha256(course.read_bytes()).hexdigest() == provenance["sha256"], "Course hash")
    literature = rows(ROOT / "docs/literature.csv")
    require(4 <= len(literature) <= 6, "Wrong literature size")
    require(len({r["doi"] for r in literature}) == len(literature), "Duplicate literature DOI")
    require(all(r["verified"] == "true" and r["evidence_location"] for r in literature), "Evidence")
    require(config["replication"]["standard_errors"] == "unresolved", "Original SE overclaim")
    require(config["inference"]["covariance"] == "HC3", "Protocol covariance mismatch")
    require(config["inference"]["use_t"] is False, "Protocol normal-inference mismatch")
    require(config["inference"]["multiple_testing"] == "holm", "Multiplicity mismatch")
    require(len(config["inference"]["primary_family"]) == 2, "Primary test family mismatch")
    require(len(config["inference"]["secondary_family"]) == 2, "Secondary test family mismatch")
    print("P02 integrity passed: 68 reviewed coefficient/SE pairs, 8 models, source hashes,")
    print("literature evidence, Decimal tolerances and protocol configuration.")
    print(
        "No student data loaded; no models fitted. Scientific/source audit is documented separately."
    )


if __name__ == "__main__":
    main()
