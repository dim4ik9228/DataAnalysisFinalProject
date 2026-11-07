# K4 — технічна відтворюваність і готовність до здачі

Дата:2026-11-07. **technical_reproducibility_status=PASS**.
**course_submission_status=open; готовність до здачі не підтверджено.**

Код candidate9e31b46 перевірено у робочій копії й незалежному локальному clone
на тому самому Windowsx64 комп'ютері. Нові analysis/renderer середовища, нове
завантаження UCI, без перенесення фазових логів або обчислених входів. Під час
виправлень candidate зберігали встановлені незмінні pinned середовища; raw/
processed/logs/generated outputs перед фінальним clone-run видалено.

- Обидва повні запуски:00–05 у чистих ядрах, reports,267 тестів/Ruff/protocol/lock.
- 46/46baseline файлів збіглися побайтово; K3seal/review та6 фінальних висновкових
  outputs чинні. H1/H2/H3, partialM10, unknownSE та літературні межі незмінні.
- Renderer без Codex:Quarto1.11.9/Typst0.15.1, Node22.15.0/Playwright1.62.1,
  Python3.12.10/pypdf6.21.4. Chrome156.0.8078.80 записаний, не pinned.
- Самодостатні HTML,12 сторінок звіту/16 слайдівPDF;16notes і5Plotly;0 зовнішніх
  HTTP(S)запитів. Усі28PDFсторінок оглянуто незалежно.
- Reviewcandidate ZIP:allowlist, hashes після unpack,6executednotebooks без
  studentdebugrows/локальних шляхів у outputs. Перевірено Gitinit/add/commit
  розпакованого комплекту:sealed P07review bytes збережено.

Storage-виправлення P09 зберігає точні історично аудитовані байти P07review уGit;
це виправлення кінців рядків/зберігання, не новий дослідницький аудит і не reseal.

[Незалежний аудит](reviews/P09_reproducibility_review.md),
[публічні докази](evidence/p09_validation.json),
[checklist](submission_checklist.md), [відтворення](reproducibility.md).
Sidecar K4_readiness.json зв'язує код/входи/виходи/review й execution receipts.
Читати PASS лише разом із чинними hashes; старий текст не підтверджує змінені
артефакти. Повторний запуск із новими фазовими receipt потребує перевірки нового
ланцюга; sidecar автоматично не перезаписується під бажаний результат.

Відкрито:вимога3–5citing/checking (1 первинне цитування,1metadata-only,
0 перевірених освітніх реплікацій); реальна репетиція10–15 хв; фактичний канал,
строк і формат подання. Бюджет720 с не є виміряним виступом. Погодження викладача
не отримано й не вигадується. Reviewcandidate не є підтверджено готовою здачею.
Нічого не опубліковано/не завантажено до системи курсу.
