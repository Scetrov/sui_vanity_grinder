# Threat model

## Scope

This repository contains a locally run Python utility that generates Sui vanity
addresses and emits the corresponding private-key material. This document covers
the code, its Docker build, the dependency sources used by that build, and the
local machine and output destination selected by the user.

## Assets

- Generated private keys, including the `suiprivkey` and raw hexadecimal values.
- Output files written with `--out`.
- Integrity of the Python source, Docker base image, and installed crypto
  dependencies.
- The local host's entropy source and execution environment.

## Trust boundaries

- PyPI packages installed by the Dockerfile cross from third-party package
  infrastructure into the local build.
- The Docker base image crosses from its registry into the local build.
- Command-line arguments and the `--out` path cross from the user into the
  utility and local filesystem.
- Generated private keys cross from process memory to terminal output or an
  optional JSONL file.

## Threats and mitigations

| Threat | Impact | Mitigations and operator actions |
| --- | --- | --- |
| Dependency or container-image substitution | Malicious code can access generated key material. | Review dependency and image updates; Dependabot monitors the Docker base image. Build from trusted sources and review Docker changes before use. |
| Execution on a compromised or networked host | Private keys can be copied from memory, terminal history, or output files. | Run offline on a trusted machine, as documented in the README. Avoid shell history and protect or securely remove result files. |
| Private-key disclosure through output handling | Anyone with output access can control the associated Sui account. | Treat `suiprivkey`, raw private-key hex, and JSONL output as secrets. Do not upload, commit, share, or log them. |
| Malicious or unintended output path | Sensitive output can be written where other users or services can read it. | Supply a deliberate `--out` path, use restrictive filesystem permissions, and inspect the destination before running. |
| Unreviewed source or workflow changes | A change can weaken analysis or introduce key exfiltration. | Review pull requests, require appropriate status checks, and protect the default branch through repository settings. |

## Security-sensitive decisions

- Key generation and private-key export occur locally; the tool does not provide
  a remote key-storage or transmission mechanism.
- The repository currently uses inline pip installation in its Dockerfile rather
  than a Python dependency manifest. Until a supported manifest is introduced,
  Dependabot cannot manage those Python packages.
- CodeQL and OpenSSF Scorecard workflows provide continuous repository analysis;
  their enforcement and alert triage require maintainer-managed GitHub settings.

## Review triggers

Revisit this model when changing key generation, output serialization, dependency
sources, Docker build behavior, CI workflows, release processes, or the threat
model's stated trust boundaries.
