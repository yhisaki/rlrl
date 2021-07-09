import argparse

import wandb
import rlrl
from rlrl.agents import SacAgent
from rlrl.utils import is_state_terminal, manual_seed
from rlrl.experiments import GymInteractions
from rlrl.wrappers import make_env


def train_sac():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env_id", default="Swimmer-v2", type=str)
    parser.add_argument("--seed", default=None, type=int)
    parser.add_argument("--max_step", default=int(1e6), type=int)
    parser.add_argument("--gamma", default=0.99, type=float)
    parser.add_argument("--t_init", default=int(1e4), type=int)
    parser.add_argument("--save_video_interval", default=None, type=int)
    parser.add_argument("--save_agent", default=False, type=bool)
    args = parser.parse_args()

    run = wandb.init(project="test_example_sac")
    conf: wandb.Config = run.config

    conf.update(args)

    # fix seed
    if args.seed is not None:
        manual_seed(args.seed)

    # make environment
    env = make_env(
        args.env_id,
        args.seed,
        monitor=args.save_video_interval is not None,
        monitor_args={"interval_step": args.save_video_interval},
    )

    # make agent
    sac_agent = SacAgent.configure_agent_from_gym(env, gamma=args.gamma)

    print(sac_agent)

    # ------------------------ START INTERACTING WITH THE ENVIRONMENT ------------------------
    try:

        def random_actor(state):
            return env.action_space.sample()

        def agent_actor(state):
            return sac_agent.act(state)

        interactions = GymInteractions(env, random_actor, max_step=args.max_step)
        for step, state, next_state, action, reward, done in interactions:
            terminal = is_state_terminal(env, step, done)
            sac_agent.observe(state, next_state, action, reward, terminal)

            if interactions.total_step == args.t_init:
                interactions.actor = agent_actor  # finish sampling and change actor

            if interactions.actor is agent_actor:
                sac_agent.update()

            if done:

                if interactions.actor is random_actor:
                    log_data = {"reward_sum": interactions.reward_sum}
                elif interactions.actor is agent_actor:
                    log_data = {
                        "evaluation/reward_sum": interactions.reward_sum,
                        "loss/q1": sac_agent.q1_loss,
                        "loss/q2": sac_agent.q2_loss,
                        "loss/policy": sac_agent.policy_loss,
                        "loss/temperature": sac_agent.temperature_loss,
                    }

                if isinstance(env, rlrl.wrappers.NumpyArrayMonitor) and not env.is_frames_empty():
                    log_data.update({"video": wandb.Video(env.frames, fps=60, format="mp4")})
                    print("save video")
                print(f"Epi : {interactions.total_step}, Reward Sum : {interactions.reward_sum}")
                wandb.log(log_data, step=interactions.total_step)

    finally:
        if args.save_agent:
            sac_agent.save(wandb.run.dir + "/agent")


if __name__ == "__main__":
    # nohup python3 -u rlrl/example/agents/example_sac.py --env_id "Swimmer-v2" --save_video_interval 5000 --seed 0 --gamma 0.997 --save_agent True &  # noqa: E501
    train_sac()
