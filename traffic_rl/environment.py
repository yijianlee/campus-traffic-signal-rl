"""SUMO-RL wrapper: seeded demand, bounded greens and auditable rewards."""
from __future__ import annotations

import os
from pathlib import Path

import gymnasium as gym
import numpy as np

from .runtime import ROOT, configure_sumo
from .scenario import DIRECTIONS, network, routes

configure_sumo()
from sumo_rl import SumoEnvironment  # noqa: E402


class SmoothSumoEnvironment(SumoEnvironment):
    """Preserve SUMO-RL's one-second signal clock with subsecond vehicle motion."""

    def __init__(self, *, step_length: float, **kwargs):
        self.motion_steps_per_second = round(1 / step_length)
        super().__init__(**kwargs)

    def _sumo_step(self):
        # SUMO-RL calls TrafficSignal.update() once after this method and that
        # method increments its clock by one SECOND, not one physics step.
        if self.use_gui:
            for _ in range(self.motion_steps_per_second):
                self.sumo.simulationStep()
        else:
            # Batch the same physics steps in SUMO, avoiding extra socket calls.
            self.sumo.simulationStep(self.sim_step + 1)


class IntersectionEnv(gym.Wrapper):
    def __init__(self, config: dict, scenario: str, seed: int, *, vary_demand: bool = False, gui: bool = False, gui_delay: int = 100, tripinfo: Path | None = None):
        self.config = config
        self.scenario = scenario
        self.base_seed = seed
        self.vary_demand = vary_demand
        self.episode_index = 0
        self.switches = 0
        self.forced_switches = 0
        sim = config["simulation"]
        net = network(config)
        route, self.planned_vehicles = routes(config, scenario, seed)
        # SUMO-RL 1.4.5 splits additional_sumo_cmd on spaces. Paths below are
        # relative to ROOT and internally generated, with no whitespace.
        extra = "--no-step-log true --duration-log.disable true --xml-validation never"
        step_length = sim.get("step_length", 0.1)
        extra += f" --step-length {step_length}"
        if gui_delay < 0:
            raise ValueError("gui_delay must be nonnegative (milliseconds per simulation second).")
        if gui:
            # Keep CLI units in ms per simulated second as before. SUMO's
            # delay option itself applies to each physics/rendering step.
            extra += f" --delay {gui_delay * step_length:g}"
        if tripinfo:
            tripinfo.parent.mkdir(parents=True, exist_ok=True)
            relative = tripinfo.resolve().relative_to(ROOT).as_posix()
            if any(c.isspace() for c in relative):
                raise ValueError("Output directory names must not contain whitespace.")
            extra += f" --tripinfo-output {relative} --tripinfo-output.write-unfinished true"
        # The CLI also changes to ROOT. Keep the same contract for direct use.
        os.chdir(ROOT)
        env = SmoothSumoEnvironment(
            step_length=step_length,
            net_file=net.relative_to(ROOT).as_posix(),
            route_file=route.relative_to(ROOT).as_posix(),
            single_agent=True, use_gui=gui, num_seconds=sim["duration_seconds"],
            delta_time=sim["delta_time"], yellow_time=sim["yellow_time"],
            min_green=sim["min_green"], max_green=sim["max_green"],
            sumo_seed=seed, time_to_teleport=-1, max_depart_delay=-1,
            reward_fn="queue", additional_sumo_cmd=extra,
        )
        super().__init__(env)
        # Default SUMO-RL observation + green age + elapsed episode fraction.
        self.observation_space = gym.spaces.Box(0.0, 1.0, shape=(env.observation_space.shape[0] + 2,), dtype=np.float32)

    @property
    def signal(self):
        return self.env.traffic_signals["J"]

    @property
    def green_age(self) -> float:
        # First phase begins green at t=0; later phases follow a yellow.
        yellow = self.config["simulation"]["yellow_time"] if self.switches else 0
        return max(0.0, self.signal.time_since_last_phase_change - yellow)

    def queues(self) -> dict[str, int]:
        return {direction: self.env.sumo.lane.getLastStepHaltingNumber(f"{direction}_in_0") for direction in DIRECTIONS}

    def _observation(self, observation):
        sim = self.config["simulation"]
        return np.concatenate([observation, [min(1.0, self.green_age / sim["max_green"]), min(1.0, self.env.sim_step / sim["duration_seconds"])]]).astype(np.float32)

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self.base_seed = int(seed)
            self.episode_index = 0
        # Training gets a separate seed namespace from held-out evaluation.
        episode_seed = 100000 + self.base_seed * 1000 + self.episode_index if self.vary_demand else self.base_seed
        route, self.planned_vehicles = routes(self.config, self.scenario, episode_seed)
        self.env._route = route.relative_to(ROOT).as_posix()
        self.switches = self.forced_switches = 0
        observation, info = self.env.reset(seed=episode_seed)
        self.episode_index += 1
        info["demand_seed"] = episode_seed
        return self._observation(observation), info

    def step(self, action):
        requested = int(action)
        if not self.action_space.contains(requested):
            raise ValueError(f"Invalid phase: {action}")
        sim = self.config["simulation"]
        previous = self.signal.green_phase
        executed = requested
        forced = False
        # SUMO-RL 1.4.5 stores max_green but does not enforce it. Switch before
        # the next decision interval would exceed the upper bound.
        if self.green_age + sim["delta_time"] > sim["max_green"]:
            executed = 1 - previous
            forced = requested == previous
        observation, _, terminated, truncated, info = self.env.step(executed)
        switched = self.signal.green_phase != previous
        self.switches += int(switched)
        self.forced_switches += int(forced and switched)
        queue = self.queues()
        weights = self.config["reward"]
        imbalance = abs(queue["N"] + queue["S"] - queue["E"] - queue["W"])
        reward = -(weights["queue_weight"] * sum(queue.values()) + weights["imbalance_weight"] * imbalance + weights["switch_weight"] * int(switched))
        info.update({"requested_action": requested, "selected_action": executed, "phase": self.signal.green_phase, "switched": switched, "forced_switch": forced and switched, "switches": self.switches, "queue_total": sum(queue.values()), "green_age": self.green_age})
        info.update({f"queue_{key}": value for key, value in queue.items()})
        return self._observation(observation), float(reward), terminated, truncated, info

    def baseline_action(self, policy: str) -> int:
        phase = self.signal.green_phase
        if policy == "fixed":
            return 1 - phase if self.green_age >= self.config["simulation"]["fixed_green"] else phase
        if policy == "queue":
            queue = self.queues()
            scores = [queue["N"] + queue["S"], queue["E"] + queue["W"]]
            return 1 - phase if scores[1 - phase] > scores[phase] else phase
        raise ValueError(f"Unknown baseline: {policy}")
