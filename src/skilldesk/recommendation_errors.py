"""Fixed recommendation diagnostics. Never include provider or reviewed text."""

FAILURE_MESSAGES = {
    'invalid_summary': 'The agent returned an invalid recommendation summary.',
    'invalid_recommendations': 'The agent returned an invalid recommendation list; expected at most six recommendations.',
    'unknown_skill': 'The agent recommended a skill outside the bundled collections.',
    'duplicate_recommendation': 'The agent returned a duplicate recommendation.',
    'invalid_reason': 'The agent returned an invalid recommendation reason; expected 1 to 1200 characters.',
    'invalid_evidence_count': 'Each recommendation must cite between one and three supporting excerpt IDs.',
    'unknown_evidence_id': 'The agent cited supporting excerpt IDs outside the reviewed sample.',
    'invalid_first_step': 'The agent returned an invalid first step.',
    'invalid_covered': 'The agent returned invalid overlap comparisons.',
    'unknown_covered_skill': 'The agent cited an unknown skill in its overlap comparison.',
    'invalid_covered_item': 'The agent returned conflicting or invalid overlap comparisons.',
    'unknown': 'This recommendation job failed. The cause is unknown.',
}
FAILURE_STAGES = frozenset({'preparing', 'generating', 'validating'})


class RecommendationError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(FAILURE_MESSAGES[code]+' Try again with the reviewed sample.')


def safe_failure_fields(code, stage):
    return dict(
        failure_code=code if isinstance(code, str) and code in FAILURE_MESSAGES else 'unknown',
        failure_stage=stage if isinstance(stage, str) and stage in FAILURE_STAGES else 'unknown',
    )
