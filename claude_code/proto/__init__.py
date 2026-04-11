"""Proto package - generated code will be here"""

import sys
from pathlib import Path

_proto_dir = str(Path(__file__).parent)
sys.path.insert(0, _proto_dir)

from . import claude_code_pb2
from . import claude_code_pb2_grpc

sys.path.remove(_proto_dir)

__all__ = ["claude_code_pb2", "claude_code_pb2_grpc"]
