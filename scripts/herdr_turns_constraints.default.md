# herdr-turns default constraints (autonomous coding)

Bundled default for `herdr-turns` when `--constraints` is omitted.
Disable with `--no-default-constraints`. Override with `--constraints PATH`.

## Write boundaries

Allowed write roots (unless the owner goal explicitly widens scope):

- `scripts/`
- `.agents/skills/herdr-self-evolve/`
- `FORK.md`
- `README.md`

Do **not** edit `src/` or other staged Rust / upstream cherry-pick trees.

## Hard stops

- Do **not** `git commit`, `git push`, create tags, or force-push.
- Do **not** print, copy, or send secrets (API keys, tokens, `.env`, private keys).
- Do **not** exfiltrate private data to public remotes or paste sites.

## Verify before done

- Before writing `VERIFIED` / claiming DONE, run a concrete command or check
  for the scope you changed (e.g. `python3 -m unittest …`, `just check`).
- Vague VERIFIED (`looks good`, `manual review`, `should work`) is rejected.

## Headless / overnight

Prefer small, verifiable turns. If blocked on owner judgment, ESCALATE with a
clear question rather than guessing.
