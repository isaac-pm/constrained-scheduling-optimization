# constrained-scheduling-optimization

## Environment

- Use a local venv at `.venv/` (README uses `python -m venv ./.venv`), then `pip install -r requirements.txt`.
- Required Python deps are only those in `requirements.txt` (minizinc, psplib, PyYAML).
- MiniZinc solvers `chuffed` (CP) and `coin-bc` (ILP) must be installed and on PATH.

## Running + outputs

- `python run.py` runs the benchmark; it reads `instance_config.yaml` for instance selection and `runs_per_instance`.
- Benchmark outputs are written to `results/` as timestamped `*-results.csv`, `*-hardware.json`, and `*-config.yaml` files.
- `run.py` uses `rcpsp_cp.mzn` (faster, chuffed) and `rcpsp_ilp.mzn` (slower, coin-bc).

## Container + Slurm

- Container workflow uses Apptainer: build `scheduling.sif` from `scheduling.def`, then `apptainer run --userns scheduling.sif`.
- Slurm runs are expected via `sbatch run_benchmark.sbatch`; interactive instructions in README include module loads and optional Gurobi bindings for ILP.

## Data + parsing

- PSPLIB `.sm` instances live under `data/` (j30/j60/j90/j120).
- psplib is 0-based but MiniZinc is 1-based; `parse_sm_file` in `run.py` converts indices.

## Notes

- No tests, linting, or CI workflows are configured.
