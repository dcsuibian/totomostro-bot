from sqlalchemy import select, func, distinct
from sqlalchemy.orm import Session

from models import get_session, Match, MatchResult, MatchTeam, BattleRecord


class TotomostroRepository:
    """Totomostro 数据仓库"""

    def __init__(self, session: Session | None = None):
        self._session = session

    @property
    def session(self) -> Session:
        if self._session is None:
            self._session = get_session()
        return self._session

    def close(self):
        if self._session:
            self._session.close()
            self._session = None

    # ========== 写入 ==========
    def add_match(
            self,
            choice: str,
            teams: list[tuple[str, float]],  # [(name, odds), ...]
            result: str | None = None,  # 'win' / 'lose' / 'draw' / None
            bet_amount: int = 0,
    ) -> Match:
        """添加比赛记录"""
        winner = choice if result == MatchResult.WIN.value else None

        match = Match(
            choice=choice,
            winner=winner,
            result=result,
            bet_amount=bet_amount,
        )
        self.session.add(match)
        self.session.flush()

        # 参赛队伍
        for name, odds in teams:
            self.session.add(MatchTeam(
                match_id=match.id,
                name=name,
                odds=odds,
            ))

        # 赢了才记录对战
        if result == MatchResult.WIN.value and winner:
            for name, _ in teams:
                if name != winner:
                    self.session.add(BattleRecord(
                        match_id=match.id,
                        winner=winner,
                        loser=name,
                    ))

        self.session.commit()
        return match

    # ========== 内部方法 ==========
    def _get_recent_match_ids(self, limit: int | None) -> list[int] | None:
        """获取最近N场比赛的ID，None表示不限制"""
        if limit is None:
            return None
        rows = self.session.execute(
            select(Match.id)
            .where(Match.result.isnot(None))
            .order_by(Match.id.desc())
            .limit(limit)
        ).scalars().all()
        return list(rows) if rows else []

    # ========== 统计查询 ==========
    def total_rounds(self, limit: int | None = None) -> int:
        """
        已完成的比赛总数
        :param limit: 只统计最近N场，None表示全部
        """
        if limit is None:
            return self.session.scalar(
                select(func.count(Match.id)).where(Match.result.isnot(None))
            ) or 0
        return min(limit, self.session.scalar(
            select(func.count(Match.id)).where(Match.result.isnot(None))
        ) or 0)

    def wins(self, limit: int | None = None) -> int:
        """
        赢的场次
        :param limit: 只统计最近N场
        """
        match_ids = self._get_recent_match_ids(limit)
        query = select(func.count(Match.id)).where(Match.result == MatchResult.WIN.value)
        if match_ids is not None:
            if not match_ids:
                return 0
            query = query.where(Match.id.in_(match_ids))
        return self.session.scalar(query) or 0

    def losses(self, limit: int | None = None) -> int:
        """
        输的场次
        :param limit: 只统计最近N场
        """
        match_ids = self._get_recent_match_ids(limit)
        query = select(func.count(Match.id)).where(Match.result == MatchResult.LOSE.value)
        if match_ids is not None:
            if not match_ids:
                return 0
            query = query.where(Match.id.in_(match_ids))
        return self.session.scalar(query) or 0

    def win_rate(self, limit: int | None = None) -> float:
        """
        胜率
        :param limit: 只统计最近N场
        """
        total = self.total_rounds(limit)
        return self.wins(limit) / total if total > 0 else 0.0

    # ========== 怪物相关查询 ==========
    def get_monster_win_rate(self, name: str, limit: int | None = None) -> float | None:
        """
        获取某怪物作为我方选择时的胜率
        :param name: 怪物名称
        :param limit: 只统计最近N场
        """
        match_ids = self._get_recent_match_ids(limit)

        total_query = select(func.count(Match.id)).where(
            Match.choice == name,
            Match.result.isnot(None)
        )
        wins_query = select(func.count(Match.id)).where(
            Match.choice == name,
            Match.result == MatchResult.WIN.value
        )

        if match_ids is not None:
            if not match_ids:
                return None
            total_query = total_query.where(Match.id.in_(match_ids))
            wins_query = wins_query.where(Match.id.in_(match_ids))

        total = self.session.scalar(total_query) or 0
        if total == 0:
            return None
        wins = self.session.scalar(wins_query) or 0
        return wins / total

    def get_head_to_head(self, a: str, b: str, limit: int | None = None) -> tuple[int, int]:
        """
        获取 a 对 b 的战绩
        :param a: 怪物A名称
        :param b: 怪物B名称
        :param limit: 只统计最近N场
        :return: (a赢b的次数, 总交手次数)
        """
        match_ids = self._get_recent_match_ids(limit)

        a_wins_query = select(func.count(BattleRecord.id)).where(
            BattleRecord.winner == a,
            BattleRecord.loser == b
        )
        b_wins_query = select(func.count(BattleRecord.id)).where(
            BattleRecord.winner == b,
            BattleRecord.loser == a
        )

        if match_ids is not None:
            if not match_ids:
                return 0, 0
            a_wins_query = a_wins_query.where(BattleRecord.match_id.in_(match_ids))
            b_wins_query = b_wins_query.where(BattleRecord.match_id.in_(match_ids))

        a_wins = self.session.scalar(a_wins_query) or 0
        b_wins = self.session.scalar(b_wins_query) or 0
        return a_wins, a_wins + b_wins

    def get_monster_total_wins(self, name: str, limit: int | None = None) -> int:
        """某怪物赢过多少场"""
        match_ids = self._get_recent_match_ids(limit)
        query = select(func.count(BattleRecord.id)).where(BattleRecord.winner == name)
        if match_ids is not None:
            if not match_ids:
                return 0
            query = query.where(BattleRecord.match_id.in_(match_ids))
        return self.session.scalar(query) or 0

    def get_monster_total_losses(self, name: str, limit: int | None = None) -> int:
        """某怪物输过多少场"""
        match_ids = self._get_recent_match_ids(limit)
        query = select(func.count(BattleRecord.id)).where(BattleRecord.loser == name)
        if match_ids is not None:
            if not match_ids:
                return 0
            query = query.where(BattleRecord.match_id.in_(match_ids))
        return self.session.scalar(query) or 0

    def get_all_monsters(self) -> list[str]:
        """获取所有怪物名称"""
        return list(self.session.scalars(
            select(distinct(MatchTeam.name)).order_by(MatchTeam.name)
        ))

    # ========== 记录查询 ==========
    def get_recent_matches(self, limit: int = 500) -> list[Match]:
        """获取最近完成的比赛"""
        return list(self.session.scalars(
            select(Match)
            .where(Match.result.isnot(None))
            .order_by(Match.id.desc())
            .limit(limit)
        ))

    def get_matches_as_dicts(self, limit: int = 500) -> list[dict]:
        """获取比赛记录（字典格式，方便处理）"""
        matches = self.get_recent_matches(limit)
        return [{
            'choice': m.choice,
            'winner': m.winner,
            'result': m.result,
            'is_win': m.is_winner,
            'bet_amount': m.bet_amount,
            'all_team_names': m.all_team_names,
        } for m in matches]

    def get_battle_stats(self, limit: int | None = None) -> dict[str, dict[str, int]]:
        """
        获取所有对战统计
        :param limit: 只统计最近N场
        :return: {winner: {loser: count, ...}, ...}
        """
        match_ids = self._get_recent_match_ids(limit)
        query = select(BattleRecord)
        if match_ids is not None:
            if not match_ids:
                return {}
            query = query.where(BattleRecord.match_id.in_(match_ids))

        records = self.session.scalars(query).all()
        stats: dict[str, dict[str, int]] = {}
        for r in records:
            if r.winner not in stats:
                stats[r.winner] = {}
            if r.loser not in stats[r.winner]:
                stats[r.winner][r.loser] = 0
            stats[r.winner][r.loser] += 1
        return stats


if '__main__' == __name__:
    repo = TotomostroRepository()
    print("Total rounds:", repo.total_rounds())
    print("Wins:", repo.wins())
    print("Losses:", repo.losses())
    print("Win rate:", repo.win_rate())
    print("All monsters:", repo.get_all_monsters())
    repo.close()
