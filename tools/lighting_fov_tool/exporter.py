"""Configuration exporter for the lighting/FOV tool."""

from datetime import UTC, datetime
from pathlib import Path

from tools.lighting_fov_tool.scene import ElementType, get_element_name
from tools.lighting_fov_tool.tile_config import (
    ConfigSnapshot,
    ElementConfig,
    LightConfig,
    LightConfigSnapshot,
    TileConfigState,
)


def _format_color(color: tuple[int, int, int]) -> str:
    """Format a color tuple as a string."""
    return f"({color[0]}, {color[1]}, {color[2]})"


def _format_element_section(
    element_type: ElementType,
    config: ElementConfig,
    original: ConfigSnapshot | None,
    is_changed: bool,
) -> list[str]:
    """Format an element configuration section."""
    lines: list[str] = []
    section_name = get_element_name(element_type).lower().replace(" ", "_")
    lines.append(f"[{section_name}]")
    lines.append(f'tile = "{config.tile_name}"')
    lines.append(f"tile_id = {config.tile_id}")
    lines.append(f"fg_color = {_format_color(config.fg_color)}")
    lines.append(f"bg_color = {_format_color(config.bg_color)}")

    if is_changed and original is not None:
        # Add original values as comments
        original_parts: list[str] = []
        if config.tile_name != original.tile_name:
            original_parts.append(f'tile = "{original.tile_name}"')
        if config.fg_color != original.fg_color:
            original_parts.append(f"fg_color = {_format_color(original.fg_color)}")
        if config.bg_color != original.bg_color:
            original_parts.append(f"bg_color = {_format_color(original.bg_color)}")
        if original_parts:
            lines.append(f"# original: {', '.join(original_parts)}")
    else:
        lines.append("# (unchanged)")

    lines.append("")
    return lines


def _format_light_section(
    light_name: str,
    config: LightConfig,
    original: LightConfigSnapshot | None,
    is_changed: bool,
) -> list[str]:
    """Format a light configuration section."""
    lines: list[str] = []
    lines.append(f"[light.{light_name}]")
    lines.append(f"color = {_format_color(config.color)}")
    lines.append(f"radius = {config.radius}")
    lines.append(f"intensity = {config.intensity:.2f}")

    if is_changed and original is not None:
        # Add original values as comments
        original_parts: list[str] = []
        if config.color != original.color:
            original_parts.append(f"color = {_format_color(original.color)}")
        if config.radius != original.radius:
            original_parts.append(f"radius = {original.radius}")
        if abs(config.intensity - original.intensity) > 0.001:
            original_parts.append(f"intensity = {original.intensity:.2f}")
        if original_parts:
            lines.append(f"# original: {', '.join(original_parts)}")
    else:
        lines.append("# (unchanged)")

    lines.append("")
    return lines


def export_configuration(config_state: TileConfigState, output_path: Path) -> None:
    """Export the current configuration to a text file.

    Args:
        config_state: The current configuration state.
        output_path: Path to write the configuration file.
    """
    lines: list[str] = []

    # Header
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines.append("# Lighting/FOV Tool Configuration Export")
    lines.append(f"# Generated: {timestamp}")
    lines.append("")

    # Count changes for summary
    element_changes = sum(
        1 for et in ElementType if config_state.is_element_changed(et)
    )
    light_changes = sum(
        1 for ln in config_state.lights if config_state.is_light_changed(ln)
    )
    total_elements = len(list(ElementType))
    total_lights = len(config_state.lights)

    lines.append(
        f"# Summary: {element_changes}/{total_elements} elements changed, "
        f"{light_changes}/{total_lights} lights changed"
    )
    lines.append("")

    # Elements section header
    lines.append("# =============")
    lines.append("# TILE ELEMENTS")
    lines.append("# =============")
    lines.append("")

    # Export each element type
    for element_type in ElementType:
        if element_type not in config_state.elements:
            continue
        config = config_state.elements[element_type]
        original = config_state.get_element_original(element_type)
        is_changed = config_state.is_element_changed(element_type)
        lines.extend(
            _format_element_section(element_type, config, original, is_changed)
        )

    # Lights section header
    lines.append("# =============")
    lines.append("# LIGHT SOURCES")
    lines.append("# =============")
    lines.append("")

    # Export each light source
    for light_name in sorted(config_state.lights.keys()):
        config = config_state.lights[light_name]
        original = config_state.get_light_original(light_name)
        is_changed = config_state.is_light_changed(light_name)
        lines.extend(_format_light_section(light_name, config, original, is_changed))

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def get_default_export_path() -> Path:
    """Get the default export path for configuration files."""
    return Path.cwd() / "lighting_fov_config.txt"
