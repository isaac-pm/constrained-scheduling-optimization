# constrained-scheduling-optimization

## Environment

- Use a local venv at `.venv/` (README uses `python -m venv ./.venv`), then `pip install -r requirements.txt`.
- Required Python deps are only those in `requirements.txt` (minizinc, psplib, psutil, PyYAML).
- MiniZinc solvers `chuffed` (CP) and `coin-bc` (ILP) must be installed and on PATH; `run.py` also tries `gecode`, `cp-sat`, and `gurobi`.

## Running + outputs

- `python run.py` runs the benchmark; it reads `instance_config.yaml` for instance selection and `runs_per_instance`.
- Benchmark outputs are written to `results/` as timestamped `*-results.csv`, `*-hardware.json`, and `*-config.yaml` files.
- `run.py` uses `rcpsp_cp.mzn` for CP solvers and `rcpsp_ilp.mzn` for ILP solvers; Gurobi expects `/opt/gurobi/lib/libgurobi120.so` and adjusts `LD_LIBRARY_PATH` if missing.
- Use `test_solvers.sh` to check which MiniZinc solver IDs are available; it falls back to the `ortools` ID if `cp-sat` is not registered.

## Container + Slurm

- Container workflow uses Apptainer: build `scheduling.sif` from `scheduling.def`, then `apptainer run --userns scheduling.sif`.
- Slurm runs are expected via `sbatch run_benchmark.sbatch`; it loads Apptainer + Gurobi modules and injects Gurobi into the container via `APPTAINER_BIND`/`APPTAINERENV_*`.

## Data + parsing

- PSPLIB `.sm` instances live under `data/<problem_size>.sm/` (j30/j60/j90/j120), and `run.py` assembles paths as `data/<size>.sm/<instance>.sm`.
- psplib is 0-based but MiniZinc is 1-based; `parse_sm_file` in `run.py` converts indices.

## Notes

- No tests, linting, or CI workflows are configured.
