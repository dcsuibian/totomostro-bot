"""机器学习选队策略"""
import logging
import pickle
from pathlib import Path

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder

from recognizer import RecognizedTeam
from repository import TotomostroRepository

logger = logging.getLogger(__name__)


class MlStrategy:
    """基于梯度提升的选队策略"""

    def __init__(self, repo: TotomostroRepository, model_path: Path):
        self.repo = repo
        self.model_path = model_path

        self.label_encoder = LabelEncoder()
        self.model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            min_samples_split=5,
            random_state=42,
        )
        self.is_trained = False
        self._monster_strength: dict[str, float] = {}

        self._load_model()
        self.current_win_prob: float = 0.5

    # ========== 模型持久化 ==========

    def _load_model(self):
        """加载模型"""
        if not self.model_path.exists():
            return

        try:
            data = pickle.loads(self.model_path.read_bytes())
            self.model = data['model']
            self.label_encoder = data['encoder']
            self.is_trained = data.get('is_trained', False)
            self._monster_strength = data.get('monster_strength', {})
            n_monsters = len(self.label_encoder.classes_) if self.is_trained else 0
            logger.info(f'已加载模型，{n_monsters} 个怪物')
        except Exception as e:
            logger.warning(f'加载模型失败: {e}')

    def _save_model(self):
        """保存模型"""
        data = {
            'model': self.model,
            'encoder': self.label_encoder,
            'is_trained': self.is_trained,
            'monster_strength': self._monster_strength,
        }
        self.model_path.write_bytes(pickle.dumps(data))

    # ========== 训练 ==========

    def train(self):
        """训练模型"""
        matches = self.repo.get_recent_matches(5000)
        if len(matches) < 20:
            logger.info(f'数据不足（{len(matches)}场），暂不训练')
            return

        # 计算怪物强度
        self._monster_strength = self._calculate_monster_strength(matches)

        # 收集所有怪物
        all_monsters = set()
        for m in matches:
            all_monsters.update(m.all_team_names)
        all_monsters = sorted(list(all_monsters))

        if len(all_monsters) < 2:
            logger.info('怪物种类不足，暂不训练')
            return

        self.label_encoder.fit(all_monsters)
        n_monsters = len(all_monsters)

        # 构建训练数据
        x, y = [], []
        for m in matches:
            if not m.choice or m.result is None:
                continue

            teams = m.all_team_names
            if len(teams) < 2:
                continue

            try:
                features = self._build_features(m.choice, teams, n_monsters)
                x.append(features)
                y.append(1 if m.is_winner else 0)
            except ValueError:
                continue

        if len(x) < 20:
            logger.info(f'有效样本不足（{len(x)}），暂不训练')
            return

        x = np.array(x)
        y = np.array(y)

        self.model.fit(x, y)
        self.is_trained = True
        self._save_model()

        logger.info(f'训练完成: {len(x)}样本, 历史胜率{y.mean():.1%}')

    def _calculate_monster_strength(self, matches) -> dict[str, float]:
        """
        计算怪物强度
        强度 = 该怪物赢的次数 / 该怪物参赛次数
        """
        wins: dict[str, int] = {}
        total: dict[str, int] = {}

        for m in matches:
            teams = m.all_team_names
            winner = m.winner

            for t in teams:
                total[t] = total.get(t, 0) + 1

            if winner:
                wins[winner] = wins.get(winner, 0) + 1

        strength = {}
        for name in total:
            if total[name] >= 3:
                strength[name] = wins.get(name, 0) / total[name]
            else:
                strength[name] = 0.5  # 样本不足用0.5

        return strength

    def _build_features(self, choice: str, all_teams: list[str], n_monsters: int) -> np.ndarray:
        """
        构建特征向量：
        [choice_onehot(n), opponents_multihot(n), choice_strength, opponents_avg_strength, n_opponents]
        """
        # 我选的怪物 one-hot
        choice_idx = self.label_encoder.transform([choice])[0]
        choice_onehot = np.zeros(n_monsters)
        choice_onehot[choice_idx] = 1

        # 对手 multi-hot
        opponents = [t for t in all_teams if t != choice]
        opp_multihot = np.zeros(n_monsters)
        for opp in opponents:
            try:
                opp_idx = self.label_encoder.transform([opp])[0]
                opp_multihot[opp_idx] = 1
            except ValueError:
                pass

        # 额外特征
        choice_strength = self._monster_strength.get(choice, 0.5)
        opp_strengths = [self._monster_strength.get(o, 0.5) for o in opponents]
        avg_opp_strength = np.mean(opp_strengths) if opp_strengths else 0.5
        max_opp_strength = max(opp_strengths) if opp_strengths else 0.5
        n_opponents = len(opponents) / 4.0  # 归一化

        extra_features = np.array([
            choice_strength,
            avg_opp_strength,
            max_opp_strength,
            n_opponents,
            choice_strength - avg_opp_strength,  # 强度差
        ])

        return np.concatenate([choice_onehot, opp_multihot, extra_features])

    # ========== 选队 ==========

    def select_team(self, teams: list[RecognizedTeam]) -> RecognizedTeam:
        """选择预测胜率最高的队伍"""
        if not teams:
            raise ValueError('没有可选队伍')

        # 数据不足时用启发式策略
        if not self.is_trained or self.repo.total_rounds() < 20:
            selected, prob = self._select_by_heuristic(teams)
            self.current_win_prob = prob
            return selected

        n_monsters = len(self.label_encoder.classes_)
        team_names = [t.name for t in teams]

        best_team = None
        best_prob = -1

        for team in teams:
            try:
                features = self._build_features(team.name, team_names, n_monsters)
                prob = self.model.predict_proba([features])[0][1]
            except (ValueError, IndexError):
                # 未见过的怪物，用历史胜率或默认值
                prob = self._get_fallback_prob(team.name)

            logger.info(f'  {team.name}: 预测胜率 {prob:.1%}')

            if prob > best_prob:
                best_prob = prob
                best_team = team

        self.current_win_prob = best_prob

        logger.info(f'[策略] 选择 {best_team.name} (预测胜率 {best_prob:.1%})')
        return best_team

    def _select_by_heuristic(self, teams: list[RecognizedTeam]) -> tuple[RecognizedTeam, float]:
        """
        启发式选队（数据不足时使用）
        优先选历史胜率高的，没有历史数据则选第一个
        """
        best_team = teams[0]
        best_score = -1

        for team in teams:
            wr = self.repo.get_monster_win_rate(team.name)
            strength = self._monster_strength.get(team.name, 0.5)

            if wr is not None:
                score = wr
            else:
                score = strength

            if score > best_score:
                best_score = score
                best_team = team

        # 计算预估胜率
        base_prob = 1.0 / len(teams)
        adjusted_prob = min(base_prob * (1 + best_score), 0.9)

        logger.info(f'[策略-启发式] 选择 {best_team.name} (预估胜率 {adjusted_prob:.1%})')
        return best_team, adjusted_prob

    def _get_fallback_prob(self, name: str) -> float:
        """获取未知怪物的预测概率"""
        wr = self.repo.get_monster_win_rate(name)
        if wr is not None:
            return wr
        return self._monster_strength.get(name, 0.5)

    # ========== 下注 ==========

    def calculate_bet_amount(self) -> int:
        """
        动态计算下注金额
        根据场次和胜率调整
        """
        total = self.repo.total_rounds()
        prob = self.current_win_prob

        if total < 30:
            return 1

        if total < 100:
            if prob >= 0.6:
                return 50
            elif prob >= 0.5:
                return 10
            elif prob >= 0.4:
                return 5
            return 1

        # 100场以上，根据预测胜率下注
        if prob >= 0.7:
            return 9999
        elif prob >= 0.6:
            return 1000
        elif prob >= 0.55:
            return 500
        elif prob >= 0.5:
            return 100
        elif prob >= 0.4:
            return 50
        elif prob >= 0.3:
            return 10
        return 1