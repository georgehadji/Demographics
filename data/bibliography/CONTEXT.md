# data/bibliography/

The works the project cites, each once (ADR 0006). `grpop-bib` (`pipeline/src/grpop/bibliography.py`) resolves every DOI and checks it against the expected title and authors before the CSL-JSON is written.

| File | What it does |
|---|---|
| `references.csv` | Citation key, DOI, expected title and author surnames (`;`-separated, in order) of every cited work |
