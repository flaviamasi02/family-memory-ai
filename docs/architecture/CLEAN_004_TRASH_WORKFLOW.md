# CLEAN-004 — Smart Cleanup and Trash Workflow

`to_trash` is a stable system cleanup category; its display label may be
customized without changing persisted identity. A proposal is separate from the
workflow state (`proposed_to_trash`, `confirmed_to_trash`, `moved_to_trash`,
`move_failed`, or `restored`). Manual corrections remain authoritative.

Automatic proposals are intentionally conservative. Only strong existing
classifier or exact-duplicate evidence can propose Trash. People, strong memory
scores, rarity, restored records, and manual corrections safeguard photographs
from casual proposals. Confidence, source, and a plain-language explanation are
retained. A proposal never initiates a file operation.

The Product Owner must explicitly confirm proposals before moving them. The
deterministic default destination is `Family Memory Trash`, beside the imported
library. A destination inside the scanned library or application repository is
rejected. Moves preserve bytes and extensions, never overwrite, and resolve
name collisions with stable numeric suffixes. The application has no permanent
delete operation in this workflow.

Successful moves preserve PhotoID, set the record inactive for normal Photo
Browser and Memory Review queries, and remain available through Trash history.
Every confirmation, move, failure, rejection, and restore is retained in audit
history. Failed moves retain the source and can be retried. Restore uses the
original folder where possible or an alternate folder and never overwrites.

Cleanup Review defaults to **To review**, which contains active work only. A
separate **Trash History** view contains moved/audit records and their original
and current paths; moved records are never mixed into the normal queue. The same
active predicate gates Photo Browser, Memory Review, classification, thumbnail
and embedding scheduling, candidate selection, scoring, and Album Draft input.
Restore moves bytes safely back to the original folder, marks the logical photo
active with state `restored`, retains both move and restore history, and prevents
an immediate automatic re-proposal.

Database and history writes are batch-capable. UI consumers must refresh once
per completed batch rather than once per file. Tab-switch latency remains a
deferred performance issue and is not addressed by CLEAN-004. Face recognition
is not implemented by this work.
