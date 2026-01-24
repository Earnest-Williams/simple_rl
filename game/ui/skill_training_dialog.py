"""Interactive skill training UI for managing skill progression.

Allows players to:
- Toggle skills on/off
- Set focused training (2x XP)
- Set target levels for auto-disable
- Switch between manual and automatic training modes
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from skills.models import Skill, SkillCategory, TrainingMode, TrainingState
from skills.system import set_skill_training, set_training_mode

if TYPE_CHECKING:
    from game.entities.registry import EntityRegistry


class SkillTrainingDialog(QDialog):
    """Interactive dialog for managing skill training configuration."""

    def __init__(
        self,
        registry: EntityRegistry,
        entity_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.registry = registry
        self.entity_id = entity_id

        self.setWindowTitle("Skill Training")
        self.resize(900, 700)

        # Track UI elements for each skill
        self.skill_widgets: dict[Skill, dict[str, QWidget]] = {}

        self._setup_ui()
        self._load_current_config()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        main_layout = QVBoxLayout()

        # Header with training mode selector
        header = self._create_header()
        main_layout.addWidget(header)

        # Scrollable skill list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()

        # Get skills organized by category
        categories = [
            (SkillCategory.OFFENSIVE, "Offensive Skills"),
            (SkillCategory.DEFENSIVE, "Defensive Skills"),
            (SkillCategory.MAGIC, "Magic Skills"),
            (SkillCategory.MISCELLANEOUS, "Miscellaneous Skills"),
        ]

        skills = self.registry.get_skills(self.entity_id)

        for category, category_name in categories:
            category_skills = [
                skill for skill in Skill if self._get_skill_category(skill) == category
            ]
            category_skills = [s for s in category_skills if s in skills]

            if not category_skills:
                continue

            # Category header
            category_label = QLabel(f"--- {category_name} ---")
            category_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            scroll_layout.addWidget(category_label)

            # Add skill rows
            for skill in category_skills:
                skill_row = self._create_skill_row(skill, skills[skill])
                scroll_layout.addWidget(skill_row)

        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)

        # Footer with buttons
        footer = self._create_footer()
        main_layout.addWidget(footer)

        self.setLayout(main_layout)

    def _create_header(self) -> QWidget:
        """Create header with training mode selector."""
        header = QWidget()
        layout = QHBoxLayout()

        # Training mode label
        mode_label = QLabel("Training Mode:")
        mode_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(mode_label)

        # Training mode selector
        self.mode_selector = QComboBox()
        self.mode_selector.addItems(["Manual", "Automatic"])
        self.mode_selector.currentTextChanged.connect(self._on_mode_changed)
        layout.addWidget(self.mode_selector)

        # Info label
        info_label = QLabel(
            "Manual: Set weights explicitly  |  Automatic: Based on usage"
        )
        info_label.setStyleSheet("color: gray;")
        layout.addWidget(info_label)

        layout.addStretch()
        header.setLayout(layout)
        return header

    def _create_skill_row(self, skill: Skill, progress: any) -> QWidget:
        """Create a row for a single skill with training controls."""
        row = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)

        # Skill name
        name_label = QLabel(skill.name.replace("_", " ").title())
        name_label.setMinimumWidth(180)
        name_label.setFont(QFont("Arial", 9))
        layout.addWidget(name_label)

        # Level display
        level_label = QLabel(f"Lv {progress.level:2d}")
        level_label.setMinimumWidth(50)
        level_label.setFont(QFont("Courier", 9))
        layout.addWidget(level_label)

        # XP progress
        from skills.progression import calculate_xp_to_next_level

        if progress.level >= 27:
            xp_label = QLabel("(MAX)")
        else:
            xp_to_next = calculate_xp_to_next_level(progress.xp, progress.aptitude)
            xp_label = QLabel(f"({xp_to_next:5d} XP)")
        xp_label.setMinimumWidth(90)
        xp_label.setFont(QFont("Courier", 9))
        layout.addWidget(xp_label)

        # Enabled checkbox
        enabled_cb = QCheckBox("Enabled")
        enabled_cb.setChecked(True)
        layout.addWidget(enabled_cb)

        # Focused checkbox
        focused_cb = QCheckBox("Focused (2x)")
        focused_cb.setChecked(False)
        layout.addWidget(focused_cb)

        # Target level spinbox
        target_label = QLabel("Target:")
        layout.addWidget(target_label)

        target_spin = QSpinBox()
        target_spin.setMinimum(0)
        target_spin.setMaximum(27)
        target_spin.setValue(0)
        target_spin.setSpecialValueText("None")
        target_spin.setMinimumWidth(70)
        layout.addWidget(target_spin)

        layout.addStretch()
        row.setLayout(layout)

        # Store widgets for this skill
        self.skill_widgets[skill] = {
            "row": row,
            "enabled": enabled_cb,
            "focused": focused_cb,
            "target": target_spin,
        }

        # Connect signals
        enabled_cb.stateChanged.connect(
            lambda state, s=skill: self._on_enabled_changed(s, state)
        )
        focused_cb.stateChanged.connect(
            lambda state, s=skill: self._on_focused_changed(s, state)
        )

        return row

    def _create_footer(self) -> QWidget:
        """Create footer with action buttons."""
        footer = QWidget()
        layout = QHBoxLayout()

        # Help text
        help_label = QLabel(
            "Tip: Focused skills train 2x faster. Set target levels to auto-disable."
        )
        help_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(help_label)

        layout.addStretch()

        # Apply button
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply_changes)
        layout.addWidget(apply_btn)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

        footer.setLayout(layout)
        return footer

    def _get_skill_category(self, skill: Skill) -> SkillCategory:
        """Get the category for a skill."""
        offensive = [
            Skill.FIGHTING,
            Skill.AXES,
            Skill.MACES_AND_FLAILS,
            Skill.POLEARMS,
            Skill.STAVES,
            Skill.LONG_BLADES,
            Skill.SHORT_BLADES,
            Skill.RANGED_WEAPONS,
            Skill.THROWING,
            Skill.UNARMED_COMBAT,
        ]

        defensive = [
            Skill.ARMOUR,
            Skill.DODGING,
            Skill.SHIELDS,
            Skill.STEALTH,
        ]

        magic = [
            Skill.SPELLCASTING,
            Skill.CONJURATIONS,
            Skill.HEXES,
            Skill.SUMMONINGS,
            Skill.NECROMANCY,
            Skill.FORGECRAFT,
            Skill.TRANSLOCATIONS,
            Skill.ALCHEMY,
            Skill.FIRE_MAGIC,
            Skill.AIR_MAGIC,
            Skill.ICE_MAGIC,
            Skill.EARTH_MAGIC,
        ]

        if skill in offensive:
            return SkillCategory.OFFENSIVE
        elif skill in defensive:
            return SkillCategory.DEFENSIVE
        elif skill in magic:
            return SkillCategory.MAGIC
        else:
            return SkillCategory.MISCELLANEOUS

    def _load_current_config(self) -> None:
        """Load current training configuration from registry."""
        training_config = self.registry.get_skill_training(self.entity_id)

        if not training_config:
            return

        # Set training mode
        mode_text = "Manual" if training_config.mode == TrainingMode.MANUAL else "Automatic"
        self.mode_selector.setCurrentText(mode_text)

        # Set skill states
        for skill, widgets in self.skill_widgets.items():
            weight = training_config.weights.get(skill, 1.0)
            target = training_config.targets.get(skill)

            # Enabled state
            enabled = weight > 0.0
            widgets["enabled"].setChecked(enabled)

            # Focused state
            focused = weight >= 2.0
            widgets["focused"].setChecked(focused)
            widgets["focused"].setEnabled(enabled)

            # Target level
            if target is not None:
                widgets["target"].setValue(target)

    def _on_mode_changed(self, mode_text: str) -> None:
        """Handle training mode change."""
        # Enable/disable focused checkboxes based on mode
        is_manual = mode_text == "Manual"

        for widgets in self.skill_widgets.values():
            widgets["focused"].setEnabled(is_manual and widgets["enabled"].isChecked())

    def _on_enabled_changed(self, skill: Skill, state: int) -> None:
        """Handle skill enabled/disabled."""
        widgets = self.skill_widgets[skill]
        enabled = state == Qt.CheckState.Checked.value

        # Enable/disable focused checkbox
        is_manual = self.mode_selector.currentText() == "Manual"
        widgets["focused"].setEnabled(enabled and is_manual)

        if not enabled:
            widgets["focused"].setChecked(False)

    def _on_focused_changed(self, skill: Skill, state: int) -> None:
        """Handle focused training toggle."""
        pass  # No immediate action needed

    def _apply_changes(self) -> None:
        """Apply training configuration changes."""
        # Update training mode
        mode_text = self.mode_selector.currentText()
        mode = TrainingMode.MANUAL if mode_text == "Manual" else TrainingMode.AUTOMATIC
        set_training_mode(self.registry, self.entity_id, mode)

        # Update each skill
        for skill, widgets in self.skill_widgets.items():
            enabled = widgets["enabled"].isChecked()
            focused = widgets["focused"].isChecked()
            target_value = widgets["target"].value()

            # Determine training state
            if not enabled:
                state = TrainingState.DISABLED
            elif focused:
                state = TrainingState.FOCUSED
            else:
                state = TrainingState.NORMAL

            # Target level (0 means None)
            target = target_value if target_value > 0 else None

            # Apply to skill system
            set_skill_training(
                self.registry,
                self.entity_id,
                skill,
                state,
                target,
            )

        self.accept()


def show_skill_training_dialog(
    registry: EntityRegistry,
    entity_id: int,
    parent: QWidget | None = None,
) -> bool:
    """Show the skill training dialog.

    Args:
        registry: Entity registry
        entity_id: Entity to configure
        parent: Parent widget

    Returns:
        True if user clicked Apply, False if canceled
    """
    dialog = SkillTrainingDialog(registry, entity_id, parent)
    return dialog.exec() == QDialog.DialogCode.Accepted
