# HN/AN blank after automatic fill — 2026-09-10

Observed: synthetic case8051 has HN/AN in SSCC but both fields are blank on nRefer; later fields contain the synthetic data. The user manually typed the same HN and tabbed away; it remained. This rules out rejection of that alphanumeric HN in the tested manual interaction.

Source trace: public `chunk-UIVIL3PE.js`, `getStrokePatient()` awaits `getEvaluateChoice()` before replacing `editRow` for a new record. The old `open_add_form()` waited only for a visible HN input. The request tracker in `fill_form()` was attached after opening the form and could miss requests already in flight. This is a demonstrated race compatible with the screenshot, but the precise live reset has not been captured in runtime traces.

Reproduction: local mock exposes the inputs immediately and resets HN/AN after a delayed initialization response. `test_open_waits_for_form_initialization` failed before the fix (initialized marker absent), then passed after the fix, including final HN/AN readback.

Fix: attach request tracking before navigation/Add new; wait for fetch/XHR completion and one second of quiet before typing. Detach listeners in finally. Also settle each HN/AN lookup separately and stop if either identity changes, rather than continuing to populate the rest of a mismatched record. No forced DOM/model writes or automatic identity retries.

Validation: full isolated suite passed 37 tests in 70.519 seconds. User approved restart after completing review; browser state was closed and the local server was restarted with the fix. Production re-test remains necessary; the same live reset has not yet been confirmed with instrumentation.
