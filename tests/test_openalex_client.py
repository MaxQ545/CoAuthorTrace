"""
Tests for OpenAlex client.
"""
import pytest
from datetime import datetime

from src.crawler.openalex_client import OpenAlexClient, parse_work


class TestParseWork:
    """Tests for work parsing function."""

    def test_parse_basic_work(self):
        """Test parsing a basic work response."""
        work_data = {
            "id": "https://openalex.org/W1234567890",
            "doi": "https://doi.org/10.1234/test",
            "title": "Test Paper Title",
            "publication_date": "2023-06-15",
            "type": "article",
            "cited_by_count": 42,
            "open_access": {"is_oa": True},
            "primary_location": {
                "source": {
                    "id": "https://openalex.org/S1234567890",
                    "display_name": "Test Journal",
                }
            },
            "authorships": [
                {
                    "author": {
                        "id": "https://openalex.org/A1111111111",
                        "display_name": "John Doe",
                        "orcid": "0000-0001-2345-6789",
                    },
                    "author_position": "first",
                    "is_corresponding": True,
                    "raw_author_name": "J. Doe",
                    "institutions": [
                        {
                            "id": "https://openalex.org/I1111111111",
                            "display_name": "Test University",
                        }
                    ],
                },
                {
                    "author": {
                        "id": "https://openalex.org/A2222222222",
                        "display_name": "Jane Smith",
                    },
                    "author_position": "last",
                    "is_corresponding": False,
                    "institutions": [],
                },
            ],
        }

        work, authors, authorships = parse_work(work_data)

        # Check work
        assert work["id"] == "W1234567890"
        assert work["doi"] == "https://doi.org/10.1234/test"
        assert work["title"] == "Test Paper Title"
        assert work["publication_year"] == 2023
        assert work["cited_by_count"] == 42
        assert work["is_open_access"] is True
        assert work["source_id"] == "S1234567890"
        assert work["source_name"] == "Test Journal"

        # Check authors
        assert len(authors) == 2
        assert authors[0]["id"] == "A1111111111"
        assert authors[0]["display_name"] == "John Doe"
        assert authors[0]["orcid"] == "0000-0001-2345-6789"
        assert authors[0]["last_known_institution_id"] == "I1111111111"

        # Check authorships
        assert len(authorships) == 2
        assert authorships[0]["author_id"] == "A1111111111"
        assert authorships[0]["work_id"] == "W1234567890"
        assert authorships[0]["author_position"] == 0
        assert authorships[0]["is_corresponding"] is True

    def test_parse_work_minimal(self):
        """Test parsing work with minimal data."""
        work_data = {
            "id": "https://openalex.org/W9999999999",
            "title": "Minimal Paper",
            "authorships": [],
        }

        work, authors, authorships = parse_work(work_data)

        assert work["id"] == "W9999999999"
        assert work["title"] == "Minimal Paper"
        assert work["doi"] is None
        assert work["publication_date"] is None
        assert len(authors) == 0
        assert len(authorships) == 0

    def test_parse_work_missing_author_id(self):
        """Test that authorships with missing author ID are skipped."""
        work_data = {
            "id": "https://openalex.org/W1234567890",
            "title": "Test Paper",
            "authorships": [
                {
                    "author": {
                        "display_name": "No ID Author",
                    },
                    "is_corresponding": False,
                },
                {
                    "author": {
                        "id": "https://openalex.org/A1111111111",
                        "display_name": "Has ID Author",
                    },
                    "is_corresponding": True,
                },
            ],
        }

        work, authors, authorships = parse_work(work_data)

        # Only the author with ID should be included
        assert len(authors) == 1
        assert authors[0]["id"] == "A1111111111"

    def test_parse_work_preferred_institution(self):
        """Prefer matching institution IDs when multiple affiliations exist."""
        work_data = {
            "id": "https://openalex.org/W1234567890",
            "title": "Multi-affiliation Paper",
            "authorships": [
                {
                    "author": {
                        "id": "https://openalex.org/A1111111111",
                        "display_name": "John Doe",
                    },
                    "institutions": [
                        {
                            "id": "https://openalex.org/I1111111111",
                            "display_name": "Institute of Art",
                        },
                        {
                            "id": "https://openalex.org/I2222222222",
                            "display_name": "Beihang University",
                        },
                    ],
                },
            ],
        }

        _, authors, _ = parse_work(work_data, preferred_institution_ids=["I2222222222"])

        assert authors[0]["last_known_institution_id"] == "I2222222222"
        assert authors[0]["last_known_institution_name"] == "Beihang University"


class TestOpenAlexClient:
    """Tests for OpenAlexClient class."""

    def test_build_filter_single_institution(self):
        """Test building filter with single institution."""
        client = OpenAlexClient()
        filter_str = client._build_works_filter(
            institution_ids=["I1234567890"]
        )
        assert "authorships.institutions.id:I1234567890" in filter_str

    def test_build_filter_multiple_concepts(self):
        """Test building filter with multiple concepts."""
        client = OpenAlexClient()
        filter_str = client._build_works_filter(
            concept_ids=["C123", "C456"]
        )
        assert "concepts.id:C123|C456" in filter_str

    def test_build_filter_with_date(self):
        """Test building filter with date range."""
        client = OpenAlexClient()
        filter_str = client._build_works_filter(
            from_date="2023-01-01"
        )
        assert "from_publication_date:2023-01-01" in filter_str

    def test_build_filter_combined(self):
        """Test building filter with multiple criteria."""
        client = OpenAlexClient()
        filter_str = client._build_works_filter(
            institution_ids=["I123"],
            concept_ids=["C456"],
            from_date="2023-01-01",
        )
        assert "authorships.institutions.id:I123" in filter_str
        assert "concepts.id:C456" in filter_str
        assert "from_publication_date:2023-01-01" in filter_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
