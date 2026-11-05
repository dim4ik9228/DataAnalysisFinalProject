# Еталони публікації: таблиця 8 Da (2025)

Ці файли містять **опубліковані автором числа**, а не наші розрахунки.
Дата транскрипції: 2026-11-05. Потрібні колонки: 1–4 (mat), 7–10 (por), залежна змінна G3.

## Файли

- table8_coefficients.csv: 68 наведених оцінок і стандартних похибок.
- table8_models.csv: 8 рядків із N та adjusted R².
- sources/da2025_fulltext.xml: повний відкритий JATS XML Europe PMC, Table8 = id Tab8.
- sources/table8_source_cells.json: читабельний похідний експорт усіх клітинок таблиці; сам по собі не є незалежною звіркою.
- sources/uci320.html: snapshot офіційного опису датасету, без учнівських CSV.
- sources/manifest.json: адреси, час завантаження UTC і SHA-256 snapshot-джерел.
- sources/cortez2008_reading.md: нотатка перевірки первинного PDF, прочитаного через авторську ResearchGate-копію; локального PDF немає.

Першоджерело: https://www.nature.com/articles/s41598-025-89394-2/tables/8.
Доступна офіційна репозиторна копія: https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11968921/fullTextXML.
Стаття має ліцензію CC BY 4.0; атрибуція: Da, T. (2025), Scientific Reports 15, 11521, DOI 10.1038/s41598-025-89394-2. UCI snapshot: Cortez, P., Student Performance, DOI 10.24432/C5TG7T, CC BY 4.0.

## Схема coefficients

Ключ: (subject, model_id, term). model_id зберігає номер авторської колонки, наприклад M10.

| Поле | Значення |
|---|---|
| subject | mat або por |
| model_id | M1, M2, M3, M4, M7, M8, M9, M10 |
| term | Канонічна назва параметра, див. нижче |
| estimate, std_error | Десяткові значення з ASCII-мінусом, без зірочок/дужок |
| estimate_printed, se_printed | Друкований числовий запис зі збереженням точності; Unicode-мінус можливий |
| estimate_source_text, se_source_text | Оригінальна клітинка зі зірочками/дужками, щоб не втрачати provenance |
| estimate_decimals, se_decimals | Кількість десяткових розрядів надрукованого значення |
| estimate_tolerance, se_tolerance | Допуски округлення, обчислені Decimal, див. нижче |
| significance_marker | Порожньо, *, ** або ***; це не точне p-value |
| source_url, source_column | Канонічна адреса Table8 і номер колонки |
| source_xml_id, source_snapshot | Tab8 та відносний шлях локальної копії |
| verified | false до незалежної звірки; true лише після перевірки reviewer |

Канонічні назви: Medu_2, Medu_3, Medu_4, Fedu_2, Fedu_3, Fedu_4, age, sex_F, school_GP, guardian_mother, guardian_father. Вони позначають конкретні регресори, а не назви колонок Patsy; у P05 треба явно відобразити на них назви statsmodels.

Reference-категорії: освіта 1, sex M, school MS, guardian other. Вони не мають оцінених коефіцієнтів у цій dummy-специфікації й не включені як нулі. Рядки параметрів, відсутніх у моделі, не створюються. Intercept за Eq.(2) входить у моделі, але його число в Table8 не наведене, тому еталонного рядка для нього немає.

Число наведених коефіцієнтів для M1/M2/M3/M4 та M7/M8/M9/M10: відповідно 6/8/9/11 і 6/8/9/11. Точних p-value та CI джерело не дає — їх не вигадуємо.

## Схема models

Ключ: (subject, model_id). Поля outcome=G3, nobs (точне ціле), adjusted_r2, adjusted_r2_printed, adjusted_r2_tolerance та ті самі source/provenance/verified-поля. N 390 для mat і 637 для por — авторські значення, ще не перевірені на рядках UCI.

## Правило числового порівняння

Для числа x з надрукованим розрядом 10^e допуск = 0.5 × 10^e + 1e-10; розряд визначається через Decimal із друкованого запису, не float. Однакове правило застосовано до SE й adjusted R², N має збігтися точно. Для 0.098 допуск 0.0005000001; для −0.0042 — 0.0000500001; для 0.046 adjusted R² — 0.0005000001. Estimate і SE мають окремі допуски.

Поле printed_decimals саме по собі не годиться для майбутнього наукового запису: при його появі потрібно врахувати експоненту. Поточні вибрані клітинки таблиці мають звичайний десятковий запис. Порожні клітинки — структурна відсутність параметра, а не точний нуль.

Порівняння SE не встановлює авторський covariance estimator: оригінальний варіант HC лишається невідомим. Критерії змістового висновку й власного inference задаються окремо у протоколі.

## Незалежна перевірка

Усі CSV мають verified=true після незалежної перевірки 2026-11-05: 68/68 пар estimate/SE та 8/8 model rows. Reviewer окремо прочитав Tab8 у первинному XML, звірив повне покриття непорожніх клітинок, raw printed, Unicode signs, stars, допуски, N, adjusted R² та provenance. Звіт: [P02_protocol_review](../../docs/reviews/P02_protocol_review.md). Автор транскрипції та reviewer — різні субагенти. Ця перевірка підтверджує перенесення авторських чисел, а не відтворення їх на даних UCI.
