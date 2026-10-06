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

# Kinematic arrival model for "who gets there first".
# Phase 2 revision: the Phase 1 placeholders (0.2 s / 7.5 m/s / 4 m/s^2) were never
# validated. We use the published Spearman (2018) pitch-control parameters instead
# (reaction 0.7 s, top speed 5 m/s, time sigma 0.45 s), with a body-reach block zone
# so a defender already standing in a lane stops the ball without "reacting".
REACTION_TIME_S = 0.7
MAX_SPEED_M_S = 5.0
MAX_ACCEL_M_S2 = 4.0  # unused by the Phase 2 model; kept for reference
TIME_SIGMA_S = 0.45
TIME_SIGMA_EXTRAPOLATED_S = 0.9  # off-camera players: SkillCorner estimate, so less certain
REACH_M = 1.0  # leg/body reach: ball passing within this of a defender is blocked
LUNGE_M = 2.0  # beyond reach, reaction time ramps in over this distance

# Ball model
PASS_RELEASE_S = 0.2  # set-up time before the ball leaves the foot
GROUND_PASS_SPEED_M_S = 15.0
LOFTED_PASS_SPEED_M_S = 17.0  # horizontal speed of a driven/lofted long ball
LOFTED_PASS_M = 25.0  # passes longer than this are assumed to be in the air
LOFTED_LANDING_M = 6.0  # a lofted ball can only be won near its landing spot
CONTROL_TIME_S = 0.1
LANE_STEP_M = 1.5  # spacing of interception check points along a pass
CARRY_SPEED_M_S = 5.5  # top speed with the ball at feet
CARRY_ACCEL_M_S2 = 6.0  # with the ball: ~1.55 s to cover the first 6 m from standing
CARRY_REACTION_S = 0.3  # defenders already watching the carrier react to a dribble fast
CARRY_DISTANCES_M = (6.0, 12.0)
CARRY_ANGLES_DEG = (0.0, 40.0, -40.0)
MAX_OPTION_RANGE_M = 50.0
PASS_ACCURACY_SCALE_M = 55.0  # long passes lose accuracy: exp(-(L/scale)^2)
# Rush: calibrated on SkillCorner xPass of played passes in match 2017461 (650 passes).
# xPass is ~0.96 when the nearest defender is >1.5 s away, ~0.88 for short and ~0.75
# for 25 m+ passes once he is within ~1.1 s.
RUSH_TIME_S = 1.2  # nearest-defender arrival time at which the carrier is half "rushed"
RUSH_WIDTH_S = 0.2
RUSH_BASE_PENALTY = 0.08  # accuracy loss on any pass when fully rushed
RUSH_LONG_PASS_PENALTY = 0.17  # extra loss, scaling up to a 40 m pass

# Carrier momentum: running the wrong way costs time to stop and turn
CARRIER_TURN_DECEL_M_S2 = 5.0
MAX_PASS_TURN_DELAY_S = 0.4  # a pass can be played on the half-turn, so cap the delay
MOVING_CARRIER_M_S = 1.5  # below this the carrier is treated as standing (no momentum)

# What counts as a useful (escape) option
PROGRESS_OPTION_M = 5.0
SWITCH_OPTION_M = 25.0
BYPASS_OPTION_N = 2

# Lane Tax evaluation timing: the headline tax is read just before the carrier releases
# the ball (the moment he actually chooses); also reported 1 s in and at its peak.
RELEASE_LOOKBACK_FRAMES = 3
PEAK_STEP_FRAMES = 2
LANE_SAMPLE_POINTS = 5  # Phase 1 corridor model (review visuals only)

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
