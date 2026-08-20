"""OctoMarket replay and learning engine."""

from .comparison import compare_plan_to_outcome
from .decision_score import SCORING_SCHEMA_VERSION, grade_from_score
from .market_snapshot import capture_market_snapshot
from .pattern_features import PATTERN_SCHEMA_VERSION, extract_pattern_features
from .pattern_service import PatternService, get_pattern_service, index_closed_record, reset_pattern_service
from .pattern_store import PatternStore, get_pattern_store, reset_pattern_store
from .replay_memory import ReplayMemory, get_replay_memory, reset_replay_memory
from .replay_record import build_replay_record_from_plan
from .scoring_service import ScoringService, apply_scoring, get_scoring_service, score_replay_record
from .replay_session import ReplaySessionManager, get_replay_session, is_replay_mode
from .replay_store import ReplayStore, get_replay_store, reset_replay_store

__all__ = [
    "ReplaySessionManager",
    "get_replay_session",
    "is_replay_mode",
    "compare_plan_to_outcome",
    "capture_market_snapshot",
    "PATTERN_SCHEMA_VERSION",
    "extract_pattern_features",
    "PatternStore",
    "get_pattern_store",
    "reset_pattern_store",
    "PatternService",
    "get_pattern_service",
    "index_closed_record",
    "reset_pattern_service",
    "SCORING_SCHEMA_VERSION",
    "grade_from_score",
    "ScoringService",
    "get_scoring_service",
    "score_replay_record",
    "apply_scoring",
    "ReplayStore",
    "get_replay_store",
    "reset_replay_store",
    "ReplayMemory",
    "get_replay_memory",
    "reset_replay_memory",
    "build_replay_record_from_plan",
]
