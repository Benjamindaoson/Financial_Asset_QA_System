from __future__ import annotations

import math
from datetime import date, datetime
from enum import Enum
from typing import Literal, Sequence, TypeAlias, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, JsonValue
from trust_rag.core.evidence import Provenance

BBox: TypeAlias = tuple[float, float, float, float]


def _validate_bbox(coords: Sequence[float]) -> BBox:
    if len(coords) != 4:
        raise ValueError("bbox must contain exactly four coordinates")
    x1, y1, x2, y2 = coords
    for coord in coords:
        if not math.isfinite(coord):
            raise ValueError("bbox coordinates must be finite")
    if x2 < x1 or y2 < y1:
        raise ValueError("bbox max coordinates must be greater than or equal to min coordinates")
    return cast(BBox, (float(x1), float(y1), float(x2), float(y2)))


class DocType(str, Enum):
    PDF = "pdf"
    HTML = "html"
    AUDIO = "audio"
    TRANSCRIPT = "transcript"


class BlockType(str, Enum):
    TITLE = "title"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST = "list"
    FOOTNOTE = "footnote"
    HEADER = "header"
    FOOTER = "footer"


class TableCellIR(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        frozen=True,
        str_strip_whitespace=True,
        arbitrary_types_allowed=False,
    )

    text: str
    bbox: BBox | None = None
    dtype: str | None = None

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, value: BBox | Sequence[float] | None) -> BBox | None:
        if value is None:
            return None
        coords = tuple(value)
        return _validate_bbox(coords)


class TableIR(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        frozen=True,
        str_strip_whitespace=True,
        arbitrary_types_allowed=False,
    )

    n_rows: int = Field(ge=1)
    n_cols: int = Field(ge=1)
    cells: list[list[TableCellIR]]
    dtypes: dict[int, str] | None = None
    caption: str | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "TableIR":
        if len(self.cells) != self.n_rows:
            raise ValueError("cells row count must match n_rows")
        for row in self.cells:
            if len(row) != self.n_cols:
                raise ValueError("cells column count must match n_cols for each row")
        return self


class Block(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        frozen=True,
        str_strip_whitespace=True,
        arbitrary_types_allowed=False,
    )

    block_id: str = Field(min_length=1)
    block_type: BlockType
    text: str | None = None
    table: TableIR | None = None
    hierarchy_path: list[str]
    provenance: Provenance
    signals: dict[str, JsonValue] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("hierarchy_path")
    @classmethod
    def validate_hierarchy_path(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("hierarchy_path entries must be non-empty strings")
        return normalized

    @model_validator(mode="after")
    def validate_content(self) -> "Block":
        if self.text is None and self.table is None:
            raise ValueError("either text or table must be provided for a block")
        return self


class DocIR(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        frozen=True,
        str_strip_whitespace=True,
        arbitrary_types_allowed=False,
    )

    doc_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    doc_type: DocType
    language: str = Field(min_length=2)
    effective_date: date | None = None
    blocks: list[Block]
    doc_meta: dict[str, JsonValue] = Field(default_factory=dict)
    schema_version: Literal["1.0"] = "1.0"

    @model_validator(mode="after")
    def validate_blocks(self) -> "DocIR":
        if not self.blocks:
            raise ValueError("blocks must contain at least one Block")
        return self
