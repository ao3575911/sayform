# Security

## Capability model
Sayform code has no ambient authority (spec/09-effects-capabilities.md):
- A function declares what it may touch with `needs` (for example `needs console, files`).
- The host grants capabilities only to `main`, under a host policy (`--allow`, `--deny`).
- `with files limited to "./data":` narrows a capability for a block; narrowing can only
  remove authority, never add it.
- `use` imports names, never capabilities.
- `evaluate` runs data-as-code with at most the caller's capabilities.
- The v0 host refuses `network`.

## In scope
- Escaping a capability or a narrowing.
- Bypassing the reference host's sandbox or policy.
- Collisions or ambiguities in the SCS-1 encoding behind content hashes.

## Reporting
Report privately through GitHub Security Advisories:
<https://github.com/ao3575911/sayform/security/advisories/new>. Please do not open a
public issue for a vulnerability.
