#!/usr/bin/env python3
import argparse
import csv
import glob
import os
import re
import sys


def extract_node_name(path):
    base = os.path.basename(path)
    match = re.search(r"(aion-\d+)", base)
    return match.group(1) if match else ""


def parse_problem_size(value):
    if value is None:
        return ("", -1)
    match = re.match(r"([A-Za-z]+)(\d+)", value)
    if match:
        return (match.group(1).lower(), int(match.group(2)))
    return (value.lower(), -1)


def sort_key(row):
    size_prefix, size_number = parse_problem_size(row.get("problem_size", ""))
    instance_name = row.get("instance_name", "")
    solver = row.get("solver", "")
    timestamp = row.get("timestamp", "")
    return (size_prefix, size_number, instance_name, solver, timestamp)


def read_csv_files(paths):
    header = None
    rows = []
    for path in paths:
        node_name = extract_node_name(path)
        with open(path, newline="") as handle:
            reader = csv.DictReader(handle)
            if header is None:
                header = reader.fieldnames
            elif reader.fieldnames != header:
                raise ValueError(
                    "CSV header mismatch in %s. Expected %s but found %s"
                    % (path, header, reader.fieldnames)
                )
            for row in reader:
                if node_name:
                    row["run_number"] = node_name
                rows.append(row)
    return header, rows


def write_csv(path, header, rows):
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in header})


def main():
    parser = argparse.ArgumentParser(
        description="Merge CSV files, replace run_number with node name, and sort rows."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=".",
        help="Directory containing CSV files (default: current directory).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="merged.csv",
        help="Output CSV path (default: merged.csv).",
    )
    parser.add_argument(
        "-p",
        "--pattern",
        default="*.csv",
        help="Glob pattern for CSV files (default: *.csv).",
    )
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)

    if os.path.isdir(input_path):
        pattern = os.path.join(input_path, args.pattern)
        paths = sorted(path for path in glob.glob(pattern) if os.path.isfile(path))
    elif os.path.isfile(input_path):
        paths = [input_path]
    else:
        raise SystemExit("Input path not found: %s" % input_path)

    paths = [path for path in paths if os.path.abspath(path) != output_path]
    if not paths:
        raise SystemExit("No CSV files found to merge.")

    try:
        header, rows = read_csv_files(paths)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if not header:
        raise SystemExit("No headers found in CSV files.")

    rows.sort(key=sort_key)
    write_csv(output_path, header, rows)


if __name__ == "__main__":
    main()
