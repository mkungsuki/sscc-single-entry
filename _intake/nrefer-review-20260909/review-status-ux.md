# Review status and Stroke Unit timing — 2026-09-10

The local page rendered the duplicate-recovery panel whenever the database state was `review`, including a currently running fill. This confused normal progress with an unconfirmed prior save. The optional `ref` input also exposed implementation vocabulary and the global input width separated the checkbox from its label.

Changes: hide recovery by default; show only after browser work has ended and a fresh case-status response still requires reconciliation. Explain why a registry check is needed, keep the original explicit confirmation, place the optional reference under details, and align checkbox and label. Browser progress now distinguishes waiting from finished work; inspection instructions no longer tell the user to close Edge. Stroke Unit source text displays the actual admission date/time used by the mapper.

Validation: three existing UI/template tests and the new `test_recovery_instructions_only_after_job_ends` passed in disposable test copies. The new test verifies visibility across working/idle/review states, optional-reference collapse, and the derived Stroke Unit time.

Live case8051: HN/AN succeeded after initialization fix. At 23:48:59 the worker reported failures for all eight date groups, including Stroke Unit and birth; other numeric/text fields populated. Public template disables date controls while `loading` is true. HIS getPerson uses a POST read and does not clear loading if its awaited call throws; the no-save guard blocks unlisted POST reads. This is a hypothesis pending confirmation, not yet a validated root cause. Do not broaden the guard or claim dates fixed without observing the failed read/control behavior.

Current local server retains its cached templates and live Edge review session. UX changes are on disk; activation requires a server restart once user review is complete. Do not discard that session without permission.
