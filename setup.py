#!/usr/bin/env python
from setuptools import setup

setup(
    name="rlrl",
    version="1.0.0",
    install_requires=[
        "torch",
        "gym@git+https://github.com/openai/gym.git",
        "numpy",
    ],
    extras_require={
        "dev": [
            "wandb",
            "black",
            "flake8",
            "isort",
            "moviepy",
            "imageio",
        ]
    },
    description="Library for RL research",
    author="hisaki",
    packages=["rlrl"],
)
