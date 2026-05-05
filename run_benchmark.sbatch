#!/bin/bash
#SBATCH --job-name=rcpsp-benchmark
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=8G
#SBATCH --time=08:00:00
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err

# 1. Start with strict mode
set -eo pipefail
set -u 

# 2. Temporarily disable 'nounset' to allow system scripts to run
set +u
if [ -f /etc/profile.d/modules.sh ]; then
    source /etc/profile.d/modules.sh
fi
# Re-enable 'nounset' for your actual logic
set -u

# 3. Load your modules
module purge
module --ignore_cache load env/development/2024a
module load tools/Apptainer/1.4.1

# 4. Rest of your script...
cd "${SLURM_SUBMIT_DIR:-$PWD}"

if [[ ! -f scheduling.sif ]]; then
    echo "scheduling.sif not found."
    exit 1
fi

apptainer run --userns scheduling.sif
