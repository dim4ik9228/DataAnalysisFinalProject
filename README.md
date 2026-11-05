# Освіта матері й батька та успішність учнів

Реплікація і перевірка стійкості результатів Da (2025), таблиця 8.

**Статус:** P01 і методичну P02 завершено; протокол v1.0 зафіксовано комітом `20476c4`.
P03 завершено: дані підготовлено, запуск відтворено, незалежний аудит пройдено.
Ноутбуки 00–01 виконуються в чистих ядрах; 02–05 залишаються шаблонами.
Вибірки реплікації: **390** записів mat і **637** por. Регресії та перевірки гіпотез ще не запускалися.
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
reports/               звіт і майбутня презентація
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
Реалізовано ноутбуки 00–01. Після P03 потрібні P04 (EDA) та
контрольна точка K1; лише після цього оцінюємо моделі.

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

### Ролі агентів

Три описи у .codex/agents проходять TOML-перевірку та успадковують модель сесії.
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
