#!/usr/bin/env python3

"""Checks if the test coverage is above a threshold."""

import argparse
import json
import sys

COVERAGE_REPORT="coverage/coverage.json"
THRESHOLD=30

def get_value_by_path(data, path):
    """Returns the value from a dict specified by path

    :param data: Dict the value is taken from.
    :type  data: dict
    :param path: Value path, separated by "/".
    :type  path: str

    :return: Value or None, if value is not found
    :rtype: any
    """
    current = data
    for part in path.split("/"):
        if part in current:
            current = current[part]
        else:
            return None
    return current

def get_percent_covered(filename):
    """Returns the coverage of note.py's tests in percent

    :param filename: name of the json file containing the coverage info
    :type  filename: str

    :return: Coverage of note.py's tests in percent.
    :rtype: number
    """
    with open(filename, "r") as report_file:
        data = json.load(report_file)
    return get_value_by_path(data, "files/note.py/summary/percent_covered")

def do_check(filename, threshold):
    """Checks if the coverage is above a given threshold

    :param filename: name of the json file containing the actual coverage
    :type  filename: str
    :param threshold: threshold to check
    :type  threshold: number

    :return: True if actual coverage is above the threshold, False otherwise
    :rtype: bool
    """
    actual = get_percent_covered(filename)
    if (actual < threshold):
        print(f"error: coverage too low: threshold is {THRESHOLD}, but actual coverage is {actual}", file=sys.stderr)
    return actual >= threshold 

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--filename', type=str, required=False, default=COVERAGE_REPORT)
    parser.add_argument('-t', '--threshold', type=int, required=False, default=THRESHOLD)
    args = parser.parse_args()
    check_okay = do_check(args.filename, args.threshold)
    sys.exit(0 if check_okay else 1)
