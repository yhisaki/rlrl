import torch
import torch.nn as nn
from torch import distributions
from rlrl.utils.env_info import EnvInfo


class GaussianPolicy(nn.Module):
  def __init__(self, env_info: EnvInfo, hidden_dim: int):

    super(GaussianPolicy, self).__init__()

    self._dim_state = env_info.dim_state
    self._dim_action = env_info.dim_action

    action_bias = torch.from_numpy(env_info.action_high + env_info.action_low) / 2
    action_scale = torch.from_numpy(env_info.action_high - env_info.action_low) / 2

    self.register_buffer('_action_bias', action_bias)
    self.register_buffer('_action_scale', action_scale)

    self._layer = nn.Sequential(
        nn.Linear(self._dim_state, hidden_dim),
        nn.ReLU(),
        nn.Linear(hidden_dim, self._dim_action * 2),
        nn.Tanh(),
    )
    self._layer[2].weight.detach().mul_(1e-1)

  def forward(self, state):
    x = self._layer(state)
    mean, log_scale = torch.chunk(x, 2, dim=x.dim()//2)
    log_scale = torch.clamp(log_scale, -20.0, 2.0)
    var = torch.exp(log_scale * 2)
    base_distribution = distributions.Independent(
        distributions.Normal(loc=mean, scale=torch.sqrt(var)), 1
    )
    # https://pytorch.org/docs/stable/distributions.html#torch.distributions.transformed_distribution.TransformedDistribution
    return distributions.transformed_distribution.TransformedDistribution(
        base_distribution,
        [distributions.transforms.TanhTransform(cache_size=1),
         distributions.transforms.AffineTransform(loc=self._action_bias, scale=self._action_scale)]
    )
