"""Compatibility CLI: python -m traffic_rl."""
from .cli.main import main
from .common.artifacts import output_dir, versions

if __name__ == "__main__":
    main()
