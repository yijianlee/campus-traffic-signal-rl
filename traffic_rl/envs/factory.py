"""Shared environment construction and model compatibility."""
from .roads import RoadEnv

def make_env(config, *args, **kwargs):
    if config.get("layout", "intersection") == "intersection":
        from ..envs.intersection import IntersectionEnv
        return IntersectionEnv(config, *args, **kwargs)
    return RoadEnv(config, *args, **kwargs)


def validate_model(model, env):
    if model is not None and (model.observation_space.shape != env.observation_space.shape or model.action_space.n != env.action_space.n):
        raise ValueError("Model space mismatch: legacy intersection models cannot control the new layouts. Train with --layout mixed first.")
