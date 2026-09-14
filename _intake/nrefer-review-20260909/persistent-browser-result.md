# SSCC/nRefer continuous browser workflow — 10 September 2026

## Outcome

The local application now dispatches both targets to `app/browser_session.py` rather than launching a disposable filler process for each request. A single Playwright owner thread retains one browser context and a separate live tab for each target. New jobs submitted later reuse those tabs; no token is copied or injected. The live-app SSCC path does not export or restore the legacy session-cookie file.

Confirmed saves return the application to idle without closing tabs. Incomplete/failed jobs hold the current form and block new submissions. The application banner exposes “จบรอบนี้ — คงเบราว์เซอร์ไว้” only during review/hold, with explicit confirmation that unsaved form changes will be discarded and remaining queued cases cancelled. Browser ownership remains reserved even when no fill job is active, preventing the legacy CLI from opening the same profile concurrently.

The no-save guard stays installed while its form is open. Finishing a review returns to the register before removing only that job's guard; if navigation fails the affected tab closes before guard removal. A normal nRefer result that remains uncertain requires local reconciliation after the user checks the remote register.

## Validation

`python mock/test_nrefer.py`: **33 tests passed** in an isolated source/database/profile copy with local mock services.

- Actual SSCC filler: two independent jobs complete using the same browser tab, with local-only automatic Save as a test surrogate. The session marker survives and no legacy cookie file is exported.
- Actual nRefer filler: two separate no-save jobs reuse the same tab/session marker; login flow is called once. Finish/review is coordinated through the application manager, not by closing the browser.
- SSCC/nRefer tabs remain distinct and survive target switching and a synthetic failure.
- Busy/review submissions are rejected, finishing while filling is rejected, and finishing requires explicit acknowledgement in the application endpoint.
- Existing mapping, readback, saved-admission, guard, response-observer and template-JavaScript tests continue passing.
- Python syntax validation and `git diff --check` passed (Windows line-ending warnings only).

The updated local app was started at http://127.0.0.1:8547 and its `/browser/status` endpoint responds. No production patient submission was performed during this change.

## Limits

The new multi-job session workflow has not yet been exercised through real SSCC/nRefer authentication. Earlier live nRefer testing established single-job filling only. Server-side expiry/logout, user closure of a target tab or the app, and browser crashes can still require login. Keeping a tab alive does not extend or bypass server session expiration.

The developer CLI scripts and isolated `mock/live_nrefer_inspection.py` remain one-shot tools. Continuous use is through the local application's send buttons. Existing user edits outside this change were retained; no commit or deployment to an external service was made.
