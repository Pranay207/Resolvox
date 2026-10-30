"""Finite checks: a public refund projection does not prove timely settlement.

This rejects recognized unconditional assurances, not every possible unsupported
claim. Dates are read from the actual host projection; no policy dates or
business-day counts are embedded here. Verified record handling is separate.
"""
from datetime import date, timedelta
import re

_FUTURE = re.compile(
    r"\bthere\s+(?:will|would)\s+be\s+no\s+(?:(?:further|additional)\s+)?delays?\b|"
    r"\b(?:will\s+not|won't|would\s+not|wouldn't)\s+(?:be\s+(?:delayed|late|overdue)|(?:experience|face|have|suffer)\s+(?:any\s+)?delays?)\b|"
    r"\bno\s+(?:(?:further|additional)\s+)?delays?\s+(?:will|would)\s+(?:occur|happen)\b|"
    r"\b(?:koi\s+)?(?:aur\s+)?(?:delay|deri|der)\s+(?:bilkul\s+)?(?:nahi|nahin|naheen)\s+(?:hoga|hogi|honge)\b|"
    r"(?:कोई\s+)?(?:और\s+)?(?:देरी|विलंब)\s+(?:बिल्कुल\s+)?नहीं\s+(?:होगी|होगा|होंगे)(?=\s|[.,;!?।]|$)", re.I)
_PRESENT = re.compile(
    r"\b(?:is|has\s+been)\s+not\s+(?:yet\s+)?(?:late|delayed|overdue)\b|"
    r"\b(?:is|remains)\s+(?:still\s+)?on\s+time\b|"
    r"\b(?:delay|deri|der)\s+(?:nahi|nahin)\s+(?:hai|hua)\b|"
    r"(?:देरी|विलंब)\s+नहीं\s+(?:है|हुआ)(?=\s|[.,;!?।]|$)", re.I)
# A delivery estimate cannot certify a delay-free transaction, even while
# its latest projected date is still in the future. This is separate from
# the calendar-consistency check for the comparative word overdue below.
_NO_DELAY_PRESENT = re.compile(
    r"\bthere\s+(?:is|are|has\s+been|have\s+been)\s+no\s+(?:(?:further|additional)\s+)?delays?\b|"
    r"\b(?:delay|deri|der)\s+(?:nahi|nahin)\s+(?:hai|hain|hua|hui)\b|"
    r"(?:देरी|विलंब)\s+नहीं\s+(?:है|हैं|हुआ|हुई)(?=\s|[.,;!?।]|$)", re.I)
_UNCERTAIN_PREFIX = re.compile(
    r"\b(?:cannot|can't|(?:do|does|did)\s+not|unable\s+to)\s+(?:guarantee|promise|confirm|assure|verify)\s+"
    r"(?:you\s+)?(?:that\s+)?(?:(?:it|(?:your|the|this)\s+(?:refund|payment|transaction))\s+)?$|"
    r"\b(?:no|without)\s+(?:a\s+)?(?:guarantee|promise|confirmation)\s+(?:that\s+)?(?:(?:it|(?:your|the|this)\s+(?:refund|payment|transaction))\s+)?$|"
    r"\b(?:guarantee|confirm|promise)\s+(?:nahi|nahin)\s+(?:kar|de)\s+sakt[ai]\s+(?:ki\s+)?$|"
    r"(?:पुष्टि|गारंटी)\s+नहीं\s+(?:कर|दे)\s+सकत[ाी]\s+(?:कि\s+)?$", re.I)
_UNCERTAIN_SUFFIX = re.compile(
    r"^\s*['\"’”)]*\s*(?:is\s+not\s+guaranteed|cannot\s+be\s+(?:guaranteed|confirmed)|"
    r"cannot\s+be\s+promised|ki\s+guarantee\s+nahi|की\s+गारंटी\s+नहीं)", re.I)


def _projection(facts):
    if not isinstance(facts, dict) or facts.get('verified_order'):
        return None
    claim = facts.get('customer_provided_refund_claim')
    if not isinstance(claim, dict) or claim.get('verified') is not False:
        return None
    found = []
    calculations = facts.get('calculations', [])
    if not isinstance(calculations, list):
        return None
    for item in calculations:
        if not isinstance(item, dict) or item.get('operation') != 'refund_business_date_range':
            continue
        if (item.get('input_status') != 'customer_provided_unverified'
                or item.get('record_field') != 'customer_provided_refund_claim.initiated_on'):
            continue
        inputs, result = item.get('inputs', {}), item.get('result', {})
        if not isinstance(inputs, dict) or not isinstance(result, dict):
            continue
        if (inputs.get('customer_statement_verified') is not False
                or inputs.get('initiated_on') != claim.get('initiated_on')):
            continue
        try:
            reference = date.fromisoformat(facts['reference_date'])
            if inputs.get('reference_date') != reference.isoformat():
                continue
            earliest = date.fromisoformat(result['earliest_date'])
            latest = date.fromisoformat(result['latest_date'])
        except (KeyError, TypeError, ValueError):
            continue
        if earliest <= latest:
            found.append((reference, latest))
    return found[0] if len(set(found)) == 1 else None


def check_public_refund_timeliness(answer, facts):
    projection = _projection(facts)
    if projection is None:
        return
    reference, latest = projection
    for clause in re.split(r'[.!;।\n]+', answer):
        if '?' in clause:
            continue
        patterns = [_FUTURE, _NO_DELAY_PRESENT] + ([_PRESENT] if reference > latest else [])
        for pattern in patterns:
            for match in pattern.finditer(clause):
                prefix, suffix = clause[:match.start()], clause[match.end():]
                if _UNCERTAIN_PREFIX.search(prefix) or _UNCERTAIN_SUFFIX.search(suffix):
                    continue
                # A directly conditional phrase is not a definite status claim.
                if re.search(r'\b(?:if|whether|agar|yadi)\s*$|(?:यदि|अगर)\s*$', prefix, re.I):
                    continue
                raise ValueError('unverified_refund_timeliness')



_ORDINAL = re.compile(r'\b(?P<english>first|second|third|fourth|fifth|sixth|seventh|\d{1,2}(?:st|nd|rd|th))\s+(?:business|working)\s+day\b|\b(?P<latin>pahla|pehla|pehle)\s+(?:business|working)\s+day\b|(?P<hindi>पहला|पहले|प्रथम)\s*(?:कार्यदिवस|कारोबारी\s+दिन|बिजनेस\s+डे)', re.I)
_ORDINALS = {word: index for index, word in enumerate(('first','second','third','fourth','fifth','sixth','seventh'),1)}


def check_public_refund_business_day_roles(answer, facts, *, date_mentions):
    """Check recognized dated ordinal claims against the supplied calendar.

    An arrival-range lower bound is not automatically day one after initiation.
    Multiple dates or unspecified roles are left to other finite validators.
    """
    if _projection(facts) is None:
        return
    rows=[row for row in facts['calculations'] if isinstance(row,dict)
          and row.get('record_field')=='customer_provided_refund_claim.initiated_on'
          and row.get('operation')=='refund_business_date_range']
    if len(rows)!=1:
        return
    inputs=rows[0]['inputs']
    try:
        start=date.fromisoformat(inputs['initiated_on'])
        weekdays=set(inputs['business_weekdays'])
        holidays={date.fromisoformat(day) for day in inputs['holidays']}
        if not weekdays or any(type(day) is not int or not 0<=day<=6 for day in weekdays):
            return
    except (KeyError,TypeError,ValueError):
        return
    split=r'[,;]|\b(?:and|but|however|aur|lekin)\b|और|लेकिन'
    for clause in re.split(r'[.!?;।\n]+',answer):
        for match in _ORDINAL.finditer(clause):
            left=re.split(split,clause[:match.start()],flags=re.I)[-1]
            right=re.split(split,clause[match.end():],maxsplit=1,flags=re.I)[0]
            local=left+match[0]+right
            if re.search(r'\b(?:cannot|can.t)\s+(?:confirm|verify)|\b(?:if|whether|agar|yadi)\b|(?<![A-Za-z\u0900-\u097f])(?:यदि|अगर)(?![A-Za-z\u0900-\u097f])',local,re.I):
                continue
            dates=date_mentions(local)
            if len(dates)!=1:
                continue
            word=(match['english'] or '').casefold()
            ordinal=_ORDINALS.get(word)
            if ordinal is None:
                digits=re.match(r'\d+',word)
                ordinal=int(digits[0]) if digits else 1
            if not 1<=ordinal<=99:
                continue
            range_role=bool(re.search(r'\b(?:of|in)\s+(?:the\s+)?(?:expected\s+|estimated\s+|arrival\s+)?(?:range|window)|\brange\s+ka\b',local,re.I))
            if range_role:
                if ordinal!=1:
                    continue
                expected=date.fromisoformat(rows[0]['result']['earliest_date'])
            else:
                expected=start;count=0
                for _ in range(3660):
                    expected+=timedelta(days=1)
                    if expected.weekday() in weekdays and expected not in holidays:
                        count+=1
                    if count==ordinal:
                        break
                else:
                    continue
            if dates!={expected}:
                raise ValueError('conflicted_refund_business_day_role')
