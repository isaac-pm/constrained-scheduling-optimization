#!/bin/bash
#SBATCH --job-name=rcpsp-benchmark
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=0
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err

set -euo pipefail

cd "${SLURM_SUBMIT_DIR:-$PWD}"

module load env/development/2024a
module load tools/Apptainer/1.4.1

if [[ ! -f scheduling.sif ]]; then
    echo "scheduling.sif not found. Build it first with: apptainer build --fakeroot scheduling.sif scheduling.def"
    exit 1
fi

apptainer run --userns scheduling.sif