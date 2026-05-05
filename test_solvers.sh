#!/bin/bash

# Ensure minizinc is available in the current environment
if ! command -v minizinc &> /dev/null; then
    echo "ERROR: minizinc command not found."
    echo "Ensure you have loaded your modules or are running this inside your Apptainer container."
    exit 1
fi

# 1. Create the dummy model
TEST_FILE="test.mzn"
echo "var 1..10: x;" > "$TEST_FILE"
echo "solve satisfy;" >> "$TEST_FILE"

# 2. Define the target solvers in the exact requested order
# Note: The array uses the internal MiniZinc IDs required to run the test.
SOLVER_IDS=("coin-bc" "gurobi" "cplex" "chuffed" "cp-sat" "gecode")
SOLVER_NAMES=("Coin-BC (ILP)" "Gurobi (ILP)" "CPLEX (ILP)" "Chuffed (CP)" "OR-Tools (CP)" "Gecode (CP)")

AVAILABLE=()
UNAVAILABLE=()

echo "========================================"
echo "   Testing Target MiniZinc Solvers      "
echo "========================================"

# 3. Test each solver in order
for i in "${!SOLVER_IDS[@]}"; do
    id="${SOLVER_IDS[$i]}"
    name="${SOLVER_NAMES[$i]}"
    
    printf "Testing %-15s [%-7s] ... " "$name" "$id"
    
    # Run minizinc with a 5-second timeout to prevent hangs.
    if timeout 5 minizinc --solver "$id" "$TEST_FILE" > /dev/null 2>&1; then
        echo "[ OK ]"
        AVAILABLE+=("$name")
    else
        # Fallback check specifically for OR-Tools, as some local installs use 'ortools' instead of 'cp-sat'
        if [ "$id" == "cp-sat" ] && timeout 5 minizinc --solver "ortools" "$TEST_FILE" > /dev/null 2>&1; then
            echo "[ OK ] (using 'ortools' ID)"
            AVAILABLE+=("$name")
        else
            echo "[ FAILED ]"
            UNAVAILABLE+=("$name")
        fi
    fi
done

# 4. Clean up the dummy file
rm "$TEST_FILE"

# 5. Print Summary Report
echo ""
echo "========================================"
echo "               SUMMARY                  "
echo "========================================"

echo "Available Solvers:"
if [ ${#AVAILABLE[@]} -eq 0 ]; then
    echo "  (None)"
else
    for s in "${AVAILABLE[@]}"; do
        echo "  - $s"
    done
fi

echo ""
echo "Unavailable/Unlicensed Solvers:"
if [ ${#UNAVAILABLE[@]} -eq 0 ]; then
    echo "  (None)"
else
    for s in "${UNAVAILABLE[@]}"; do
        echo "  - $s"
    done
fi
echo "========================================"
