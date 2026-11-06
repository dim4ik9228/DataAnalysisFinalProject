# Стійкість оцінок, studytime та плацебо (P06)

Додатний знак Medu_4 збережено у 9/9 оцінюваних categorical-варіантах стійкості. Величини й точність відрізняються; це не вимога значущості в кожній підгрупі.

Усі результати нижче згенеровано з outputs/tables/robustness_*.csv. HC3/use_t=false, 95% normal CI. Усі p/CI P06 описові або перевірки чутливості; CI не одночасні. Варіанти не накопичуються; H1/H2 і числовий вердикт P05 залишаються незмінними.

## Повнота варіантів та відмови

| subject | base_model_id | variant | school | nobs | model_status | reason | input_layer |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mat | M4 | baseline | — | 390 | available | — | replication |
| mat | M4 | R1 | — | 395 | available | — | validated |
| mat | M4 | R2 | — | 352 | available | — | replication |
| mat | M4 | R3 | — | 390 | available | — | replication |
| mat | M4 | R4 | MS | 46 | not_estimable | min_subgroup_n | replication |
| mat | M4 | R4 | GP | 344 | available | — | replication |
| mat | M4 | R5 | — | 390 | available | — | replication |
| mat | M4 | placebo | — | 390 | available | — | replication |
| por | M10 | baseline | — | 637 | available | — | replication |
| por | M10 | R1 | — | 649 | available | — | validated |
| por | M10 | R2 | — | 622 | available | — | replication |
| por | M10 | R3 | — | 637 | available | — | replication |
| por | M10 | R4 | MS | 220 | available | — | replication |
| por | M10 | R4 | GP | 417 | available | — | replication |
| por | M10 | R5 | — | 637 | available | — | replication |
| por | M10 | placebo | — | 637 | available | — | replication |

Відмова not_estimable — видимий результат перевірки оцінюваності, не нульова beta. Шкільні пороги N>=50, count1/count4>=5, повний ранг, df>0, leverage<0.999999 незмінні; mat/MS N46 не оцінюємо.

## Освіта батьків: categorical-контрасти

| subject | variant | school | parent | nobs | estimate | ci_low | ci_high | delta_beta | status | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mat | baseline | — | Medu | 390 | 2.99321 | 1.19026 | 4.79617 | 0 | available | — |
| mat | baseline | — | Fedu | 390 | -0.00864454 | -1.82521 | 1.80792 | 0 | available | — |
| mat | R1 | — | Medu | 395 | 2.77273 | 0.934332 | 4.61114 | -0.220479 | available | — |
| mat | R1 | — | Fedu | 395 | 0.140574 | -1.68027 | 1.96142 | 0.149218 | available | — |
| mat | R2 | — | Medu | 352 | 1.85523 | 0.546047 | 3.16441 | -1.13798 | available | — |
| mat | R2 | — | Fedu | 352 | 0.526329 | -0.839253 | 1.89191 | 0.534973 | available | — |
| mat | R4 | MS | Medu | 46 | — | — | — | — | not_estimable | min_subgroup_n |
| mat | R4 | MS | Fedu | 46 | — | — | — | — | not_estimable | min_subgroup_n |
| mat | R4 | GP | Medu | 344 | 2.91976 | 0.857896 | 4.98162 | -0.073455 | available | — |
| mat | R4 | GP | Fedu | 344 | -0.281368 | -2.25926 | 1.69652 | -0.272724 | available | — |
| mat | R5 | — | Medu | 390 | 2.72533 | 0.93966 | 4.51099 | -0.267888 | available | — |
| mat | R5 | — | Fedu | 390 | 0.0388756 | -1.74863 | 1.82638 | 0.0475202 | available | — |
| por | baseline | — | Medu | 637 | 1.47026 | 0.500198 | 2.44033 | 0 | available | — |
| por | baseline | — | Fedu | 637 | 0.606525 | -0.295902 | 1.50895 | 0 | available | — |
| por | R1 | — | Medu | 649 | 1.38774 | 0.421284 | 2.35419 | -0.0825259 | available | — |
| por | R1 | — | Fedu | 649 | 0.659405 | -0.239539 | 1.55835 | 0.0528795 | available | — |
| por | R2 | — | Medu | 622 | 1.96576 | 1.21289 | 2.71863 | 0.495495 | available | — |
| por | R2 | — | Fedu | 622 | 0.183084 | -0.627343 | 0.993512 | -0.423441 | available | — |
| por | R4 | MS | Medu | 220 | 0.384331 | -2.28837 | 3.05703 | -1.08593 | available | — |
| por | R4 | MS | Fedu | 220 | 2.37862 | -0.372592 | 5.12983 | 1.77209 | available | — |
| por | R4 | GP | Medu | 417 | 1.98206 | 0.981383 | 2.98274 | 0.5118 | available | — |
| por | R4 | GP | Fedu | 417 | 0.0296351 | -0.936002 | 0.995273 | -0.57689 | available | — |
| por | R5 | — | Medu | 637 | 1.34802 | 0.390137 | 2.3059 | -0.122243 | available | — |
| por | R5 | — | Fedu | 637 | 0.572931 | -0.321547 | 1.46741 | -0.0335943 | available | — |

R1 повертає освіту0; R2 виключає лише G3=0; R4 аналізує школи окремо; R5 додає studytime. Зміна beta описова: зміна вибірки може змінювати склад порівнюваних груп. Стійкість оцінюємо за знаком, величиною та CI, без вимоги p<0.05 у всіх варіантах. Неперетин або перекриття CI не є тестом різниці.

## R3: інша одиниця вимірювання

| subject | base_model_id | variant | school | parent | term | estimand | nobs | reference_n | target_n | model_status | status | reason | comparison_reason | baseline_estimate | delta_beta | estimate | std_error | ci_low | ci_high | p_value | adjusted_r2 | covariance_type | use_t |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mat | M4 | R3 | — | Medu | Medu_ordinal | ordinal_per_level | 390 | 58 | 130 | available | available | — | incomparable_estimand | 2.99321 | — | 0.951736 | 0.279245 | 0.404426 | 1.49905 | 0.000653812 | 0.0652801 | HC3 | False |
| mat | M4 | R3 | — | Fedu | Fedu_ordinal | ordinal_per_level | 390 | 81 | 96 | available | available | — | incomparable_estimand | -0.00864454 | — | -0.00998681 | 0.288081 | -0.574614 | 0.554641 | 0.972346 | 0.0652801 | HC3 | False |
| por | M10 | R3 | — | Medu | Medu_ordinal | ordinal_per_level | 637 | 138 | 174 | available | available | — | incomparable_estimand | 1.47026 | — | 0.464256 | 0.158773 | 0.153067 | 0.775445 | 0.00345533 | 0.153146 | HC3 | False |
| por | M10 | R3 | — | Fedu | Fedu_ordinal | ordinal_per_level | 637 | 172 | 128 | available | available | — | incomparable_estimand | 0.606525 | — | 0.209432 | 0.149172 | -0.0829393 | 0.501803 | 0.160329 | 0.153146 | HC3 | False |

Ordinal beta описує зміну на один рівень за припущення однакового приросту. Це інший estimand; його величину не прирівнюємо до вища-vs-початкова й не множимо на3 як заміну categorical-контрасту. Delta_beta до baseline тут NA.

## H3: додавання studytime

| subject | base_model_id | variant | school | beta_base | beta_augmented | base_ci_low | base_ci_high | augmented_ci_low | augmented_ci_high | nobs | delta_abs | sign_change |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mat | M4 | R5 | — | 2.99321 | 2.72533 | 1.19026 | 4.79617 | 0.93966 | 4.51099 | 390 | -0.267888 | False |
| por | M10 | R5 | — | 1.47026 | 1.34802 | 0.500198 | 2.44033 | 0.390137 | 2.3059 | 637 | -0.122243 | False |

- mat: Medu_4 2.993 → 2.725; delta_abs=-0.268, абсолютна оцінка зменшилася.
- por: Medu_4 1.470 → 1.348; delta_abs=-0.122, абсолютна оцінка зменшилася.

H3 описове: p-value або CI для delta_abs не обчислювали. CI окремих beta — невизначеність цих оцінок. Studytime — категорії, не точні години; зміна після контролювання не доводить медіацію або причинний механізм.

## Noise-плацебо

| subject | base_model_id | variant | school | term | estimate | std_error | ci_low | ci_high | p_value | nobs | adjusted_r2 | covariance_type | use_t | seed | rng | order_noise_sha256 | model_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mat | M4 | placebo | — | noise | -0.246287 | 0.246049 | -0.728533 | 0.235959 | 0.316842 | 390 | 0.0570637 | HC3 | False | 20261206 | numpy.random.default_rng/PCG64 | be047f2492fc4082bd1c66c62b00fac96c34ad81e7d6f84cd7c44c240378dbb1 | available |
| por | M10 | placebo | — | noise | -0.104563 | 0.116972 | -0.333823 | 0.124697 | 0.371366 | 637 | 0.151402 | HC3 | False | 20261207 | numpy.random.default_rng/PCG64 | b362576d26a69330488e797d30c94c614204f8836a22052859f04e7248b000cf | available |

На предмет рівно один noise-вектор N(0,1) у baseline-порядку: default_rng(seed+101) mat і seed+102 por. Шум не перегенеровували залежно від p; випадкова значущість можлива. Raw p описовий, не нова сім'я H1/H2. Плацебо не є permutation p-value або доказом відсутності confounding.

## Діагностика та межі

| subject | variant | school | nobs | rank | df_resid | max_leverage | max_vif | cooks_flag_count | leverage_flag_count | model_status | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mat | baseline | — | 390 | 12 | 378 | 0.090972 | 3.57376 | 32 | 14 | available | — |
| mat | R1 | — | 395 | 14 | 381 | 0.510567 | 3.54815 | 26 | 7 | available | — |
| mat | R2 | — | 352 | 12 | 340 | 0.102795 | 3.8131 | 16 | 15 | available | — |
| mat | R3 | — | 390 | 8 | 382 | 0.0809356 | 3.55584 | 30 | 29 | available | — |
| mat | R4 | MS | 46 | 11 | 35 | — | — | — | — | not_estimable | min_subgroup_n |
| mat | R4 | GP | 344 | 11 | 333 | 0.0966438 | 3.98556 | 27 | 13 | available | — |
| mat | R5 | — | 390 | 15 | 375 | 0.0968958 | 3.60934 | 32 | 5 | available | — |
| mat | placebo | — | 390 | 13 | 377 | 0.0928035 | 3.58329 | 32 | 8 | available | — |
| por | baseline | — | 637 | 12 | 625 | 0.0521256 | 4.25732 | 34 | 24 | available | — |
| por | R1 | — | 649 | 14 | 635 | 0.275212 | 4.16187 | 33 | 20 | available | — |
| por | R2 | — | 622 | 12 | 610 | 0.0536827 | 4.27995 | 31 | 24 | available | — |
| por | R3 | — | 637 | 8 | 629 | 0.0470361 | 4.23273 | 32 | 44 | available | — |
| por | R4 | MS | 220 | 11 | 209 | 0.142656 | 5.45186 | 20 | 9 | available | — |
| por | R4 | GP | 417 | 11 | 406 | 0.0740735 | 3.88169 | 21 | 22 | available | — |
| por | R5 | — | 637 | 15 | 622 | 0.0691713 | 4.2835 | 33 | 18 | available | — |
| por | placebo | — | 637 | 13 | 624 | 0.0554794 | 4.25746 | 33 | 22 | available | — |

### Частоти освіти в R1/R4

| subject | variant | school | nobs | Medu_0_n | Medu_1_n | Medu_2_n | Medu_3_n | Medu_4_n | Fedu_0_n | Fedu_1_n | Fedu_2_n | Fedu_3_n | Fedu_4_n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mat | R1 | — | 395 | 3 | 59 | 103 | 99 | 131 | 2 | 82 | 115 | 100 | 96 |
| mat | R4 | MS | 46 | 0 | 17 | 7 | 11 | 11 | 0 | 15 | 12 | 10 | 9 |
| mat | R4 | GP | 344 | 0 | 41 | 96 | 88 | 119 | 0 | 66 | 101 | 90 | 87 |
| por | R1 | — | 649 | 6 | 143 | 186 | 139 | 175 | 7 | 174 | 209 | 131 | 128 |
| por | R4 | MS | 220 | 0 | 81 | 62 | 37 | 40 | 0 | 81 | 79 | 32 | 28 |
| por | R4 | GP | 417 | 0 | 57 | 124 | 102 | 134 | 0 | 91 | 127 | 99 | 100 |

Діагностичний сигнал: por, R4, школа MS: max VIF=5.452>5. Точність окремих умовних оцінок обмежена; регресори не вилучали.

Найбільший leverage 0.511 у mat/R1; технічна межа не порушена. Рідкісні категорії R1 і впливові записи потребують обережної інтерпретації.

VIF за термами — robustness_vif.csv. Cook/leverage/VIF-прапорці не видаляють записи. Baseline звірено з P05 на atol=rtol=1e-10; усі baseline_check мають matches=true. Три фігури у PNG/SVG показують різні estimands окремо й залишають видимими відмови.

Самозвіти, дві школи, невиміряні здібності/ресурси, можливий перетин предметів та оригінальний відбір моделі обмежують узагальнення. Немає причинного ефекту або доказу відсутності асоціації з незначущості. Guardian-розбіжність M10, невідомий авторський SE й бібліографічна вимога курсу лишаються відкритими. Передача P07: P06_handoff.md; аудит: reviews/P06_robustness_review.md. K3 ще не пройдена.
