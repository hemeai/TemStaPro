# Running TemStaPro on Modal

## Conda Environment Setup

How to manage conda: 
https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-conda.html

How to manage environments: 
https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html

- Install Miniconda or Anaconda if needed.
- Create an isolated environment (Python 3.10+):
  - `conda create -n hemeai python=3.10`
  - `conda activate hemeai`
- Inside the environment, install any project extras you require (e.g. `pip install -e .`).

## Install Modal & Sign In

- With the environment active: `pip install modal`
- Authenticate once per machine: `modal token new` and complete the browser flow to create the user session.
- Run commands from the repo root so `modal_temstapro.py` sits alongside the `temstapro/` package.
- Expect the first run to spend a few minutes provisioning the Modal container image.

## Examples

- Single sequence with default thresholds:
  `modal run modal_temstapro.py --fasta-path data/example.fasta --output-path outputs/example.tsv`
- Batch of short sequences plus plots:
  `modal run modal_temstapro.py --fasta-path tests/data/multiple_short_sequences.fasta --output-path outputs/multi.tsv --per-res-output outputs/per_res.csv --plot-dir outputs/plots`

## Command Template

```
modal run modal_temstapro.py \
  --fasta-path path/to/input.fasta \
  --output-path outputs/mean_predictions.tsv \
  [--per-res-output outputs/per_residue.tsv] \
  [--per-segment-output outputs/per_segment.tsv] \
  [--plot-dir outputs/plots] \
  [--more-thresholds] [--curve-smoothening] \
  [--portion-size 1000] [--segment-size 41] [--window-size-predictions 81]
```

- `--output-path` / `--per-res-output` / `--per-segment-output` save Modal results locally; directories are created automatically.
- `--plot-dir` downloads any per-residue plots generated remotely.
- `--more-thresholds` and `--curve-smoothening` forward the matching TemStaPro CLI flags.
- Chunking parameters (`--portion-size`, `--segment-size`, `--window-size-predictions`) are optional overrides for edge cases.

## GPU & Timeout Tweaks

- Set `GPU` to request hardware (default is CPU):
  - `GPU=A10G modal run …`
  - Supported values: `A10G`, `A100`, `H100`, `L4`.
- Extend Modal's execution time limit via `TIMEOUT` (minutes): `TIMEOUT=240 modal run …`.

Outputs are written once the remote job finishes; stdout/stderr from TemStaPro stream back to your terminal.
