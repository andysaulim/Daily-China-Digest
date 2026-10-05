"""
China Daily Brief — Pipeline Entry Point
Orchestrates collect → resolve → enrich → digest → post-process → validate
(regenerate on failure) → trackers → render → archive → send → ledger → metrics.

Posture, carried over from the Korea, Japan and Australia briefs after each of
them learned it the hard way:

  * SOURCE-OR-SKIP is enforced in code, not only in the prompt. An item whose
    URL is not in the collected corpus is repaired by headline match or
    deleted. Nothing unsourced ships.
  * The send is fail-closed. A CRITICAL validation finding regenerates (Sonnet,
    then Opus); if it persists the brief is rendered for review, NOT sent, and
    the run exits non-zero so the failure alert fires. The previous version
    printed the failures and sent anyway.
  * Trackers, the published ledger and last_sent.txt are written only after
    validation passes and (for the ledger and marker) only after the email
    actually went out, so a failed run cannot poison state or block a retry.
"""