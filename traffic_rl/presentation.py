"""Export real SUMO trajectories into a portable, offline presentation viewer."""
from __future__ import annotations

import hashlib
import copy
import json
import shutil
import webbrowser
import xml.etree.ElementTree as ET
from pathlib import Path

from .runtime import ROOT, save_json


def _present_layout(args, config):
    from .__main__ import output_dir, versions
    from .multi_environment import make_env, validate_model
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
    junction = net.find("junction[@id='J']")
    center = [float(junction.get("x")), float(junction.get("y"))] if junction is not None else [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2]
    controlled = {link.get("from")[0]: int(link.get("linkIndex")) for link in net.findall("connection") if link.get("tl") == "J"}
    data = {"version": 1, "duration": duration, "sampleInterval": 0.2, "seed": args.seed, "center": center, "source": "SUMO simulation / synthetic demand", "modelNote": model_note, "runs": []}
    layout = config.get("layout", "intersection")
    data["layout"] = layout
    def points(shape):
        return [[float(n) for n in pair.split(",")] for pair in shape.split()]
    data["geometry"] = {
        "lanes": [{"id": lane.get("id"), "shape": points(lane.get("shape")), "width": float(lane.get("width", "3.2"))} for lane in net.findall("edge/lane")],
        "junctions": [points(j.get("shape")) for j in net.findall("junction") if j.get("shape")],
        "signals": [{"direction": lane.get("id")[0], "position": points(lane.get("shape"))[-1]} for lane in net.findall("edge/lane") if lane.get("id").endswith("_in_0")],
    }
    for scenario in args.scenarios:
        for policy in ["fixed", "queue"] + (["yield"] if layout == "roundabout" else []) + (["dqn"] if model else []):
            case = run / f"{scenario}_{policy}"
            case.mkdir()
            fcd = case / "vehicles.xml"
            tripinfo = case / "tripinfo.xml"
            route_file, planned = routes(config, scenario, args.seed)
            env = make_env(config, scenario, args.seed, tripinfo=tripinfo)
            validate_model(model, env)
            core = env.unwrapped
            core.additional_sumo_cmd += f" --fcd-output {fcd.relative_to(ROOT).as_posix()} --device.fcd.period 0.2"
            signals = []
            trace = []
            decisions = []
            try:
                obs, _ = env.reset(seed=args.seed)
                original_step = core._sumo_step

                def light_state():
                    if layout != "intersection":
                        return core.light_state()
                    state = core.sumo.trafficlight.getRedYellowGreenState("J")
                    return "".join(state[controlled[d]] for d in "NSEW")

                def record_signal():
                    signals.append([int(core.sim_step), light_state()])
                    original_step()

                core._sumo_step = record_signal
                if layout == "intersection":
                    lanes = list(env.signal.lanes)
                    observation_labels = ["南北相位", "东西相位", "满足最小相位时长"] + [f"{lane} 密度" for lane in lanes] + [f"{lane} 排队比例" for lane in lanes] + ["绿灯年龄比例", "回合进度"]
                else:
                    observation_labels = [f"{d} 进口存在" for d in "NSEW"] + [f"{d} 排队比例" for d in "NSEW"] + [f"{d} 密度" for d in "NSEW"] + [f"{d} 放行相位" for d in "NSEW"] + ["绿灯年龄比例", "回合进度", "环内密度", "十字路口", "丁字路口", "环岛"]

                def snapshot():
                    return {"queue": env.queues(), "greenAge": float(env.green_age), "light": light_state(), "density": {d: round(core.sumo.lane.getLastStepVehicleNumber(f"{d}_in_0") / max(1, core.sumo.lane.getLength(f"{d}_in_0") / 7.5), 4) if f"{d}_in_0" in lane_ids else None for d in "NSEW"}}

                lane_ids = set(core.sumo.lane.getIDList())
                done = False
                while not done:
                    before = snapshot()
                    previous_obs = obs.copy()
                    start = float(core.sim_step)
                    action = int(model.predict(obs, deterministic=True)[0]) if policy == "dqn" else env.baseline_action(policy)
                    obs, reward, terminated, truncated, info = env.step(action)
                    decisions.append({"index": len(decisions) + 1, "start": start, "end": float(core.sim_step), "state": before, "nextState": snapshot(), "observation": previous_obs.tolist(), "nextObservation": obs.tolist(), "requested": action, "executed": int(info["phase"]), "reason": info["action_reason"], "reward": float(reward), "rewardTerms": info["reward_terms"], "rewardInputs": info["reward_inputs"]})
                    trace.append(info)
                    done = terminated or truncated
                terminal = []
                for vid in core.sumo.vehicle.getIDList():
                    x, y = core.sumo.vehicle.getPosition(vid)
                    terminal.append([vid, x, y, core.sumo.vehicle.getAngle(vid), core.sumo.vehicle.getSpeed(vid)])
                terminal_queue = list(env.queues().values())
                terminal_light = light_state()
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
            data["runs"][-1].update({"layout": layout, "decisions": decisions, "observationLabels": observation_labels, "vehicleIds": list(ids), "rewardScope": "进口停车车辆" if layout == "intersection" else "全路网停车车辆"})
            save_json(case / "decisions.json", decisions)
            save_json(case / "metrics.json", metrics)
            print(f"Recorded {scenario}/{policy}: {len(frames)} frames, {len(ids)} vehicles", flush=True)
    assets = Path(__file__).parent / "web"
    data.update({"version": 2, "simulation": config["simulation"], "rewardWeights": config["reward"], "layouts": [{"id": layout, "center": center, "geometry": data["geometry"]}]})
    for name in ("index.html", "style.css", "app.js", "renderer.js"):
        shutil.copyfile(assets / name, run / name)
    (run / "recordings.js").write_text("window.TRAFFIC_REPLAY=" + json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + ";", encoding="utf-8")
    save_json(run / "manifest.json", {"config": config, "seed": args.seed, "packages": versions(), "model": str(Path(args.model).resolve()) if args.model else None, "model_sha256": hashlib.sha256(Path(args.model).read_bytes()).hexdigest() if args.model else None, "note": "Recorded SUMO replay. Visual interpolation is only for display; indicators come from recorded samples. Landscape is illustrative; pedestrians are not simulated. Turning movements are included in the new layouts."})
    print(f"Presentation ready: {run / 'index.html'}", flush=True)
    if not args.no_open:
        webbrowser.open((run / "index.html").as_uri())
    return data, run


def present(args, config):
    """One portable package can contain multiple independently recorded layouts."""
    from .__main__ import output_dir
    layouts = list(dict.fromkeys(getattr(args, "layouts", None) or []))
    if not layouts:
        return _present_layout(args, config)
    root = output_dir(args.out, "learning_lab")
    bundle = None
    packages = []
    model_shape = None
    if args.model:
        from stable_baselines3 import DQN
        model_shape = DQN.load(args.model, device="cpu").observation_space.shape
    for layout in layouts:
        child_args, child_config = copy.copy(args), copy.deepcopy(config)
        child_args.out = (root / layout).relative_to(ROOT).as_posix()
        child_args.no_open = True
        child_config["layout"] = layout
        if layout == "intersection" and "surge" in child_args.scenarios:
            child_args.scenarios = [s for s in child_args.scenarios if s != "surge"]
        if not child_args.scenarios:
            continue
        if model_shape is not None and model_shape != ((13,) if layout == "intersection" else (22,)):
            child_args.model = None
        data, path = _present_layout(child_args, child_config)
        packages.append({"layout": layout, "manifest": f"{layout}/manifest.json", "modelIncluded": bool(child_args.model)})
        if bundle is None:
            bundle = copy.copy(data)
            bundle["layouts"], bundle["runs"] = [], []
        bundle["layouts"].extend(data["layouts"])
        for recording in data["runs"]:
            recording["modelNote"] = data["modelNote"]
        bundle["runs"].extend(data["runs"])
    if bundle is None:
        raise ValueError("No compatible layout/scenario combinations to export.")
    for name in ("index.html", "style.css", "app.js", "renderer.js"):
        shutil.copyfile(Path(__file__).parent / "web" / name, root / name)
    (root / "recordings.js").write_text("window.TRAFFIC_REPLAY=" + json.dumps(bundle, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + ";", encoding="utf-8")
    save_json(root / "manifest.json", {"version": 2, "seed": args.seed, "packages": packages, "note": "Offline evaluation replay. Model weights do not update during playback."})
    print(f"Presentation ready: {root / 'index.html'}", flush=True)
    if not args.no_open:
        webbrowser.open((root / "index.html").as_uri())
    return bundle, root
