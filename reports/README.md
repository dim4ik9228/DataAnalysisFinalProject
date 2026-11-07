# Звіт і презентація P08

Автор: **Дмитро Степанюк, МУП-1**. Метадані редагуються у metadata.toml.

- rendered/report.pdf і report.html — звіт українською, повні вісім моделей у додатку.
- rendered/slides.html — основний самодостатній офлайн-показ: 12 основних + 4 резервні слайди.
- rendered/slides.pdf — резерв: один слайд на сторінку, без нотаток поверх матеріалів.
- speaker_notes.md — окремий сценарій усіх 16 слайдів. Бюджет основної частини 720 с (12 хв);
  це розрахунковий бюджет, користувацької репетиції ще не проводили.
- report.qmd, slides.qmd, references.bib, slides.scss, _quarto.yml — редаговані джерела.
- content_map.csv поєднує секції/слайди з claim IDs, значеннями, таблицями та hashes.
  outputs/tables/report_values.csv зберігає raw і відображення з походженням.

## Перегляд

Відкрити rendered/slides.html у Chrome/Edge, перейти на повний екран. Стрілки або
пробіл перемикають слайди; Esc показує огляд. Посилання резервного слайда B1
ведуть до конкретного доказу. Для доповідача відкрити speaker_notes.md окремо.
Офлайн speaker-view із popup не є перевіреним маршрутом: користуємося окремими
нотатками. Усі графіки та формули основного HTML працюють без зовнішніх запитів.

## Збирання

Із кореня проєкту після успішної P07/K3:

```powershell
uv sync --locked
.venv/Scripts/python.exe tools/reporting/setup.py
uv run --locked python scripts/build_reports.py
```

Команда перевіряє source/input/output hashes P07 і K3, читає готові CSV,
підставляє числа, створює графіки, рендерить чотири виходи та перевіряє їх.
Моделі не оцінюються. `--skip-render` лише готує джерела/CSV; статус буде
`data_prepared`, а не `ready`. Будь-яка помилка замінює старий ready на failed.

Windows-маршрут P08: Quarto 1.11.9 portable, завантажений з офіційного релізу,
SHA-256 перевіряється; кеш у build/toolchain/ (не Git). PDF звіту — bundled Typst,
шрифт DejaVu Serif із зафіксованого Matplotlib. Формули HTML — native MathML,
щоб основний показ не потребував мережі. Графіки Plotly мають статичні SVG-пари;
Plotly JS збережений локально з ліцензійним заголовком.

Windows x64 без Codex: потрібні Git, uv і встановлений Chrome або Edge.
`tools/reporting/setup.py` створює окрему `.venv` із Python 3.12.10 та
pypdf 6.21.4 через власний `uv.lock`, завантажує офіційний portable Node
22.15.0 у `build/toolchain/node/` з перевіркою SHA-256 і виконує `npm ci`
за `tools/reporting/package-lock.json` (Playwright 1.62.1). Аналітичний
`uv.lock` не змінюється. Перший setup потребує мережі; повторний build працює
з локальними залежностями. Binaries, `.venv` і node_modules не входять у Git.

Builder шукає встановлений Chrome/Edge або приймає `$env:REPORT_BROWSER`
із повним шляхом до Chromium executable. Версія браузера записується після
реального запуску; вона не pinned, тому побайтову тотожність PDF між різними
версіями браузера не гарантуємо. Додаткові явні overrides: `REPORT_PYTHON`,
`REPORT_NODE`, `REPORT_NODE_MODULES`. Вони мають відповідати pinned версіям;
`REPORT_NODE` під час setup має вказувати на повний Node distribution із npm.
Стандартні шляхи — `tools/reporting/.venv/Scripts/python.exe`,
`tools/reporting/node_modules` і portable Node у `build/toolchain/node/`.
Перевірка версій, шрифту й чинності P07 передує рендерингу. Фактичні версії,
шляхи renderer, hashes lock-файлів і шрифту записуються в toolchain_manifest.json.

Локальні metadata: outputs/logs/reports_run.json; QA: build/p08/browser_validation.json,
pdf_validation.json, qa/ із PNG усіх сторінок/слайдів. Вони ігноруються в Git.
Дати PDF metadata нормалізовано до дати проєкту; це не дата фактичного запуску,
UTC запуску зберігається окремо в reports_run.json. Матеріали містять лише агрегати.

## Межі

P08 готує матеріали для перегляду й захисту. K3 чинна; course_submission_status=open.
Невідомий авторський SE, частковий збіг M10 та відкрита вимога 3–5 citing/checking
робіт явно збережені. P09 і K4 ще попереду. Нічого не опубліковано й не подано.
