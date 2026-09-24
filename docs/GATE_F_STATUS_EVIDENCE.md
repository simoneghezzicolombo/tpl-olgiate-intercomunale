# Gate F upstream status evidence

A typed command such as `--gate-status B=PASS` is useful for provisional development tests but is **not authoritative evidence** and can never unlock a definitive Gate F PASS.

For definitive execution, Gate F requires `--gate-status-file <bundle.json>`. The bundle follows `schemas/gate_f_status_bundle.schema.json` and contains exactly Gates A-E.

Each Gate entry records:

- verdict;
- full 40-character source commit SHA;
- source branch;
- one or more repository-relative evidence files;
- exact SHA256 of every evidence file.

The loader verifies that each evidence path stays inside the repository, exists and matches the declared SHA256. This prevents a stale or subsequently edited PASS document from silently unlocking Gate F.

This mechanism validates **identity and integrity of the cited evidence**, not its substantive correctness. A bad upstream audit does not become true because its hash matches. Gate F still depends on independent substantive review of B/C/D/E.

## Integration rule

The final integration workstream should create the bundle only after the relevant upstream commits and evidence documents have been incorporated into the integrated repository state. `integration_id` identifies that integration snapshot or release candidate.

If all manually supplied statuses say PASS but no verified bundle is provided, Gate F forcibly downgrades the result to:

`PROVISIONAL / BLOCKED_UNVERIFIED_GATE_STATUS_EVIDENCE`

and removes any recommended scenario ID.
