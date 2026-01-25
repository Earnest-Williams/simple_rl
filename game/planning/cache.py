from __future__ import annotations

from functools import lru_cache


def compute_goap_plan(agent_sig: tuple[int, ...], world_sig: tuple[int, ...]) -> object:
    raise NotImplementedError("compute_goap_plan must be implemented by the caller")


@lru_cache(maxsize=1024)
def cached_goap_plan(agent_sig: tuple[int, ...], world_sig: tuple[int, ...]) -> object:
    return compute_goap_plan(agent_sig, world_sig)
