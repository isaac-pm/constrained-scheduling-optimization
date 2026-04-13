import os
import time
import glob
from pathlib import Path

from psplib import parse


def parse_sm_file(filepath):
    inst = parse(filepath, instance_format="psplib")
    n = len(inst.activities)
    horizon = sum(a.modes[0].duration for a in inst.activities)

    duration = [a.modes[0].duration for a in inst.activities]
    resource_usage = [
        [a.modes[0].demands[r] for r in range(4)] for a in inst.activities
    ]
    capacity = [r.capacity for r in inst.resources]
    successors = [[s + 1 for s in a.successors] for a in inst.activities]

    return {
        "n": n,
        "horizon": horizon,
        "duration": duration,
        "resource_usage": resource_usage,
        "capacity": capacity,
        "successors": successors,
    }


def generate_dzn(data, output_path):
    dzn_dir = os.path.dirname(output_path)
    if dzn_dir:
        os.makedirs(dzn_dir, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(f"n = {data['n']};\n")
        f.write(f"horizon = {data['horizon']};\n")
        f.write(f"duration = {data['duration']};\n")
        ru_rows = []
        for ru in data["resource_usage"]:
            ru_rows.append(", ".join(str(x) for x in ru))
        sparse_array = "[| " + " | ".join(ru_rows) + " |]"
        f.write(f"resource_usage = {sparse_array};\n")
        f.write(f"capacity = {data['capacity']};\n")
        succ_lines = [
            "{" + ", ".join(str(s) for s in succ) + "}" if succ else "{}"
            for succ in data["successors"]
        ]
        f.write(f"successors = [{', '.join(succ_lines)}];\n")


def solve_instance(instance_path, model_path, solver_name="chuffed"):
    from minizinc import Instance, Model, Solver

    data = parse_sm_file(instance_path)
    dzn_path = str(Path(instance_path).with_suffix(".dzn"))
    generate_dzn(data, dzn_path)

    start_time = time.time()

    try:
        model = Model(model_path)
        solver = Solver.lookup(solver_name)
        inst = Instance(solver, model)
        inst.add_file(dzn_path)
        result = inst.solve()
        elapsed = time.time() - start_time

        if os.path.exists(dzn_path):
            os.remove(dzn_path)

        if result.solution is None:
            return elapsed, None
        return elapsed, result.solution.makespan
    except Exception as e:
        elapsed = time.time() - start_time
        if os.path.exists(dzn_path):
            os.remove(dzn_path)
        return elapsed, f"Error"


def get_available_solvers():
    from minizinc import Solver

    try:
        solvers = Solver.all()
        print(f"Available solvers: {[s.name for s in solvers]}")
        return [s.name for s in solvers]
    except:
        return []


def main():
    print("RCPSP Benchmark Solver")
    print("=" * 75)

    solvers = get_available_solvers()
    print()

    data_dirs = sorted(glob.glob("data/j*.sm"))
    print(
        f"Found {len(data_dirs)} problem sets: {[d.split('/')[1] for d in data_dirs]}\n"
    )

    cp_model = "rcpsp_cp.mzn"
    ilp_model = "rcpsp_ilp.mzn"

    results = {}

    for data_dir in data_dirs:
        problem_set = data_dir.split("/")[1]
        instances = sorted(glob.glob(f"{data_dir}/*.sm"))
        print(f"\n{problem_set}: {len(instances)} instances")
        print("-" * 75)

        cp_times = []
        ilp_times = []
        cp_solutions = []
        ilp_solutions = []

        for i, instance_path in enumerate(instances):
            instance_name = Path(instance_path).stem
            base_str = f"  [{i+1:03d}/{len(instances):03d}] {instance_name:<12}"

            # Print live status for CP
            print(f"{base_str} | Status: Solving CP...          ", end="\r", flush=True)

            # Solve CP with Chuffed
            cp_time, cp_makespan = solve_instance(
                instance_path, cp_model, solver_name="chuffed"
            )
            cp_times.append(cp_time)
            cp_solutions.append(cp_makespan)
            cp_res = (
                f"{cp_makespan} ({cp_time:.2f}s)"
                if cp_makespan
                else f"N/A ({cp_time:.2f}s)"
            )

            # Print live status for ILP
            print(
                f"{base_str} | CP: {cp_res:<15} | Status: Solving ILP... ",
                end="\r",
                flush=True,
            )

            # Solve ILP with Coin-BC
            ilp_time, ilp_makespan = solve_instance(
                instance_path, ilp_model, solver_name="coin-bc"
            )
            ilp_times.append(ilp_time)
            ilp_solutions.append(ilp_makespan)
            ilp_res = (
                f"{ilp_makespan} ({ilp_time:.2f}s)"
                if ilp_makespan
                else f"N/A ({ilp_time:.2f}s)"
            )

            # Finalize the line with both results and clear the status text
            print(
                f"{base_str} | CP: {cp_res:<15} | ILP: {ilp_res:<15}                        "
            )

            # Print running averages every 10 iterations
            if (i + 1) % 10 == 0:
                avg_cp = sum(cp_times) / len(cp_times)
                avg_ilp = sum(ilp_times) / len(ilp_times)
                print(f"    [Running Avg] CP: {avg_cp:.2f}s | ILP: {avg_ilp:.2f}s")

        results[problem_set] = {
            "cp": {"times": cp_times, "makespans": cp_solutions},
            "ilp": {"times": ilp_times, "makespans": ilp_solutions},
        }

        print(
            f"  Summary: CP avg={sum(cp_times)/len(cp_times):.2f}s, ILP avg={sum(ilp_times)/len(ilp_times):.2f}s"
        )

    print("\n" + "=" * 75)
    print("OVERALL SUMMARY")
    print("=" * 75)

    all_cp = []
    all_ilp = []
    for ps, data in results.items():
        all_cp.extend(data["cp"]["times"])
        all_ilp.extend(data["ilp"]["times"])

    print(f"Total instances: {len(all_cp)}")
    print(
        f"CP  - Total: {sum(all_cp):.2f}s, Avg: {sum(all_cp)/len(all_cp):.2f}s, Min: {min(all_cp):.2f}s, Max: {max(all_cp):.2f}s"
    )
    print(
        f"ILP - Total: {sum(all_ilp):.2f}s, Avg: {sum(all_ilp)/len(all_ilp):.2f}s, Min: {min(all_ilp):.2f}s, Max: {max(all_ilp):.2f}s"
    )


if __name__ == "__main__":
    main()
