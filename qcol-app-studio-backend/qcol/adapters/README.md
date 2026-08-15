# Phase 5 adapter boundary

Provider adapters will replace only the `Execute → counts` implementation.
They must accept validated/unrolled OpenQASM 2 measurement circuits and return
a common result contract containing provider, backend, job ID, shots, counts,
compiled metrics, and provenance.

Planned adapters:

- IBM
- Google
- AWS Braket

They are intentionally not implemented or imported in the current release.
