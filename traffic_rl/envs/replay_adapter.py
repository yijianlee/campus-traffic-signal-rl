"""Normalize observation metadata and snapshots without changing either environment."""


class ReplayAdapter:
    def __init__(self, env, layout, controlled):
        self.env = env
        self.core = env.unwrapped
        self.layout = layout
        self.controlled = controlled
        self.lane_ids = set(self.core.sumo.lane.getIDList())

    def light_state(self):
        if self.layout != "intersection":
            return self.core.light_state()
        state = self.core.sumo.trafficlight.getRedYellowGreenState("J")
        return "".join(state[self.controlled[d]] for d in "NSEW")

    @property
    def observation_labels(self):
        if self.layout == "intersection":
            lanes = list(self.env.signal.lanes)
            return (["南北相位", "东西相位", "满足最小相位时长"]
                    + [f"{lane} 密度" for lane in lanes]
                    + [f"{lane} 排队比例" for lane in lanes]
                    + ["绿灯年龄比例", "回合进度"])
        return ([f"{d} {label}" for label in ("进口存在", "排队比例", "密度", "放行相位") for d in "NSEW"]
                + ["绿灯年龄比例", "回合进度", "环内密度", "十字路口", "丁字路口", "环岛"])

    def snapshot(self):
        lane = self.core.sumo.lane
        density = {}
        for direction in "NSEW":
            lane_id = f"{direction}_in_0"
            density[direction] = (round(lane.getLastStepVehicleNumber(lane_id)
                                       / max(1, lane.getLength(lane_id) / 7.5), 4)
                                  if lane_id in self.lane_ids else None)
        return {"queue": self.env.queues(), "greenAge": float(self.env.green_age),
                "light": self.light_state(), "density": density}
