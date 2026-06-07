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
    lines.append(f'shape = "{config.shape}"')
    lines.append(f"direction = {config.direction:.2f}")
    lines.append(f"cone_angle = {config.cone_angle:.2f}")
    lines.append(f"beam_width = {config.beam_width:.2f}")
    lines.append(f"beam_length = {config.beam_length}")
    lines.append(f"softness = {config.softness:.2f}")
    lines.append(f"ambient_spill_enabled = {config.ambient_spill_enabled}")
    lines.append(f"ambient_spill_extra_radius = {config.ambient_spill_extra_radius}")
    lines.append(f"ambient_spill_strength = {config.ambient_spill_strength:.2f}")
    lines.append(f"ambient_spill_decay = {config.ambient_spill_decay:.2f}")
    lines.append(f"ambient_spill_max_rgb = {config.ambient_spill_max_rgb:.1f}")

    if is_changed and original is not None:
        # Add original values as comments
        original_parts: list[str] = []
        if config.color != original.color:
            original_parts.append(f"color = {_format_color(original.color)}")
        if config.radius != original.radius:
            original_parts.append(f"radius = {original.radius}")
        if abs(config.intensity - original.intensity) > 0.001:
            original_parts.append(f"intensity = {original.intensity:.2f}")
        if config.shape != original.shape:
            original_parts.append(f'shape = "{original.shape}"')
        if abs(config.direction - original.direction) > 0.001:
            original_parts.append(f"direction = {original.direction:.2f}")
        if abs(config.cone_angle - original.cone_angle) > 0.001:
            original_parts.append(f"cone_angle = {original.cone_angle:.2f}")
        if abs(config.beam_width - original.beam_width) > 0.001:
            original_parts.append(f"beam_width = {original.beam_width:.2f}")
        if config.beam_length != original.beam_length:
            original_parts.append(f"beam_length = {original.beam_length}")
        if abs(config.softness - original.softness) > 0.001:
            original_parts.append(f"softness = {original.softness:.2f}")
        if config.ambient_spill_enabled != original.ambient_spill_enabled:
            original_parts.append(
                f"ambient_spill_enabled = {original.ambient_spill_enabled}"
            )
        if config.ambient_spill_extra_radius != original.ambient_spill_extra_radius:
            original_parts.append(
                f"ambient_spill_extra_radius = {original.ambient_spill_extra_radius}"
            )
        if abs(config.ambient_spill_strength - original.ambient_spill_strength) > 0.001:
            original_parts.append(
                f"ambient_spill_strength = {original.ambient_spill_strength:.2f}"
            )
        if abs(config.ambient_spill_decay - original.ambient_spill_decay) > 0.001:
            original_parts.append(
                f"ambient_spill_decay = {original.ambient_spill_decay:.2f}"
            )
        if abs(config.ambient_spill_max_rgb - original.ambient_spill_max_rgb) > 0.001:
            original_parts.append(
                f"ambient_spill_max_rgb = {original.ambient_spill_max_rgb:.1f}"
            )
        if original_parts:
            lines.append(f"# original: {', '.join(original_parts)}")
    else:
        lines.append("# (unchanged)")

    lines.append("")
    return lines


def _format_tool_render_section(config_state: TileConfigState) -> list[str]:
    """Format tool-only render controls."""
    return [
        "[tool.render]",
        f"ambient_spill_enabled = {config_state.ambient_spill_enabled}",
        (
            "ambient_spill_debug_show_only = "
            f"{config_state.ambient_spill_debug_show_only}"
        ),
        "",
    ]


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

    lines.append("# ===========")
    lines.append("# TOOL RENDER")
    lines.append("# ===========")
    lines.append("")
    lines.extend(_format_tool_render_section(config_state))

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


def load_configuration(config_state: TileConfigState, path: Path) -> None:
    """Load configuration from a text file.

    Args:
        config_state: The configuration state to update.
        path: Path to the configuration file.
    """
    import ast

    if not path.exists():
        return

    def parse_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    current_section = None
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Remove inline comments if present
            if "#" in line:
                line = line.split("#")[0].strip()

            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].strip()
                continue

            if "=" in line:
                key, val_str = line.split("=", 1)
                key = key.strip()
                val_str = val_str.strip()
                try:
                    val = ast.literal_eval(val_str)
                except Exception:
                    val = val_str

                if not current_section:
                    continue

                if current_section == "tool.render":
                    if key == "ambient_spill_enabled":
                        config_state.ambient_spill_enabled = parse_bool(val)
                    elif key == "ambient_spill_debug_show_only":
                        config_state.ambient_spill_debug_show_only = parse_bool(val)
                elif current_section.startswith("light."):
                    light_name = current_section[len("light.") :]
                    if light_name not in config_state.lights:
                        # Create LightConfig if not present
                        config_state.lights[light_name] = LightConfig(
                            color=(255, 255, 255),
                            radius=5,
                            intensity=1.0,
                        )
                    light_cfg = config_state.lights[light_name]
                    if key == "color":
                        light_cfg.color = val
                    elif key == "radius":
                        light_cfg.radius = int(val)
                    elif key == "intensity":
                        light_cfg.intensity = float(val)
                    elif key == "shape":
                        light_cfg.shape = str(val)
                    elif key == "direction":
                        light_cfg.direction = float(val)
                    elif key == "cone_angle":
                        light_cfg.cone_angle = float(val)
                    elif key == "beam_width":
                        light_cfg.beam_width = float(val)
                    elif key == "beam_length":
                        light_cfg.beam_length = int(val)
                    elif key == "softness":
                        light_cfg.softness = float(val)
                    elif key == "ambient_spill_enabled":
                        light_cfg.ambient_spill_enabled = parse_bool(val)
                    elif key == "ambient_spill_extra_radius":
                        light_cfg.ambient_spill_extra_radius = int(val)
                    elif key == "ambient_spill_strength":
                        light_cfg.ambient_spill_strength = float(val)
                    elif key == "ambient_spill_decay":
                        light_cfg.ambient_spill_decay = float(val)
                    elif key == "ambient_spill_max_rgb":
                        light_cfg.ambient_spill_max_rgb = float(val)
                else:
                    # Match ElementType
                    for et in ElementType:
                        name = get_element_name(et).lower().replace(" ", "_")
                        if name == current_section:
                            element_config = config_state.elements[et]
                            if key == "tile":
                                element_config.tile_name = str(val)
                            elif key == "tile_id":
                                element_config.tile_id = int(val)
                            elif key == "fg_color":
                                element_config.fg_color = val
                            elif key == "bg_color":
                                element_config.bg_color = val
                            break
