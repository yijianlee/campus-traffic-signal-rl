"""Export real SUMO trajectories into a portable, offline presentation viewer."""
from __future__ import annotations

import hashlib
import json
import shutil
import webbrowser
import xml.etree.ElementTree as ET
from pathlib import Path

from .runtime import ROOT, save_json


def present(args, config):
    from .__main__ import output_dir, versions
    from .environment import IntersectionEnv
    from .metrics import episode_metrics
    from .scenario import network, routes

    model = None
    model_note = None
    if args.model:
        import torch
        from stable_baselines3 import DQN
        torch.set_num_threads(2)
        model = DQN.load(args.model, device="cpu")
        metadata = Path(args.model).resolve().parent / "run.json"
        if metadata.exists():
            info = json.loads(metadata.read_text(encoding="utf-8"))
            model_note = f"{info.get('actual_steps', '未知')} 步训练；效果需独立评估"
        else:
            model_note = "用户提供模型；训练程度未验证"
    run = output_dir(args.out, "presentation")
    duration = config["simulation"]["duration_seconds"]
    net = ET.parse(network(config)).getroot()
    bounds = [float(x) for x in net.find("location").get("convBoundary").split(",")]
    center = [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2]
    controlled = {link.get("from")[0]: int(link.get("linkIndex")) for link in net.findall("connection") if link.get("tl") == "J"}
    data = {"version": 1, "duration": duration, "sampleInterval": 0.2, "seed": args.seed, "center": center, "source": "SUMO simulation / synthetic demand", "modelNote": model_note, "runs": []}
    for scenario in args.scenarios:
        for policy in (["fixed", "queue", "dqn"] if model else ["fixed", "queue"]):
            case = run / f"{scenario}_{policy}"
            case.mkdir()
            fcd = case / "vehicles.xml"
            tripinfo = case / "tripinfo.xml"
            route_file, planned = routes(config, scenario, args.seed)
            env = IntersectionEnv(config, scenario, args.seed, tripinfo=tripinfo)
            env.env.additional_sumo_cmd += f" --fcd-output {fcd.relative_to(ROOT).as_posix()} --device.fcd.period 0.2"
            signals = []
            trace = []
            try:
                obs, _ = env.reset(seed=args.seed)
                original_step = env.env._sumo_step

                def record_signal():
                    state = env.env.sumo.trafficlight.getRedYellowGreenState("J")
                    signals.append([int(env.env.sim_step), "".join(state[controlled[d]] for d in "NSEW")])
                    original_step()

                env.env._sumo_step = record_signal
                done = False
                while not done:
                    action = int(model.predict(obs, deterministic=True)[0]) if policy == "dqn" else env.baseline_action(policy)
                    obs, _, terminated, truncated, info = env.step(action)
                    trace.append(info)
                    done = terminated or truncated
                terminal = []
                for vid in env.env.sumo.vehicle.getIDList():
                    x, y = env.env.sumo.vehicle.getPosition(vid)
                    terminal.append([vid, x, y, env.env.sumo.vehicle.getAngle(vid), env.env.sumo.vehicle.getSpeed(vid)])
                terminal_queue = list(env.queues().values())
                terminal_state = env.env.sumo.trafficlight.getRedYellowGreenState("J")
                terminal_light = "".join(terminal_state[controlled[d]] for d in "NSEW")
            finally:
                env.close()
            ids = {}
            frames = []
            seen = set()
            for _, element in ET.iterparse(fcd, events=("end",)):
                if element.tag != "timestep":
                    continue
                vehicles = []
                queue = dict.fromkeys("NSEW", 0)
                total_speed = 0.0
                for vehicle in element:
                    item = vehicle.attrib
                    vid = item["id"]
                    if vid not in ids:
                        ids[vid] = len(ids)
                    seen.add(vid)
                    speed = float(item["speed"])
                    total_speed += speed
                    lane = item["lane"]
                    if lane.endswith("_in_0") and speed < 0.1:
                        queue[lane[0]] += 1
                    vehicles.append([ids[vid], float(item["x"]), float(item["y"]), float(item["angle"]), speed])
                t = float(element.get("time"))
                light = signals[min(int(t), len(signals) - 1)][1]
                frames.append({"t": t, "v": vehicles, "q": list(queue.values()), "light": light, "completed": len(seen) - len(vehicles), "speed": round(total_speed / len(vehicles) * 3.6, 1) if vehicles else None})
                element.clear()
            metrics = episode_metrics(tripinfo, route_file, duration, trace)
            end_vehicles = []
            for vehicle in terminal:
                vid = vehicle[0]
                if vid not in ids:
                    ids[vid] = len(ids)
                end_vehicles.append([ids[vid], *vehicle[1:]])
            frames.append({"t": duration, "v": end_vehicles, "q": terminal_queue, "light": terminal_light, "completed": metrics["completed_vehicles"], "speed": round(sum(v[4] for v in end_vehicles) / len(end_vehicles) * 3.6, 1) if end_vehicles else None})
            data["runs"].append({"scenario": scenario, "policy": policy, "planned": planned, "frames": frames, "metrics": metrics, "demandHash": hashlib.sha256(route_file.read_bytes()).hexdigest()})
            save_json(case / "metrics.json", metrics)
            print(f"Recorded {scenario}/{policy}: {len(frames)} frames, {len(ids)} vehicles", flush=True)
    assets = Path(__file__).parent / "web"
    for name in ("index.html", "style.css", "app.js"):
        shutil.copyfile(assets / name, run / name)
    (run / "recordings.js").write_text("window.TRAFFIC_REPLAY=" + json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + ";", encoding="utf-8")
    save_json(run / "manifest.json", {"config": config, "seed": args.seed, "packages": versions(), "model": str(Path(args.model).resolve()) if args.model else None, "model_sha256": hashlib.sha256(Path(args.model).read_bytes()).hexdigest() if args.model else None, "note": "Recorded SUMO replay. Visual interpolation is only for display; indicators come from recorded samples. Landscape is illustrative; pedestrians and turning movements are not simulated."})
    print(f"Presentation ready: {run / 'index.html'}", flush=True)
    if not args.no_open:
        webbrowser.open((run / "index.html").as_uri())
