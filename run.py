import argparse
import collections
import csv
import json
import os
import platform
import resource
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import psutil
import yaml
from psplib import parse

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "instance_config.yaml"
DEFAULT_OUTPUT_DIR = Path.cwd() / "results"
DEFAULT_CP_MODEL = BASE_DIR / "rcpsp_cp.mzn"
DEFAULT_ILP_MODEL = BASE_DIR / "rcpsp_ilp.mzn"
TIMEOUT_MINUTES = 20
SOLVERS = {
    "cp": ["chuffed", "gecode", "cp-sat"],
    "ilp": ["coin-bc", "gurobi"],
}


class ResourceMonitor:
    def __init__(self, interval_seconds=0.05):
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._samples = []
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join()

    def _run(self):
        try:
            root = psutil.Process(os.getpid())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            root = None

        while not self._stop_event.is_set():
            total_rss = 0
            if root is not None:
                try:
                    children = root.children(recursive=True)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    children = []
                for proc in children:
                    try:
                        total_rss += proc.memory_info().rss
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            with self._lock:
                self._samples.append(total_rss)
            self._stop_event.wait(self.interval_seconds)

    def stats_mb(self):
        with self._lock:
            samples = list(self._samples)
        if not samples:
            return 0.0, 0.0
        active_samples = [sample for sample in samples if sample > 0]
        if not active_samples:
            return 0.0, 0.0
        avg_bytes = sum(active_samples) / len(active_samples)
        max_bytes = max(active_samples)
        mb = 1024 * 1024
        return avg_bytes / mb, max_bytes / mb


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


def resolve_config_path(config_path):
    path = Path(config_path).expanduser()
    if path.exists():
        return path

    base_relative_path = BASE_DIR / path
    if base_relative_path.exists():
        return base_relative_path

    raise FileNotFoundError(
        f"Config file not found: {config_path}. Tried '{path}' and '{base_relative_path}'."
    )


def calculate_greedy_horizon(data, topological_order):
    """Computes a fast upper bound using a greedy parallel schedule."""
    n = data["n"]
    durations = data["duration"]
    reqs = data["resource_usage"]
    caps = data["capacity"]
    successors = data["successors"]

    preds = [[] for _ in range(n)]
    indegree = [0] * n
    for u, succs in enumerate(successors):
        for v in succs:
            v_idx = v - 1
            preds[v_idx].append(u)
            indegree[v_idx] += 1

    start_times = [-1] * n
    finish_times = [-1] * n
    current_time = 0
    active_tasks = []
    completed = set()

    while len(completed) < n:
        active_tasks = [
            task for task in active_tasks if finish_times[task] > current_time
        ]

        available_res = list(caps)
        for task in active_tasks:
            for r in range(len(caps)):
                available_res[r] -= reqs[task][r]

        progress_made = False
        for task in topological_order:
            if start_times[task] != -1:
                continue

            if all(p in completed for p in preds[task]):
                if all(reqs[task][r] <= available_res[r] for r in range(len(caps))):
                    start_times[task] = current_time
                    finish_times[task] = current_time + durations[task]
                    active_tasks.append(task)

                    for r in range(len(caps)):
                        available_res[r] -= reqs[task][r]

                    progress_made = True

        if active_tasks:
            next_time = min(finish_times[task] for task in active_tasks)
            for task in active_tasks:
                if finish_times[task] == next_time:
                    completed.add(task)
            current_time = next_time
        elif not progress_made and len(completed) < n:
            break

    return max(finish_times) if max(finish_times) > 0 else sum(durations)


def parse_sm_file(filepath):
    inst = parse(filepath, instance_format="psplib")
    n = len(inst.activities)
    durations = [a.modes[0].duration for a in inst.activities]
    successors_zero_based = [list(a.successors) for a in inst.activities]
    predecessors = [[] for _ in inst.activities]
    indegree = [0 for _ in inst.activities]
    for pred_index, succs in enumerate(successors_zero_based):
        for succ_index in succs:
            predecessors[succ_index].append(pred_index)
            indegree[succ_index] += 1

    queue = collections.deque(i for i, degree in enumerate(indegree) if degree == 0)
    topological_order = []
    while queue:
        node = queue.popleft()
        topological_order.append(node)
        for succ in successors_zero_based[node]:
            indegree[succ] -= 1
            if indegree[succ] == 0:
                queue.append(succ)

    earliest_finish = [0 for _ in inst.activities]
    for node in topological_order:
        if predecessors[node]:
            earliest_start = max(earliest_finish[pred] for pred in predecessors[node])
        else:
            earliest_start = 0
        earliest_finish[node] = earliest_start + durations[node]

    num_resources = len(inst.resources)

    duration = [a.modes[0].duration for a in inst.activities]
    resource_usage = [
        [a.modes[0].demands[r] for r in range(num_resources)] for a in inst.activities
    ]
    capacity = [r.capacity for r in inst.resources]
    successors = [[s + 1 for s in a.successors] for a in inst.activities]

    data_dict = {
        "n": n,
        "duration": duration,
        "resource_usage": resource_usage,
        "capacity": capacity,
        "successors": successors,
    }
    horizon = calculate_greedy_horizon(data_dict, topological_order)

    return {
        "n": n,
        "horizon": horizon,
        "num_resources": num_resources,
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
        file.write(f"num_resources = {data['num_resources']};\n")
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
    config_path = resolve_config_path(config_path)
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    instances = config.get("instances")
    if not isinstance(instances, dict) or not instances:
        raise ValueError(
            f"{config_path} must define a non-empty 'instances' mapping"
        )

    runs_per_instance = int(config.get("runs_per_instance", 3))
    if runs_per_instance < 1:
        raise ValueError("runs_per_instance must be at least 1")

    return {
        "instances": instances,
        "runs_per_instance": runs_per_instance,
        "config_path": config_path,
    }


def normalize_instance_path(problem_size, instance_name):
    return BASE_DIR / "data" / f"{problem_size}.sm" / f"{instance_name}.sm"


def solve_instance(instance_path, model_path, solver_name):
    from minizinc import Instance, Model, Solver
    import os

    instance_path = Path(instance_path)
    model_path = Path(model_path)
    data = parse_sm_file(instance_path)

    with tempfile.NamedTemporaryFile(suffix=".dzn", delete=False) as temp_file:
        dzn_path = Path(temp_file.name)

    generate_dzn(data, dzn_path)
    monitor = ResourceMonitor()
    start_time = time.perf_counter()
    ru_start = resource.getrusage(resource.RUSAGE_CHILDREN)
    monitor.start()

    try:
        if solver_name == "gurobi":
            current_ld = os.environ.get("LD_LIBRARY_PATH", "")
            if "/opt/gurobi/lib" not in current_ld:
                os.environ["LD_LIBRARY_PATH"] = f"/opt/gurobi/lib:{current_ld}"

        model = Model(str(model_path))
        solver = Solver.lookup(solver_name)

        instance = Instance(solver, model)
        instance.add_file(str(dzn_path))

        solve_kwargs = {"timeout": timedelta(minutes=TIMEOUT_MINUTES)}
        if solver_name == "gurobi":
            solve_kwargs["gurobi-dll"] = "/opt/gurobi/lib/libgurobi120.so"

        result = instance.solve(**solve_kwargs)
        elapsed = time.perf_counter() - start_time
        monitor.stop()

        avg_ram_mb, max_ram_mb = monitor.stats_mb()
        ru_end = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu_time_used = (ru_end.ru_utime - ru_start.ru_utime) + (
            ru_end.ru_stime - ru_start.ru_stime
        )
        cpu_percent = (cpu_time_used / elapsed) * 100.0 if elapsed > 0 else 0.0

        if result.solution is None:
            return {
                "elapsed_seconds": elapsed,
                "avg_ram_mb": avg_ram_mb,
                "max_ram_mb": max_ram_mb,
                "cpu_percent": cpu_percent,
                "makespan": None,
                "status": "no_solution",
                "error": "",
            }

        return {
            "elapsed_seconds": elapsed,
            "avg_ram_mb": avg_ram_mb,
            "max_ram_mb": max_ram_mb,
            "cpu_percent": cpu_percent,
            "makespan": result.solution.makespan,
            "status": "ok",
            "error": "",
        }
    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        monitor.stop()
        avg_ram_mb, max_ram_mb = monitor.stats_mb()
        ru_end = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu_time_used = (ru_end.ru_utime - ru_start.ru_utime) + (
            ru_end.ru_stime - ru_start.ru_stime
        )
        cpu_percent = (cpu_time_used / elapsed) * 100.0 if elapsed > 0 else 0.0
        print(
            f"Error solving {instance_path} with {model_path} on {solver_name}: {exc}"
        )
        return {
            "elapsed_seconds": elapsed,
            "avg_ram_mb": avg_ram_mb,
            "max_ram_mb": max_ram_mb,
            "cpu_percent": cpu_percent,
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
    config_path = config["config_path"]
    timestamp = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    hostname = platform.node() or "unknown-host"
    safe_hostname = hostname.replace(" ", "_")
    file_stamp = f"{timestamp}-{safe_hostname}"

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / f"{file_stamp}-results.csv"
    hardware_path = output_dir / f"{file_stamp}-hardware.json"
    config_snapshot_path = output_dir / f"{file_stamp}-config.yaml"

    fieldnames = [
        "timestamp",
        "problem_size",
        "instance_name",
        "run_number",
        "runs_per_instance",
        "paradigm",
        "solver",
        "model",
        "started_at",
        "finished_at",
        "elapsed_seconds",
        "avg_ram_mb",
        "max_ram_mb",
        "cpu_percent",
        "makespan",
        "status",
        "error",
    ]

    selected_instances = {
        problem_size: list(instance_names)
        for problem_size, instance_names in config["instances"].items()
    }

    write_timestamped_config_snapshot(
        config_snapshot_path,
        config_path,
        config,
        selected_instances,
    )

    hardware_info = collect_hardware_info()
    with hardware_path.open("w", encoding="utf-8") as file:
        json.dump(hardware_info, file, indent=2, sort_keys=True)
        file.write("\n")

    rows = []
    results_exists = results_path.exists() and results_path.stat().st_size > 0
    results_file = results_path.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(results_file, fieldnames=fieldnames)
    if not results_exists:
        writer.writeheader()
        results_file.flush()
        os.fsync(results_file.fileno())
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
                base_label = (
                    f"  [{instance_index:02d}/{len(instance_names):02d}] {instance_name:<12} "
                    f"run {run_number:02d}/{config['runs_per_instance']:02d}"
                )

                run_finished_at = datetime.now().isoformat(timespec="seconds")

                summary_labels = []
                for paradigm, solver_list in SOLVERS.items():
                    model_path = (
                        DEFAULT_CP_MODEL if paradigm == "cp" else DEFAULT_ILP_MODEL
                    )
                    for solver_name in solver_list:
                        started_at = datetime.now().isoformat(timespec="seconds")
                        print(
                            f"{base_label} | Status: Solving {paradigm.upper()}:{solver_name}...",
                            end="\r",
                            flush=True,
                        )
                        result = solve_instance(instance_path, model_path, solver_name)
                        finished_at = datetime.now().isoformat(timespec="seconds")

                        row = {
                            "timestamp": timestamp,
                            "problem_size": problem_size,
                            "instance_name": instance_name,
                            "run_number": run_number,
                            "runs_per_instance": config["runs_per_instance"],
                            "paradigm": paradigm,
                            "solver": solver_name,
                            "model": model_path.name,
                            "started_at": started_at,
                            "finished_at": finished_at,
                            "elapsed_seconds": f"{result['elapsed_seconds']:.6f}",
                            "avg_ram_mb": f"{result['avg_ram_mb']:.2f}",
                            "max_ram_mb": f"{result['max_ram_mb']:.2f}",
                            "cpu_percent": f"{result['cpu_percent']:.1f}",
                            "makespan": result["makespan"],
                            "status": result["status"],
                            "error": result["error"],
                        }
                        rows.append(row)
                        writer.writerow(row)
                        results_file.flush()
                        os.fsync(results_file.fileno())

                        label = (
                            f"{result['makespan']} ({result['elapsed_seconds']:.2f}s)"
                            if result["makespan"] is not None
                            else f"{result['status']} ({result['elapsed_seconds']:.2f}s)"
                        )
                        summary_labels.append(
                            f"{paradigm.upper()}:{solver_name} {label}"
                        )

                print(f"{base_label} | " + " | ".join(summary_labels))

    print("\n" + "=" * 75)
    print("OVERALL SUMMARY")
    print("=" * 75)
    print(f"Total instance-run pairs: {len(rows)}")
    solver_stats = {}
    for row in rows:
        solver = row["solver"]
        stats = solver_stats.setdefault(solver, {"time": [], "ram": [], "cpu": []})
        stats["time"].append(float(row["elapsed_seconds"]))
        stats["ram"].append(float(row["avg_ram_mb"]))
        stats["cpu"].append(float(row["cpu_percent"]))

    for solver_name, metrics in sorted(solver_stats.items()):
        times = metrics["time"]
        rams = metrics["ram"]
        cpus = metrics["cpu"]
        avg_time = sum(times) / len(times)
        avg_ram = sum(rams) / len(rams)
        avg_cpu = sum(cpus) / len(cpus)
        print(
            f"{solver_name:<8} - Time: {sum(times):.2f}s (Avg {avg_time:.2f}s, Min {min(times):.2f}s, Max {max(times):.2f}s) | "
            f"Avg RAM: {avg_ram:.1f}MB | Avg CPU: {avg_cpu:.0f}%"
        )
    results_file.close()
    print(f"\nSaved results to {results_path}")
    print(f"Saved hardware characteristics to {hardware_path}")
    print(f"Saved selected-instance snapshot to {config_snapshot_path}")


if __name__ == "__main__":
    main()
