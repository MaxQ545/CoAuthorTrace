"""Repository for Collaboration operations."""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from src.database.models import (
    Collaboration,
    RelationshipScore,
    Authorship,
    Work,
    Author,
)


class CollaborationRepository:
    """Repository for Collaboration CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def get_collaboration(
        self,
        author_id_1: str,
        author_id_2: str
    ) -> Optional[Collaboration]:
        """Get collaboration between two authors."""
        # Ensure consistent ordering
        if author_id_1 > author_id_2:
            author_id_1, author_id_2 = author_id_2, author_id_1

        return (
            self.session.query(Collaboration)
            .filter(
                and_(
                    Collaboration.author_id_1 == author_id_1,
                    Collaboration.author_id_2 == author_id_2
                )
            )
            .first()
        )

    def create_or_update(
        self,
        author_id_1: str,
        author_id_2: str,
        weight: float,
        collaboration_date: Optional[datetime] = None
    ) -> Collaboration:
        """Create or update a collaboration record."""
        # Ensure consistent ordering
        if author_id_1 > author_id_2:
            author_id_1, author_id_2 = author_id_2, author_id_1

        collab = self.get_collaboration(author_id_1, author_id_2)

        if collab:
            collab.collaboration_count += 1
            collab.total_weight += weight
            if collaboration_date:
                if collab.first_collaboration is None or collaboration_date < collab.first_collaboration:
                    collab.first_collaboration = collaboration_date
                if collab.last_collaboration is None or collaboration_date > collab.last_collaboration:
                    collab.last_collaboration = collaboration_date
        else:
            collab = Collaboration(
                author_id_1=author_id_1,
                author_id_2=author_id_2,
                collaboration_count=1,
                total_weight=weight,
                first_collaboration=collaboration_date,
                last_collaboration=collaboration_date,
            )
            self.session.add(collab)

        return collab

    def get_collaborations_for_author(
        self,
        author_id: str,
        min_count: int = 1,
        limit: int = 100
    ) -> list[Collaboration]:
        """Get all collaborations for an author."""
        return (
            self.session.query(Collaboration)
            .filter(
                or_(
                    Collaboration.author_id_1 == author_id,
                    Collaboration.author_id_2 == author_id
                )
            )
            .filter(Collaboration.collaboration_count >= min_count)
            .order_by(Collaboration.total_weight.desc())
            .limit(limit)
            .all()
        )

    def batch_get_collaborations(
        self,
        author_id: str,
        other_ids: list[str],
    ) -> dict[str, Optional[Collaboration]]:
        """Batch get collaborations between one author and multiple others.

        Returns dict mapping other_id -> Collaboration (or None).
        Uses a single query instead of N individual lookups.
        """
        if not other_ids:
            return {}

        # Fetch all collaborations for this author in one query
        all_collabs = (
            self.session.query(Collaboration)
            .filter(
                or_(
                    Collaboration.author_id_1 == author_id,
                    Collaboration.author_id_2 == author_id,
                )
            )
            .all()
        )

        # Build lookup: other_id -> Collaboration
        collab_map: dict[str, Collaboration] = {}
        for c in all_collabs:
            other = c.author_id_2 if c.author_id_1 == author_id else c.author_id_1
            collab_map[other] = c

        return {oid: collab_map.get(oid) for oid in other_ids}

    def rebuild_collaborations_for_work(
        self,
        work_id: str,
        weight_calculator
    ) -> int:
        """Rebuild collaboration edges for a specific work."""
        # Get all authorships for this work
        authorships = (
            self.session.query(Authorship)
            .filter(Authorship.work_id == work_id)
            .all()
        )

        if len(authorships) < 2:
            return 0

        # Get work for publication date
        work = self.session.query(Work).filter(Work.id == work_id).first()
        pub_date = work.publication_date if work else None

        # Create edges between all author pairs
        edge_count = 0
        for i, auth1 in enumerate(authorships):
            for auth2 in authorships[i + 1:]:
                weight = weight_calculator.calculate_weight(
                    position_1=auth1.author_position,
                    position_2=auth2.author_position,
                    is_corresponding_1=auth1.is_corresponding,
                    is_corresponding_2=auth2.is_corresponding,
                    total_authors=len(authorships),
                    publication_date=pub_date,
                )
                self.create_or_update(
                    auth1.author_id,
                    auth2.author_id,
                    weight,
                    pub_date
                )
                edge_count += 1

        return edge_count

    def count(self) -> int:
        """Get total number of collaboration edges."""
        return self.session.query(func.count(Collaboration.id)).scalar()

    def get_statistics(self) -> dict:
        """Get collaboration statistics."""
        return {
            "total_edges": self.count(),
            "avg_collaboration_count": (
                self.session.query(func.avg(Collaboration.collaboration_count))
                .scalar() or 0
            ),
            "avg_weight": (
                self.session.query(func.avg(Collaboration.total_weight))
                .scalar() or 0
            ),
        }

    # Relationship Score methods
    def save_relationship_score(
        self,
        author_id_1: str,
        author_id_2: str,
        graphsage_score: Optional[float] = None,
        weighted_score: Optional[float] = None,
        combined_score: Optional[float] = None,
        model_version: Optional[str] = None
    ) -> RelationshipScore:
        """Save or update relationship score."""
        # Ensure consistent ordering
        if author_id_1 > author_id_2:
            author_id_1, author_id_2 = author_id_2, author_id_1

        score = (
            self.session.query(RelationshipScore)
            .filter(
                and_(
                    RelationshipScore.author_id_1 == author_id_1,
                    RelationshipScore.author_id_2 == author_id_2
                )
            )
            .first()
        )

        if score:
            if graphsage_score is not None:
                score.graphsage_score = graphsage_score
            if weighted_score is not None:
                score.weighted_score = weighted_score
            if combined_score is not None:
                score.combined_score = combined_score
            if model_version is not None:
                score.model_version = model_version
            score.computed_at = datetime.utcnow()
        else:
            score = RelationshipScore(
                author_id_1=author_id_1,
                author_id_2=author_id_2,
                graphsage_score=graphsage_score,
                weighted_score=weighted_score,
                combined_score=combined_score,
                model_version=model_version,
            )
            self.session.add(score)

        return score

    def get_top_relations_for_author(
        self,
        author_id: str,
        score_type: str = "combined_score",
        limit: int = 20
    ) -> list[tuple[str, float]]:
        """Get top related authors with scores."""
        scores = (
            self.session.query(RelationshipScore)
            .filter(
                or_(
                    RelationshipScore.author_id_1 == author_id,
                    RelationshipScore.author_id_2 == author_id
                )
            )
            .order_by(getattr(RelationshipScore, score_type).desc())
            .limit(limit)
            .all()
        )

        result = []
        for score in scores:
            other_id = (
                score.author_id_2
                if score.author_id_1 == author_id
                else score.author_id_1
            )
            result.append((other_id, getattr(score, score_type)))

        return result

    def bulk_save_relationship_scores(
        self,
        scores: list[dict]
    ) -> int:
        """Bulk save relationship scores. Returns count saved."""
        count = 0
        for score_data in scores:
            self.save_relationship_score(**score_data)
            count += 1
        return count

    def get_co_authored_works(
        self,
        author_id_1: str,
        author_id_2: str,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "publication_date",
        sort_order: str = "desc",
        from_year: Optional[int] = None,
        to_year: Optional[int] = None
    ) -> tuple[list[Work], int]:
        """
        获取两位作者共同合作的论文列表。

        支持处理合并作者 (alias_ids) 的情况：
        - 如果任一作者是 canonical 记录，会同时查询其所有 alias_ids
        """
        import json

        # 获取两位作者的所有相关 ID (包括 alias_ids)
        def get_all_author_ids(author_id: str) -> list[str]:
            """获取作者及其所有别名 ID"""
            author = self.session.query(Author).filter(Author.id == author_id).first()
            if not author:
                return [author_id]

            ids = [author_id]
            if author.alias_ids:
                try:
                    alias_list = json.loads(author.alias_ids)
                    ids.extend(alias_list)
                except:
                    pass
            return ids

        author_ids_1 = get_all_author_ids(author_id_1)
        author_ids_2 = get_all_author_ids(author_id_2)

        # 子查询：找到作者1参与的所有 work_id
        subq1 = (
            self.session.query(Authorship.work_id)
            .filter(Authorship.author_id.in_(author_ids_1))
            .subquery()
        )

        # 子查询：找到作者2参与的所有 work_id
        subq2 = (
            self.session.query(Authorship.work_id)
            .filter(Authorship.author_id.in_(author_ids_2))
            .subquery()
        )

        # 查询两者都参与的论文
        base_query = (
            self.session.query(Work)
            .filter(Work.id.in_(subq1))
            .filter(Work.id.in_(subq2))
        )

        # 添加年份过滤
        if from_year is not None:
            base_query = base_query.filter(Work.publication_year >= from_year)
        if to_year is not None:
            base_query = base_query.filter(Work.publication_year <= to_year)

        # 计算总数
        total = base_query.count()

        # 排序
        sort_column = getattr(Work, sort_by, Work.publication_date)
        if sort_order == "desc":
            base_query = base_query.order_by(sort_column.desc().nulls_last())
        else:
            base_query = base_query.order_by(sort_column.asc().nulls_last())

        # 分页
        works = base_query.offset(offset).limit(limit).all()

        return works, total
