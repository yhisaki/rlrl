import gym
import numpy as np
from gym.vector import VectorEnv
from typing import List, Optional, Union


class SingleAsVectorEnv(VectorEnv):
    def __init__(self, env: gym.Env) -> None:
        self.env = env
        super().__init__(1, env.observation_space, env.action_space)

    def seed(self, seeds=None):
        if isinstance(seeds, list):
            self.env.seed(seeds[0])
        else:
            self.env.seed(seeds)

    def step_async(self, actions) -> None:
        self._action = actions

    def step_wait(self, **kwargs):
        observation, reward, done, info = self.env.step(self._action[0])
        if done:
            info["terminal_observation"] = observation
            observation = self.env.reset()
        return np.array([observation]), np.array([reward]), np.array([done]), [info]

    def reset_wait(self, seed: Optional[Union[int, List[int]]] = None, **kwargs):
        observation = self.env.reset(seed=seed, **kwargs)
        return np.array([observation])

    def close_extras(self, **kwargs):
        self.env.close()
