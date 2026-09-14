# Clinical form UX revision — 2026-09-10

User review found that the nRefer-only appendix repeated clinical entry and separated GCS components from the total. `case_form.arrange()` now places the existing stored keys beside the relevant clinical fields; no database migration or patient-data rewrite was performed.

- GCS total and E/V/M share one panel. Complete valid components calculate the total; total-only records remain possible. An existing inconsistent total is shown for explicit reconciliation on initial load.
- AN and birth are beside patient details; transport beside EMS arrival; BP beside admission GCS; CT, Stroke Unit and surgery timing beside their corresponding clinical questions.
- Known ward mappings and supported diagnosis mappings show their source instead of asking for a second choice. Death/referral reuse existing answers. Existing explicit values remain visible and preserved for review.
- CT timing can explicitly reuse C5. This is opt-in because C5 also covers MRI. Choosing separate CT timing retains the previous fields; switching to shared timing does not erase previous overrides. The mapper validates and uses C5 only when selected.
- ICD category options now include names, using the NHS tabular list: https://classbrowser.nhs.uk/ICD-10-5TH-Edition/vol1/block-i60-i69.htm . TIA/CVT still require a registry decision; no new diagnosis inference was introduced.

Validation: isolated `python -X utf8 mock/test_nrefer.py` passed all 36 tests (47.923 seconds), including UI interaction, hidden-field value preservation, mapping, no-save guards and consecutive jobs retaining browser tabs for both targets. The restricted-shell run failed the three persistent-browser tests before reaching their expected states; the same suite passed with permission to launch the browser. The application was restarted in that execution context while its browser status was closed.

The local `/case/new` page was inspected in the in-app browser: E3/V4/M5 produced total12 in the same panel, and TIA revealed ICD options with names. Only synthetic unsaved form inputs were used. The user's existing case8001 was not reloaded or saved by this review. No new production nRefer or SSCC submission occurred. Live website session expiry remains governed by those websites.
