"""Project reserved audit hash maps out of a copied model facts payload.

Host validators and traces must keep the original facts. Exact paths and strict
map shapes keep unrelated business fields, source IDs and authority untouched.
"""
import copy
import re


_AUDIT_MAP_PATHS = (
    ('calculation_source_sha256',),
    ('reporting_time_check', 'source_sha256'),
    ('operational_escalation', 'source_sha256'),
    ('return_condition_policy', 'source_sha256'),
    ('warranty_duration', 'assured', 'source_sha256'),
    ('warranty_duration', 'brand', 'source_sha256'),
    ('source_semantic_constraints', '*', 'source_sha256'),
    ('source_semantic_constraints', '*', 'source_provenance_sha256'),
)
_SHA256 = re.compile(r'[0-9a-fA-F]{64}')


def _omit_audit_map(value, path):
    key = path[0]
    if key == '*':
        if isinstance(value, list):
            for record in value:
                _omit_audit_map(record, path[1:])
    elif isinstance(value, dict):
        if len(path) > 1:
            _omit_audit_map(value.get(key), path[1:])
        else:
            record = value.get(key)
            if (isinstance(record, dict) and record
                    and all(isinstance(source_id, str) and source_id.strip()
                            and isinstance(digest, str) and _SHA256.fullmatch(digest)
                            for source_id, digest in record.items())):
                del value[key]


def project_inference_facts(facts):
    """Return an independent copy with only valid reserved audit maps omitted."""
    projected = copy.deepcopy(facts)
    for path in _AUDIT_MAP_PATHS:
        _omit_audit_map(projected, path)
    return projected
