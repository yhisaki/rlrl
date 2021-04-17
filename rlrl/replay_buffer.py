"""ReplayBufferの抽象クラス．
  [pfrl.replay_buffer.AbstractReplayBuffer]
  (https://github.com/pfnet/pfrl/blob/0639d2f4d0317a01e85978fa5c0c60a04f0cff33/pfrl/replay_buffer.py#L15)
  をトレースしている

"""
from abc import ABCMeta, abstractmethod
from typing import Optional


class AbstractReplayBuffer(object, metaclass=ABCMeta):
  """Defines a common interface of replay buffer.
  You can append transitions to the replay buffer and later sample from it.
  Replay buffers are typically used in experience replay.
  """

  @abstractmethod
  def append(
      self,
      state,
      action,
      reward,
      next_state=None,
      next_action=None,
      is_state_terminal=False,
      env_id=0,
      **kwargs
  ):
    """Append a transition to this replay buffer.
    Args:
        state: s_t
        action: a_t
        reward: r_t
        next_state: s_{t+1} (can be None if terminal)
        next_action: a_{t+1} (can be None for off-policy algorithms)
        is_state_terminal (bool)
        env_id (object): Object that is unique to each env. It indicates
            which env a given transition came from in multi-env training.
        **kwargs: Any other information to store.
    """
    raise NotImplementedError

  @abstractmethod
  def sample(self, n):
    """Sample n unique transitions from this replay buffer.
    Args:
        n (int): Number of transitions to sample.
    Returns:
        Sequence of n sampled transitions.
    """
    raise NotImplementedError

  @abstractmethod
  def __len__(self):
    """Return the number of transitions in the buffer.
    Returns:
        Number of transitions in the buffer.
    """
    raise NotImplementedError

  @abstractmethod
  def save(self, filename):
    """Save the content of the buffer to a file.
    Args:
        filename (str): Path to a file.
    """
    raise NotImplementedError

  @abstractmethod
  def load(self, filename):
    """Load the content of the buffer from a file.
    Args:
        filename (str): Path to a file.
    """
    raise NotImplementedError

  @property
  @abstractmethod
  def capacity(self) -> Optional[int]:
    """Returns the capacity of the buffer in number of transitions.
    If unbounded, returns None instead.
    """
    raise NotImplementedError

  @abstractmethod
  def stop_current_episode(self, env_id=0):
    """Notify the buffer that the current episode is interrupted.
    You may want to interrupt the current episode and start a new one
    before observing a terminal state. This is typical in continuing envs.
    In such cases, you need to call this method before appending a new
    transition so that the buffer will treat it as an initial transition of
    a new episode.
    This method should not be called after an episode whose termination is
    already notified by appending a transition with is_state_terminal=True.
    Args:
        env_id (object): Object that is unique to each env. It indicates
            which env's current episode is interrupted in multi-env
            training.
    """
    raise NotImplementedError
