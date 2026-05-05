#!/bin/bash
#SBATCH --job-name=rcpsp-benchmark
#SBATCH --nodes=1
#SBATCH --exclusive
#SBATCH --mem=0
#SBATCH --time=12:00:00
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
# Re-enable 'nounset' for actual logic
set -u

# 3. Clear environment and load modules
module purge
module --ignore_cache load env/development/2024a
module load tools/Apptainer/1.4.1
module load math/Gurobi/12.0.1-GCCcore-13.3.0

# Verify the EasyBuild variable exists (fail fast if not)
# Using :- to prevent 'set -u' from crashing the script before the custom error message prints
if [ -z "${EBROOTGUROBI:-}" ]; then
    echo "ERROR: \$EBROOTGUROBI is not set. Gurobi module did not load correctly."
    exit 1
fi

# 4. Apptainer Bind Mounts and Environment Injection
# Bind the host Gurobi directory to a matching path in the container
export APPTAINER_BIND="$EBROOTGUROBI:/opt/gurobi"

# Inject Gurobi binaries and libraries into the container's execution paths
export APPTAINERENV_PREPEND_PATH="/opt/gurobi/bin"
export APPTAINERENV_PREPEND_LD_LIBRARY_PATH="/opt/gurobi/lib"

# Pass the cluster's Gurobi license file into the container
# Using :- to avoid a crash if the cluster doesn't export this by default
export APPTAINERENV_GRB_LICENSE_FILE="${GRB_LICENSE_FILE:-/opt/gurobi/gurobi.lic}"

# 5. Execute the benchmark script
cd "${SLURM_SUBMIT_DIR:-$PWD}"

if [[ ! -f scheduling.sif ]]; then
    echo "ERROR: scheduling.sif not found."
    exit 1
fi

echo "Starting benchmark with Gurobi bound from host on an exclusive node..."
apptainer run --userns scheduling.sif