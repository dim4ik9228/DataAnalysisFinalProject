# Освіта матері й батька та успішність учнів

Реплікація і перевірка стійкості результатів Da (2025), таблиця 8.

**Статус:** P01 і методичну P02 завершено; протокол v1.0 зафіксовано комітом `20476c4`.
P03 завершено: дані підготовлено, запуск відтворено, незалежний аудит пройдено.
P04 завершено: 8 описових таблиць, 5 графіків у PNG/SVG, незалежний аудит.
P05 реалізовано: 7 моделей збігаються повністю, M10 частково; глобально 82/84 перевірки.
P06 реалізовано: R1–R5, описове H3 та два фіксовані noise-плацебо.
P07 реалізовано: синтез H1–H3, реєстр тверджень/доказів і літературний follow-up.
P08 реалізовано: [звіт PDF](reports/rendered/report.pdf), [презентація HTML](reports/rendered/slides.html),
[резерв PDF](reports/rendered/slides.pdf) та [нотатки](reports/speaker_notes.md); [збирання](reports/README.md).
Ноутбуки 00–05 виконуються в чистих ядрах; [K3](docs/K3_conclusions.md) пройдена, готовність до здачі лишається open.
Вибірки реплікації: **390** записів mat і **637** por. H1 підтримано в обох предметах; для H2 недостатньо доказів різниці коефіцієнтів.
Відкриті застереження P02: точний авторський тип SE невідомий; три тематично пов'язані роботи не замінюють буквально вимогу курсу про 3–5 citing/checking робіт.

Питання: чи відтворюється зв'язок між вищою освітою матері та підсумковими
оцінками після врахування освіти батька, і наскільки він стійкий до зміни моделі?

## Структура

```text
.codex/agents/         ролі спеціалізованих агентів
AGENTS.md              спільні правила дослідження і роботи з кодом
configs/               машинозчитувані параметри аналізу
data/raw/              незмінні завантажені дані
data/processed/        дані, підготовлені кодом
docs/                  архітектура, протокол, джерела, журнал рішень
notebooks/             послідовна розповідь дослідження у Jupyter
src/parentedu/         повторно використовуваний Python-код
outputs/tables/        CSV з розрахованими результатами
outputs/figures/       графіки для звіту
outputs/executed/      виконані копії ноутбуків
outputs/logs/          метадані запусків
reports/               джерела й готові звіт/презентація
tests/                 перевірки критичних дослідницьких інваріантів
```

## Запуск

Запускати команди PowerShell із кореня проєкту. Потрібен uv; точну версію
Python **3.13.3** задає .python-version, пакети зафіксовано в uv.lock.
Перевірене середовище: uv 0.13.0. Системний Python не замінюється.

Початкове налаштування після отримання проєкту:

```powershell
uv sync --locked
uv run --locked python -m ipykernel install --prefix .venv --name parentedu-replication --display-name "Python (parentedu-replication)"
uv run --locked jupyter lab
```

Вибрати ядро **Python (parentedu-replication)**. Активація .venv вручну не потрібна.
Після переміщення або перейменування папки повторити налаштування: kernelspec
містить шлях до інтерпретатора; за потреби відновити .venv у новому розташуванні.

Повторні запуски:

```powershell
uv lock --check
uv sync --locked
uv run --locked jupyter lab
```

Lock-файл зберігаємо в Git; змінюємо його лише свідомо разом із залежностями.
Проєкт встановлюється як editable-пакет із src/parentedu; sys.path/PYTHONPATH
налаштовувати не потрібно. Ноутбук 00 перевіряє реальний інтерпретатор і версії.

### Перевірка середовища без браузера

```powershell
uv run --locked ruff check src
uv run --locked jupyter nbconvert --to notebook --execute notebooks/00_project_setup.ipynb --output 00_project_setup.executed.ipynb --output-dir outputs/executed --ExecutePreprocessor.timeout=120 --ExecutePreprocessor.kernel_name=parentedu-replication
```

Виконана копія: outputs/executed/00_project_setup.executed.ipynb.
Метадані: outputs/logs/environment.json — UTC-час, Python, uv, версії пакетів,
хеш uv.lock, seed та стан Git на момент запуску. Обидва файли локальні й ігноруються
в Git. Вихідні ноутбуки зберігаємо без outputs; для інтерактивного запуску
використовуйте Restart Kernel and Run All Cells.

Ноутбуки виконувати за номерами 00 → 01 → 02 → 03 → 04 → 05, кожен у чистому ядрі.
Реалізовано ноутбуки 00–05. [K2](docs/K2_replication.md) описує частковий
числовий збіг, [передача P07](docs/P06_handoff.md) — результати стійкості й межі синтезу.

### Типові проблеми

- Kernel not found: повторити команду реєстрації ядра у .venv.
- Помилка перевірки інтерпретатора: вибрати ядро проєкту й перезапустити його.
- Застарілий lock: перевірити зміни pyproject.toml; не обходити --locked.
- Помилка Git лише в цьому чаті після перейменування: перевірити актуальний cwd
  і доступ до нової папки. У P01 Git поза застарілим обмеженням доступу працював;
  повторна ініціалізація .git не потрібна.

### Підготовка даних P03

На першому запуску після checkout notebook01 завантажує офіційний архів UCI;
версія перевіряється за хешами в [data_provenance.json](docs/data_provenance.json).
Далі використовується локальний кеш без мережі. Скрипт не замінює змінені raw-файли
автоматично: на hash mismatch він зупиняється, щоб причину можна було розслідувати.

```powershell
uv run --locked jupyter nbconvert --to notebook --execute notebooks/01_data.ipynb --output 01_data.executed.ipynb --output-dir outputs/executed --ExecutePreprocessor.timeout=120 --ExecutePreprocessor.kernel_name=parentedu-replication
uv run --locked pytest -q
```

- [Паспорт](docs/data_passport.md) і [словник](docs/data_dictionary.csv) генеруються кодом зі схеми та фактичних підрахунків.
- [Sample flow](outputs/tables/sample_flow.csv) та [порівняння з оригіналом](outputs/tables/original_vs_ours_data.csv) пояснюють 395→390 і 649→637.
- Локальні student_*_validated.csv зберігають усі рядки, включно з освітою 0; student_*_replication.csv містять лише фільтр Medu>=1 & Fedu>=1.
- G3=0 збережено: 38 mat та 15 por. Нульова оцінка не вважається автоматично пропуском чи неявкою.
- data/raw і data/processed не входять у Git. Рядковий журнал — data/processed/sample_membership.csv; агрегована якість — outputs/tables/data_quality.csv.
- Acquisition manifest — data/raw/data_manifest.json; стан запуску та хеші outputs — outputs/logs/data_run.json. metadata.status має бути prepared; після failed старі outputs не слід вважати актуальними.

Метадані містять час UTC, Python/версії, seed, Git HEAD/dirty та хеші коду,
схеми, конфігу, протоколу й даних. Після переміщення проєкту перевірка підтверджує
правильність шляхів через фактичне ядро; за потреби відновіть .venv та kernelspec.
Повторні підготовки детерміновані для CSV; UTC-час журналів закономірно змінюється.

### Описовий аналіз P04

Після успішної підготовки P03:

```powershell
uv run --locked jupyter nbconvert --to notebook --execute notebooks/02_eda.ipynb --output 02_eda.executed.ipynb --output-dir outputs/executed --ExecutePreprocessor.timeout=120 --ExecutePreprocessor.kernel_name=parentedu-replication
uv run --locked pytest -q
```

EDA перевіряє P03 status, хеші даних, схеми, конфігу, протоколу та коду перед
читанням processed CSV. Відсутні або змінені входи зупиняють запуск; повторіть
notebook01 або розслідуйте розбіжність. При помилці eda_run.json має status=failed,
і старі артефакти не слід вважати актуальними. Успішний статус — ready.

[Висновки](docs/eda_findings.md), [незалежний аудит](docs/reviews/P04_eda_review.md)
та [K1](docs/K1_readiness.md) пояснюють результати й межі переходу до моделей.
8 агрегованих CSV — outputs/tables/eda_*; 5 пар PNG/SVG — outputs/figures/eda_*.
SD використовує ddof=1, квартилі — linear interpolation. На графіках показано
медіану/IQR; Spearman описовий, без p-values. Метадані — outputs/logs/eda_run.json.
Повторний запуск відтворює всі 19 хешів таблиць, графіків і згенерованих висновків.
Усього 64 тести перевіряють підготовку, EDA та захист від застарілих входів/збоїв.

### Реплікація P05

```powershell
uv run --locked jupyter nbconvert --to notebook --execute notebooks/03_replication.ipynb --output 03_replication.executed.ipynb --output-dir outputs/executed --ExecutePreprocessor.timeout=120 --ExecutePreprocessor.kernel_name=parentedu-replication
uv run --locked pytest -q
```

Перед запуском потрібні актуальні prepared P03 та ready P04. Workflow перевіряє
хеші даних/коду/протоколу/еталонів, K1 і повноту джерел; збій робить
replication_run.status=failed. Старі результати після failed не є актуальними.
Нова версія Git за незмінних релевантних байтів допустима.

8 CSV — outputs/tables/replication_*; 4 пари PNG/SVG — outputs/figures/replication_*.
Рядкові residual/leverage/Cook залишаються локально в data/processed/replication_diagnostics.csv.
Метадані — outputs/logs/replication_run.json. Повторний запуск відтворює всі18
вихідних хешів. Усього 113 тестів; [висновки](docs/replication_findings.md),
[аудит](docs/reviews/P05_replication_review.md), [K2](docs/K2_replication.md).

66/68 коефіцієнтів, усі N та adjusted R² збігаються; guardian-пара M10 має
невирішений незбіг, можливу перестановку підписів. SE оригіналу невідомий:
HC3 основний, nonrobust/HC1 звітуються окремо. H1/H2 перевірено двобічно з
окремими Holm-сімействами; studytime/плацебо/стійкість реалізовано окремо у P06.

### Стійкість P06

```powershell
uv run --locked jupyter nbconvert --to notebook --execute notebooks/04_robustness.ipynb --output 04_robustness.executed.ipynb --output-dir outputs/executed --ExecutePreprocessor.timeout=120 --ExecutePreprocessor.kernel_name=parentedu-replication
uv run --locked pytest -q
```

Потрібні актуальні P03–P05 та локальні рядкові diagnostics P05: після checkout
виконати ноутбуки 00→01→02→03→04 у чистих ядрах. Workflow перевіряє всі
source/input/output hashes P05 і K2, потім4390 baseline-перевірок на atol=rtol=1e-10.
Помилка до/під час fit/export скасовує ready; очікувана R4-відмова його не скасовує.
Метадані — outputs/logs/robustness_run.json, успішний статус ready.

Усі16 кандидатів присутні,15 оцінено; mat/MS N46 має not_estimable з причиною.
8 CSV — outputs/tables/robustness_*;3 PNG/SVG-пари — outputs/figures/robustness_*.
Membership, row_diagnostics і noise залишаються локально в data/processed/robustness_*.
Повтор відтворює всі18 output-хешів, включно з фіксованим шумом;178 тестів проходять.

[Висновки](docs/robustness_findings.md), [аудит](docs/reviews/P06_robustness_review.md),
[передача P07](docs/P06_handoff.md). Усі p/CI P06 описові/sensitivity, CI не одночасні.
Ordinal-нахили мають інші одиниці; delta_abs studytime не є тестом медіації.
H1/H2 P05 і невирішені M10/SE застереження незмінні. K3 ще не пройдена.

### Підсумкові висновки P07

```powershell
uv run --locked jupyter nbconvert --to notebook --execute notebooks/05_conclusions.ipynb --output 05_conclusions.executed.ipynb --output-dir outputs/executed --ExecutePreprocessor.timeout=120 --ExecutePreprocessor.kernel_name=parentedu-replication
uv run --locked pytest -q
```

Notebook05 читає перевірені P05/P06 CSV і локальні літературні докази; нових
fit, p-values, noise або мережевого пошуку немає. Відсутні/застарілі outputs
відновлювати відповідним notebook, не текстом із handoff. Preflight перевіряє
всі source/input/output hashes P05/P06, статуси й аудити.

П'ять final_*.csv лежать в outputs/tables: гіпотези, окремі вердикти, стійкість,
36 тверджень і179 доказових записів. [Висновки](docs/final_conclusions.md),
[аудит](docs/reviews/P07_conclusions_review.md), [K3](docs/K3_conclusions.md).
Метадані — outputs/logs/conclusions_run.json; шість output-хешів відтворюються.
Усього223 тести проходять; незалежний аудит підтвердив36 тверджень і179 доказів.
Після аудиту K3_conclusions.json фіксує ці6 хешів і review hash. Перевірка
після експорту зупиняє запуск, якщо старий K3 стосується інших висновків/review;
K3 не входить у цикл власного preflight. Невдалий запуск не залишає ready.

[Літературний follow-up](docs/literature_followup.md) підтвердив1 пряме цитування
первинним текстом і ще1 тільки метаданими; освітніх перевірок таблиці8 не
підтверджено. Вимога3–5 лишається unresolved; course_submission_status=open.
Дослідницький PASS K3 не замінює цю вимогу або майбутні звіт/повний запуск P08/P09.

### Ролі агентів

Три ролі у .codex/agents використовують gpt-6.1-sol з reasoning effort low.
У .codex/config.toml ці самі значення задано за замовчуванням для всіх субагентів.
Автоматичне виявлення цих project-scoped ролей клієнтом **не підтверджено**:
поточний інтерфейс виклику субагентів не надає вибору custom agent за ім'ям.
Незалежний огляд P01 виконується субагентом з явно переданими інструкціями reviewer;
це не доказ автоматичної активації TOML-ролі. Для перевірки виявлення відкрити новий
чат цього проєкту в підтримуваному клієнті й перевірити доступність ролі за її ім'ям.

### Артефакти P02

- [Протокол v1.0](docs/replication_protocol.md) і configs/analysis.toml: моделі, гіпотези, inference, критерії та стійкість.
- [Літературний огляд](docs/literature_review.md) і [таблиця](docs/literature.csv): основна + три перевірені пов'язані роботи.
- [Еталони](data/reference/README.md): 68 опублікованих пар estimate/SE та 8 моделей; це не наші результати.
- [Аудит](docs/reviews/P02_protocol_review.md), [вимоги й відхилення](docs/course_requirements.md), [джерела](docs/sources.md).

Перевірка структури, контрольних сум, допусків і узгодження еталонів із конфігом:

```powershell
uv run --locked python scripts/validate_protocol.py
```

Ця команда не читає учнівські дані й не оцінює моделей. Вона не замінює незалежного аудиту змісту.

План роботи: [фази, обсяг і критерії завершення](docs/roadmap.md).

Деталі: [архітектура](docs/architecture.md),
[протокол](docs/replication_protocol.md), [джерела](docs/sources.md).

## Джерела

- Da, T. (2025). *A three-stage machine learning and inference approach for
  educational data*. Scientific Reports 15, 11521.
  https://doi.org/10.1038/s41598-025-89394-2
- Таблиця 8: https://www.nature.com/articles/s41598-025-89394-2/tables/8
- Дані: https://archive.ics.uci.edu/dataset/320/student+performance
- Інструкція курсу: https://kleban.notion.site/research-how-to

Аналіз стосується асоціацій. Він не встановлює причинний вплив освіти батьків.
