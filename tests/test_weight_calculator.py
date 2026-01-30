"""
Tests for weight calculator.
"""
import pytest
from datetime import datetime, timedelta

from src.analysis.weight_calculator import WeightCalculator


class TestWeightCalculator:
    """Tests for WeightCalculator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calc = WeightCalculator(half_life_days=730)  # 2 years

    def test_position_factor_first_author_corresponding(self):
        """First author + corresponding should have highest factor."""
        factor = self.calc.calculate_position_factor(
            position_1=0,
            position_2=1,
            is_corresponding_1=True,
            is_corresponding_2=False,
            total_authors=3,
        )
        assert factor > 0
        assert factor <= 1

    def test_position_factor_middle_authors(self):
        """Middle authors should have lower factor."""
        factor_first = self.calc.calculate_position_factor(
            position_1=0,
            position_2=1,
            is_corresponding_1=True,
            is_corresponding_2=False,
            total_authors=5,
        )

        factor_middle = self.calc.calculate_position_factor(
            position_1=2,
            position_2=3,
            is_corresponding_1=False,
            is_corresponding_2=False,
            total_authors=5,
        )

        assert factor_first > factor_middle

    def test_time_factor_recent(self):
        """Recent publications should have high time factor."""
        recent = datetime.utcnow() - timedelta(days=30)
        factor = self.calc.calculate_time_factor(recent)
        assert factor > 0.9

    def test_time_factor_old(self):
        """Old publications should have decayed time factor."""
        # Exactly one half-life ago
        old = datetime.utcnow() - timedelta(days=730)
        factor = self.calc.calculate_time_factor(old)
        assert 0.45 < factor < 0.55  # Should be ~0.5

    def test_time_factor_very_old(self):
        """Very old publications should have very low factor."""
        very_old = datetime.utcnow() - timedelta(days=2190)  # 6 years
        factor = self.calc.calculate_time_factor(very_old)
        assert factor < 0.2

    def test_time_factor_none(self):
        """None publication date should return default."""
        factor = self.calc.calculate_time_factor(None)
        assert factor == 0.5

    def test_calculate_weight(self):
        """Test combined weight calculation."""
        pub_date = datetime.utcnow() - timedelta(days=365)

        weight = self.calc.calculate_weight(
            position_1=0,
            position_2=1,
            is_corresponding_1=True,
            is_corresponding_2=False,
            total_authors=3,
            publication_date=pub_date,
        )

        assert weight > 0
        assert weight <= 1

    def test_more_authors_lower_weight(self):
        """More authors should result in lower weight."""
        pub_date = datetime.utcnow()

        weight_few = self.calc.calculate_weight(
            position_1=0,
            position_2=1,
            is_corresponding_1=True,
            is_corresponding_2=False,
            total_authors=2,
            publication_date=pub_date,
        )

        weight_many = self.calc.calculate_weight(
            position_1=0,
            position_2=1,
            is_corresponding_1=True,
            is_corresponding_2=False,
            total_authors=10,
            publication_date=pub_date,
        )

        assert weight_few > weight_many


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
