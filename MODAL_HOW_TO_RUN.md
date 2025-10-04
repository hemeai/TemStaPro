# Running TemStaPro on Modal

- **Install Modal CLI:** `pip install modal`
- **Authenticate once:** `modal token new` and follow the browser prompt.
- **Run commands from the repo root** (`modal_temstapro.py` must be next to the `temstapro/` package).
- The first invocation provisions the container image and may take several minutes.

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

- `--output-path` / `--per-res-output` / `--per-segment-output` save Modal results locally. Directories are created automatically.
- `--plot-dir` downloads any per-residue plots generated remotely.
- `--more-thresholds` and `--curve-smoothening` forward the matching TemStaPro CLI flags.
- Chunking parameters (`--portion-size`, `--segment-size`, `--window-size-predictions`) are optional overrides for edge cases.

## GPU & Timeout Tweaks

- Set `GPU` to request hardware (default is CPU):
  - `GPU=A10G modal run …`
  - Supported values: `A10G`, `A100`, `H100`, `L4`.
- Extend Modal's execution time limit via `TIMEOUT` (minutes): `TIMEOUT=240 modal run …`.

## Examples

- Single sequence with default thresholds:
  `modal run modal_temstapro.py --fasta-path data/example.fasta --output-path outputs/example.tsv`
- Batch of short sequences plus plots:
  `modal run modal_temstapro.py --fasta-path tests/data/multiple_short_sequences.fasta --output-path outputs/multi.tsv --per-res-output outputs/per_res.csv --plot-dir outputs/plots`
- `modal run modal_temstapro.py --fasta-path tests/data/multiple_short_sequences.fasta --output-path multiple_short_sequences_pred.tsv`

Outputs are written once the remote job finishes; stdout/stderr from TemStaPro stream back to your terminal.
