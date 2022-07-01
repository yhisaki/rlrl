import copy
import logging
from typing import Callable, Tuple, Union

import torch
import torch.nn.functional as F
from torch import cuda, distributions, nn
from torch.optim import Adam, Optimizer

from rl_algos.agents.agent_base import AgentBase, AttributeSavingMixin
from rl_algos.buffers import ReplayBuffer, TrainingBatch
from rl_algos.explorers import ExplorerBase, GaussianExplorer
from rl_algos.modules import ConcatStateAction, evaluating
from rl_algos.modules.distributions import DeterministicHead
from rl_algos.utils import synchronize_parameters
from rl_algos.utils.statistics import Statistics


def default_policy_fn(dim_state, dim_action, device):
    net = nn.Sequential(
        nn.Linear(dim_state, 256),
        nn.ReLU(),
        nn.Linear(256, 256),
        nn.ReLU(),
        nn.Linear(256, dim_action),
        nn.Tanh(),
        DeterministicHead(),
    ).to(device)

    opti = Adam(net.parameters(), lr=3e-4)

    return net, opti


def default_q_fn(dim_state, dim_action, device):
    net = nn.Sequential(
        ConcatStateAction(),
        nn.Linear(dim_state + dim_action, 256),
        nn.ReLU(),
        nn.Linear(256, 256),
        nn.ReLU(),
        nn.Linear(256, 1),
    ).to(device)

    opti = Adam(net.parameters(), lr=3e-4)

    return net, opti


NetworkAndOptimizerFunc = Callable[[int, int, torch.device], Tuple[nn.Module, Optimizer]]


class DDPG(AttributeSavingMixin, AgentBase):
    saved_attributes = (
        "q",
        "q_target",
        "q_optimizer",
        "policy",
        "policy_target",
        "policy_optimizer",
    )

    def __init__(
        self,
        dim_state: int,
        dim_action: int,
        q_fn: NetworkAndOptimizerFunc = default_q_fn,
        policy_fn: NetworkAndOptimizerFunc = default_policy_fn,
        tau: float = 5e-3,
        explorer: ExplorerBase = GaussianExplorer(0.1, -1, 1),
        gamma: float = 0.99,
        replay_buffer: ReplayBuffer = ReplayBuffer(10**6),
        batch_size: int = 256,
        replay_start_size: int = 25e3,
        calc_stats: bool = True,
        logger: logging.Logger = logging.getLogger(__name__),
        device: Union[str, torch.device] = torch.device("cuda:0" if cuda.is_available() else "cpu"),
    ) -> None:
        super().__init__()

        if isinstance(device, str):
            device = torch.device(device)
        self.device = device

        self.dim_state = dim_state
        self.dim_action = dim_action
        self.gamma = gamma

        self.policy, self.policy_optimizer = policy_fn(self.dim_state, self.dim_action, self.device)
        self.policy_target = copy.deepcopy(self.policy).eval().requires_grad_(False)

        self.q, self.q_optimizer = q_fn(self.dim_state, self.dim_action, self.device)
        self.q_target = copy.deepcopy(self.q).eval().requires_grad_(False)

        self.replay_buffer = replay_buffer
        self.batch_size = batch_size
        self.replay_start_size = replay_start_size
        self.explorer = explorer
        self.tau = tau

        self.num_update = 0

        self.logger = logger
        self.stats = Statistics() if calc_stats else None

    def observe(self, states, next_states, actions, rewards, terminals, resets) -> None:
        if self.training:
            for state, next_state, action, reward, terminal, reset in zip(
                states, next_states, actions, rewards, terminals, resets
            ):
                self.replay_buffer.append(
                    state=state,
                    next_state=next_state,
                    action=action,
                    reward=reward,
                    terminal=terminal,
                    reset=reset,
                )
            self.update_if_dataset_is_ready()

    def act(self, states):
        with torch.no_grad():
            states = torch.tensor(states, device=self.device)
            if self.training:
                if len(self.replay_buffer) < self.replay_start_size:
                    actions = torch.rand(len(states), self.dim_action) * 2 - 1
                else:
                    action_distribs: distributions.Distribution = self.policy(states)
                    actions: torch.Tensor = action_distribs.sample()
                    actions = self.explorer.select_action(..., lambda: actions)
            else:
                with self.policy[-1].deterministic():
                    actions = self.policy(states)

        actions = actions.detach().cpu().numpy()
        return actions

    def update_if_dataset_is_ready(self):
        assert self.training
        self.just_updated = False
        if len(self.replay_buffer) > self.replay_start_size:
            self.just_updated = True
            if self.num_update == 0:
                self.logger.info("Start Update")
            sampled = self.replay_buffer.sample(self.batch_size)
            batch = TrainingBatch(**sampled, device=self.device)
            self._update_critic(batch)
            self._update_actor(batch)
            self._sync_target_network()
            self.num_update += 1

    def _update_critic(self, batch: TrainingBatch):
        q_loss = self.compute_q_loss(batch)
        self.q_optimizer.zero_grad()
        q_loss.backward()
        self.q_optimizer.step()

    def _update_actor(self, batch: TrainingBatch):
        policy_loss = self.compute_policy_loss(batch)
        self.policy_optimizer.zero_grad()
        policy_loss.backward()
        self.policy_optimizer.step()

    def compute_q_loss(self, batch: TrainingBatch):
        with torch.no_grad(), evaluating(self.policy_target, self.q):
            next_actions: torch.Tensor = self.policy_target(batch.next_state).sample()
            next_q = self.q_target((batch.next_state, next_actions))
            q_target = batch.reward + self.gamma * batch.terminal.logical_not() * torch.flatten(
                next_q
            )
        q_pred = torch.flatten(self.q((batch.state, batch.action)))
        loss = F.mse_loss(q_pred, q_target)
        if self.stats is not None:
            self.stats("q_pred").extend(q_pred.detach().cpu().numpy())
            self.stats("q_target").extend(q_target.detach().cpu().numpy())
            self.stats("q_loss").append(loss.detach().cpu().numpy())

        return loss

    def compute_policy_loss(self, batch: TrainingBatch):
        actions = self.policy(batch.state).rsample()
        q = self.q((batch.state, actions))
        policy_loss = -torch.mean(q)
        if self.stats is not None:
            self.stats("policy_loss").append(float(policy_loss))
        return policy_loss

    def _sync_target_network(self):
        """Synchronize target network with current network."""
        synchronize_parameters(
            src=self.policy,
            dst=self.policy_target,
            method="soft",
            tau=self.tau,
        )
        synchronize_parameters(
            src=self.q,
            dst=self.q_target,
            method="soft",
            tau=self.tau,
        )