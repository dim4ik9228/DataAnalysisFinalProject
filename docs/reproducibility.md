# Повний запуск і незалежне відтворення

Підтриманий маршрут: Windows x64, Git, uv, встановлений Chrome або Edge.
Аналітичні залежності — кореневий uv.lock/Python3.13.3; renderer окремий,
без залежності від Codex. Із кореня копії репозиторію:

```powershell
uv sync --locked
.venv/Scripts/python.exe tools/reporting/setup.py
uv run --locked python scripts/run_project.py
uv run --locked python scripts/package_submission.py
```

За потреби вказати REPORT_BROWSER на інший встановлений Chromium executable.
Setup встановлює pinned Node22.15.0/Playwright1.62.1/Python3.12.10/pypdf6.21.4;
Quarto1.11.9 завантажується builder з перевіркоюSHA. Версія встановленого браузера
записується, але не pinned. Інші ОС і друга фізична машина не заявлені перевіреними.

## Контракт запуску

Runner послідовно виконує00–05 в окремих локальних ядрах, потім reports,
pytest/Ruff/protocol/lock і порівняння. Будь-яка помилка/timeout зупиняє наступні
кроки; старий ready не приймається. Source notebooks не змінюються. Виконані
копії в outputs/executed/<run_id>/; логи й comparison — outputs/logs/<run_id>/.
Поточний receipt — outputs/logs/full_run.json. Він фіксує source inventory,
input/output hashes, часові межі й hash кожного нового фазового marker та K3seal/review.
Шлях старого commit у журналі попередньої фази не є самостійною помилкою;
застарілі bytes/source/input/status — помилка.

Baseline формується з committed агрегованих CSV/висновків або передається
`--baseline <папка>` із baseline.json. Це очікування лише для фінальної звірки,
не вхід оцінювання. Зафіксовано atol=rtol=1e-10, точні категорії/NA/N/членство;
K3-файли вимагають побайтового збігу. Історичні6K3outputs і review не reseal
автоматично. Нові UTC/path/executionIDs не прирівнюються до числових результатів.

`--analysis-only` означає лише перерахунок аналізу, status analysis_ready;
це не повний technicalPASS і не право пакувати. Основний перевірений CLI —
повний запуск. `--timeout` задає ліміт subprocess-кроку, типовий600 с;
ядро має cell timeout180 с. Частковий запуск не є resume повного.

## Перевірка чистої копії

Окремий clone фіксованого candidate commit, нові .venv/renderer, без raw/processed/
logs/executed/build. Tracked outputs зберегти для порівняння поза робочими output
каталогами й прибрати перед виконанням. У цій фазі не копіювати ready-логи або
готові розрахунки з основної копії. Програма мусить заново отримати UCI і створити
всі фазові артефакти. Дата нового отримання локальна; docs/data_provenance.json
лишається незмінним pinnedджерелом. Незалежний reviewer записує реальні команди
та результат у docs/reviews/P09_reproducibility_review.md.

## Комплект

Пакувальник перевіряє саме поточний full ready run і hashes, застосовує allowlist,
не включає raw/processed/.venv/.codex/cache/credentials. Виконані notebook містять
лише агреговані результати; службова guardcell видаляється, локальні шляхи outputs/
metadata редагуються з явним записом трансформації та початкового hash. Source
notebook і наукові результати не змінюються. Manifest не хешує себе; ZIPchecksum
зовнішній. Кожен ZIP розпаковується в тимчасову папку для перевірки всіхpayload.
Git може бути відсутнім у розпакованому комплекті: для повторного запуску
спершу `git init`, `git add .`, `git commit` (локально), потім команди вище.
Оригінальний project commit і review-кандидат фіксуються manifest/receipt.
Архівний full_run.json має ті самі поля з нормалізацією UTF-8/LF; public evidence
містить canonical_full_run_sha256 для цього подання окремо від hash локального
receipt. Це зміна формату JSON, не даних. Контрольну суму ZIP можна звірити
через Get-FileHash -Algorithm SHA256 та зовнішній файл .zip.sha256.

Пакет є review candidate, поки course_submission_status=open. Бібліографічні
вимоги та реальна репетиція — у submission_checklist.md. Публікація/надсилання
до системи курсу — окреме доручення автора.
