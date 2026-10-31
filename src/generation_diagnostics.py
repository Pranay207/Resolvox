"""Bounded, content-free diagnostics for failed document generation.

Only known validator code names and explicitly typed transport counters may
cross this boundary. Dynamic code suffixes and all free-form metric strings
are deliberately excluded; neither exception text nor model text is copied.
"""
import math

from .llm import LLMUnavailable


MAX_ATTEMPTS = 2
MAX_COUNTER = 1_000_000
MAX_MILLISECONDS = 86_400_000
MAX_HTTP_STATUSES = 16

_VALIDATOR_CODES = frozenset("""
absence_causal_policy_denial absence_repair_requires_uncertainty source_absence_marked_covered contradicted_effective_return_window
internal_metadata_in_answer source_condition_metadata_mismatch source_condition_restatement_uncertain ordinary_condition_outcome_missing unsupported_reported_item_attribute
answer_constraint_missing conflicting_navigation_source_id
conflicting_semantic_source_identity contradicted_customer_item_premise
contradicted_return_condition contradicted_return_condition_polarity
contradictory_answer_acknowledgment unverified_catalog_fulfillment_event contradicted_reporting_window_status duplicate_source_id echoed_question incomplete_policy_answer
incomplete_policy_coverage inconsistent_covered_refusal invalid_answer
invalid_answer_constraint invalid_answer_constraint_unit
invalid_answer_constraint_value invalid_answer_constraints invalid_citation
invalid_citations invalid_clarification_flag invalid_covered invalid_decision
invalid_facts invalid_generation_inputs invalid_json invalid_language_repair_contract
invalid_personal_money_inputs invalid_personal_money_record invalid_provenance_mode
invalid_query invalid_required_application_inputs invalid_response
invalid_response_fields invalid_semantic_source invalid_semantic_source_authority
invalid_source invalid_timeout invented_delivery_class_membership
invented_delivery_premise invented_placement_premise
language_repair_changed_control_fields missing_citations missing_remedy_prerequisite
missing_required_input not_covered omitted_negative_condition omitted_numeric_constraint
omitted_policy_aspect omitted_quantity_constraint private_identifier
source_credit_membership_exclusion_missing source_credit_paid_fee_condition_missing
source_permission_reversed source_refund_condition_missing source_membership_refund_speed missing_pending_refund_condition unrecorded_refund_quality_claim unrecorded_refund_initiation_claim unrecorded_refund_reference_advice
repeated_answer_sentence missing_refund_initiation_anchor missing_refund_arrival_range unsupported_refund_arrival_date wrong_refund_payment_method unbound_refund_arrival_policy
unbound_answer_constraint unbound_delivery_exception unbound_placement_exception
unbound_required_application_input unbound_return_condition unbound_return_date_input
unbound_return_date_policy unbound_warranty_duration uncited_numeric_or_long_reply
uncited_policy_claim uncited_private_or_external_information
uncited_substantive_clarification uncited_substantive_refusal uncovered_answer
unsupported_action unsupported_answer_constraint unsupported_brand_warranty_coverage
unsupported_brand_warranty_start unsupported_citation unsupported_delivery_clock_availability
unsupported_delivery_exception_entitlement unsupported_delivery_exception_personal_window
unsupported_language unsupported_navigation_label unsupported_navigation_procedure
unsupported_number unsupported_personal_money_amount unsupported_placement_exception_entitlement
unsupported_placement_exception_personal_window
unsupported_quantity_unit unverified_record_completion unverified_record_status
unverified_refund_reference unverified_refund_timeliness conflicted_refund_business_day_role unsupported_physical_store_claim unsupported_category_label wrong_output_language
""".split())
_COUNTERS = frozenset((
    'attempts', 'http_attempts', 'rate_limit_events', 'rate_limit_retries',
    'prompt_eval_count', 'eval_count',
))
_TIMINGS = frozenset((
    'wall_ms', 'load_ms', 'prompt_eval_ms', 'eval_ms',
    'rate_limit_wait_ms', 'rate_limit_planned_wait_ms',
))
_BOOLEANS = frozenset(('cache_hit', 'unavailable'))
_STATUSES = frozenset(('last_http_status', 'rate_limit_last_http_status'))


def validation_code(error):
    """Return a known code, never a dynamic suffix or arbitrary exception text."""
    if isinstance(error, BaseException):
        error = str(error)
    if not isinstance(error, str):
        return 'invalid_response'
    code = error.split(':', 1)[0]
    return code if code in _VALIDATOR_CODES else 'invalid_response'


def safe_attempt_metrics(value):
    """Copy only finite, bounded, explicitly typed metric values."""
    if not isinstance(value, dict):
        return {}
    result = {}
    for key in _BOOLEANS:
        if type(value.get(key)) is bool:
            result[key] = value[key]
    for key in _COUNTERS:
        item = value.get(key)
        if type(item) is int and 0 <= item <= MAX_COUNTER:
            result[key] = item
    for key in _TIMINGS:
        item = value.get(key)
        if type(item) in (int, float) and 0 <= item <= MAX_MILLISECONDS and math.isfinite(item):
            result[key] = item
    for key in _STATUSES:
        item = value.get(key)
        if type(item) is int and 100 <= item <= 599:
            result[key] = item
    statuses = value.get('http_statuses')
    if isinstance(statuses, (list, tuple)):
        result['http_statuses'] = [item for item in statuses[:MAX_HTTP_STATUSES]
                                   if type(item) is int and 100 <= item <= 599]
    reason = value.get('rate_limit_exhausted')
    if isinstance(reason, str) and reason in ('retry_limit', 'wait_budget'):
        result['rate_limit_exhausted'] = reason
    return result


def _diagnostics(errors, attempt_metrics, *, failure_kind, attempts=None):
    metrics = [safe_attempt_metrics(item) for item in attempt_metrics[:MAX_ATTEMPTS]]
    errors = [validation_code(item) for item in errors[:MAX_ATTEMPTS]]
    attempts = len(metrics) if attempts is None else attempts
    attempts = max(0, min(MAX_ATTEMPTS, attempts)) if type(attempts) is int else 0
    return {'generation_failed': True, 'failure_kind': failure_kind,
            'generation_attempts': attempts, 'repair_attempted': attempts > 1,
            'repair_errors': errors, 'validation_error': errors[-1] if errors else None,
            'attempt_metrics': metrics}


class GenerationValidationError(ValueError):
    """ValueError-compatible carrier containing only sanitized diagnostics."""
    def __init__(self, errors, attempt_metrics):
        self.diagnostics = _diagnostics(errors, attempt_metrics, failure_kind='validation')
        super().__init__('document_generation_failed:' +
                         (self.diagnostics['validation_error'] or 'invalid_response'))


class GenerationUnavailable(LLMUnavailable):
    """LLMUnavailable-compatible carrier without provider exception text."""
    def __init__(self, errors, attempt_metrics):
        self.diagnostics = _diagnostics(errors, attempt_metrics, failure_kind='model_unavailable')
        super().__init__('model_unavailable_or_invalid')


def failure_diagnostics(exc, *, attempts=0, last_metrics=None):
    """Extract a defensive copy, or describe a pre-carrier failure safely."""
    if isinstance(exc, (GenerationValidationError, GenerationUnavailable)):
        data = exc.diagnostics
        return _diagnostics(data['repair_errors'], data['attempt_metrics'],
                            failure_kind='model_unavailable' if isinstance(exc, LLMUnavailable) else 'validation',
                            attempts=data['generation_attempts'])
    metrics = [safe_attempt_metrics(last_metrics)] if attempts else []
    errors = [] if isinstance(exc, LLMUnavailable) else [validation_code(exc)]
    return _diagnostics(errors, metrics,
                        failure_kind='model_unavailable' if isinstance(exc, LLMUnavailable) else 'validation',
                        attempts=attempts)


def failure_validation_error(exc):
    """Keep the existing failure label shape without copying private text."""
    if isinstance(exc, GenerationValidationError):
        return 'document_generation_failed:' + (failure_diagnostics(exc)['validation_error'] or 'invalid_response')
    return validation_code(exc) if isinstance(exc, ValueError) else 'model_unavailable_or_invalid'
