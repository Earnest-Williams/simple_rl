from __future__ import annotations


class Dirty:
    def __init__(self) -> None:
        self.frame: bool = True
        self.flow_fields: bool = True


dirty = Dirty()
