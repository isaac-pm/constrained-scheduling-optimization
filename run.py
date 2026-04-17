import argparse
import csv
import json
import os
import platform
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

import yaml
from psplib import parse


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "instance_config.yaml"
DEFAULT_OUTPUT_DIR = Path.cwd() / "results"
DEFAULT_CP_MODEL = BASE_DIR / "rcpsp_cp.mzn"
DEFAULT_ILP_MODEL = BASE_DIR / "rcpsp_ilp.mzn"
DEFAULT_CP_SOLVER = "chuffed"
DEFAULT_ILP_SOLVER = "coin-bc"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmark RCPSP CP and ILP models on a reproducible instance subset."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the YAML file with the reproducible instance selection.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where timestamped benchmark outputs are written.",
    )
    return parser.parse_args()


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
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        file.write(f"n = {data['n']};\n")
        file.write(f"horizon = {data['horizon']};\n")
        file.write(f"duration = {data['duration']};\n")
        ru_rows = [", ".join(str(x) for x in ru) for ru in data["resource_usage"]]
        sparse_array = "[| " + " | ".join(ru_rows) + " |]"
        file.write(f"resource_usage = {sparse_array};\n")
        file.write(f"capacity = {data['capacity']};\n")
        succ_lines = [
            "{" + ", ".join(str(s) for s in succ) + "}" if succ else "{}"
            for succ in data["successors"]
        ]
        file.write(f"successors = [{', '.join(succ_lines)}];\n")


def load_instance_config(config_path):
    with Path(config_path).open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    instances = config.get("instances")
    if not isinstance(instances, dict) or not instances:
        raise ValueError(
            "instance_config.yaml must define a non-empty 'instances' mapping"
        )

    runs_per_instance = int(config.get("runs_per_instance", 3))
    if runs_per_instance < 1:
        raise ValueError("runs_per_instance must be at least 1")

    return {
        "instances": instances,
        "runs_per_instance": runs_per_instance,
    }


def normalize_instance_path(problem_size, instance_name):
    return BASE_DIR / "data" / f"{problem_size}.sm" / f"{instance_name}.sm"


def solve_instance(instance_path, model_path, solver_name):
    from minizinc import Instance, Model, Solver

    instance_path = Path(instance_path)
    model_path = Path(model_path)
    data = parse_sm_file(instance_path)

    with tempfile.NamedTemporaryFile(suffix=".dzn", delete=False) as temp_file:
        dzn_path = Path(temp_file.name)

    generate_dzn(data, dzn_path)
    start_time = time.perf_counter()

    try:
        model = Model(str(model_path))
        solver = Solver.lookup(solver_name)
        instance = Instance(solver, model)
        instance.add_file(str(dzn_path))
        result = instance.solve()
        elapsed = time.perf_counter() - start_time

        if result.solution is None:
            return {
                "elapsed_seconds": elapsed,
                "makespan": None,
                "status": "no_solution",
                "error": "",
            }

        return {
            "elapsed_seconds": elapsed,
            "makespan": result.solution.makespan,
            "status": "ok",
            "error": "",
        }
    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        return {
            "elapsed_seconds": elapsed,
            "makespan": None,
            "status": "error",
            "error": str(exc),
        }
    finally:
        if dzn_path.exists():
            dzn_path.unlink()


def collect_solver_inventory():
    try:
        from minizinc import Solver

        return sorted(solver.name for solver in Solver.all())
    except Exception:
        return []


def run_command(command):
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return ""

    output = completed.stdout.strip()
    error = completed.stderr.strip()
    if output and error:
        return output + "\n" + error
    return output or error


def extract_lscpu_value(lscpu_output, label):
    for line in lscpu_output.splitlines():
        if line.startswith(f"{label}:"):
            return line.split(":", 1)[1].strip()
    return ""


def collect_hardware_info():
    lscpu_output = run_command(["lscpu"])
    physical_cpu_count = ""
    sockets = extract_lscpu_value(lscpu_output, "Socket(s)")
    cores_per_socket = extract_lscpu_value(lscpu_output, "Core(s) per socket")
    if sockets.isdigit() and cores_per_socket.isdigit():
        physical_cpu_count = int(sockets) * int(cores_per_socket)
    else:
        physical_cpu_count = os.cpu_count()

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "hostname": platform.node(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "logical_cpu_count": os.cpu_count(),
        "physical_cpu_count": physical_cpu_count,
        "platform": platform.platform(),
        "uname": platform.uname()._asdict(),
        "slurm": {
            "job_id": os.getenv("SLURM_JOB_ID", ""),
            "job_name": os.getenv("SLURM_JOB_NAME", ""),
            "node_list": os.getenv("SLURM_NODELIST", ""),
            "cpus_on_node": os.getenv("SLURM_CPUS_ON_NODE", ""),
            "mem_per_node": os.getenv("SLURM_MEM_PER_NODE", ""),
            "submit_dir": os.getenv("SLURM_SUBMIT_DIR", ""),
        },
        "commands": {
            "lscpu": lscpu_output,
            "free_h": run_command(["free", "-h"]),
            "minizinc_version": run_command(["minizinc", "--version"]),
        },
        "available_solvers": collect_solver_inventory(),
    }


def write_timestamped_config_snapshot(output_path, config_path, config, selection):
    snapshot = {
        "source_config": str(Path(config_path).resolve()),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "runs_per_instance": config["runs_per_instance"],
        "instances": selection,
    }
    with Path(output_path).open("w", encoding="utf-8") as file:
        yaml.safe_dump(snapshot, file, sort_keys=False)


def main():
    args = parse_args()
    config = load_instance_config(args.config)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H:%M")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / f"{timestamp}-results.csv"
    hardware_path = output_dir / f"{timestamp}-hardware.json"
    config_snapshot_path = output_dir / f"{timestamp}-config.yaml"

    selected_instances = {
        problem_size: list(instance_names)
        for problem_size, instance_names in config["instances"].items()
    }

    write_timestamped_config_snapshot(
        config_snapshot_path,
        args.config,
        config,
        selected_instances,
    )

    hardware_info = collect_hardware_info()
    with hardware_path.open("w", encoding="utf-8") as file:
        json.dump(hardware_info, file, indent=2, sort_keys=True)
        file.write("\n")

    rows = []
    total_instances = sum(
        len(instance_names) for instance_names in selected_instances.values()
    )

    print("RCPSP Benchmark Solver")
    print("=" * 75)
    print(f"Output directory: {output_dir}")
    print(f"Results file: {results_path.name}")
    print(f"Hardware file: {hardware_path.name}")
    print(f"Config snapshot: {config_snapshot_path.name}")
    print(f"Repetitions per instance: {config['runs_per_instance']}")
    print(
        f"Selected instances: {total_instances} across {len(selected_instances)} problem sizes"
    )
    print()

    for problem_size, instance_names in selected_instances.items():
        print(f"{problem_size}: {len(instance_names)} instances")
        print("-" * 75)

        for instance_index, instance_name in enumerate(instance_names, start=1):
            instance_path = normalize_instance_path(problem_size, instance_name)
            if not instance_path.exists():
                raise FileNotFoundError(f"Missing instance file: {instance_path}")

            for run_number in range(1, config["runs_per_instance"] + 1):
                run_started_at = datetime.now().isoformat(timespec="seconds")
                base_label = (
                    f"  [{instance_index:02d}/{len(instance_names):02d}] {instance_name:<12} "
                    f"run {run_number:02d}/{config['runs_per_instance']:02d}"
                )

                cp_started_at = datetime.now().isoformat(timespec="seconds")
                print(f"{base_label} | Status: Solving CP... ", end="\r", flush=True)
                cp_result = solve_instance(
                    instance_path, DEFAULT_CP_MODEL, DEFAULT_CP_SOLVER
                )
                cp_finished_at = datetime.now().isoformat(timespec="seconds")

                ilp_started_at = datetime.now().isoformat(timespec="seconds")
                print(f"{base_label} | Status: Solving ILP...", end="\r", flush=True)
                ilp_result = solve_instance(
                    instance_path, DEFAULT_ILP_MODEL, DEFAULT_ILP_SOLVER
                )
                ilp_finished_at = datetime.now().isoformat(timespec="seconds")

                run_finished_at = datetime.now().isoformat(timespec="seconds")

                rows.append(
                    {
                        "timestamp": timestamp,
                        "problem_size": problem_size,
                        "instance_name": instance_name,
                        "run_number": run_number,
                        "runs_per_instance": config["runs_per_instance"],
                        "cp_solver": DEFAULT_CP_SOLVER,
                        "cp_model": DEFAULT_CP_MODEL.name,
                        "cp_started_at": cp_started_at,
                        "cp_finished_at": cp_finished_at,
                        "cp_elapsed_seconds": f"{cp_result['elapsed_seconds']:.6f}",
                        "cp_makespan": cp_result["makespan"],
                        "cp_status": cp_result["status"],
                        "cp_error": cp_result["error"],
                        "ilp_solver": DEFAULT_ILP_SOLVER,
                        "ilp_model": DEFAULT_ILP_MODEL.name,
                        "ilp_started_at": ilp_started_at,
                        "ilp_finished_at": ilp_finished_at,
                        "ilp_elapsed_seconds": f"{ilp_result['elapsed_seconds']:.6f}",
                        "ilp_makespan": ilp_result["makespan"],
                        "ilp_status": ilp_result["status"],
                        "ilp_error": ilp_result["error"],
                        "run_started_at": run_started_at,
                        "run_finished_at": run_finished_at,
                    }
                )

                cp_label = (
                    f"{cp_result['makespan']} ({cp_result['elapsed_seconds']:.2f}s)"
                    if cp_result["makespan"] is not None
                    else f"{cp_result['status']} ({cp_result['elapsed_seconds']:.2f}s)"
                )
                ilp_label = (
                    f"{ilp_result['makespan']} ({ilp_result['elapsed_seconds']:.2f}s)"
                    if ilp_result["makespan"] is not None
                    else f"{ilp_result['status']} ({ilp_result['elapsed_seconds']:.2f}s)"
                )

                print(f"{base_label} | CP: {cp_label:<18} | ILP: {ilp_label:<18}")

    fieldnames = list(rows[0].keys()) if rows else []
    with results_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    cp_times = [float(row["cp_elapsed_seconds"]) for row in rows]
    ilp_times = [float(row["ilp_elapsed_seconds"]) for row in rows]

    print("\n" + "=" * 75)
    print("OVERALL SUMMARY")
    print("=" * 75)
    print(f"Total instance-run pairs: {len(rows)}")
    print(
        f"CP  - Total: {sum(cp_times):.2f}s, Avg: {sum(cp_times) / len(cp_times):.2f}s, Min: {min(cp_times):.2f}s, Max: {max(cp_times):.2f}s"
    )
    print(
        f"ILP - Total: {sum(ilp_times):.2f}s, Avg: {sum(ilp_times) / len(ilp_times):.2f}s, Min: {min(ilp_times):.2f}s, Max: {max(ilp_times):.2f}s"
    )
    print(f"\nSaved results to {results_path}")
    print(f"Saved hardware characteristics to {hardware_path}")
    print(f"Saved selected-instance snapshot to {config_snapshot_path}")


if __name__ == "__main__":
    main()
