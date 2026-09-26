# Security

This repository ships configuration, a launcher script, and benchmark scripts that start a
local `llama-server` process. By default that server binds to `127.0.0.1:8080` (localhost only)
— it is not exposed to the network unless you deliberately change that.

## Reporting a vulnerability

Please do not open a public issue for a security concern. Instead:

- Use [GitHub's private vulnerability reporting](https://github.com/victoralcazardev/rx7900xtx-local-llm/security/advisories/new)
  for this repository, or
- Reach out privately via the author's website: <https://victoralcazar.com>.

## Practical notes

- Never commit `local.toml`, `.env` files, API tokens, or Hugging Face access tokens — `local.toml`
  is already git-ignored.
- `scripts/check-repo.py` scans every tracked file for secret-looking strings before each push;
  run it if you're unsure.
- Weights (GGUF files) are never tracked in this repository.
