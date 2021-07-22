"""Kluster fleet manager package."""
import argparse as _argparse

from manager import _runner


def parse() -> dict:
    """Parse command line arguments to invoke the fleet manager."""
    parser = _argparse.ArgumentParser(prog="fleet-manager")
    parser.add_argument("--cluster-name")
    parser.add_argument("-p", "--profile", dest="aws_profile")
    parser.add_argument("--external", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--pretty-print", action="store_true")
    parser.add_argument("--config-path")
    return vars(parser.parse_args())


def main():
    """Execute the kluster fleet manager."""
    return 1 if _runner.main(parse()) else 0
