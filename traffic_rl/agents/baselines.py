"""Rule policies; environment controllers still enforce timing constraints."""
from ..networks.scenario import DIRECTIONS

def intersection_action(env, policy: str) -> int:
    phase = env.signal.green_phase
    if policy == "fixed":
        return 1 - phase if env.green_age >= env.config["simulation"]["fixed_green"] else phase
    if policy == "queue":
        queue = env.queues()
        scores = [queue["N"] + queue["S"], queue["E"] + queue["W"]]
        return 1 - phase if scores[1 - phase] > scores[phase] else phase
    raise ValueError(f"Unknown baseline: {policy}")

def road_action(env, policy):
    if policy == "yield":
        if env.layout != "roundabout":
            raise ValueError("The yield baseline is only available for roundabouts.")
        env.unmetered = True
        env._lights("G")
        return env.phase
    if policy == "fixed":
        if env.green_age < env.config["simulation"]["fixed_green"]:
            return env.phase
        return DIRECTIONS.index(env.active[(env.active.index(DIRECTIONS[env.phase]) + 1) % len(env.active)])
    if policy == "queue":
        q = env.queues()
        best = max(env.active, key=lambda d: q[d])
        return env.phase if q[best] == q[DIRECTIONS[env.phase]] else DIRECTIONS.index(best)
    raise ValueError(f"Unknown baseline: {policy}")
