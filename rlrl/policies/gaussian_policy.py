from typing import overload
import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Normal

from rlrl.utils.global_device import get_global_torch_device
from rlrl.utils.env_info import EnvInfo


class GaussianPolicy(nn.Module):
  def __init__(self, env_info: EnvInfo, hidden_dim: int, log_std_bounds=(2, -20)):
    super(GaussianPolicy, self).__init__()

    device = get_global_torch_device()
    self.dev_ = device
    self.dim_state_ = env_info.dim_state
    self.dim_action_ = env_info.dim_action
    self.action_high = env_info.action_high
    self.action_low = env_info.action_low

    # 方策のエントロピーが大きくなりすぎたり小さくなりすぎるのを防ぐために範囲を指定
    self.log_std_max, self.log_std_min = log_std_bounds

    # actionをaction_high > a > action_lowにおさめるため
    self.action_bias_ = torch.FloatTensor(
        (self.action_high + self.action_low) / 2.0).to(device)
    self.action_scale_ = torch.FloatTensor(
        (self.action_high - self.action_low) / 2.0).to(device)

    # 方策に関するニューラルネットワーク
    shared_layers = [
        nn.Linear(self.dim_state_, hidden_dim),
        nn.ReLU(),
        nn.Linear(hidden_dim, hidden_dim),
        nn.ReLU()
    ]
    self.shared_layers_ = nn.Sequential(*shared_layers)
    self.mean_layer_ = nn.Linear(hidden_dim, self.dim_action_)
    self.log_std_layer_ = nn.Linear(hidden_dim, self.dim_action_)

  def forward(self, state):
    out = self.shared_layers_(state)
    loc = self.mean_layer_(out)
    log_std = self.log_std_layer_(out)
    log_std = log_std.clamp(min=self.log_std_min, max=self.log_std_max)
    return loc, log_std

  def sample_action(self, state, action_type=np.ndarray):
    if isinstance(state, np.ndarray) & (action_type == np.ndarray):
      # 純粋に行動をサンプルするとき．勾配などは不要
      with torch.no_grad():
        state = torch.FloatTensor(np.asmatrix(state)).to(self.dev_)
        mean, log_std = self.forward(state)
        std = log_std.exp()  # 0 < std
        normal = Normal(mean, std)
        _u = normal.rsample()
        _action = torch.tanh(_u)
        action = _action * self.action_scale_ + self.action_bias_
        action = action[0].detach().to('cpu').numpy()
    return action

  def sample(self, state, **kwargs):
    """a~πΦ(・|s)となる確率変数aをサンプルしその対数尤度logπΦ(a|s)をもとめる．戻り値は微分可能

    Args:
        state ([type]): 状態量

    Returns:
        action, log_prob [type]: [description]
    """

    state = state.to(self.dev_)
    mean, log_std = self.forward(state)
    std = log_std.exp()  # 0 < std
    normal = Normal(mean, std)
    _u = normal.rsample()  # noise, for reparameterization trick (mean + std * N(0,1))
    _action = torch.tanh(_u)  # -1 < _action < 1, スケーリング前
    # action_low < action < action_high
    action = _action * self.action_scale_ + self.action_bias_

    # actionの対数尤度をもとめる
    # tanhとかscale, biasで補正した分normal.log_prob(u)だけでは求まらない
    log_prob = normal.log_prob(_u).sum(dim=1)
    log_prob -= 2 * \
        (self.action_scale_ * (np.log(2) - _u
                               - F.softplus(-2 * _u))).sum(dim=1)

    return action, log_prob

  # @overload
  # def sample(self, state, another_actions):
  #   """a~πΦ(・|s)となる確率変数aをサンプルしその対数尤度logπΦ(a|s)をもとめる．戻り値は微分可能

  #   Args:
  #       state ([type]): 状態量

  #   Returns:
  #       action, log_prob [type]: [description]
  #   """
  #   change_numpy_and_1d = False
  #   if isinstance(state, np.ndarray) and (state.ndim == 1):
  #     change_numpy_and_1d = True
  #     state = torch.Tensor([state])

  #   state = state.to(self.dev_)
  #   mean, log_std = self.forward(state)
  #   std = log_std.exp()  # 0 < std
  #   normal = Normal(mean, std)
  #   _u = normal.rsample()  # noise, for reparameterization trick (mean + std * N(0,1))
  #   _action = torch.tanh(_u)  # -1 < _action < 1, スケーリング前
  #   # action_low < action < action_high
  #   action = _action * self.action_scale_ + self.action_bias_

  #   # actionの対数尤度をもとめる
  #   # tanhとかscale, biasで補正した分normal.log_prob(u)だけでは求まらない
  #   my_log_prob = normal.log_prob(_u).sum(dim=1)
  #   my_log_prob -= 2 * \
  #       (self.action_scale_ * (np.log(2) - _u
  #                              - F.softplus(-2 * _u))).sum(dim=1)

  #   if change_numpy_and_1d:
  #     action = action[0].detach()
  #     my_log_prob = my_log_prob[0].detach()
  #   return action, my_log_prob
