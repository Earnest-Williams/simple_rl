"""Experimental lighting, field-of-view, and perception prototypes.

.. deprecated::
    ``lights_dev`` is **frozen R&D pending retirement**.

    * Do **not** add new production imports from this package.
    * Production lighting lives in :mod:`engine.render_lighting`.
    * Production FOV/LOS lives in :mod:`game.world.fov`.
    * Migrate selected algorithms to production owners before deleting this folder.

    See ``docs/SYSTEMS_INVENTORY.md`` and the migration plan in the issue tracker.
"""

import warnings

warnings.warn(
    "lights_dev is frozen R&D pending retirement. "
    "Do not add production imports from it. "
    "See docs/SYSTEMS_INVENTORY.md for the migration plan.",
    DeprecationWarning,
    stacklevel=2,
)
