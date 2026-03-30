"""하위 호환 shim — 모든 public 심볼을 core/policy/eval에서 re-export한다.

기존에 `from tcp_batching_core import ...`으로 접근하던 코드가
수정 없이 동작하도록 유지하기 위한 파일이다.
"""

from core.constants import (  # noqa: F401
    DEFAULT_SEED,
    FIXED_BATCH_GRID,
    FIXED_FLUSH_GRID_MS,
    OBJECTIVE_WEIGHTS,
    REVERSE_SCORE_METRICS,
    STATIC_OBJECTIVE_WEIGHTS,
    VIDEO_OBJECTIVE_WEIGHTS,
    snap,
    safe_mean,
    safe_quantile,
)
from core.transport import (  # noqa: F401
    TransportConfig,
    serialize_transport_config,
)
from core.workload import (  # noqa: F401
    StaticFileConfig,
    VideoTraceConfig,
    WorkloadConfig,
    build_policy_features,
    frame_interval_ms,
    generate_static_file_events,
    generate_workload,
    load_video_trace_events,
    resolve_repo_root,
    scenario_id,
    serialize_workload_config,
    workload_kind,
)
from core.simulator import (  # noqa: F401
    evaluate_fixed_policy_grid,
    run_simulation,
)
from policy.legacy import (  # noqa: F401
    PolicyConfig,
    resolve_policy,
)
from eval.scoring import (  # noqa: F401
    build_metric_ranges,
    normalize_metric,
    score_policy_result,
    score_policy_rows,
    select_best_fixed_config,
)

_safe_mean = safe_mean
_safe_quantile = safe_quantile
_frame_interval_ms = frame_interval_ms
fixed_sweep = evaluate_fixed_policy_grid
build_score_bounds = build_metric_ranges
score_rows = score_policy_rows
score_candidate_row = score_policy_result
pick_oracle = select_best_fixed_config
