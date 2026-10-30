"""A public catalog does not establish an actual fulfillment event.

Finite absence check, not a proof of every shipment/delivery claim. Actual
verified order records and supplied delivery premises are handled separately.
"""
import re

_COMPLETED = re.compile(
    r"\b(?:was|were|has\s+been|have\s+been|had\s+been|is\s+already)\s+(?:not\s+)?(?:shipped|dispatched|delivered)\b|"
    r"(?:डिलीवर|डिलिवर|शिप)\s+हो\s+(?:गय[ाीे]|चुक[ाीे])|"
    r"\b(?:deliver(?:ed)?|ship(?:ped)?|dispatch(?:ed)?)\s+(?:ho\s+)?(?:hua|hui|chuka|chuki|gaya|gayi)\b", re.I)
_BOUNDARY = re.compile(r'[,;.!?।\n]|\b(?:and|but|however|aur|lekin)\b|और|लेकिन', re.I)
_CONDITIONAL = re.compile(r'\b(?:if|whether|when|once|after|before|assuming|provided|agar|yadi|jab|chahe)\b|यदि|अगर|जब|चाहे|के\s+बाद', re.I)
_UNCERTAIN = re.compile(r"\b(?:cannot|can't|unable\s+to|do\s+not|don't)\s+(?:confirm|verify|establish|know)|\bno\s+(?:record|evidence|confirmation)|पुष्टि\s+नहीं|सत्यापित\s+नहीं", re.I)
_GENERIC = re.compile(r'\b(?:items|products|orders|parcels)\s+(?:that|which)\s*$', re.I)


def check_catalog_fulfillment_claim(answer, query, facts):
    if (not isinstance(facts, dict) or not facts.get('catalog') or facts.get('verified_order')
            or (facts.get('public_context') or {}).get('delivered_on')):
        return
    # A stated customer premise is distinct from an invented event. Direct
    # questions such as "Was my product delivered?" do not match this form.
    if _COMPLETED.search(query):
        return
    for match in _COMPLETED.finditer(answer):
        prefix = _BOUNDARY.split(answer[:match.start()])[-1][-160:]
        if _CONDITIONAL.search(prefix) or _UNCERTAIN.search(prefix) or _GENERIC.search(prefix):
            continue
        raise ValueError('unverified_catalog_fulfillment_event')
