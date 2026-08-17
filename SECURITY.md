# Security Policy

## Supported Versions

`zero-employee` is pre-1.0 (`0.x`) and evolving quickly. Security fixes are released
against the **latest published version only** — there is no long-term support branch
while the project is in this phase.

| Version | Supported |
| ------- | --------- |
| Latest `0.x` on PyPI | ✅ |
| Anything older | ❌ |

Once the project reaches `1.0`, this table will be revised to name a support window.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for a security vulnerability.**

Instead, report it privately by emailing **zeroemployeeorg@dreamhuggers.com** with:

- A description of the vulnerability and its potential impact.
- Steps to reproduce it (a minimal repro is enormously helpful).
- The version of `zero-employee` affected (`zeo --help` or `pip show zero-employee`).
- Your assessment of severity, if you have one — we'll form our own independently, but
  it helps us triage.

You can expect an acknowledgment within **5 business days**. We'll keep you updated as
we investigate and work on a fix, and we'll credit you in the release notes (unless you'd
prefer to stay anonymous).

## Scope

`zero-employee` is a CLI tool that reads and writes files in a local git corpus, executes
git subprocesses, and (only when explicitly asked via `--count-via anthropic` or
`--calibrate`) makes outbound calls to Anthropic's `count_tokens` API using a credential
you provide. Categories worth reporting:

- **Path traversal / arbitrary file write** — anything that lets a malicious corpus or
  a malicious template (`$ZEO_TEMPLATES_DIR`, `~/.config/zeo/templates/`) cause `zeo` to
  read or write outside the intended target directory.
- **Command injection** — anything that lets untrusted frontmatter or file content reach
  a shell command unsanitized.
- **Credential handling** — anything that could cause an `ANTHROPIC_API_KEY` (or a
  credential under a caller-specified `--api-key-env` variable) to be logged, written to
  disk, or leaked into a committed artifact.
- **Supply chain** — a compromised dependency, a malicious PyPI upload impersonating this
  project, or a weakness in the trusted-publishing (OIDC) release pipeline described in
  [`docs/releasing.md`](docs/releasing.md).

**Not in scope:** the governance/linting rules themselves being "too strict" or "too
loose" for your use case — that's a design discussion, not a security report. Open a
regular issue for those.

## Our Commitments

- We never commit tokens or credentials to this repository, and CI never has access to
  publish credentials except through GitHub's OIDC trusted-publishing flow (no long-lived
  PyPI tokens stored anywhere).
- Every release wheel is scanned for identity/credential leakage before publishing (see
  [`docs/releasing.md`](docs/releasing.md)) — the same discipline we ask contributors to
  follow when preparing a release.
- We will not disclose a reported vulnerability publicly until a fix is released, unless
  the reporter and maintainers agree on an earlier disclosure timeline together.
