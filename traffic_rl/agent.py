"""DQN construction and loading; experiment logging stays in experiments/."""


def create_model(env, settings, seed):
    import torch
    from stable_baselines3 import DQN
    torch.set_num_threads(2)
    keys = ("learning_rate", "buffer_size", "learning_starts", "batch_size", "gamma",
            "train_freq", "target_update_interval", "exploration_fraction",
            "exploration_final_eps", "device")
    return DQN("MlpPolicy", env, seed=seed, verbose=1,
               policy_kwargs={"net_arch": settings["net_arch"]},
               **{key: settings[key] for key in keys})


def load_model(path):
    import torch
    from stable_baselines3 import DQN
    torch.set_num_threads(2)
    return DQN.load(path, device="cpu")
