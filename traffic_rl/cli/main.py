"""Command parsing only; workflows live in experiments and replay."""
import argparse
import os
from ..common.runtime import ROOT, read_config
from .doctor import doctor
from ..experiments.training import train
from ..experiments.evaluation import evaluate

def main():
    os.chdir(ROOT)
    parser = argparse.ArgumentParser(description="Campus Traffic Signal RL")
    parser.add_argument("--config", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check packages, SUMO and Gymnasium connection")
    build = sub.add_parser("build", help="Generate network and evaluation demand")
    show = sub.add_parser("show", help="Build and open the polished offline traffic presentation")
    show.add_argument("--seconds", type=int, default=300)
    show.add_argument("--seed", type=int, default=101)
    show.add_argument("--layouts", nargs="+", choices=["intersection", "crossroads", "tjunction", "roundabout"], help="Bundle several road layouts into one learning viewer")
    show.add_argument("--scenarios", nargs="+", choices=["balanced", "peak", "tidal", "surge"], default=["balanced", "peak", "tidal"])
    show.add_argument("--model", help="Optional DQN model to include in the strategy switcher")
    show.add_argument("--out", help="New output directory under the project")
    show.add_argument("--no-open", action="store_true", help="Export without opening a browser")
    training = sub.add_parser("train", help="Train and verify DQN")
    training.add_argument("--steps", type=int)
    training.add_argument("--seed", type=int)
    training.add_argument("--scenario", choices=["balanced", "peak", "tidal", "surge", "mixed"])
    evaluation = sub.add_parser("evaluate", help="Evaluate policies on identical traffic")
    evaluation.add_argument("--policies", nargs="+", choices=["fixed", "queue", "dqn", "yield"], default=["fixed", "queue"])
    evaluation.add_argument("--scenarios", nargs="+", choices=["balanced", "peak", "tidal", "surge"])
    evaluation.add_argument("--seeds", nargs="+", type=int)
    evaluation.add_argument("--model")
    evaluation.add_argument("--gui", action="store_true", help="Open SUMO GUI for each episode")
    evaluation.add_argument("--gui-delay", type=int, default=100, metavar="MS", help="GUI delay per simulation second in milliseconds (default: 100; 0: fastest)")
    evaluation.add_argument("--no-gui-pause", action="store_true", help="Close GUI automatically at the end instead of waiting for Enter")
    for item in (build, training, evaluation):
        item.add_argument("--seconds", type=int, help="Override episode length in simulated seconds")
    for item in (training, evaluation):
        item.add_argument("--out", help="New output directory under the project; omit for timestamped directory")
    for item in (build, show, training, evaluation):
        item.add_argument("--layout", choices=["intersection", "crossroads", "tjunction", "roundabout"] + (["mixed"] if item is training else []), help="Road topology; mixed randomizes topology each training episode")
    args = parser.parse_args()
    if getattr(args, "gui_delay", 0) < 0:
        parser.error("--gui-delay must be nonnegative")
    config = read_config(args.config)
    if getattr(args, "layout", None):
        config["layout"] = args.layout
    layout = config.get("layout", "intersection")
    if getattr(args, "layouts", None) and getattr(args, "layout", None):
        parser.error("Use either --layout or --layouts, not both")
    if layout == "mixed" and args.command != "train":
        parser.error("Select a concrete --layout for evaluation, export or build")
    requested_scenarios = ([args.scenario or config["training"]["scenario"]] if args.command == "train" else getattr(args, "scenarios", None) or config["evaluation"]["scenarios"])
    if layout == "intersection" and not getattr(args, "layouts", None) and any(s in ("mixed", "surge") for s in requested_scenarios):
        parser.error("surge/mixed demand requires --layout crossroads, tjunction, roundabout or mixed")
    if "yield" in getattr(args, "policies", []) and layout != "roundabout":
        parser.error("--policies yield requires --layout roundabout")
    if getattr(args, "seconds", None) is not None:
        if args.seconds <= 0 or args.seconds % config["simulation"]["delta_time"]:
            parser.error("--seconds must be positive and divisible by delta_time")
        config["simulation"]["duration_seconds"] = args.seconds
    if args.command == "doctor":
        doctor(args, config)
    elif args.command == "build":
        from ..networks.scenario import network, routes
        print(network(config))
        for scenario in config["evaluation"]["scenarios"]:
            for seed in config["evaluation"]["seeds"]:
                path, count = routes(config, scenario, seed)
                print(scenario, seed, count, path)
    elif args.command == "show":
        from ..replay.export import present
        present(args, config)
    elif args.command == "train":
        train(args, config)
    else:
        evaluate(args, config)
