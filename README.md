# constrained-scheduling-optimization

Comparative Modeling and Optimization of the Resource-Constrained Project Scheduling Problem.

## How to run

### Preparation

#### Set up the container

```bash
# Build the container locally to copy the .sif to the HPC cluster
apptainer build --fakeroot scheduling.sif scheduling.def
```

#### HPC setup (Aion - University of Luxembourg HPC cluster)

```bash
# Allocate an interactive allocation (necessary for scheduling the job)
salloc

# Load required modules
module purge
module --ignore_cache load env/development/2024a
module load tools/Apptainer/1.4.1
module load math/Gurobi/12.0.1-GCCcore-13.3.0
```

### Run interactively

```bash
export APPTAINER_BIND="$EBROOTGUROBI:/opt/gurobi"
export APPTAINERENV_PREPEND_LD_LIBRARY_PATH="/opt/gurobi/lib"
export APPTAINERENV_GRB_LICENSE_FILE="/opt/gurobi/gurobi.lic"
apptainer shell --userns scheduling.sif # Open an interactive shell inside the container
python run.py
```

### Scheduled job

```bash
sbatch run_benchmark.sbatch
```

## Benchmark workflow

The benchmark runner uses the reproducible instance list in `instance_config.yaml`.
It runs N instances per size ($j30$, $j60$, $j90$, $j120$) and solves each selected instance M times with both CP and ILP.

Outputs are written to `results/` with timestamped names:

- `YYYY-MM-DD-HH:MM-results.csv`
- `YYYY-MM-DD-HH:MM-hardware.json`
- `YYYY-MM-DD-HH:MM-config.yaml`

Edit `instance_config.yaml` if you want to change the selected instances or repetitions.

Problem size: 4 problem sizes ($j30$, $j60$, $j90$, $j120$) x N (currently 10) files per size x 5 available solvers x M (currently 5) repetitions.

### Solvers

| Solver           | Strategy | Available?                |
| ---------------- | -------- | ------------------------- |
| Coin-BC          | ILP      | Yes                       |
| Gurobi           | ILP      | Yes (load from module)    |
| CPLEX            | ILP      | No                        |
| Chuffed          | CP       | Yes                       |
| Gecode           | CP       | Yes                       |
| OR-Tools (cpsat) | CP       | Yes (downloaded manually) |
