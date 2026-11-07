# Незалежний аудит P09: відтворення і комплект

Дата: 2026-11-07. Роль: research_reviewer, gpt-6.1-sol / low.
Вердикт: **PASS для технічної відтворюваності перевіреного Windows-маршруту**.
`course_submission_status=open`: літературний мінімум і фактична репетиція не закриті.
Перевірений candidate: `9e31b46f7605ee78cda12a33bbb6c2c75dc86e56`.

## Обсяг і незалежність

Прочитано AGENTS.md, архітектуру, README, протокол, план P09, runner,
execute_notebook, submission, renderer bootstrap/builder і змістові тести.
Reviewer не редагував pipeline або основні розрахунки. Виконання проведено
в окремому локальному clone `build/p09/Clean verification project`, шлях містить пробіли.
Це та сама фізична Windows-машина, не перевірка іншого комп'ютера чи ОС.

Фактичний маршрут (PowerShell, із відповідного кореня):

```powershell
git clone --no-hardlinks <основний-репозиторій> "build/p09/Clean verification project"
uv sync --locked
.venv/Scripts/python.exe tools/reporting/setup.py
git fetch origin
git checkout -f 9e31b46
.venv/Scripts/python.exe scripts/run_project.py --baseline <основний-репозиторій>/build/p09/baseline
```

Перший clone був 0b3f656. Створено нові аналітичну `.venv` і
`tools/reporting/.venv`; Node і Quarto отримано власним bootstrap у clone.
Після виправлень checkout оновлено до 47bc716, потім 9e31b46. Locks/версії середовищ
не змінювалися, тому щойно створені reviewer-середовища збережено;
основна `.venv` не копіювалася. Використано системний uv і встановлений Chrome;
кеш інсталятора пакетів міг використовуватися. Bootstrap не залежав від Codex runtime.
Для незалежного візуального аудиту використано наявний Poppler.

Перед виконанням збережено committed baseline і перелік видалених файлів.
Видалено тільки файли всередині перевіреного абсолютного clone: raw/processed,
logs/executed, таблиці/графіки, assets/rendered/content_map/speaker_notes/toolchain_manifest;
`.gitkeep`, код і toolchain залишено. Перед остаточним запуском прибрано 132
згенеровані файли. Жодні готові raw/processed або фазові журнали основного запуску
не копіювалися. Основний 46-файловий baseline використано виключно для звірки,
не для обчислень; його frozen hashes перевірено до виконання.

## Доказ остаточного clean-run

- HEAD: `9e31b46f7605ee78cda12a33bbb6c2c75dc86e56`.
- Run ID: `20261107T091837-368c6b5e`, mode full, status ready.
- UTC: 2026-11-07T09:18:37.948519+00:00 — 2026-11-07T09:19:55.846124+00:00.
- SHA-256 незалежного `outputs/logs/full_run.json`:
  `4a97b818f4f3ec195e821141ed52c602b4e0409023c07735013226de753b6a1f`.
- UCI отримано заново: `cache_hit=false`, acquired_at_utc
  `2026-11-07T09:18:51.080954+00:00`; provenance SHA
  `717274cc27337e7efe27fb8c2a65679b91bde70cefcdd569995fe323b4bbad52`.
- 00→05, кожен із власним локальним ядром, reports, protocol/Ruff/lock/pytest пройдено.
  Pytest: **267 passed in 22.67s**.
- Незалежний повторний `validate_full_run`: PASS. Поточний source inventory точно
  дорівнює записаному; source/input/output hashes і фазові receipts чинні.
- **46/46 baseline-файлів побайтово однакові**, включно з додатковими
  processed/sample/diagnostic/noise перевірками baseline. Допуски atol=rtol=1e-10
  не послаблювалися. Усі 6 K3 outputs та seal/review чинні.
- K3 seal SHA `a06eeae5927853884d0caae6fdebef7a7b3435271d509227064d2415aa47d5d8`;
  P07 review SHA `8ca30dc43b8d59a01aae5282bc70d0514e7e8a96dc52f6129b7511ca28ef3254`.

Між основним та незалежним run порівняно 80 report/table/figure виходів:
79 побайтово однакові, включно з обома HTML/PDF, content_map, report_values та notes.
Єдина відмінність — toolchain_manifest: renderer_paths і hashes двох текстів
renderer (package-lock.json, pyproject.toml) через Git CRLF/LF checkout.
Окремо підтверджено, що в цих двох файлах відмінні тільки переноси рядків;
версії/залежності/вміст однакові. Це не нормалізація числових результатів.
Tracked-зміни clone після виконання обмежені згенерованими артефактами й переносами
рядків. `git diff --name-only` для src/scripts/tests/notebooks/configs/analysis lock/
tools reporting порожній. Source notebook залишилися чистими.

Середовище: Python3.13.3; renderer Python3.12.10, Node22.15.0,
Playwright1.62.1, pypdf6.21.4, Quarto1.11.9, Typst0.15.1,
Chrome156.0.8078.80. Браузер записаний, але не pinned; PASS не поширюється
автоматично на іншу його версію.

## Комплект і візуальна перевірка

Фактично аудійовано `dist/submission-review-candidate.zip` основної копії:

- SHA-256 `5cf017f6c1fd8eab9bed018552995c913375ee022cfd36dff2674783a29b437e`;
- run ID пакета `20261107T091639-e94529f1` — основний full run того самого candidate;
- 230 payload-файлів плюс manifest; detached checksum збігається;
- verify_package, нове розпакування, allowlist, відсутність traversal/дублікатів,
  розмір і SHA кожного payload: PASS;
- шість executed notebooks без error outputs, з описаними перетвореннями guard/
  metadata/output paths; raw/processed і середовищ немає;
- `.gitattributes` і `.gitignore` присутні. У розпакованому комплекті реально
  виконано transient git init/add/commit: Git blob P07 review точно дорівнює
  hash seal за системного core.autocrlf=true.

Обидва розпаковані HTML відкрито незалежним Playwright із блокуванням усіх HTTP(S).
Report: 6 images, 0 broken; slides: 16 слайдів, 5 Plotly, 16 notes.
Немає page errors, unresolved tokens або мережевих запитів.
Poppler перетворив **усі 12 сторінок report.pdf і 16 сторінок slides.pdf**;
reviewer переглянув усі сторінки на позначених contact sheets і додатково відкрив
окремий графічний слайд. Матеріального обрізання, накладання, зниклих символів
або невидимих графіків не виявлено; додаток переходить між сторінками зі збереженими
заголовками таблиць. PDF/HTML незалежного final-run побайтово збігаються
з аудійованими матеріалами пакета. Speaker notes наявні;
реальна репетиція автором не імітувалася.

Контрольні висновки: H1 підтримано, H2 недостатньо доказів, H3 описова;
82/84 числових перевірок, M10 partial, авторський SE невідомий;
9/9 у визначеному знаменнику оцінених categorical variants, R3 має інші одиниці,
R4 mat/MS відмовлено за N, fixed-noise placebo не тлумачиться як доказ нуля.
Citing/checking мінімум не закрито: 1 первинний текст, 1 metadata-only,
0 підтверджених освітніх перевірок. Причинні висновки не заявлено.

## Знайдені дефекти й опрацювання

1. Початковий clone 0b3f656 реально зупинився на notebook05: K3 відхилив review hash.
   Git autocrlf перетворив committed LF-review на CRLF, тоді як seal прив'язаний до
   історичних mixed newline bytes. Координатор зберіг незмінні історичні bytes як
   literal Git blob і додав -text attribute (47bc716). Seal і текст дослідження не
   змінено, reseal не виконано. Provisional47 і final9e31 пройшли K3.
2. Початкове пакування пропускало `.gitattributes`: bootstrap архіву міг знову
   зруйнувати sealed bytes. Виправлено в 9e31b46; реальна перевірка
   unpack/init/add/commit вище закриває дефект.
3. Read-only review виявив неповну перевірку source inventory і відсутність
   tools/reporting/.python-version у source identity. Координатор виправив
   identity/inventory; final-run підтверджує чинність. Також опрацьовано
   analysis-only/baseline контракт та archive bootstrap dirs. Analysis-only
   не називається full PASS і не пакується; його окремий інтеграційний запуск
   reviewer не проводив, перевірено код і змістові тести.

Невирішених матеріальних дефектів у перевіреному candidate-маршруті не залишилося.
Локальні докази в clone `build/p09/`: inventories, independent_summary.json,
package_audit_result.json, offline_package_result.json, pdf_pages/;
receipts і comparison — в outputs/logs/<run_id>/.
Публічний підсумок координатора — docs/evidence/p09_validation.json.

## Межі PASS і фінальна фіксація

Це технічний PASS локального Windows clone/fresh environments/fresh UCI/full runner
і фактично перевіреного candidate ZIP. Не перевірено іншу машину/ОС чи майбутню
версію браузера. Пакет лишається review candidate; публікація й надсилання не
здійснювалися. Загальна готовність курсу лишається open.

Фінальний пакет після додавання review/K4/checklist/evidence треба зібрати повторно
й перевірити нові unpack/hashes/allowlist. Допустимі лише перелічені документаційні
дельти за незмінних executable/input/material bytes. Новий ZIP SHA і зв'язок із
reviewed candidate записати зовні без hash-циклу. Цей review не засвідчує ще
не створений фінальний ZIP.
