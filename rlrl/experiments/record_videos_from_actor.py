import logging
from typing import List

import gym
import numpy as np
from gym.wrappers.pixel_observation import PixelObservationWrapper
from gym.wrappers.record_video import RecordVideo  # NOQA


def record_videos_from_actor(
    env: gym.Env, actor, num_videos=1, pixel=False, dir=None, logger=logging.getLogger(__name__)
):
    if pixel:
        videos: List[np.ndarray] = []
        env = PixelObservationWrapper(env, pixels_only=False)

        for i in range(num_videos):
            video = []
            state_and_pixels = env.reset()
            video.append(state_and_pixels["pixels"].transpose(2, 0, 1))
            reward_sum = 0
            while True:
                action = actor(state_and_pixels["state"])
                state_and_pixels, reward, done, info = env.step(action)
                video.append(state_and_pixels["pixels"].transpose(2, 0, 1))
                reward_sum += reward
                if done:
                    break

            logger.info(f"Recording video {i+1}/{num_videos}, reward_sum={reward_sum}")
            videos.append(np.array(video))

        return videos
    elif isinstance(dir, str):
        raise NotImplementedError()  # TODO