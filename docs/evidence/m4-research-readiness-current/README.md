# M4 research readiness and local availability

This evidence is a read-only operator preflight for the current formal trial
package. It is separate from participant assignment and collection, and it
does not modify the frozen package or start a service.

The check is run with:

```bash
.venv/bin/python scripts/research_trial_readiness.py \
  --package .archcanvas/m4-research-trial-routing-user-simulation-v2 \
  --output docs/evidence/m4-research-readiness-current/attempt-2/receipt.json
```

`research_trial.py verify` must pass, every slot must remain pristine and
unassigned, and the package inventory must be byte-identical before and after
the check. The companion port probe binds and releases `127.0.0.1` at each
registered slot port. `available` means no process occupied that endpoint at
the instant of the probe; it does not mean that a service was started. An
occupied or permission-blocked port is never reported as free.

Attempt 1 ran in the managed restricted environment and recorded `EPERM` for
all five socket probes in
`attempt-1/receipt.json`. Attempt 2 used a read-only network probe with the
necessary local capability and recorded ports 43911–43915 as available. The
official package verification passed, all five slots remained pristine, and
the package inventory was unchanged.

The resulting state is `packageReadyForOperatorLaunch=true`. Services remain
`not-started`, no assignment was made, `humanAcceptance=false`, and
`humanPublicationReview=false`. A real operator must still record the browser
environment, assign each real participant immediately before timing, start
one service per assigned slot, collect actual task/export/screenshot bytes,
and obtain independent review.
