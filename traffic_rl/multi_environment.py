"""Shared four-approach signal control across turning junctions and metered rings."""
from __future__ import annotations

import copy
import uuid
import xml.etree.ElementTree as ET

import gymnasium as gym
import numpy as np

from .runtime import ROOT, binary, configure_sumo
from .roadnet import DIRECTIONS, LAYOUTS, SCENARIOS, directions, network, routes

configure_sumo()
import traci


class RoadEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, config, scenario, seed, vary_demand=False, gui=False, gui_delay=100, tripinfo=None):
        super().__init__()
        if config["layout"] not in (*LAYOUTS, "mixed") or scenario not in (*SCENARIOS, "mixed"):
            raise ValueError("Unsupported road layout or traffic scenario.")
        if config["simulation"]["road_length_m"] <= 60:
            raise ValueError("New layouts require road_length_m > 60 to leave space for the junction and ring entry gates.")
        self.config = copy.deepcopy(config)
        self.layout_choice = config["layout"]
        self.scenario_choice = scenario
        self.base_seed = seed
        self.vary_demand = vary_demand
        self.episode_index = 0
        self.episodes = []
        self.gui, self.gui_delay, self.tripinfo = gui, gui_delay, tripinfo
        self.additional_sumo_cmd = ""
        self.sumo = None
        self.action_space = gym.spaces.Discrete(4)
        self.observation_space = gym.spaces.Box(0, 1, (22,), np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.close()
        if seed is not None:
            self.base_seed, self.episode_index = seed, 0
        demand_seed = 100000 + self.base_seed * 1000 + self.episode_index if self.vary_demand else self.base_seed
        self.episode_index += 1
        rng = np.random.default_rng(demand_seed)
        self.layout = str(rng.choice(LAYOUTS)) if self.layout_choice == "mixed" else self.layout_choice
        self.scenario = str(rng.choice(SCENARIOS)) if self.scenario_choice == "mixed" else self.scenario_choice
        self.config["layout"] = self.layout
        self.active = directions(self.layout)
        net = network(self.config)
        route, _ = routes(self.config, self.scenario, demand_seed)
        self.episodes.append({"layout": self.layout, "scenario": self.scenario, "demand_seed": demand_seed})
        sim = self.config["simulation"]
        command = [binary("sumo-gui" if self.gui else "sumo"), "-n", net.relative_to(ROOT).as_posix(), "-r", route.relative_to(ROOT).as_posix(), "--seed", str(demand_seed), "--step-length", str(sim["step_length"]), "--no-step-log", "true", "--duration-log.disable", "true", "--xml-validation", "never", "--time-to-teleport", "-1", "--max-depart-delay", "-1", "--collision.check-junctions", "true"]
        if self.gui:
            command += ["--start", "--delay", str(self.gui_delay * sim["step_length"])]
        if self.tripinfo:
            path = self.tripinfo.resolve()
            relative = path.relative_to(ROOT).as_posix()
            if any(c.isspace() for c in relative):
                raise ValueError("Tripinfo path must not contain whitespace.")
            path.parent.mkdir(parents=True, exist_ok=True)
            command += ["--tripinfo-output", relative, "--tripinfo-output.write-unfinished", "true"]
        command += self.additional_sumo_cmd.split()
        label = uuid.uuid4().hex
        traci.start(command, label=label, doSwitch=False)
        self.sumo = traci.getConnection(label)
        self.links = {}
        for link in ET.parse(net).getroot().findall("connection"):
            if link.get("tl"):
                self.links.setdefault(link.get("tl"), {})[int(link.get("linkIndex"))] = link.get("from")[0]
        self.phase = DIRECTIONS.index(self.active[0])
        self.green_age = 0
        self.sim_step = 0
        self.switches = self.forced_switches = self.collisions = self.teleports = 0
        self.unmetered = False
        self._lights("G")
        return self._observation(), {}

    def _lights(self, color):
        for tl, links in self.links.items():
            state = "".join("G" if self.unmetered else color if links[i] == DIRECTIONS[self.phase] else "r" for i in range(len(links)))
            self.sumo.trafficlight.setRedYellowGreenState(tl, state)

    def light_state(self):
        colors = dict.fromkeys(DIRECTIONS, "-")
        for tl, links in self.links.items():
            state = self.sumo.trafficlight.getRedYellowGreenState(tl)
            for i, d in links.items():
                colors[d] = state[i]
        return "".join(colors.values())

    def _sumo_step(self):
        # Poll every physics tick so collision/teleport events cannot be skipped.
        for _ in range(round(1 / self.config["simulation"]["step_length"])):
            self.sumo.simulationStep()
            self.collisions += self.sumo.simulation.getCollidingVehiclesNumber()
            self.teleports += self.sumo.simulation.getStartingTeleportNumber()
        self.sim_step += 1

    def queues(self):
        return {d: self.sumo.lane.getLastStepHaltingNumber(f"{d}_in_0") if d in self.active else 0 for d in DIRECTIONS}

    def _observation(self):
        sim = self.config["simulation"]
        mask = [float(d in self.active) for d in DIRECTIONS]
        queue = [min(q / 40, 1) for q in self.queues().values()]
        density = [min(self.sumo.lane.getLastStepVehicleNumber(f"{d}_in_0") / max(1, self.sumo.lane.getLength(f"{d}_in_0") / 7.5), 1) if d in self.active else 0 for d in DIRECTIONS]
        ring = sum(self.sumo.edge.getLastStepVehicleNumber(f"ring_{d}") for d in DIRECTIONS) / 24 if self.layout == "roundabout" else 0
        return np.array(mask + queue + density + [float(i == self.phase) for i in range(4)] + [min(self.green_age / sim["max_green"], 1), self.sim_step / sim["duration_seconds"], min(ring, 1)] + [float(self.layout == v) for v in LAYOUTS], dtype=np.float32)

    def step(self, action):
        if not self.action_space.contains(action):
            raise ValueError(f"Invalid action: {action}")
        sim = self.config["simulation"]
        requested = int(action)
        invalid = DIRECTIONS[requested] not in self.active
        selected = self.phase if invalid or self.green_age < sim["min_green"] else requested
        forced = not self.unmetered and self.green_age + sim["delta_time"] > sim["max_green"]
        if forced:
            selected = DIRECTIONS.index(self.active[(self.active.index(DIRECTIONS[self.phase]) + 1) % len(self.active)])
            self.forced_switches += 1
        switched = selected != self.phase and not self.unmetered
        if switched:
            self.switches += 1
        for tick in range(sim["delta_time"]):
            if switched:
                # Entire decision interval clears the intersection: yellow then all-red.
                self._lights("y" if tick < sim["yellow_time"] else "r")
            else:
                self._lights("G")
            self._sumo_step()
        if switched:
            self.phase, self.green_age = selected, 0
            self._lights("G")
        else:
            self.green_age += sim["delta_time"]
        q = self.queues()
        stopped = sum(self.sumo.vehicle.getSpeed(v) < .1 for v in self.sumo.vehicle.getIDList())
        reward = -float(stopped) * self.config["reward"]["queue_weight"] - float(invalid) - float(switched) * self.config["reward"]["switch_weight"]
        info = {"step": self.sim_step, "requested_action": requested, "selected_action": self.phase, "phase": self.phase, "green_age": self.green_age, "switched": int(switched), "forced_switch": int(forced), "queue_total": sum(q.values()), "collisions": self.collisions, "teleports": self.teleports, **{f"queue_{d}": v for d, v in q.items()}}
        return self._observation(), reward, False, self.sim_step >= sim["duration_seconds"], info

    def baseline_action(self, policy):
        if policy == "yield":
            if self.layout != "roundabout":
                raise ValueError("The yield baseline is only available for roundabouts.")
            self.unmetered = True
            self._lights("G")
            return self.phase
        if policy == "fixed":
            if self.green_age < self.config["simulation"]["fixed_green"]:
                return self.phase
            return DIRECTIONS.index(self.active[(self.active.index(DIRECTIONS[self.phase]) + 1) % len(self.active)])
        if policy == "queue":
            q = self.queues()
            best = max(self.active, key=lambda d: q[d])
            return self.phase if q[best] == q[DIRECTIONS[self.phase]] else DIRECTIONS.index(best)
        raise ValueError(f"Unknown baseline: {policy}")

    def close(self):
        if self.sumo is not None:
            self.sumo.close()
            self.sumo = None


def make_env(config, *args, **kwargs):
    if config.get("layout", "intersection") == "intersection":
        from .environment import IntersectionEnv
        return IntersectionEnv(config, *args, **kwargs)
    return RoadEnv(config, *args, **kwargs)


def validate_model(model, env):
    if model is not None and (model.observation_space.shape != env.observation_space.shape or model.action_space.n != env.action_space.n):
        raise ValueError("Model space mismatch: legacy intersection models cannot control the new layouts. Train with --layout mixed first.")
