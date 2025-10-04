# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "modal>=1.0",
# ]
# ///
"""Modal Labs entrypoint for running TemStaPro predictions.

The script mirrors the CLI exposed by ``temstapro`` while providing
dependency installation, cached model weights, and optional GPU execution
inside Modal Labs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import modal


HERE = Path(__file__).resolve().parent
REMOTE_REPO_PATH = Path("/workspace/TemStaPro")
REMOTE_FASTA_DIR = Path("/tmp/temstapro")
HF_CACHE_ROOT = Path("/cache/hf")
EMBEDDINGS_CACHE_ROOT = Path("/cache/embeddings")
PROTTRANS_DIR = HF_CACHE_ROOT / "prottrans"


def _gpu_from_env() -> Optional[modal.gpu.GpuType]:
    """Translate the ``GPU`` environment variable into a Modal GPU config."""

    gpu_env = os.environ.get("GPU", "").upper()
    if gpu_env == "A10G":
        return modal.gpu.A10G()
    if gpu_env == "A100":
        return modal.gpu.A100()
    if gpu_env == "H100":
        return modal.gpu.H100()
    if gpu_env == "L4":
        return modal.gpu.L4()
    return None


GPU_CONFIG = _gpu_from_env()
TIMEOUT_MINUTES = int(os.environ.get("TIMEOUT", "180"))


image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libgl1")
    .run_commands(
        "pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.2.1"
    )
    .pip_install(
        "huggingface-hub==0.21.4",
        "matplotlib==3.8.3",
        "numpy==1.26.4",
        "pandas==2.2.1",
        "sentencepiece==0.1.99",
        "tqdm==4.66.2",
        "transformers==4.38.2",
    )
    .add_local_dir(str(HERE), str(REMOTE_REPO_PATH))
)


hf_volume = modal.Volume.from_name("temstapro-hf-cache", create_if_missing=True)
embeddings_volume = modal.Volume.from_name("temstapro-embeddings", create_if_missing=True)


app = modal.App("temstapro")


def _prepare_workdir(fasta_name: str) -> Tuple[Path, Path, Path]:
    """Create a clean working directory for each remote execution."""

    if REMOTE_FASTA_DIR.exists():
        shutil.rmtree(REMOTE_FASTA_DIR)
    REMOTE_FASTA_DIR.mkdir(parents=True, exist_ok=True)

    input_path = REMOTE_FASTA_DIR / fasta_name
    outputs_path = REMOTE_FASTA_DIR / "outputs"
    plots_path = REMOTE_FASTA_DIR / "plots"
    outputs_path.mkdir(parents=True, exist_ok=True)
    plots_path.mkdir(parents=True, exist_ok=True)
    return input_path, outputs_path, plots_path


def _env_prepare() -> None:
    """Ensure cache directories exist and update env vars for huggingface/torch."""

    for path in (HF_CACHE_ROOT, EMBEDDINGS_CACHE_ROOT, PROTTRANS_DIR):
        path.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("HF_HOME", str(HF_CACHE_ROOT))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(HF_CACHE_ROOT / "transformers"))
    os.environ.setdefault("XDG_CACHE_HOME", str(HF_CACHE_ROOT))
    os.environ.setdefault("TORCH_HOME", str(HF_CACHE_ROOT / "torch"))


def _collect_outputs(paths: Dict[str, Optional[Path]]) -> Dict[str, Optional[bytes]]:
    """Return the contents of generated files keyed by output identifier."""

    results: Dict[str, Optional[bytes]] = {}
    for key, output_path in paths.items():
        if output_path and output_path.exists():
            results[key] = output_path.read_bytes()
        else:
            results[key] = None
    return results


def _gather_plot_files(plot_dir: Path) -> List[Tuple[str, bytes]]:
    """Return relative paths and bytes for every file found in ``plot_dir``."""

    if not plot_dir.exists():
        return []

    entries: List[Tuple[str, bytes]] = []
    for file_path in sorted(plot_dir.rglob("*")):
        if file_path.is_file():
            rel = file_path.relative_to(plot_dir)
            entries.append((str(rel), file_path.read_bytes()))
    return entries


@app.function(
    image=image,
    gpu=GPU_CONFIG,
    timeout=TIMEOUT_MINUTES * 60,
    volumes={
        str(HF_CACHE_ROOT): hf_volume,
        str(EMBEDDINGS_CACHE_ROOT): embeddings_volume,
    },
)
def run_temstapro(
    *,
    fasta_bytes: bytes,
    fasta_name: str,
    more_thresholds: bool,
    portion_size: int,
    segment_size: int,
    window_size_predictions: int,
    curve_smoothening: bool,
    include_plots: bool,
    mean_output_name: Optional[str],
    per_res_output_name: Optional[str],
    per_segment_output_name: Optional[str],
) -> Dict[str, object]:
    """Remote execution wrapper around the original TemStaPro CLI."""

    _env_prepare()
    input_path, outputs_path, plots_path = _prepare_workdir(fasta_name)
    input_path.write_bytes(fasta_bytes)

    mean_output_path = outputs_path / mean_output_name if mean_output_name else None
    per_res_output_path = (
        outputs_path / per_res_output_name if per_res_output_name else None
    )
    per_segment_output_path = (
        outputs_path / per_segment_output_name if per_segment_output_name else None
    )

    cmd: List[str] = [
        "python",
        str(REMOTE_REPO_PATH / "temstapro"),
        "-f",
        str(input_path),
        "-d",
        str(PROTTRANS_DIR),
        "-t",
        str(REMOTE_REPO_PATH),
        "-e",
        str(EMBEDDINGS_CACHE_ROOT),
        "--portion-size",
        str(portion_size),
        "--segment-size",
        str(segment_size),
        "--window-size-predictions",
        str(window_size_predictions),
    ]

    if more_thresholds:
        cmd.append("--more-thresholds")
    if curve_smoothening:
        cmd.append("--curve-smoothening")
    if mean_output_path:
        cmd.extend(["--mean-output", str(mean_output_path)])
    if per_res_output_path:
        cmd.extend(["--per-res-output", str(per_res_output_path)])
    if per_segment_output_path:
        cmd.extend(["--per-segment-output", str(per_segment_output_path)])
    if include_plots:
        cmd.extend(["--per-residue-plot-dir", str(plots_path)])

    completed = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "TemStaPro execution failed with return code "
            f"{completed.returncode}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )

    file_payload = _collect_outputs(
        {
            "mean": mean_output_path,
            "per_res": per_res_output_path,
            "per_segment": per_segment_output_path,
        }
    )

    plots_payload = _gather_plot_files(plots_path) if include_plots else []

    return {
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "files": file_payload,
        "plots": plots_payload,
    }


def _write_optional_file(output_path: Optional[str], payload: Optional[bytes]) -> None:
    if output_path and payload is not None:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)


def _write_plots(plot_dir: Optional[str], plots: Iterable[Tuple[str, bytes]]) -> None:
    if not plot_dir:
        return

    base = Path(plot_dir)
    base.mkdir(parents=True, exist_ok=True)
    for relative_path, blob in plots:
        target = base / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)


@app.local_entrypoint()
def main(
    *,
    fasta_path: str,
    output_path: Optional[str] = None,
    more_thresholds: bool = False,
    per_res_output: Optional[str] = None,
    per_segment_output: Optional[str] = None,
    plot_dir: Optional[str] = None,
    portion_size: int = 1000,
    segment_size: int = 41,
    window_size_predictions: int = 81,
    curve_smoothening: bool = False,
) -> None:
    """Run TemStaPro remotely on Modal using local CLI-style arguments."""

    fasta_file = Path(fasta_path)
    if not fasta_file.is_file():
        raise FileNotFoundError(f"FASTA file not found: {fasta_path}")

    results = run_temstapro.remote(
        fasta_bytes=fasta_file.read_bytes(),
        fasta_name=fasta_file.name,
        more_thresholds=more_thresholds,
        portion_size=portion_size,
        segment_size=segment_size,
        window_size_predictions=window_size_predictions,
        curve_smoothening=curve_smoothening,
        include_plots=bool(plot_dir),
        mean_output_name=Path(output_path).name if output_path else None,
        per_res_output_name=Path(per_res_output).name if per_res_output else None,
        per_segment_output_name=(
            Path(per_segment_output).name if per_segment_output else None
        ),
    )

    files_dict = dict(results.get("files") or {})
    plots_list = list(results.get("plots") or [])

    _write_optional_file(output_path, files_dict.get("mean"))
    _write_optional_file(per_res_output, files_dict.get("per_res"))
    _write_optional_file(per_segment_output, files_dict.get("per_segment"))
    _write_plots(plot_dir, plots_list)

    stdout = results.get("stdout")
    stderr = results.get("stderr")
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=os.sys.stderr)
