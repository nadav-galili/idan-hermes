# Holmes Place Israel class-registration automation research

Validated 2026-09-10. Scope: public GitHub implementations that target Holmes Place Israel, plus non-destructive checks of the public services they call. No real member login or booking was attempted.

## Bottom line

The best starting point is [`raviv-steinberg/holmesplace_register`](https://github.com/raviv-steinberg/holmesplace_register), but it should be treated as reference code rather than installed and run unchanged. Its newer PHP endpoints are still reachable and return the same structured error format the client expects. The other two Israel-specific registrars found are 2017 code built around routes that no longer work as written.

| Repository | Last code push | What it does | Current assessment |
| --- | --- | --- | --- |
| [`raviv-steinberg/holmesplace_register`](https://github.com/raviv-steinberg/holmesplace_register) | 2024-07-02 | Logs in, waits until the configured opening second, polls every second for up to three minutes, selects a preferred/free seat, and registers. | **Promising protocol reference; not production-ready as-is.** |
| [`ehudhala/Holmes`](https://github.com/ehudhala/Holmes) | 2017-02-09 | Scrapes the old website/iframe, discovers favorite activities, and schedules registration when each opens. | **Does not work as written.** Old web and calendar routes are gone; code is Python 2. |
| [`Moshikol/HolmesPlaceRegisterer`](https://github.com/Moshikol/HolmesPlaceRegisterer) | 2017-07-05 | C# one-off for a hard-coded spinning class/seat list using the old SOAP/mobile site. | **Does not work as written.** Old HTTP and registration routes fail, and it contains hard-coded personal/service credentials. |

## Evidence and validation

### 1. `raviv-steinberg/holmesplace_register`

Why it is relevant:

- Its [endpoint configuration](https://github.com/raviv-steinberg/holmesplace_register/blob/main/config.yaml) targets `https://www.holmesplace.co.il/api.php` actions for login, available seats, seat registration, registration, logout, and cancellation.
- The [API wrapper](https://github.com/raviv-steinberg/holmesplace_register/blob/main/src/common/holmes_place_api.py) maintains a cookie session and submits the same branch, lesson, date, time, instructor, and seat fields needed by the current booking flow.
- The [registration manager](https://github.com/raviv-steinberg/holmesplace_register/blob/main/src/utils/lesson_registration_manager.py) logs in shortly before opening, attempts once per second, understands Holmes Place error codes, and falls back from preferred seats to other available seats.
- Commits through [July 2024](https://github.com/raviv-steinberg/holmesplace_register/commits/main/) show it was used for real recurring Pilates/Yoga configuration, substantially newer than the 2017 projects.

Live checks on 2026-09-10:

- An empty, form-encoded POST to the configured [`login` action](https://www.holmesplace.co.il/api.php?action=login) returned HTTP 200 and JSON `success: false` with error code `(1)` for invalid credentials. This matches the repository's expected response envelope and strongly indicates the route is still active.
- Unauthenticated requests to the configured [`getAvailableSeats` action](https://www.holmesplace.co.il/api.php?action=getAvailableSeats) and [`registerToLesson` action](https://www.holmesplace.co.il/api.php?action=registerToLesson) reached the current Cloudflare/PHP application with HTTP 200. A real registration was intentionally not attempted.
- The official [Holmes Place Israel Android listing](https://play.google.com/store/apps/details?id=com.holmesplace) says the app still supports class booking and was updated in June/August 2026; its support contact is Fizikal, consistent with the backend lineage seen in the older integrations.

Why not run it unchanged:

- It has no README, automated tests, CI, release, or license.
- Club, lesson, instructor, weekday, and opening-time data are manually hard-coded in [`holmes_lessons.yaml`](https://github.com/raviv-steinberg/holmesplace_register/blob/main/holmes_lessons.yaml), mostly for club `205`. These values will not reliably map to another branch and can drift whenever the timetable changes.
- The repository commits plaintext member credentials and personal data under [`users_data/`](https://github.com/raviv-steinberg/holmesplace_register/tree/main/users_data). Do not copy that configuration model; use environment secrets or a local ignored secrets file and rotate any credentials ever committed.
- [`main.py`](https://github.com/raviv-steinberg/holmesplace_register/blob/main/main.py) is left in a debugging state: an enormous threshold, a hard-coded user file, and its intended continuous loop commented out. The useful entry point is the lower-level client/registration manager, not the repository's main program.
- The dependency lock is from 2023 and includes unrelated Selenium, Google, email, and WhatsApp packages. It needs trimming and current dependency/security checks.
- Full viability remains **unconfirmed** until one authorized member login can list/validate a target branch's current class IDs and perform a controlled test booking/cancellation. Public probing cannot prove authenticated session semantics or current anti-automation controls.

### 2. `ehudhala/Holmes`

The [README](https://github.com/ehudhala/Holmes/blob/master/README.md) describes exactly the desired behavior: discover favorite activities every few hours and schedule registration at opening time. Its implementation is useful for product behavior, especially schedule discovery and rescheduling.

It is not a viable implementation today:

- [Authentication](https://github.com/ehudhala/Holmes/blob/master/src/holmes/authentication.py) posts to the old `/user/login` page and relies on a specific iframe/cookie handshake. On 2026-09-10 that path redirected to the current homepage rather than exposing the old login form.
- [Activity discovery and registration](https://github.com/ehudhala/Holmes/blob/master/src/holmes/activities.py) call `http://api.holmesplace.co.il/WebSite/HPCalendar.aspx/...`. Port 80 timed out, while the equivalent HTTPS calendar route returned 404.
- It uses Python 2-only behavior (`xrange`, Python 2 `map` list semantics), has no tests, and has not received code since [February 2017](https://github.com/ehudhala/Holmes/commits/master/).

Verdict: borrow its discovery/scheduling idea, not its protocol code.

### 3. `Moshikol/HolmesPlaceRegisterer`

The single [`Program.cs`](https://github.com/Moshikol/HolmesPlaceRegisterer/blob/master/HolmesPlaceRegisterer/Program.cs) logs in through an old SOAP service and repeatedly calls a hard-coded spinning registration route while cycling through preferred seats.

Validation:

- The old code uses plain HTTP. The host did not answer on port 80 during the check.
- Switching to HTTPS showed the [`LoginService.asmx` WSDL](https://api.holmesplace.co.il/WebServices/LoginService.asmx?WSDL) is still published, but the exact `/MobileWebSite/Pages/Spinning.aspx/RegisterToSpinningClass` route used for registration returned 404.
- The program hard-codes a member ID, class/branch details, an email address, service headers, and SMTP credentials. It also depends on Windows drive paths and desktop Notepad. Those are immediate security and portability blockers.
- No code has landed since [July 2017](https://github.com/Moshikol/HolmesPlaceRegisterer/commits/master/).

Verdict: obsolete and unsafe to reuse.

## Recommended implementation direction

Build a small new client around the still-live `api.php` flow, using `raviv-steinberg/holmesplace_register` only to bootstrap field names and response/error handling. First add a read-only discovery command that logs in and resolves the member's allowed branch, current lessons, instructor IDs, seat behavior, and exact registration-opening timestamp. Only after that succeeds should scheduled booking be enabled.

Minimum safeguards:

- local/environment secret storage; never commit member credentials or session cookies;
- `Asia/Jerusalem` timezone with clock synchronization and a small retry window around the server opening time;
- one booking attempt stream per member to avoid the repository's own “multiple devices” error condition;
- idempotency checks for “already registered,” plus conservative retry/backoff for network errors;
- dry-run/list mode, explicit branch/class allow-list, notification on success/failure, and a cancellation path;
- low request frequency (one request per second only in a short opening window), clear logs with credentials/cookies redacted, and a kill switch;
- verify Holmes Place/Fizikal terms and obtain permission before unattended automation.

## Confidence

- **High:** the three repositories above are the GitHub projects returned by exhaustive public repository searches for `"holmes place"`, `holmesplace`, and `holmes-place`, and they are the only ones found that implement Israel registration rather than an unrelated timetable/demo.
- **High:** the two 2017 registration paths do not work as written.
- **Medium:** the 2023–2024 PHP protocol remains usable after authentication; its endpoint and error contract are alive, but an authorized end-to-end booking is still required to establish this.
