# Джерела та статус перевірки

Дата P02: 2026-11-05. «Перевірено» стосується наведених тверджень і місць доказу; рівень доступу розрізняється.

| Джерело | Місце / роль | Перевірка й локальний доказ |
|---|---|---|
| [Інструкція курсу](https://kleban.notion.site/research-how-to) | Реплікаційний трек, етапи 0–10, чеклісти | Повністю повторно прочитано; [text](evidence/course_requirements_source.txt), [provenance](evidence/course_requirements_provenance.json), [матриця](course_requirements.md) |
| [Da (2025)](https://doi.org/10.1038/s41598-025-89394-2) | Data, Sec6, Case #1, Eq2, Tab8, Data availability | Повний первинний текст: [офіційний Europe PMC XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11968921/fullTextXML); [snapshot](../data/reference/sources/da2025_fulltext.xml), [manifest](../data/reference/sources/manifest.json) |
| [Таблиця 8](https://www.nature.com/articles/s41598-025-89394-2/tables/8) | 8 колонок outcome G3 | Звірено68 пар та8моделей незалежно з Tab8 XML; [еталони](../data/reference/README.md), [аудит](reviews/P02_protocol_review.md) |
| [UCI Student Performance](https://archive.ics.uci.edu/dataset/320/student+performance) | Коди, походження, CC BY4.0; DOI10.24432/C5TG7T | Сторінку прочитано й збережено snapshot; учнівські файли отримано у P03 за tracked-хешами; див. data_provenance.json і data_passport.md |
| [Cortez & Silva (2008), авторська PDF-копія](https://www.researchgate.net/profile/Paulo-Cortez-4/publication/228780408_Using_data_mining_to_predict_secondary_school_student_performance/links/0fcfd510a4efaa10b0000000/Using-data-mining-to-predict-secondary-school-student-performance.pdf) | Первинна робота датасету, Student Data/Table1 |8сторінок прочитано web PDF parser; reviewer targeted-check. [Нотатки](../data/reference/sources/cortez2008_reading.md). Прямого локального PDF немає:403; institutional/author host недоступний |
| [Davis-Kean (2005)](https://pubmed.ncbi.nlm.nih.gov/15982107/) | Очікування й домашнє середовище | Первинна анотація та доступний повний PDF; Method Participants p296, інші деталі у literature.csv |
| [Dubow et al. (2009)](https://digitalcommons.wayne.edu/mpq/vol55/iss3/4/) | Часова послідовність і віддалені результати | Первинна анотація журналу; повний текст не заявляємо прочитаним |
| [Waters et al. (2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12264891/) | Сімейні та когнітивні шляхи | PubMed abstract і релевантні Methods/Results author manuscript |

Бібліографія, DOI, популяції, методи, обмеження й точні місця доказу — [literature.csv](literature.csv). Цільовий синтез — [literature_review](literature_review.md).

## Відкриті обмеження

- Три роботи у літогляді — **пов'язані**, не три підтверджені citing/checking роботи Da. Це відкрита невиконана буквально вимога курсу; див. матрицю.
- Конкретний авторський covariance estimator таблиці8 не встановлено. HC3 у протоколі — наше наперед визначене рішення, не приписана авторові процедура.
- N390/637 — числа публікації; у P03 перевірено фактичну відповідність фільтрованим рядкам UCI. Це не відтворення коефіцієнтів.
- Текстовий знімок Notion не є повним офіційним експортом оформлення: збережено текстові властивості всіх блоків, включно з таблицями та прикладами.

Технічні правила HC/use_t/Holm звірено з офіційною документацією statsmodels; в проєкті зафіксовано0.14.6. При реалізації P05 використовувати API встановленої версії, а не автоматично оновлювати пакети до latest/stable:
[robust covariance](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.RegressionResults.get_robustcov_results.html), [multiple tests](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html).

## Дані P03

Офіційний [архів](https://archive.ics.uci.edu/static/public/320/student+performance.zip) містить актуальний student.zip та old-копію; використано лише актуальний. [Pinned provenance](data_provenance.json) зберігає п’ять raw-хешів, дату й CC BY4.0. Дані та row-level журнали локальні, у Git — тільки метадані та агрегати.
