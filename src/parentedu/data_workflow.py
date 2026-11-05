"""Orchestrate P03 data artifacts; never fit models or modify the research protocol."""

import csv
import hashlib
import json
import platform
import subprocess
from collections import Counter
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pandas as pd

from parentedu.config import load_config
from parentedu.data import DataValidationError, acquire_data, load_schema, read_student_csv
from parentedu.paths import DATA_PROCESSED, DATA_RAW, ROOT, TABLES
from parentedu.preparation import export_samples, prepare_samples


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_dictionary(schema: dict, destination: Path) -> None:
    fields = ["name", "dtype", "allowed", "min", "max", "description", "role", "source"]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for column in schema["columns"]:
            row = {field: column.get(field, "") for field in fields}
            if isinstance(row["allowed"], list):
                row["allowed"] = json.dumps(row["allowed"], ensure_ascii=False)
            writer.writerow(row)


def _write_passport(
    frames: dict, samples: dict, manifest: dict, schema: dict, docs_dir: Path
) -> None:
    original = [item["name"] for item in schema["columns"]]
    lines = []
    for subject in ("mat", "por"):
        frame = frames[subject]
        replication = samples["replication"][subject]
        lines.append(
            f"| {subject} | {len(frame)} | {len(frame) - len(replication)} | {len(replication)} | "
            f"{int((frame['G3'] == 0).sum())} | {int((replication['G3'] == 0).sum())} | "
            f"{int(frame[original].duplicated(keep='first').sum())} |"
        )
    table = "\n".join(lines)
    text = f"""# Паспорт даних Student Performance

Підготовлено кодом P03; усі обсяги нижче отримані з фактичних файлів.
Джерело: [{manifest["source_url"]}]({manifest["source_url"]}); DOI {manifest["doi"]}.
Ліцензія: [{manifest["license"]}]({manifest["license_url"]}).
Дата фактичного отримання цієї локальної копії UTC: {manifest["retrieved_at_utc"]}.

## Походження та одиниця

Автор даних — Paulo Cortez; першоджерело Cortez & Silva (2008).
Дві публічні школи Португалії, збір протягом 2005–2006 навчального року:
шкільні записи й анкети. Одиниця — запис учень × предмет, окремо математика
(mat) та португальська (por). Предмети можуть містити тих самих учнів;
record_id не є person_id, міжпредметне зіставлення не виконувалося.

Первинний текст і коди перевірено у [методичному аудиті](original_methods.md).
У файлах 33 вихідні колонки; [словник](data_dictionary.csv) генерується з
configs/data_schema.toml. Ціль G3 має шкалу 0–20; освіта Medu/Fedu кодується 0–4.
Studytime — категорії, а не точні години.

## Фактична підготовка

| Предмет | Повний валідований N | Виключено освіту 0 | Replication N | G3=0 повний | G3=0 replication | Точні дублікати понад перший |
|---|---:|---:|---:|---:|---:|---:|
{table}

Фільтр лише `(Medu >= 1) & (Fedu >= 1)`. Нуль G3 збережено; його причина
не вважається встановленою. Дублікати не видаляються. Пропуски/невідомі коди
зупиняють перевірку; імпутації, train/test, ваг і додаткового очищення немає.
Порядок рядків збережено. Склад підготовлених шарів і порівняння з авторськими N:
[original_vs_ours_data.csv](../outputs/tables/original_vs_ours_data.csv),
[sample_flow.csv](../outputs/tables/sample_flow.csv),
[data_quality.csv](../outputs/tables/data_quality.csv).

## Файли та контроль походження

[Зафіксовані хеші](data_provenance.json) зберігаються в Git без учнівських рядків.
Локальний acquisition manifest — data/raw/data_manifest.json; metadata запуску —
outputs/logs/data_run.json. У чистому checkout потрібне завантаження за README;
порівнюються зафіксовані SHA-256. Наявний кеш перевіряється без повторної мережі.
Перший хеш описує отриману версію, а не доводить тотожність невідомій копії автора.

Повний шар з освітою 0 збережено для майбутнього R1; replication — окремий піднабір.
Локальний журнал data/processed/sample_membership.csv пояснює включення кожного
record_id. Поля subject/source_file/source_row/record_id — технічні; source_row
є 1-based номером запису після заголовка, а не фізичним рядком тексту.
CSV зберігає вихідні коди; типи після читання перевіряються за схемою.

## Обмеження та наступний етап

Самозвіти, дві школи, одна країна/період, корельовані освіти батьків і невиміряні
сімейні характеристики обмежують узагальнення. Малочисельні категорії треба
дослідити в P04; на P03 їх не об'єднували й не виключали.
Аналіз асоціацій, регресії, p-values і перевірки гіпотез не виконувалися.
Наступний етап — P04 (EDA). K1 ще не пройдена.
"""
    (docs_dir / "data_passport.md").write_text(text, encoding="utf-8")


def run_data_preparation(
    raw_dir: Path = DATA_RAW,
    processed_dir: Path = DATA_PROCESSED,
    tables_dir: Path = TABLES,
    docs_dir: Path = ROOT / "docs",
    metadata_path: Path = ROOT / "outputs/logs/data_run.json",
    provenance_path: Path = ROOT / "docs/data_provenance.json",
) -> dict:
    """Use pinned sources and export only fully validated, count-matched samples."""
    raw_dir, processed_dir, tables_dir, docs_dir = map(
        Path, (raw_dir, processed_dir, tables_dir, docs_dir)
    )
    metadata_path, provenance_path = Path(metadata_path), Path(provenance_path)
    for directory in (processed_dir, tables_dir, docs_dir):
        directory.mkdir(parents=True, exist_ok=True)
    record = {"created_at_utc": datetime.now(UTC).isoformat(), "status": "running"}
    _json(metadata_path, record)
    try:
        git = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        git_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        record.update(
            {
                "git_commit": git.stdout.strip() if git.returncode == 0 else None,
                "git_dirty": bool(git_status.stdout.strip())
                if git_status.returncode == 0
                else None,
                "source_hashes": {
                    name: _digest(ROOT / name)
                    for name in (
                        "src/parentedu/data.py",
                        "src/parentedu/preparation.py",
                        "src/parentedu/data_workflow.py",
                        "notebooks/01_data.ipynb",
                    )
                },
                "python": platform.python_version(),
                "seed": load_config()["project"]["seed"],
                "versions": {
                    name: version(name) for name in ("pandas", "numpy", "parentedu-replication")
                },
                "inputs": {
                    name: _digest(ROOT / name)
                    for name in (
                        "configs/data_schema.toml",
                        "configs/analysis.toml",
                        "docs/replication_protocol.md",
                        "uv.lock",
                    )
                },
            }
        )
        manifest = acquire_data(raw_dir=raw_dir, provenance_path=provenance_path)
        schema = load_schema()
        frames, quality = {}, []
        for subject in ("mat", "por"):
            frame, report = read_student_csv(raw_dir / f"student-{subject}.csv", subject, schema)
            expected_raw = schema["dataset"]["expected_rows"][subject]
            if len(frame) != expected_raw:
                raise DataValidationError(
                    [
                        {
                            "subject": subject,
                            "source_row": None,
                            "column": "",
                            "issue_type": "source_row_count",
                            "detail": f"Expected {expected_raw} source rows, received {len(frame)}",
                        }
                    ]
                )
            frames[subject] = frame
            quality.append(report)
        quality_frame = pd.concat(quality, ignore_index=True)
        quality_frame.to_csv(tables_dir / "data_quality.csv", index=False, lineterminator="\n")
        samples = prepare_samples(frames, config=load_config())
        samples["comparison"]["n_raw_source"] = samples["comparison"]["subject"].map(
            schema["dataset"]["expected_rows"]
        )
        samples["comparison"]["raw_status"] = "match"
        files = export_samples(
            samples, processed_dir=processed_dir, tables_dir=tables_dir, schema=schema
        )
        _write_dictionary(schema, docs_dir / "data_dictionary.csv")
        _write_passport(frames, samples, manifest, schema, docs_dir)
        output_paths = [
            *(
                files[key]
                for key in (
                    "mat_validated",
                    "mat_replication",
                    "por_validated",
                    "por_replication",
                    "membership",
                )
            ),
            *(
                tables_dir / name
                for name in (
                    "data_quality.csv",
                    "sample_flow.csv",
                    "original_vs_ours_data.csv",
                )
            ),
            docs_dir / "data_dictionary.csv",
            docs_dir / "data_passport.md",
        ]
        record.update(
            {
                "status": "prepared",
                "completed_at_utc": datetime.now(UTC).isoformat(),
                "cache_hit": manifest["cache_hit"],
                "acquired_at_utc": manifest["retrieved_at_utc"],
                "raw": manifest["files"],
                "provenance_sha256": _digest(provenance_path),
                "outputs": {str(path): _digest(path) for path in output_paths},
                "counts": {
                    subject: {
                        "validated": len(frames[subject]),
                        "replication": len(samples["replication"][subject]),
                    }
                    for subject in ("mat", "por")
                },
            }
        )
        _json(metadata_path, record)
        return {
            "manifest": manifest,
            "quality": quality_frame,
            "samples": samples,
            "files": files,
            "metadata": record,
        }
    except Exception as error:
        record.update({"status": "failed", "error_type": type(error).__name__, "error": str(error)})
        if isinstance(error, DataValidationError):
            _json(metadata_path.with_name("data_validation_issues.json"), {"issues": error.issues})
            counts = Counter(
                (i.get("subject", ""), i.get("column", ""), i["issue_type"]) for i in error.issues
            )
            pd.DataFrame(
                [
                    {
                        "subject": key[0],
                        "column": key[1],
                        "check": key[2],
                        "value": count,
                        "status": "failed",
                    }
                    for key, count in counts.items()
                ]
            ).to_csv(tables_dir / "data_quality.csv", index=False, lineterminator="\n")
        comparison = getattr(error, "comparison", None)
        if isinstance(comparison, pd.DataFrame):
            comparison.to_csv(
                tables_dir / "original_vs_ours_data.csv", index=False, lineterminator="\n"
            )
        _json(metadata_path, record)
        raise
