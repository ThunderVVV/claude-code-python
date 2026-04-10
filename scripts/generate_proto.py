#!/usr/bin/env python3
"""Generate Python code from proto files"""

import subprocess
import sys
from pathlib import Path


def main():
    project_root = Path(__file__).parent.parent
    proto_dir = project_root / "claude_code" / "proto"
    proto_file = proto_dir / "claude_code.proto"

    if not proto_file.exists():
        print(f"Error: Proto file not found: {proto_file}")
        sys.exit(1)

    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"--python_out={proto_dir}",
        f"--grpc_python_out={proto_dir}",
        str(proto_file),
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error generating proto: {result.stderr}")
        sys.exit(1)

    print("Proto files generated successfully:")
    print(f"  - {proto_dir / 'claude_code_pb2.py'}")
    print(f"  - {proto_dir / 'claude_code_pb2_grpc.py'}")


if __name__ == "__main__":
    main()
