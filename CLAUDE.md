# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an HPC benchmark comparing Constraint Programming (CP) and Integer Linear Programming (ILP) approaches to the Resource-Constrained Project Scheduling Problem (RCPSP) using PSPLIB instances.

The benchmark runs on the Aion cluster (University of Luxembourg) via Apptainer containers and Slurm. Locally, you can run interactively inside the container or against a locally installed MiniZinc.

## Commands

### Run the benchmark

```bash
# Locally (requires MiniZinc installed and activated virtualenv)
source env/bin/activate
python run.py                                    # uses instance_config.yaml
python run.py --config instance_j30_config.yaml  # single problem size
python run.py --output-dir /tmp/results          # custom output dir
```

### Check which solvers are available

```bash
./test_solvers.sh   # must be run inside an environment where `minizinc` is on PATH
```

### Analysis / plots

```bash
cd plots
python main.py      # reads results.csv, writes PNGs to plots/plots/
```

### HPC (Aion cluster)

```bash
# Build container (once, locally)
apptainer build --fakeroot scheduling.sif scheduling.def

# Submit a single Slurm job
sbatch run_benchmark.sbatch                          # default config
sbatch run_benchmark.sbatch instance_j60_config.yaml # specific size

# Submit array jobs across all problem sizes, N repetitions each
bash repetition_config_script.bash 5   # 5 rotations × 4 configs = 20 jobs

# Allocate interactive node then open container shell
salloc
module purge && module --ignore_cache load env/development/2024a
module load tools/Apptainer/1.4.1 math/Gurobi/12.0.1-GCCcore-13.3.0
export APPTAINER_BIND="$EBROOTGUROBI:/opt/gurobi"
export APPTAINERENV_PREPEND_LD_LIBRARY_PATH="/opt/gurobi/lib"
export APPTAINERENV_GRB_LICENSE_FILE="/opt/gurobi/gurobi.lic"
apptainer shell --userns scheduling.sif
```

### Dependencies

```bash
pip install -r requirements.txt   # minizinc, psplib, psutil, PyYAML
```

## Architecture

### Data flow

1. **Instance config** (`instance_config.yaml` or `instance_j*_config.yaml`) — lists which PSPLIB `.sm` files to run and how many repetitions.
2. **`run.py`** — main benchmark driver:
   - `parse_sm_file()` reads a `.sm` file via `psplib.parse()`, computes earliest/latest start times, and calls `calculate_greedy_horizon()` to bound the time horizon.
   - `generate_dzn()` serialises the parsed data into a temporary `.dzn` file that MiniZinc reads.
   - `solve_instance()` invokes MiniZinc via the Python `minizinc` library, wraps the call in a `ResourceMonitor` thread (50 ms sampling of child RSS), and returns elapsed time, avg/peak RAM, CPU %, makespan, and status.
   - `main()` iterates over all (instance × run × solver) combinations in order, writes each row to the CSV immediately after the solve (fsync'd), and prints a summary.
3. **MiniZinc models** — both receive the same `.dzn` data:
   - `rcpsp_cp.mzn` — decision variables are integer start times with domain `[est..lst]`; resource feasibility enforced by `cumulative` global constraint. Also adds transitive precedence constraints for stronger propagation.
   - `rcpsp_ilp.mzn` — decision variables are binary `x[j,t]` (activity `j` starts at time `t`); precedence uses the strong LP step formulation; resource constraint sums overlapping binaries per time slot.
4. **Results** — three timestamped files per run written to `results/`:
   - `*-results.csv` — one row per (instance, run, solver)
   - `*-hardware.json` — lscpu, free, MiniZinc version, Slurm env vars
   - `*-config.yaml` — snapshot of the instance selection used
5. **Analysis** (`plots/main.py`, `plots/constrained_scheduling_optimization.ipynb`) — reads a `results.csv`, treats most runs as censored at the 1200 s timeout, and produces plots: runtime distribution curves (PAR-2 style), solve rate heatmap, outcome matrix, optimality gap, pairwise comparisons, RAM scaling.

### Solvers

| ID       | Paradigm | Notes                                      |
|----------|----------|--------------------------------------------|
| chuffed  | CP       | Bundled with MiniZinc                      |
| gecode   | CP       | Bundled with MiniZinc                      |
| cp-sat   | CP       | OR-Tools; wired in manually via `or-tools.msc` in the container |
| coin-bc  | ILP      | Bundled with MiniZinc                      |
| gurobi   | ILP      | Loaded from HPC module; requires license bind-mount |

### Problem sizes and data

PSPLIB instances live in `data/{j30,j60,j90,j120}.sm/`. Instance names follow the pattern `j{size}{set}_{variant}.sm`. The four per-size configs (`instance_j*_config.yaml`) select 10 instances each; `instance_config.yaml` includes all four sizes.

### Container

`scheduling.def` builds a Debian/Python 3.11 Apptainer image with MiniZinc 2.9.5 and OR-Tools 9.15 pre-installed. Gurobi is injected at runtime via bind-mounts because it requires a cluster license.

### Key constants in `run.py`

- `TIMEOUT_MINUTES = 20` (1200 s) — per-solve wall-clock limit passed to MiniZinc.
- `ResourceMonitor` samples every 50 ms; `stats_mb()` excludes zero-RSS samples (pre-launch).
- Results are fsynced after every row so partial runs survive job preemption.
