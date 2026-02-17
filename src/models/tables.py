from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Float, Integer, Index
from sqlalchemy.orm import mapped_column, Mapped, relationship

from models.base import Base


class MatchResult(str, Enum):
    """比赛结果"""
    WIN = 'win'
    LOSE = 'lose'
    DRAW = 'draw'  # 平局，如果有的话


class Match(Base):
    """比赛记录"""
    __tablename__ = 'match'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    choice: Mapped[str] = mapped_column(String(100), index=True, comment='我选的队伍')
    winner: Mapped[str | None] = mapped_column(String(100), nullable=True, comment='胜者，输了或平局时为空')
    result: Mapped[str | None] = mapped_column(String(100), nullable=True, comment='"win"/"lose"/"draw"/None')
    bet_amount: Mapped[int] = mapped_column(Integer, default=0, comment='投注金额')
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # 关联
    teams: Mapped[list['MatchTeam']] = relationship(back_populates='match', cascade='all, delete-orphan')

    @property
    def all_team_names(self) -> list[str]:
        return [t.name for t in self.teams]

    @property
    def is_winner(self) -> bool:
        """我是否赢了"""
        return self.result == MatchResult.WIN.value


class MatchTeam(Base):
    """比赛参赛队伍"""
    __tablename__ = 'match_team'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey('match.id', ondelete='CASCADE'))
    name: Mapped[str] = mapped_column(String(100), index=True)
    odds: Mapped[float | None] = mapped_column(Float, nullable=True, comment='倍率')

    match: Mapped['Match'] = relationship(back_populates='teams')


class BattleRecord(Base):
    """
    对战记录
    只在赢的时候记录（因为输了不知道最终谁会赢）
    winner 战胜了 loser
    """
    __tablename__ = 'battle_record'
    __table_args__ = (
        Index('idx_battle_winner_loser', 'winner', 'loser'),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey('match.id', ondelete='CASCADE'))
    winner: Mapped[str] = mapped_column(String(100), index=True)
    loser: Mapped[str] = mapped_column(String(100), index=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
