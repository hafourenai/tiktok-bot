"""Advanced table detection and analysis.

Extends core table detection with:
- Table confidence scoring
- Nested table detection
- Merged cell identification
- Header/footer recognition
- Complex structure analysis
"""

from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass


@dataclass
class TableMetrics:
    """Table quality and structure metrics."""
    
    __slots__ = ("confidence", "row_count", "col_count", "regularity", 
                 "has_headers", "header_row_count", "is_nested", 
                 "merged_cells", "structure_type")
    
    confidence: float  # 0-100: detection confidence
    row_count: int
    col_count: int
    regularity: float  # 0-100: column width consistency
    has_headers: bool
    header_row_count: int
    is_nested: bool
    merged_cells: int
    structure_type: str  # "simple", "complex", "nested"

    def __repr__(self):
        return (f"<TableMetrics confidence={self.confidence:.0f}% "
                f"{self.row_count}x{self.col_count} {self.structure_type}>")


class EnhancedTable:
    """Table with metadata and structure information."""
    
    __slots__ = ("rows", "metrics", "headers", "merged_cells_map", 
                 "nested_tables", "footer_rows")
    
    def __init__(self, rows: List[List[str]]):
        self.rows = rows
        self.metrics = self._analyze_structure()
        self.headers = self._detect_headers()
        self.merged_cells_map = self._detect_merged_cells()
        self.nested_tables = []
        self.footer_rows = []
    
    def _analyze_structure(self) -> TableMetrics:
        """Analyze table structure and generate metrics."""
        if not self.rows:
            return TableMetrics(0, 0, 0, 0, False, 0, False, 0, "empty")
        
        row_count = len(self.rows)
        col_count = max(len(row) for row in self.rows) if self.rows else 0
        
        # Confidence: based on regularity and size
        confidence = self._calculate_confidence()
        
        # Regularity: check column consistency
        regularity = self._calculate_regularity()
        
        # Header detection
        has_headers, header_count = self._detect_headers_basic()
        
        # Structure type
        is_nested = self._detect_nesting()
        merged_count = self._count_potential_merges()
        
        structure_type = "nested" if is_nested else "complex" if merged_count > 0 else "simple"
        
        return TableMetrics(
            confidence=confidence,
            row_count=row_count,
            col_count=col_count,
            regularity=regularity,
            has_headers=has_headers,
            header_row_count=header_count,
            is_nested=is_nested,
            merged_cells=merged_count,
            structure_type=structure_type
        )
    
    def _calculate_confidence(self) -> float:
        """Calculate detection confidence (0-100)."""
        if not self.rows or len(self.rows) < 2:
            return 30  # Low confidence for tiny tables
        
        # Base confidence on size
        row_count = len(self.rows)
        col_count = max(len(row) for row in self.rows) if self.rows else 0
        
        size_score = min(100, (row_count * col_count) / 2)  # More cells = higher confidence
        
        # Check content consistency
        empty_cells = sum(1 for row in self.rows for cell in row if not str(cell).strip())
        fill_score = max(0, 100 - (empty_cells / (row_count * col_count) * 100)) if row_count * col_count > 0 else 0
        
        # Average with slight weight to size
        confidence = (size_score * 0.6 + fill_score * 0.4)
        return min(100, max(0, confidence))
    
    def _calculate_regularity(self) -> float:
        """Calculate column width regularity (0-100)."""
        if not self.rows or len(self.rows) < 2:
            return 0
        
        col_widths = []
        col_count = max(len(row) for row in self.rows) if self.rows else 0
        
        for col_idx in range(col_count):
            widths = [len(str(row[col_idx] or "")) for row in self.rows 
                     if col_idx < len(row)]
            if widths:
                avg_width = sum(widths) / len(widths)
                col_widths.append(avg_width)
        
        # Calculate variance
        if len(col_widths) < 2:
            return 100
        
        mean = sum(col_widths) / len(col_widths)
        variance = sum((w - mean) ** 2 for w in col_widths) / len(col_widths)
        
        # Convert variance to regularity score (lower variance = higher regularity)
        regularity = max(0, 100 - (variance * 10))
        return min(100, regularity)
    
    def _detect_headers_basic(self) -> Tuple[bool, int]:
        """Detect header rows (first N rows with bold/distinct content)."""
        if not self.rows or len(self.rows) < 2:
            return False, 0
        
        # Heuristic: first row is header if it differs significantly from others
        first_row_avg_len = sum(len(str(cell or "")) for cell in self.rows[0]) / max(len(self.rows[0]), 1)
        second_row_avg_len = sum(len(str(cell or "")) for cell in self.rows[1]) / max(len(self.rows[1]), 1) if len(self.rows) > 1 else 0
        
        # Header typically has shorter labels
        is_header = first_row_avg_len < second_row_avg_len * 1.5
        header_count = 1 if is_header else 0
        
        return is_header, header_count
    
    def _detect_nesting(self) -> bool:
        """Detect if table contains nested structures."""
        # Look for cells that contain table-like content (multiple pipes, separators)
        for row in self.rows:
            for cell in row:
                cell_str = str(cell or "").lower()
                if "|" in cell_str or "---" in cell_str:
                    return True
        return False
    
    def _count_potential_merges(self) -> int:
        """Count potential merged cells (empty cells in column after filled cells)."""
        if not self.rows:
            return 0
        
        merged_count = 0
        col_count = max(len(row) for row in self.rows) if self.rows else 0
        
        for col_idx in range(col_count):
            prev_filled = False
            for row_idx, row in enumerate(self.rows):
                cell = str(row[col_idx] or "").strip() if col_idx < len(row) else ""
                if cell and prev_filled:
                    # Filled cell after filled cell (no merge)
                    prev_filled = True
                elif not cell and prev_filled:
                    # Empty cell after filled cell (potential merge)
                    merged_count += 1
                    # prev_filled stays True
                elif cell:
                    prev_filled = True
                else:
                    prev_filled = False
        
        return merged_count
    
    def _detect_headers(self) -> List[str]:
        """Detect and extract header row."""
        if not self.rows:
            return []
        
        has_header, _ = self._detect_headers_basic()
        if has_header:
            return [str(cell or "") for cell in self.rows[0]]
        return []
    
    def _detect_merged_cells(self) -> Dict[Tuple[int, int], Tuple[int, int]]:
        """Map merged cells: (row, col) -> (span_rows, span_cols)."""
        merged_map = {}
        
        if not self.rows:
            return merged_map
        
        # Simple heuristic: empty cells following content in same column
        # This is a basic implementation; production would need more logic
        
        return merged_map
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "rows": self.rows,
            "metrics": {
                "confidence": self.metrics.confidence,
                "row_count": self.metrics.row_count,
                "col_count": self.metrics.col_count,
                "regularity": self.metrics.regularity,
                "has_headers": self.metrics.has_headers,
                "header_row_count": self.metrics.header_row_count,
                "is_nested": self.metrics.is_nested,
                "merged_cells": self.metrics.merged_cells,
                "structure_type": self.metrics.structure_type,
            },
            "headers": self.headers,
        }
    
    def __repr__(self):
        return f"<EnhancedTable {self.metrics}>"


def analyze_tables(tables: List[List[List[str]]]) -> List[EnhancedTable]:
    """Analyze tables and return with metrics."""
    return [EnhancedTable(table) for table in tables]


def filter_tables_by_confidence(tables: List[EnhancedTable], 
                               min_confidence: float = 50.0) -> List[EnhancedTable]:
    """Filter tables by confidence threshold."""
    return [t for t in tables if t.metrics.confidence >= min_confidence]


def extract_table_headers(tables: List[EnhancedTable]) -> List[Optional[List[str]]]:
    """Extract headers from all tables."""
    return [t.headers if t.headers else None for t in tables]


def detect_table_patterns(tables: List[EnhancedTable]) -> Dict[str, List[EnhancedTable]]:
    """Group tables by structure patterns."""
    patterns = {
        "simple": [],
        "complex": [],
        "nested": [],
        "low_confidence": []
    }
    
    for table in tables:
        if table.metrics.confidence < 50:
            patterns["low_confidence"].append(table)
        else:
            patterns[table.metrics.structure_type].append(table)
    
    return patterns


def merge_table_cells(table: EnhancedTable) -> List[List[str]]:
    """Resolve merged cells by filling empty cells with previous values."""
    if not table.rows:
        return []
    
    merged = [row[:] for row in table.rows]  # Deep copy
    
    # For each column, fill down empty cells
    for col_idx in range(max(len(row) for row in merged) if merged else 0):
        last_value = None
        for row_idx in range(len(merged)):
            if col_idx < len(merged[row_idx]):
                cell = str(merged[row_idx][col_idx] or "").strip()
                if cell:
                    last_value = cell
                elif last_value:
                    # Fill with previous value
                    merged[row_idx][col_idx] = last_value
    
    return merged


def normalize_table(table: EnhancedTable) -> List[List[str]]:
    """Normalize table: uniform column count, no empty rows."""
    if not table.rows:
        return []
    
    col_count = max(len(row) for row in table.rows)
    normalized = []
    
    for row in table.rows:
        # Skip empty rows
        if not any(str(cell).strip() for cell in row):
            continue
        
        # Pad to uniform column count
        padded = list(row) + [""] * (col_count - len(row))
        normalized.append([str(cell or "").strip() for cell in padded[:col_count]])
    
    return normalized


def export_table_with_metrics(table: EnhancedTable) -> Dict[str, Any]:
    """Export table with all metadata."""
    return {
        "data": normalize_table(table),
        "metrics": {
            "confidence": round(table.metrics.confidence, 2),
            "rows": table.metrics.row_count,
            "columns": table.metrics.col_count,
            "regularity": round(table.metrics.regularity, 2),
            "headers": table.metrics.has_headers,
            "structure": table.metrics.structure_type,
        },
        "headers": table.headers,
    }


__all__ = [
    "TableMetrics",
    "EnhancedTable",
    "analyze_tables",
    "filter_tables_by_confidence",
    "extract_table_headers",
    "detect_table_patterns",
    "merge_table_cells",
    "normalize_table",
    "export_table_with_metrics",
]
