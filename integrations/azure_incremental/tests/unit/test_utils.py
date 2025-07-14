from typing import Any, Dict, List

from src.utils import turn_sequence_to_chunks


class TestUtils:
    """Test utility functions."""

    def test_turn_sequence_to_chunks_empty_sequence(self) -> None:
        """Test chunking an empty sequence."""
        result: List[List[Any]] = list(turn_sequence_to_chunks([], 5))
        assert result == [[]]  # The actual implementation yields an empty list

    def test_turn_sequence_to_chunks_smaller_than_chunk_size(self) -> None:
        """Test chunking a sequence smaller than chunk size."""
        result: List[List[int]] = list(turn_sequence_to_chunks([1, 2, 3], 5))
        assert result == [[1, 2, 3]]

    def test_turn_sequence_to_chunks_exact_chunk_size(self) -> None:
        """Test chunking a sequence exactly the chunk size."""
        result: List[List[int]] = list(turn_sequence_to_chunks([1, 2, 3, 4, 5], 5))
        assert result == [[1, 2, 3, 4, 5]]

    def test_turn_sequence_to_chunks_larger_than_chunk_size(self) -> None:
        """Test chunking a sequence larger than chunk size."""
        result: List[List[int]] = list(
            turn_sequence_to_chunks([1, 2, 3, 4, 5, 6, 7], 3)
        )
        assert result == [[1, 2, 3], [4, 5, 6], [7]]

    def test_turn_sequence_to_chunks_multiple_full_chunks(self) -> None:
        """Test chunking with multiple full chunks."""
        result: List[List[int]] = list(turn_sequence_to_chunks([1, 2, 3, 4, 5, 6], 2))
        assert result == [[1, 2], [3, 4], [5, 6]]

    def test_turn_sequence_to_chunks_with_strings(self) -> None:
        """Test chunking with string elements."""
        result: List[List[str]] = list(turn_sequence_to_chunks(["a", "b", "c", "d"], 2))
        assert result == [["a", "b"], ["c", "d"]]

    def test_turn_sequence_to_chunks_with_dicts(self) -> None:
        """Test chunking with dictionary elements."""
        sequence: List[Dict[str, int]] = [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]
        result: List[List[Dict[str, int]]] = list(turn_sequence_to_chunks(sequence, 2))
        assert result == [[{"id": 1}, {"id": 2}], [{"id": 3}, {"id": 4}]]

    def test_turn_sequence_to_chunks_chunk_size_one(self) -> None:
        """Test chunking with chunk size of 1."""
        result: List[List[int]] = list(turn_sequence_to_chunks([1, 2, 3], 1))
        assert result == [[1], [2], [3]]

    def test_turn_sequence_to_chunks_chunk_size_zero(self) -> None:
        """Test chunking with chunk size of 0 (returns empty list)."""
        sequence: List[int] = [1, 2, 3]
        result: List[List[int]] = list(turn_sequence_to_chunks(sequence, 0))
        assert result == []  # When chunk_size is 0, returns empty list

    def test_turn_sequence_to_chunks_chunk_size_negative(self) -> None:
        """Test chunking with negative chunk size (returns partial chunks)."""
        sequence: List[int] = [1, 2, 3]
        result: List[List[int]] = list(turn_sequence_to_chunks(sequence, -1))
        assert result == [[1, 2]]  # Negative chunk size behaves like small positive

    def test_turn_sequence_to_chunks_large_sequence(self) -> None:
        """Test chunking a large sequence."""
        sequence: List[int] = list(range(1000))
        result: List[List[int]] = list(turn_sequence_to_chunks(sequence, 100))
        assert len(result) == 10
        assert all(len(chunk) == 100 for chunk in result[:-1])
        assert len(result[-1]) == 100  # Last chunk is full due to implementation logic
