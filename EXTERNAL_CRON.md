# External cron: a trigger that does not depend on GitHub's scheduler

GitHub's `schedule:` is best effort. It routinely delays a slot and sometimes
drops one. On Sep 7 2026 it deferred **every** slot by about 5.5 hours: the
6:07 AM ET cron executed at 15:45 UTC. On Sep 8 2026 no slot fired at all
through 13:30 UTC. The six staggered crons in `daily-digest.yml` do not help
when the whole queue slips together, because they slip together too.

An external scheduler POSTing `workflow_dispatch` is an independent trigger.
This file is the setup.

## Why this is safe to fire repeatedly

An unforced **live** dispatch obeys the same once-a-day guard as a scheduled
run: it reads `last_sent.txt` from the live branch tip and exits without
sending if the marker is already today's ET date. Before this, any dispatch
ran unconditionally, so an external cron plus a GitHub slot that did fire
would have sent the edition twice.

The practical consequence: **point the cron at every hour of the delivery
window, not at one moment.** One failed POST, one slow morning, or one
scheduler outage then costs nothing. Recipients still get exactly one email,
on whichever attempt lands first.

`force: true` restores unconditional sending. It is the manual escape hatch
for re-sending a day deliberately. A recurring caller must never set it.

## 1. Create the token

A **fine-grained** personal access token, not a classic one.

- Resource owner: `andysaulim`
- Repository access: **Only select repositories** → `Daily-China-Digest`
- Repository permissions: **Actions: Read and write** (this is the only one
  needed; Metadata: Read is added automatically)
- Expiration: set a calendar reminder for the day before. An expired token
  fails silently from the scheduler's point of view — it just gets a 401 —
  which is the same invisible failure this whole file exists to prevent.

Store it in the scheduler's secret field. It never belongs in this repo.

## 2. The request

```http
POST /repos/andysaulim/Daily-China-Digest/actions/workflows/daily-digest.yml/dispatches HTTP/1.1
Host: api.github.com
Authorization: Bearer YOUR_TOKEN
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json

{"ref":"main","inputs":{"mode":"live"}}
```

Success is **204 No Content** with an empty body. Anything else is a failure:

| Status | Meaning |
| --- | --- |
| 401 | Token expired or wrong |
| 403 | Token lacks Actions: write, or is not scoped to this repo |
| 404 | Wrong repo, wrong workflow filename, or the token cannot see the repo |
| 422 | `ref` does not exist, or an input name is wrong |

Omit `force` entirely. It defaults to `false`, which is what makes the call
idempotent.

As curl, for testing by hand:

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $GH_DISPATCH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -w '%{http_code}\n' \
  https://api.github.com/repos/andysaulim/Daily-China-Digest/actions/workflows/daily-digest.yml/dispatches \
  -d '{"ref":"main","inputs":{"mode":"live"}}'
```

## 3. Pick a scheduler

**cron-job.org** (free, no code). Create a job:

- URL: `https://api.github.com/repos/andysaulim/Daily-China-Digest/actions/workflows/daily-digest.yml/dispatches`
- Method: `POST`
- Headers: the three above (`Authorization`, `Accept`, `X-GitHub-Api-Version`)
- Body: `{"ref":"main","inputs":{"mode":"live"}}`
- Schedule: every hour at :05, from 10:00 to 16:00 UTC, timezone **UTC**
  (`5 10-16 * * *`). Seven attempts. The window is deliberately wider than
  the delivery target so it covers both DST states: 10:05 UTC is 6:05 AM in
  daylight time but 5:05 AM in standard time, and the tail keeps a 6 AM ET
  first attempt year round. Extra attempts cost nothing once the dispatch is
  idempotent, which is the point of the guard change.
- Enable failure notifications to your email, and treat 204 as the only success

**Cloudflare Worker** (free tier, if you would rather not hand a third party
the token). `wrangler secret put GH_DISPATCH_TOKEN`, then:

```js
export default {
  async scheduled(event, env, ctx) {
    const r = await fetch(
      "https://api.github.com/repos/andysaulim/Daily-China-Digest/actions/workflows/daily-digest.yml/dispatches",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GH_DISPATCH_TOKEN}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "china-digest-cron",
        },
        body: JSON.stringify({ ref: "main", inputs: { mode: "live" } }),
      },
    );
    if (r.status !== 204) console.log(`dispatch failed: ${r.status} ${await r.text()}`);
  },
};
```

with `wrangler.toml`:

```toml
[triggers]
crons = ["5 10-16 * * *"]
```

Note `User-Agent`: GitHub's API rejects requests without one, and some
runtimes do not set a default.

**A machine you control.** If a laptop or server is reliably awake in the
morning, `crontab` calling the curl above is the fewest moving parts. It is
also the least reliable trigger if the machine sleeps, which is the failure
mode the external scheduler is meant to remove.

## 4. Verify

After the first firing:

1. The Actions tab shows a run with event `workflow_dispatch`.
2. `last_sent.txt` on `main` is today's ET date.
3. `metrics.jsonl` has exactly **one** live entry for today. Two means the
   guard did not hold, which is a bug — report it rather than working around
   it.

Then let a day pass where GitHub's own schedule also fires, and confirm
`metrics.jsonl` still shows one live run for that date. That is the real test
of the guard, and it is the whole point of the change that made this safe.
