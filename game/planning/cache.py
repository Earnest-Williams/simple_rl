from __future__ import annotations

from functools import lru_cache
from typing import Any, Tuple


def compute_goap_plan(
    agent_sig: Tuple[int, ...], world_sig: Tuple[int, ...]
) -> object:
    raise NotImplementedError("compute_goap_plan must be implemented by the caller")


@lru_cache(maxsize=1024)
def cached_goap_plan(
    agent_sig: Tuple[int, ...], world_sig: Tuple[int, ...]
) -> Any:
    return compute_goap_plan(agent_sig, world_sig)
