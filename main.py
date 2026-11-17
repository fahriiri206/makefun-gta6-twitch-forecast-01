"""Entry point for gta6-twitch-ccu-forecast-01.

The grader runs this once per case with only that case in /input.  It reads every
*.in file in name order and writes <stem>.out in the same order.  MAKEFUN_INPUT_DIR
and MAKEFUN_OUTPUT_DIR are the host-side equivalents of /input and /output.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model  # noqa: E402

def _input_dir() -> Path:
    return Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))


def _output_dir() -> Path:
    return Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))


def main() -> None:
    input_dir = _input_dir()
    output_dir = _output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(input_dir.glob("*.in")):
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
            forecast = model.forecast_case(case, path.name)
        except Exception:
            forecast = model.fallback_forecast(1.0)
        text = json.dumps(forecast, separators=(",", ":"), allow_nan=False) + "\n"
        (output_dir / f"{path.stem}.out").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
