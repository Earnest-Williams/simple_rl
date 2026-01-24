"""Cross-training system for related skill bonuses.

Uses scipy sparse matrices for O(nnz) XP distribution.
Based on DCSS weapon cross-training mechanics.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import scipy.sparse  # type: ignore[import-untyped]

from skills.models import (
    CROSS_TRAINING_PAIRS,
    SKILL_COUNT,
    Skill,
)


def build_cross_training_matrix() -> scipy.sparse.csr_matrix:
    """Build cross-training adjacency matrix.

    Uses COO format for construction, then converts to CSR for fast row slicing.
    CSR enables O(nnz_row) lookup of all skills that receive XP from a primary skill.

    Returns:
        Sparse matrix where M[i, j] = multiplier for training skill i giving XP to j
    """
    row_indices: list[int] = []
    col_indices: list[int] = []
    data: list[float] = []

    for pair in CROSS_TRAINING_PAIRS:
        row_indices.append(pair.from_skill.value)
        col_indices.append(pair.to_skill.value)
        data.append(pair.multiplier)

    coo: scipy.sparse.coo_matrix = scipy.sparse.coo_matrix(
        (data, (row_indices, col_indices)),
        shape=(SKILL_COUNT, SKILL_COUNT),
        dtype=np.float32,
    )

    return coo.tocsr()


# Global cross-training matrix (immutable after initialization)
CROSS_TRAINING_MATRIX: Final[scipy.sparse.csr_matrix] = build_cross_training_matrix()


def get_cross_trained_skills(primary_skill: Skill) -> dict[Skill, float]:
    """Get all skills that receive cross-training from primary skill.

    Args:
        primary_skill: Skill being directly trained

    Returns:
        Mapping of related skills to their XP multipliers
    """
    row: scipy.sparse.csr_matrix = CROSS_TRAINING_MATRIX[primary_skill.value, :]

    # Extract non-zero elements
    related_indices: np.ndarray = row.indices
    multipliers: np.ndarray = row.data

    result: dict[Skill, float] = {}

    for i in range(len(related_indices)):
        skill_idx: int = int(related_indices[i])
        mult: float = float(multipliers[i])
        result[Skill(skill_idx)] = mult

    return result


def calculate_cross_training_xp(
    primary_skill: Skill,
    primary_xp_gained: int,
) -> dict[Skill, int]:
    """Calculate XP bonuses for related skills.

    Args:
        primary_skill: Skill that directly received XP
        primary_xp_gained: Amount of XP gained in primary skill

    Returns:
        Mapping of related skills to cross-training XP amounts
    """
    related: dict[Skill, float] = get_cross_trained_skills(primary_skill)
    cross_xp: dict[Skill, int] = {}

    for skill, multiplier in related.items():
        bonus_xp: int = int(primary_xp_gained * multiplier)
        if bonus_xp > 0:
            cross_xp[skill] = bonus_xp

    return cross_xp


def batch_calculate_cross_training(
    primary_skills: np.ndarray,
    xp_amounts: np.ndarray,
) -> dict[Skill, int]:
    """Calculate cross-training XP for multiple skill gains.

    Aggregates all cross-training bonuses across multiple primary skills.

    Args:
        primary_skills: Array of Skill enum values, shape (N,)
        xp_amounts: Array of XP amounts, shape (N,)

    Returns:
        Aggregated cross-training XP per skill
    """
    aggregated: dict[Skill, int] = {}

    for i in range(len(primary_skills)):
        skill_value: int = int(primary_skills[i])
        xp_gained: int = int(xp_amounts[i])

        skill: Skill = Skill(skill_value)
        cross_xp: dict[Skill, int] = calculate_cross_training_xp(skill, xp_gained)

        for related_skill, bonus_xp in cross_xp.items():
            if related_skill in aggregated:
                aggregated[related_skill] += bonus_xp
            else:
                aggregated[related_skill] = bonus_xp

    return aggregated


def get_bidirectional_relationships() -> set[tuple[Skill, Skill]]:
    """Find all bidirectional cross-training pairs.

    Returns:
        Set of (skill_a, skill_b) tuples where both train each other
    """
    pairs: set[tuple[Skill, Skill]] = set()

    for pair in CROSS_TRAINING_PAIRS:
        # Check if reverse relationship exists
        reverse_mult: float = CROSS_TRAINING_MATRIX[
            pair.to_skill.value, pair.from_skill.value
        ]

        if reverse_mult > 0.0:
            # Normalize ordering (lower enum value first)
            skills: tuple[Skill, Skill] = (
                (pair.from_skill, pair.to_skill)
                if pair.from_skill.value < pair.to_skill.value
                else (pair.to_skill, pair.from_skill)
            )
            pairs.add(skills)

    return pairs


def format_cross_training_info() -> str:
    """Generate human-readable cross-training table.

    Returns:
        Formatted string showing all relationships
    """
    lines: list[str] = ["Cross-Training Relationships:", ""]

    # Group by primary skill
    for skill in Skill:
        related: dict[Skill, float] = get_cross_trained_skills(skill)

        if not related:
            continue

        lines.append(f"{skill.name}:")
        for related_skill, mult in sorted(
            related.items(), key=lambda x: x[1], reverse=True
        ):
            pct: float = mult * 100.0
            lines.append(f"  → {related_skill.name} ({pct:.0f}%)")
        lines.append("")

    return "\n".join(lines)


def get_synergistic_skill_groups() -> list[set[Skill]]:
    """Identify groups of skills with mutual cross-training.

    Uses simple connected components analysis.

    Returns:
        List of skill sets where all skills cross-train with each other
    """
    # Build adjacency list (undirected)
    adjacency: dict[Skill, set[Skill]] = {skill: set() for skill in Skill}

    for pair in CROSS_TRAINING_PAIRS:
        adjacency[pair.from_skill].add(pair.to_skill)
        adjacency[pair.to_skill].add(pair.from_skill)

    # Find connected components
    visited: set[Skill] = set()
    components: list[set[Skill]] = []

    for skill in Skill:
        if skill in visited:
            continue

        # BFS to find component
        component: set[Skill] = set()
        queue: list[Skill] = [skill]

        while queue:
            current: Skill = queue.pop(0)

            if current in visited:
                continue

            visited.add(current)
            component.add(current)

            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    queue.append(neighbor)

        if len(component) > 1:
            components.append(component)

    return components


def calculate_effective_training_rate(
    skill: Skill,
    related_skill_usage: dict[Skill, float],
) -> float:
    """Calculate effective training rate considering cross-training.

    Args:
        skill: Target skill
        related_skill_usage: Mapping of other skills to usage percentages (0.0-1.0)

    Returns:
        Effective training rate multiplier (1.0 = no cross-training bonus)
    """
    # Direct training
    base_rate: float = related_skill_usage.get(skill, 0.0)

    # Cross-training contributions
    cross_rate: float = 0.0

    for other_skill, usage_pct in related_skill_usage.items():
        if other_skill == skill:
            continue

        # Check if other_skill cross-trains this skill
        multiplier: float = CROSS_TRAINING_MATRIX[other_skill.value, skill.value]

        if multiplier > 0.0:
            cross_rate += usage_pct * multiplier

    return base_rate + cross_rate


def suggest_optimal_weapon_skill(
    current_skills: dict[Skill, int],
) -> Skill | None:
    """Suggest weapon skill to train based on current levels and cross-training.

    Args:
        current_skills: Current skill levels

    Returns:
        Recommended weapon skill, or None if no good option
    """
    weapon_skills: list[Skill] = [
        Skill.AXES,
        Skill.MACES_AND_FLAILS,
        Skill.POLEARMS,
        Skill.STAVES,
        Skill.LONG_BLADES,
        Skill.SHORT_BLADES,
    ]

    best_skill: Skill | None = None
    best_score: float = -1.0

    for skill in weapon_skills:
        # Score = current level + cross-training bonuses from other weapons
        score: float = float(current_skills.get(skill, 0))

        for other_skill in weapon_skills:
            if other_skill == skill:
                continue

            other_level: int = current_skills.get(other_skill, 0)
            multiplier: float = CROSS_TRAINING_MATRIX[other_skill.value, skill.value]

            score += other_level * multiplier

        if score > best_score:
            best_score = score
            best_skill = skill

    return best_skill
