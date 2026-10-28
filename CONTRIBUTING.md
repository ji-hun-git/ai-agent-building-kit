# Contributing

Keep it small, readable and dependency-free: the template should still read in one sitting after your change.

- **Run what CI runs**, from `template/`: `python -m unittest` and `python -m kit.evals examples/hr/cases.json --agent examples.hr:build --k 3`.
- **Every fix comes with a test that fails without it.** Every guard rule names the attack it stops.
- **Every fact carries its source and the date it was opened** in `guide/`, `sota/` and the skill. Mark vendor-reported figures as such. No prices.
- **Figures are code.** Edit [`scripts/make_figures.py`](scripts/make_figures.py) and run it; never edit a PNG. `docs/figures/social-preview.png` is the repository's social card.
- **Refreshing the snapshot:** run `python skill/building-ai-agents/scripts/check_freshness.py --no-models --write-snapshot skill/building-ai-agents/references/snapshot.json`, read the changelog of everything it reports as changed, and update `sota/README.md` to match.
- **Security issues** go by email, not issues: see [SECURITY.md](SECURITY.md).
