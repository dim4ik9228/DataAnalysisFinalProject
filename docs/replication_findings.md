# Результати реплікації таблиці 8 (P05)

Повністю збігаються 7 із 8 моделей; 82 із 84 числових перевірок пройдено. Глобальний вердикт: **partial_match**.

Згенеровано з outputs/tables/replication_*.csv. Предмети аналізуються окремо; основний inference — HC3, use_t=false. Підготовлені N390/637 і нулі G3 збережено.

## Числовий вердикт

| subject | model_id | verdict | matched_cells | total_cells | sample_match | specification_match | original_method | complete_match_models | partial_match_models | mismatch_models |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mat | M1 | complete_match | 8 | 8 | True | True | not_identified | 7 | 1 | 0 |
| mat | M2 | complete_match | 10 | 10 | True | True | not_identified | 7 | 1 | 0 |
| mat | M3 | complete_match | 11 | 11 | True | True | not_identified | 7 | 1 | 0 |
| mat | M4 | complete_match | 13 | 13 | True | True | not_identified | 7 | 1 | 0 |
| por | M7 | complete_match | 8 | 8 | True | True | not_identified | 7 | 1 | 0 |
| por | M8 | complete_match | 10 | 10 | True | True | not_identified | 7 | 1 | 0 |
| por | M9 | complete_match | 11 | 11 | True | True | not_identified | 7 | 1 | 0 |
| por | M10 | partial_match | 11 | 13 | True | True | not_identified | 7 | 1 | 0 |
| all | global | partial_match | 82 | 84 | True | True | not_identified | 7 | 1 | 0 |

SE не входять до числового вердикту. Порівняно всі 68 estimate, 8 adjusted R² та 8 N. Допуски задано до оцінювання, без попереднього округлення власних чисел.

### Журнал розбіжностей

| subject | model_id | term | metric | original_value | replicated_value | absolute_difference | tolerance | matches | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| por | M10 | guardian_mother | estimate | 1.14 | 0.641739 | 0.498261 | 0.005 | False | mismatch |
| por | M10 | guardian_father | estimate | 0.64 | 1.13956 | 0.499565 | 0.005 | False | mismatch |

При незбігу перевірено джерельні хеші, sample/рядки, reference-категорії, константу, набір термів і точність друку. Якщо відмінність лишається, її позначаємо невирішеною; це не автоматичний доказ помилки статті. Варіанти для підбору збігу не запускалися.

Дві розбіжності M10 мають структуру можливої перестановки підписів guardian_mother/guardian_father: кожна наша оцінка потрапляє в допуск числа, надрукованого в іншому рядку. Це діагностичне спостереження, а не встановлена причина: авторський код не надано. Еталони й кодування не виправляли; обидві клітинки залишаються mismatch, M10 — partial_match.

## Авторський SE/inference

Метод авторського covariance залишається **not_identified**. HC3, nonrobust та HC1 — наші заздалегідь обрані варіанти; навіть числовий збіг SE не встановлює авторський метод. Точні авторські p/CI не відновлюємо із зірочок або округлених клітинок.

| covariance_type | sum | count |
| --- | --- | --- |
| HC1 | 66 | 68 |
| HC3 | 24 | 68 |
| nonrobust | 11 | 68 |

## H1/H2 — власні тести

| subject | model_id | family | contrast | covariance_type | use_t | estimate | std_error | ci_low | ci_high | statistic | distribution | p_value | p_holm | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mat | M4 | H1 | Medu_4=0 | HC3 | False | 2.99321 | 0.919894 | 1.19026 | 4.79617 | 3.25387 | normal | 0.00113845 | 0.00227689 | expected_supported |
| mat | M4 | H2 | Medu_4-Fedu_4=0 | HC3 | False | 3.00186 | 1.66082 | -0.253295 | 6.25701 | 3.26688 | chi2 | 0.0706918 | 0.141384 | insufficient_evidence |
| por | M10 | H1 | Medu_4=0 | HC3 | False | 1.47026 | 0.494939 | 0.500198 | 2.44033 | 2.97059 | normal | 0.00297229 | 0.00297229 | expected_supported |
| por | M10 | H2 | Medu_4-Fedu_4=0 | HC3 | False | 0.863737 | 0.84391 | -0.790297 | 2.51777 | 1.04754 | chi2 | 0.306075 | 0.306075 | insufficient_evidence |

Holm виконано окремо для двох тестів H1 та двох H2. CI — звичайні 95% normal інтервали, не одночасні й не Holm-adjusted. H2 — прямий контраст із повною коваріацією; різниця значущості окремих коефіцієнтів не замінює його.

H1: очікування підтримано в обох предметах.

- mat: очікування підтримано; оцінка 2.993, 95% CI [1.190; 4.796], p_Holm=0.0023.
- por: очікування підтримано; оцінка 1.470, 95% CI [0.500; 2.440], p_Holm=0.0030.

H2: узагальненого підтвердження очікування для двох предметів немає.

- mat: недостатньо доказів; оцінка 3.002, 95% CI [-0.253; 6.257], p_Holm=0.1414.
- por: недостатньо доказів; оцінка 0.864, 95% CI [-0.790; 2.518], p_Holm=0.3061.

## Діагностика та межі

| subject | model_id | nobs | n_parameters | rank | df_resid | max_leverage | leverage_threshold | leverage_flag_count | max_cooks_distance | cooks_threshold | cooks_flag_count | max_vif | vif_flag_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mat | M1 | 390 | 7 | 7 | 383 | 0.0423831 | 0.0358974 | 1 | 0.020169 | 0.0102564 | 33 | 3.3634 | 0 |
| mat | M2 | 390 | 9 | 9 | 381 | 0.0690203 | 0.0461538 | 3 | 0.0236581 | 0.0102564 | 33 | 3.39039 | 0 |
| mat | M3 | 390 | 10 | 10 | 380 | 0.0786461 | 0.0512821 | 7 | 0.0213797 | 0.0102564 | 31 | 3.46591 | 0 |
| mat | M4 | 390 | 12 | 12 | 378 | 0.090972 | 0.0615385 | 14 | 0.0274665 | 0.0102564 | 32 | 3.57376 | 0 |
| por | M7 | 637 | 7 | 7 | 630 | 0.0245515 | 0.021978 | 2 | 0.0352562 | 0.00627943 | 27 | 2.68664 | 0 |
| por | M8 | 637 | 9 | 9 | 628 | 0.045417 | 0.0282575 | 3 | 0.0370208 | 0.00627943 | 25 | 2.70214 | 0 |
| por | M9 | 637 | 10 | 10 | 627 | 0.0466517 | 0.0313972 | 3 | 0.0352562 | 0.00627943 | 33 | 2.77793 | 0 |
| por | M10 | 637 | 12 | 12 | 625 | 0.0521256 | 0.0376766 | 24 | 0.0361669 | 0.00627943 | 34 | 4.25732 | 0 |

VIF наведено окремо в replication_vif.csv. Пороги VIF>5, Cook>4/N і leverage>2p/N — сигнали огляду; жоден рядок не видаляли й моделі після видалення не переоцінювали. Чотири фігури residuals-vs-fitted/Q–Q у PNG/SVG описують усі вісім моделей.

Це умовні асоціації в тих самих даних, на яких побудовано статтю, без причинного висновку. Дві школи, самозвіти, невиміряні ресурси/здібності, кореляція освіти батьків і перетин учнів між предметами обмежують узагальнення. Inference умовний щодо специфікації, обраної оригінальною роботою.

R1–R5, H3 зі studytime і плацебо залишаються для P06. Бібліографічна вимога про 3–5 citing/checking робіт лишається відкритою. Незалежний аудит: reviews/P05_replication_review.md; рішення K2: K2_replication.md.
