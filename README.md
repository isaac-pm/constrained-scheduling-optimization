# constrained-scheduling-optimization

Comparative Modeling and Optimization of the Resource-Constrained Project Scheduling Problem.

## How to run

1. Create and activate python environment:

```bash
python -m venv ./.venv


source ./.venv/bin/activate # For  Mac / Linux

.venv\Scripts\activate # For windows users
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Make sure MiniZinc solvers are available.

## Benchmark workflow

The benchmark runner uses the reproducible instance list in `instance_config.yaml`.
It runs 3 instances per size (`j30`, `j60`, `j90`, `j120`) and solves each selected instance 3 times with both CP and ILP.

Outputs are written to `results/` with timestamped names:

- `YYYY-MM-DD-HH:MM-results.csv`
- `YYYY-MM-DD-HH:MM-hardware.json`
- `YYYY-MM-DD-HH:MM-config.yaml`

Edit `instance_config.yaml` if you want to change the selected instances or repetitions.

## Local execution

Run the benchmark directly:

```bash
python run.py
```

## Container execution

Build the container:

```bash
apptainer build --fakeroot scheduling.sif scheduling.def
```

Run the benchmark inside the container:

```bash
apptainer run --userns scheduling.sif
```

Open an interactive shell inside the container:

```bash
apptainer shell --userns scheduling.sif
```

## Slurm execution

Start an interactive allocation:

```bash
srun --pty --exclusive -N 1 -n 1 --mem=0 /bin/bash
```

Load the required modules:

```bash
module load env/development/2024a
module load tools/Apptainer/1.4.1
```

Build the container:

```bash
apptainer build --fakeroot scheduling.sif scheduling.def
```

Run the scheduling script:

```bash
apptainer run --userns scheduling.sif
```

Open an interactive shell inside the container:

```bash
module purge
module --ignore_cache load env/development/2024a
module load tools/Apptainer/1.4.1
module load math/Gurobi/12.0.1-GCCcore-13.3.0
export APPTAINER_BIND="$EBROOTGUROBI:/opt/gurobi"
export APPTAINERENV_PREPEND_LD_LIBRARY_PATH="/opt/gurobi/lib"
export APPTAINERENV_GRB_LICENSE_FILE="${GRB_LICENSE_FILE:-/opt/gurobi/gurobi.lic}"
apptainer shell --userns scheduling.sif
python run.py
```

You can also submit the provided Slurm batch script:

```bash
sbatch run_benchmark.sbatch
```

### Solvers

| Solver   | Strategy | Available?             |
| -------- | -------- | ---------------------- |
| Coin-BC  | ILP      | Yes                    |
| Gurobi   | ILP      | Yes (Load from module) |
| CPLEX    | ILP      | No                     |
| Chuffed  | CP       | Yes                    |
| Gecode   | CP       | Yes                    |
| OR-Tools (cpsat) | CP       | Yes (Dowloaded manually) |
