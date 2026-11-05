# Освіта матері й батька та успішність учнів

Реплікація і перевірка стійкості результатів Da (2025), таблиця 8.

**Статус:** середовище P01 налаштовано й перевірено на Windows із Python 3.13.3.
Ноутбук 00 виконується в чистому ядрі. Ноутбуки 01–05 залишаються шаблонами.
Дані ще не завантажено, моделі не оцінено; числових висновків нашого дослідження поки немає.

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
Поки реалізовано лише 00. Перед аналізом слід завершити P02–P04 і зафіксувати протокол.

### Типові проблеми

- Kernel not found: повторити команду реєстрації ядра у .venv.
- Помилка перевірки інтерпретатора: вибрати ядро проєкту й перезапустити його.
- Застарілий lock: перевірити зміни pyproject.toml; не обходити --locked.
- Помилка Git лише в цьому чаті після перейменування: перевірити актуальний cwd
  і доступ до нової папки. У P01 Git поза застарілим обмеженням доступу працював;
  повторна ініціалізація .git не потрібна.

### Ролі агентів

Три описи у .codex/agents проходять TOML-перевірку та успадковують модель сесії.
Автоматичне виявлення цих project-scoped ролей клієнтом **не підтверджено**:
поточний інтерфейс виклику субагентів не надає вибору custom agent за ім'ям.
Незалежний огляд P01 виконується субагентом з явно переданими інструкціями reviewer;
це не доказ автоматичної активації TOML-ролі. Для перевірки виявлення відкрити новий
чат цього проєкту в підтримуваному клієнті й перевірити доступність ролі за її ім'ям.

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
