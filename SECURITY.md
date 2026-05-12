# Security notes (EVE-EMU)

## Bot tokens and `.env`

- **Never commit** `discord-bot/bot/.env` (or any file named `.env` containing secrets). The repo root `.gitignore` ignores `.env` everywhere so this cannot happen again from normal `git add .` flows.
- Use **`discord-bot/bot/example.env`** / **`.env.example`** as templates only (no real tokens).

## If a Discord bot token was committed

1. **Discord** may reset the token automatically (e.g. Safety Jim). Treat the token as compromised even if reset.
2. **Removing the file from the latest commit is not enough** — the token still exists in **Git history** until you rewrite history or use GitHub secret scanning / support to purge the blob.
3. To purge locally then force-push (coordinate with your team; rewrites history):

   ```bash
   # Example: install git-filter-repo, then remove path from all commits
   pip install git-filter-repo
   git filter-repo --path discord-bot/bot/.env --invert-paths
   ```

   Alternatively use [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/). After rewriting, **rotate all secrets** that ever lived in that file.

## Reporting

Report security issues to your org’s maintainers privately (do not open a public issue with secrets).
