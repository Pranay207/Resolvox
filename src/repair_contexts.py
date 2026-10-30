"""Bounded evidence-only inputs for final public-policy repair attempts.

No business answer strings or practice fixtures are read. Every duration/count
is rebound to actual supplied policy text before a focused view is returned.
"""
import json
import re
from datetime import date
from .placement_conditions import placement_exception_status
from .grounding import _numeric_text
from .inference_facts import project_inference_facts


def _active(source, reference):
    if source.get('doc_type') != 'policy' or source.get('status') != 'current':
        return False
    if source.get('effective_from'):
        try:
            if date.fromisoformat(source['effective_from']) > date.fromisoformat(str(reference)[:10]):
                return False
        except (TypeError, ValueError):
            return False
    return True


def unresolved_return_window_inputs(facts, sources):
    status = placement_exception_status(facts, sources)
    if not status or status['applicability'] != 'unknown' or status['input_origin'] != 'missing':
        return None
    policy = facts['return_policy']
    ids = set(status['source_ids']) | set(policy['source_ids'])
    reference = facts['reference_date']
    by_id = {source['id']: source for source in sources}
    if not ids <= by_id.keys():
        return None
    for source in sources:
        text = re.sub(r'[*`]', '', source.get('text', ''))
        if (_active(source, reference) and re.search(r'\breturn\s+windows?\b.{0,180}\bdelivery\b', text, re.I | re.S)):
            ids.add(source['id'])
        if source.get('doc_type') == 'catalog' and source.get('status') == 'current':
            try:
                row = json.loads(source['text'])
            except (ValueError, TypeError):
                continue
            if isinstance(row, dict) and row.get('return_category') == policy['category']:
                ids.add(source['id'])
    selected = [source for source in sources if source['id'] in ids]
    if sum(len(source['text']) for source in selected) > 4800:
        return None
    relevant = [item for item in facts.get('answer_constraints', [])
                if item.get('key') == 'return_policy.window_calendar_days']
    return {'sources': selected, 'facts': project_inference_facts(facts), 'placement_scope': status}


def delivery_attempt_inputs(facts, sources, constraints):
    requested = [item for item in constraints
                 if item.get('key') == 'delivery_policy.delivery_attempt_limit']
    if len(requested) != 1 or requested[0].get('kind') != 'number':
        return None
    limit = requested[0]['value']
    policy = facts.get('delivery_policy', {})
    if type(limit) is not int or policy.get('delivery_attempt_limit') != limit:
        return None
    by_id = {source['id']: source for source in sources}
    ids = set(requested[0]['source_ids'])
    if not ids or not ids <= by_id.keys():
        return None
    for ident in ids:
        source = by_id[ident]
        if not _active(source, facts.get('reference_date')):
            return None
        values = {int(match) for match in re.findall(r'\bup\s+to\s+(\d+)\s+delivery\s+attempts?\b',
                                                     _numeric_text(source['text']), re.I)}
        if values != {limit}:
            return None
    # Keep actual linked sections, including the conditions on consequences.
    pending = list(ids)
    while pending:
        source = by_id[pending.pop()]
        for ident in re.findall(r'\b[A-Z][A-Z0-9]{1,15}-\d{1,4}\b', source['text']):
            if ident in ids:
                continue
            if ident not in by_id or not _active(by_id[ident], facts.get('reference_date')):
                return None
            ids.add(ident); pending.append(ident)
            if len(ids) > 5:
                return None
    selected = [source for source in sources if source['id'] in ids]
    if sum(len(source['text']) for source in selected) > 4800:
        return None
    semantic = [item for item in facts.get('source_semantic_constraints', [])
                if set(item.get('source_ids', [])) <= ids]
    return {'sources': selected, 'facts': {'delivery_policy': policy,
        'answer_constraints': requested, 'source_semantic_constraints': semantic}}



def fee_only_restatement_inputs(query, facts, sources, reference_date):
    """Focus only a collection-price question, preserving original host facts."""
    if (not re.search(r'\b(?:pick[ -]?up|collect\w*)\b|पिकअप|संग्रह', query, re.I)
            or not re.search(r'\b(?:free|fees?|charg\w*|cost\w*)\b|मुफ्त|फ्री|शुल्क|चार्ज', query, re.I)
            or re.search(r'refund|replace|money\s+back|रिफंड|रिफ़ंड|धनवापसी|रिप्लेस|प्रतिस्थापन|paise\s+(?:wapas|vaapas)|पैसे\s*वापस', query, re.I)):
        return None
    fee = re.compile(r'\b(?:reverse\s+)?pick[ -]?up\s+(?:fees?|charges?)\b|\bcollection\s+(?:fees?|charges?)\b', re.I)
    selected = [source for source in sources if _active(source, reference_date)
                and isinstance(source.get('text'), str) and fee.search(source['text'])]
    if not selected or sum(len(source['text']) for source in selected) > 4800:
        return None
    return {'sources': selected, 'facts': project_inference_facts(facts)}



def troubleshooting_restatement_inputs(query, facts, sources, reference_date):
    """Use one unambiguous current procedure for a public troubleshooting retry.

    Heading overlap is a bounded selector, not an entailment proof. Compound
    policy requests and ambiguous procedures retain the complete original view.
    Every output still passes all original policy/fact validators.
    """
    if (facts.get('verified_order') or facts.get('calculations') or facts.get('operational_escalation')
            or not re.search(r"\b(?:won['’]?t|doesn['’]?t|cannot|can['’]?t|not|no)\b.{0,35}\b(?:power\w*|turn|charg\w*|work\w*|sync\w*|start\w*)\b|\b(?:nahi|nahin)\b", query, re.I)
            or re.search(r'\b(?:returns?|refund\w*|replac\w*|warrant\w*|fees?|costs?|prices?|eligible|cancel\w*)\b|money\s+back|send\s+(?:it\s+)?back|रिटर्न|रिफंड|वापस|वारंटी', query, re.I)):
        return None
    stop=set('my the this that a an it its for of to at on off in with and or not no wont won doesnt doesn t cannot can power powering powered turn turning work working start starting sync syncing charge charging'.split())
    def keys(text):
        words={word.casefold().rstrip('s') for word in re.findall(r'[A-Za-z][A-Za-z0-9_-]{2,}',text)}
        return words-{word.rstrip('s') for word in stop}
    wanted=keys(query);ranked=[]
    for source in sources:
        if source.get('doc_type')!='help' or source.get('status')!='current':
            continue
        try:
            if source.get('effective_from') and date.fromisoformat(source['effective_from'])>date.fromisoformat(str(reference_date)[:10]):
                continue
        except (TypeError,ValueError):
            continue
        text=source.get('text','')
        if not isinstance(text,str) or not re.search(r'^\s*\d+[.)]\s+',text,re.M) or len(text)>4800:
            continue
        heading=re.sub(r'^\s*#{1,6}\s*(?:\[[^\]]+\]\s*)?','',text.splitlines()[0])
        overlap=wanted & keys(heading)
        if len(overlap)>=2:ranked.append((len(overlap),source))
    if not ranked:
        return None
    ranked.sort(key=lambda item:item[0],reverse=True)
    if len(ranked)>1 and ranked[0][0]==ranked[1][0]:
        return None
    return {'sources':[ranked[0][1]],'facts':{},'scope':'public_source_procedure_only'}



def public_refund_projection_inputs(query, facts, sources, reference_date):
    """A date estimate uses its actual calendar calculation, not transaction state."""
    claim=facts.get('customer_provided_refund_claim')
    if (not isinstance(claim,dict) or claim.get('verified') is not False or facts.get('verified_order')
            or re.search(r'\b(?:amount|rrn|warranty|how\s+much|reference\s+number|order\s+status)\b|kitn\w*.{0,15}paise|कितन.{0,15}पैस',query,re.I)):
        return None
    calculations=facts.get('calculations',[])
    if not isinstance(calculations,list):return None
    rows=[row for row in calculations if isinstance(row,dict)
          and row.get('operation')=='refund_business_date_range'
          and row.get('record_field')=='customer_provided_refund_claim.initiated_on'
          and row.get('input_status')=='customer_provided_unverified']
    if len(rows)!=1:return None
    calculation=rows[0];inputs=calculation.get('inputs',{});result=calculation.get('result',{})
    if not isinstance(inputs,dict) or not isinstance(result,dict):return None
    if inputs.get('customer_statement_verified') is not False or inputs.get('initiated_on')!=claim.get('initiated_on'):
        return None
    try:
        begin=date.fromisoformat(result['earliest_date']);end=date.fromisoformat(result['latest_date'])
        if begin>end or date.fromisoformat(inputs['initiated_on'])>begin:return None
        low,high=inputs['minimum_business_days'],inputs['maximum_business_days']
        if type(low) is not int or type(high) is not int or not 0<=low<=high:return None
    except (KeyError,TypeError,ValueError):return None
    actual={source['id']:source for source in sources}
    ids=set(calculation.get('source_ids',[]))-{'data/holidays.csv'}
    if not ids or not ids<=actual.keys():return None
    today=date.fromisoformat(str(reference_date)[:10])
    for ident in ids:
        source=actual[ident]
        if source.get('doc_type') not in {'policy','meta'} or source.get('status')!='current':return None
        try:
            if source.get('effective_from') and date.fromisoformat(source['effective_from'])>today:return None
        except (TypeError,ValueError):return None
    selected=[source for source in sources if source['id'] in ids]
    if sum(len(source['text']) for source in selected)>4800:return None
    return {'sources':selected,'facts':{'customer_provided_refund_claim':dict(claim),
        'refund_projection':{'input_status':'customer_provided_unverified','initiated_on':inputs['initiated_on'],
            'payment_method':inputs['payment_method'],'minimum_business_days':low,'maximum_business_days':high,
            'earliest_expected_date':begin.isoformat(),'latest_expected_date':end.isoformat()}}}


def damage_reporting_restatement_inputs(query, facts, sources, reference_date):
    """Focus a simple reporting request on one actual current reporting rule.

    Compound remedies, late reports, product-specific decisions and ambiguous
    authorities keep the complete evidence view. No policy value is authored.
    """
    if (facts.get('verified_order') or facts.get('calculations') or facts.get('operational_escalation')
            or facts.get('public_context') or facts.get('catalog')
            or not re.search(r'\b(?:damag\w*|broken|defect\w*|torn)\b|टूट|क्षतिग्रस्त|खराब', query, re.I)
            or not re.search(r'\breport\w*\b|\bwhat\b[^.!?;]{0,40}\b(?:do|now|steps)\b|क्या[^.!?;।]{0,25}कर|रिपोर्ट', query, re.I)
            or re.search(r'\d|\b(?:returns?|refund\w*|replac\w*|warrant\w*|fees?|costs?|late|later|after|elapsed|expired|and|aur|sku)\b|रिफंड|रिफ़ंड|वापस|वारंटी|शुल्क|बाद|और', query, re.I)
            or query.count('?') > 1):
        return None
    reporting = []
    for source in sources:
        if not _active(source, reference_date) or not source.get('file'):
            continue
        text = re.sub(r'[*`]', '', source.get('text', ''))
        if (re.search(r'\breport\b[^.!?;\n]{0,180}\bwithin\s+\d+\s+hours?\s+of\s+delivery\b', text, re.I)
                and re.search(r'\bphotos?\b', text, re.I)):
            reporting.append(source)
    if len(reporting) != 1:
        return None
    selected = {reporting[0]['id']}
    by_id = {row['id']: row for row in sources}
    pending = list(selected)
    while pending:
        ident = pending.pop()
        for linked in re.findall(r'\b[A-Z][A-Z0-9]{1,15}-\d{1,4}\b', by_id[ident]['text']):
            if linked in selected:
                continue
            if linked not in by_id or not _active(by_id[linked], reference_date):
                return None
            selected.add(linked); pending.append(linked)
            if len(selected) > 4:
                return None
    rows = [row for row in sources if row['id'] in selected]
    if sum(len(row['text']) for row in rows) > 2600:
        return None
    return {'sources': rows, 'facts': {}, 'scope': 'public_reporting_obligation_only'}


def public_return_period_restatement_inputs(query, facts, sources, constraints):
    """Restate a host-bound period without replaying the customer's story.

    Keep the entire original evidence, dated exceptions and source conditions.
    Compound remedies and deadline questions retain the ordinary repair path.
    """
    if (facts.get('verified_order') or facts.get('operational_escalation')
            or not re.search(r'\breturn\w*\b|रिटर्न|वापस', query, re.I)
            or not re.search(r'\b(?:how\s+long|how\s+many|kitn\w*)\b|कितन', query, re.I)
            or re.search(r'\b(?:refund\w*|replac\w*|warrant\w*|fees?|charg\w*|pick[ -]?up|deadline|last\s+date|which\s+date|by\s+when|kab\s+tak|opened|unused|sealed|damag\w*|broken)\b|रिफंड|वारंटी|शुल्क|कब\s+तक|खोल|खुल|टूट|खराब', query, re.I)):
        return None
    policy = facts.get('return_policy')
    if not isinstance(policy, dict):
        return None
    requested = [item for item in constraints if item.get('key') == 'return_policy.window_calendar_days']
    if len(requested) != 1 or requested[0].get('value') != policy.get('window_calendar_days'):
        return None
    ids = set(requested[0].get('source_ids', []))
    actual = {row['id']: row for row in sources}
    if not ids or not ids <= actual.keys():
        return None
    # Constraints have already been rebound to source text by document_reply.
    projected = {'return_policy': dict(policy), 'answer_constraints': requested}
    return {'sources': list(sources), 'facts': projected}
