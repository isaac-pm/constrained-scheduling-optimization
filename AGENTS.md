# constrained-scheduling-optimization

## Environment

- Python venv: `env/` (create with `python -m venv env`, activate with `source env/bin/activate`)
- Dependencies: `minizinc==0.10.0`, `psplib==0.4.0`
- Install: `pip install -r requirements.txt`

## Running

```bash
python run.py
```

`run.py` benchmarks both RCPSP models on all PSPLIB SM-format instances:
- `rcpsp_cp.mzn` - Constraint Programming formulation (faster, uses `chuffed` solver)
- `rcpsp_ilp.mzn` - Integer Linear Programming formulation (slower, uses `coin-bc` solver)

## Data

Benchmark instances are PSPLIB format (`.sm` files) in `data/`. The directory contains j30, j60, j90, and j120 problem sets. Load with:

```python
from psplib import parse
instance = parse("data/j30.sm/j301_1.sm", instance_format="psplib")
```

Note: psplib uses 0-based indexing for successors (indices into activities array), MiniZinc uses 1-based. The `parse_sm_file` function in `run.py` handles this conversion.

## Models

- `model.mzn` - n-Queens example (not an RCPSP model)
- `rcpsp_cp.mzn` - CP formulation with cumulative resource constraints
- `rcpsp_ilp.mzn` - ILP formulation with time-indexed binary variables

## Notes

- `papers/` contains reference papers for RCPSP algorithms
- No test suite, linting, or CI configured
- MiniZinc solvers (chuffed, coin-bc) must be installed separately and visible in PATH
