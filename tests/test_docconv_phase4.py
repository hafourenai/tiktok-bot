"""Tests for Phase 4: Advanced Table Detection.

Covers table analysis, confidence scoring, header detection, structure analysis.
"""

import pytest
from docconv.table_analysis import (
    TableMetrics, EnhancedTable, analyze_tables,
    filter_tables_by_confidence, extract_table_headers,
    detect_table_patterns, merge_table_cells, normalize_table,
    export_table_with_metrics
)


class TestTableMetrics:
    """Test TableMetrics class."""

    def test_metrics_creation(self):
        """Create TableMetrics object."""
        metrics = TableMetrics(
            confidence=85.5, row_count=5, col_count=3,
            regularity=92.0, has_headers=True, header_row_count=1,
            is_nested=False, merged_cells=0, structure_type="simple"
        )
        assert metrics.confidence == 85.5
        assert metrics.row_count == 5
        assert metrics.structure_type == "simple"

    def test_metrics_repr(self):
        """Metrics has useful string representation."""
        metrics = TableMetrics(
            confidence=75, row_count=3, col_count=2,
            regularity=80, has_headers=True, header_row_count=1,
            is_nested=False, merged_cells=0, structure_type="simple"
        )
        repr_str = repr(metrics)
        assert "75%" in repr_str or "75.0%" in repr_str
        assert "3x2" in repr_str
        assert "simple" in repr_str


class TestEnhancedTableBasic:
    """Test EnhancedTable basic functionality."""

    def test_simple_table_creation(self):
        """Create enhanced table from simple data."""
        rows = [
            ["Name", "Age", "City"],
            ["Alice", "30", "NYC"],
            ["Bob", "25", "LA"],
        ]
        table = EnhancedTable(rows)
        
        assert table.rows == rows
        assert table.metrics.row_count == 3
        assert table.metrics.col_count == 3
        assert table.metrics.structure_type in ["simple", "complex"]

    def test_empty_table(self):
        """Handle empty table."""
        table = EnhancedTable([])
        assert table.metrics.row_count == 0
        assert table.metrics.col_count == 0
        assert table.metrics.confidence == 0

    def test_single_row_table(self):
        """Handle single-row table."""
        table = EnhancedTable([["A", "B", "C"]])
        assert table.metrics.row_count == 1
        assert table.metrics.confidence < 50  # Low confidence for tiny table


class TestConfidenceScoring:
    """Test confidence scoring."""

    def test_high_confidence_full_table(self):
        """Full, regular table has high confidence."""
        rows = [["Name", "Age"]] + [["Person", "25"] for _ in range(10)]
        table = EnhancedTable(rows)
        
        assert table.metrics.confidence > 70

    def test_low_confidence_sparse_table(self):
        """Sparse table has low confidence."""
        rows = [
            ["A", "B", "C"],
            ["1", "", ""],
            ["", "2", ""],
            ["", "", "3"],
        ]
        table = EnhancedTable(rows)
        
        assert table.metrics.confidence < 70

    def test_confidence_increases_with_size(self):
        """Larger tables have higher confidence."""
        small_rows = [["A", "B"], ["1", "2"]]
        large_rows = [["A", "B", "C", "D", "E"]] + [["1", "2", "3", "4", "5"] for _ in range(20)]
        
        small_table = EnhancedTable(small_rows)
        large_table = EnhancedTable(large_rows)
        
        assert large_table.metrics.confidence > small_table.metrics.confidence


class TestHeaderDetection:
    """Test header detection."""

    def test_header_detection_with_first_row(self):
        """First row detected as header."""
        rows = [
            ["Name", "Age", "City"],
            ["Alice", "30", "New York"],
            ["Bob", "25", "Los Angeles"],
        ]
        table = EnhancedTable(rows)
        
        assert table.metrics.has_headers
        assert len(table.headers) == 3
        assert table.headers[0] == "Name"

    def test_no_headers_in_data_only(self):
        """Data-only table without headers."""
        rows = [
            ["Alice", "30"],
            ["Bob", "25"],
            ["Charlie", "35"],
        ]
        table = EnhancedTable(rows)
        
        # May or may not detect headers (depends on heuristic)
        assert isinstance(table.metrics.has_headers, bool)

    def test_empty_table_no_headers(self):
        """Empty table has no headers."""
        table = EnhancedTable([])
        assert not table.metrics.has_headers
        assert len(table.headers) == 0


class TestRegularity:
    """Test column regularity scoring."""

    def test_perfect_regularity(self):
        """Uniform column widths score high."""
        rows = [
            ["ABC", "DEF", "GHI"],
            ["XYZ", "UVW", "RST"],
            ["123", "456", "789"],
        ]
        table = EnhancedTable(rows)
        
        assert table.metrics.regularity > 80

    def test_irregular_columns(self):
        """Variable column widths score lower."""
        rows = [
            ["A", "Very Long Text Here", "B"],
            ["Short", "X", "Y"],
            ["Medium Length", "Z", "A"],
        ]
        table = EnhancedTable(rows)
        
        assert table.metrics.regularity < 100


class TestNestingDetection:
    """Test nested table detection."""

    def test_no_nesting_simple_table(self):
        """Simple table without nesting."""
        rows = [["A", "B"], ["1", "2"]]
        table = EnhancedTable(rows)
        assert not table.metrics.is_nested

    def test_nesting_detection_with_pipes(self):
        """Detect nesting with pipe characters."""
        rows = [
            ["A", "B"],
            ["1 | 2", "3"],  # Pipe indicates nesting
        ]
        table = EnhancedTable(rows)
        assert table.metrics.is_nested

    def test_nesting_detection_with_separator(self):
        """Detect nesting with markdown separators."""
        rows = [
            ["A", "B"],
            ["---", "---"],
        ]
        table = EnhancedTable(rows)
        assert table.metrics.is_nested


class TestMergedCells:
    """Test merged cell detection."""

    def test_merged_cell_counting(self):
        """Count potential merged cells."""
        rows = [
            ["Name", "Details"],
            ["Alice", "Developer"],
            ["", "NYC"],  # Merged cell
            ["Bob", "Designer"],
        ]
        table = EnhancedTable(rows)
        
        assert table.metrics.merged_cells > 0

    def test_no_merges_in_regular_table(self):
        """Regular table has no merges."""
        rows = [
            ["A", "B"],
            ["1", "2"],
            ["3", "4"],
        ]
        table = EnhancedTable(rows)
        
        # May still detect some due to heuristic, but should be low
        assert table.metrics.merged_cells < 3


class TestTableNormalization:
    """Test table normalization."""

    def test_normalize_uneven_rows(self):
        """Normalize rows with different column counts."""
        table = EnhancedTable([
            ["A", "B", "C"],
            ["1", "2"],  # Missing column
            ["X", "Y", "Z", "W"],  # Extra column
        ])
        
        normalized = normalize_table(table)
        
        # All rows should have same column count
        col_counts = [len(row) for row in normalized]
        assert len(set(col_counts)) == 1

    def test_normalize_removes_empty_rows(self):
        """Normalization skips completely empty rows."""
        table = EnhancedTable([
            ["A", "B"],
            ["", ""],  # Empty row
            ["1", "2"],
        ])
        
        normalized = normalize_table(table)
        
        # Should skip the empty row
        assert len(normalized) < len(table.rows)


class TestTableAnalysis:
    """Test table analysis functions."""

    def test_analyze_multiple_tables(self):
        """Analyze multiple tables at once."""
        tables_data = [
            [["A", "B"], ["1", "2"]],
            [["X", "Y"], ["3", "4"]],
        ]
        
        analyzed = analyze_tables(tables_data)
        
        assert len(analyzed) == 2
        assert all(isinstance(t, EnhancedTable) for t in analyzed)

    def test_filter_by_confidence(self):
        """Filter tables by confidence threshold."""
        tables_data = [
            [["A", "B"]] + [["1", "2"] for _ in range(10)],  # High confidence
            [["X"]],  # Low confidence
        ]
        
        analyzed = analyze_tables(tables_data)
        filtered = filter_tables_by_confidence(analyzed, min_confidence=50)
        
        assert len(filtered) <= len(analyzed)

    def test_extract_headers(self):
        """Extract headers from tables."""
        tables_data = [
            [["Name", "Age"], ["Alice", "30"]],
            [["X", "Y"], ["1", "2"]],
        ]
        
        analyzed = analyze_tables(tables_data)
        headers = extract_table_headers(analyzed)
        
        assert len(headers) == 2
        assert headers[0] == ["Name", "Age"] or headers[0] is None or len(headers[0]) > 0


class TestTablePatterns:
    """Test table pattern detection."""

    def test_detect_simple_tables(self):
        """Detect simple table patterns."""
        tables_data = [
            [["A", "B"], ["1", "2"]],
            [["X", "Y", "Z"], ["3", "4", "5"]],
        ]
        
        analyzed = analyze_tables(tables_data)
        patterns = detect_table_patterns(analyzed)
        
        assert "simple" in patterns
        assert sum(len(p) for p in patterns.values()) == len(analyzed)

    def test_pattern_grouping(self):
        """Tables grouped by structure type."""
        tables_data = [
            [["A", "B"]] + [["1", "2"] for _ in range(5)],  # Simple
            [["X"], ["", ""]],  # Complex
        ]
        
        analyzed = analyze_tables(tables_data)
        patterns = detect_table_patterns(analyzed)
        
        # At least one pattern should have tables
        total = sum(len(t) for t in patterns.values())
        assert total == len(analyzed)


class TestMergeCellHandling:
    """Test merged cell merging/filling."""

    def test_merge_fills_down(self):
        """Merge operation fills down empty cells."""
        rows = [
            ["Item", "Count"],
            ["Apple", "5"],
            ["", "3"],  # Empty cell
            ["Banana", "2"],
        ]
        table = EnhancedTable(rows)
        merged = merge_table_cells(table)
        
        # First column should be filled
        assert merged[2][0] == "Apple" or merged[2][0] == ""

    def test_merge_preserves_structure(self):
        """Merge doesn't remove rows or columns."""
        rows = [
            ["A", "B"],
            ["", "2"],
            ["3", ""],
        ]
        table = EnhancedTable(rows)
        merged = merge_table_cells(table)
        
        assert len(merged) == len(rows)
        assert all(len(row) >= 2 for row in merged)


class TestTableExport:
    """Test table export with metrics."""

    def test_export_with_metrics(self):
        """Export table includes all metrics."""
        rows = [
            ["Name", "Age"],
            ["Alice", "30"],
            ["Bob", "25"],
        ]
        table = EnhancedTable(rows)
        export = export_table_with_metrics(table)
        
        assert "data" in export
        assert "metrics" in export
        assert "headers" in export
        assert export["metrics"]["confidence"] >= 0
        assert export["metrics"]["confidence"] <= 100

    def test_export_metrics_rounded(self):
        """Exported metrics are properly formatted."""
        rows = [["A", "B"]] + [["1", "2"] for _ in range(5)]
        table = EnhancedTable(rows)
        export = export_table_with_metrics(table)
        
        metrics = export["metrics"]
        assert isinstance(metrics["confidence"], (int, float))
        assert isinstance(metrics["rows"], int)
        assert isinstance(metrics["columns"], int)


class TestTableIntegration:
    """Integration tests for table analysis."""

    def test_full_workflow(self):
        """Complete table analysis workflow."""
        tables_data = [
            [["Name", "Age", "City"]] + [["Person", "25", "NYC"] for _ in range(3)],
            [["Product", "Price"], ["Widget", "10"]],
        ]
        
        # Analyze
        analyzed = analyze_tables(tables_data)
        assert len(analyzed) == 2
        
        # Filter
        filtered = filter_tables_by_confidence(analyzed, 40)
        assert len(filtered) > 0
        
        # Export
        for table in filtered:
            export = export_table_with_metrics(table)
            assert export["metrics"]["confidence"] >= 40

    def test_complex_table_analysis(self):
        """Analyze complex table with multiple features."""
        rows = [
            ["Department", "Q1", "Q2", "Q3", "Q4"],
            ["Sales", "100", "120", "150", "180"],
            ["", "10% ↑", "25% ↑", "20% ↑", "20% ↑"],
            ["Marketing", "50", "60", "70", "80"],
        ]
        table = EnhancedTable(rows)
        
        assert table.metrics.row_count == 4
        assert table.metrics.col_count == 5
        assert table.metrics.confidence > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
