"""Course workflow: check, build, train, evaluate, show."""
import argparse
from .config import read_config


def main():
    parser = argparse.ArgumentParser(description="DQN traffic-signal course project")
    parser.add_argument("--config")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check the local environment")
    build = commands.add_parser("build", help="Generate the intersection and composite demand")
    train = commands.add_parser("train", help="Train DQN and save the learning curve")
    train.add_argument("--steps", type=int)
    train.add_argument("--seed", type=int)
    evaluate = commands.add_parser("evaluate", help="Compare DQN with fixed-time control")
    evaluate.add_argument("--model", required=True)
    evaluate.add_argument("--seeds", nargs="+", type=int)
    show = commands.add_parser("show", help="Export a DQN learning replay")
    show.add_argument("--model", required=True)
    show.add_argument("--seed", type=int, default=101)
    show.add_argument("--no-open", action="store_true")
    for command in (build, train, evaluate, show):
        command.add_argument("--seconds", type=int)
    for command in (train, evaluate, show):
        command.add_argument("--out")
    args = parser.parse_args()
    config = read_config(args.config)
    if getattr(args, "seconds", None) is not None:
        if args.seconds <= 0 or args.seconds % config["simulation"]["delta_time"]:
            parser.error("--seconds must be positive and divisible by delta_time")
        config["simulation"]["duration_seconds"] = args.seconds
    if getattr(args, "seed", 0) is not None and getattr(args, "seed", 0) < 0:
        parser.error("--seed must be nonnegative")
    if args.command == "doctor":
        from .doctor import doctor
        doctor(args, config)
    elif args.command == "build":
        from .network import network
        from .demand import routes
        print(network(config))
        for seed in config["evaluation"]["seeds"]:
            print(seed, routes(config, seed))
    elif args.command == "train":
        from .train import train as run
        run(args, config)
    elif args.command == "evaluate":
        from .evaluate import evaluate as run
        run(args, config)
    else:
        from .replay import present
        present(args, config)


if __name__ == "__main__":
    main()
