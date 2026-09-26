"""Portable replay packages: a small catalog and independently loaded runs."""
import argparse
import json
import shutil
from pathlib import Path


def write_package(data, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    assets = Path(__file__).parents[1] / "web"
    for source in assets.rglob("*"):
        if source.is_file():
            target = folder / source.relative_to(assets)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    chunks = folder / "recordings"
    chunks.mkdir(exist_ok=True)
    catalog = {**data, "version": 3, "runs": []}
    for i, run in enumerate(data["runs"]):
        key = f"run_{i:03d}"
        src = f"recordings/{key}.js"
        encoded = json.dumps(run, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        (folder / src).write_text(f'window.TRAFFIC_CHUNKS["{key}"]={encoded};', encoding="utf-8")
        catalog["runs"].append({k: v for k, v in run.items() if k not in ("frames", "decisions", "vehicleIds")})
        catalog["runs"][-1].update(key=key, src=src)
    (folder / "recordings.js").write_text("window.TRAFFIC_REPLAY=" + json.dumps(catalog, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + ";", encoding="utf-8")


def read_package(folder):
    """Read both historical monolithic packages and the current chunked format."""
    folder = Path(folder)
    text = (folder / "recordings.js").read_text(encoding="utf-8")
    data = json.loads(text.removeprefix("window.TRAFFIC_REPLAY=").removesuffix(";"))
    if data["version"] == 3:
        data["runs"] = [json.loads((folder / run["src"]).read_text(encoding="utf-8").split("=", 1)[1].removesuffix(";")) for run in data["runs"]]
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Repackage existing recordings without rerunning SUMO")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Choose a new output directory")
    write_package(read_package(args.source), args.out)
    if (args.source / "manifest.json").exists():
        shutil.copyfile(args.source / "manifest.json", args.out / "manifest.json")
    print(args.out.resolve() / "index.html")
