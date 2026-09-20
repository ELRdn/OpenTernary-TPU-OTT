#!/usr/bin/env python3
"""Run Yosys via either its official Python wheel or a native yosys binary.
Usage: python scripts/yosys_driver.py 'read_verilog -sv rtl/*.sv; ...'
The wheel contains the real Yosys compiler, not a Python reimplementation.
"""
from __future__ import annotations
import argparse
import subprocess
import shutil
import sys

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('script')
    args=parser.parse_args()
    try:
        from pyosys import libyosys as ys
    except ImportError:
        native=shutil.which('yosys')
        if not native:
            print('BLOCKED: install pyosys or native yosys',file=sys.stderr)
            return 77
        return subprocess.call([native,'-p',args.script])
    design=ys.Design()
    ys.run_pass(args.script,design)
    return 0
if __name__=='__main__':
    sys.exit(main())
