"""Locked Phase 1 decisions for Lane Tax v1.

These constants are the contract for Phase 2 metric implementation.
Change them only with a documented revision in docs/phase1-decisions.md.
"""

from __future__ import annotations

# Default exploration / development match
DEFAULT_MATCH_ID = 2017461

# Press event subtypes included in the metric universe
PRESS_SUBTYPES = ("pressure", "pressing", "recovery_press", "counter_press")

# Only score presses while the ball-side phase is one of these
FOCUS_ATTACK_PHASES = ("build_up", "create", "direct")

# Tracking sample rate (SkillCorner open tracking JSONL)
TRACKING_HZ = 10

# Time windows (seconds → frames at TRACKING_HZ)
TAX_WINDOW_S = 1.0
OUTCOME_WINDOW_S = 3.0

TAX_WINDOW_FRAMES = int(TAX_WINDOW_S * TRACKING_HZ)  # 10
OUTCOME_WINDOW_FRAMES = int(OUTCOME_WINDOW_S * TRACKING_HZ)  # 30

# Lane geometry (metres, pitch coords with origin at centre)
LANE_LENGTH_M = 18.0
LANE_HALF_WIDTH_M = 4.0
# Progressive / wide corridors use this length; back lane uses shorter depth
BACK_LANE_LENGTH_M = 12.0

# Kinematic arrival model for "who gets there first"
REACTION_TIME_S = 0.2
MAX_ACCEL_M_S2 = 4.0
MAX_SPEED_M_S = 7.5

# Openness: probability-like score that offense reaches a lane sample point first.
# Lane openness is the mean over sample points along the corridor midline.
LANE_SAMPLE_POINTS = 5

# Outcome label: progressive if carrier/ball advances at least this far
# along the attacking direction within OUTCOME_WINDOW_S, without possession loss.
PROGRESSIVE_ADVANCE_M = 8.0

# Possession-loss outcomes from SkillCorner associated possession end types
POSSESSION_LOSS_END_TYPES = (
    "possession_loss",
    "clearance",
)

# Baseline proximity radii
NEAREST_DEFENDER_BASELINE = "nearest_defender_distance_m"
DEFENDERS_WITHIN_RADIUS_M = 5.0

# Review sample size for Phase 1 hand-check
REVIEW_SAMPLE_SIZE = 15
REVIEW_SEED = 42
