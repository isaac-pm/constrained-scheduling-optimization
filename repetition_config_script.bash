#!/bin/bash
set -euo pipefail

REPETITIONS="${1:-1}"

if ! [[ "$REPETITIONS" =~ ^[0-9]+$ ]] || [[ "$REPETITIONS" -lt 1 ]]; then
    echo "Usage: $0 [positive_repetitions]"
    echo "Example: $0 20"
    exit 1
fi

CONFIGS=(
    "instance_j30_config.yaml"
    "instance_j60_config.yaml"
    "instance_j90_config.yaml"
    "instance_j120_config.yaml"
)

for ((rep=1; rep<=REPETITIONS; rep++)); do
    echo "Starting rotation $rep/$REPETITIONS"

    for config in "${CONFIGS[@]}"; do
        if [[ ! -f "$config" ]]; then
            echo "ERROR: config file '$config' not found."
            exit 1
        fi

        echo "Submitting $config"
        sbatch run_benchmark.sbatch "$config"
    done
done
