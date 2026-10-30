"""Finite guard against inventing physical stores from unrelated documents.

Explicit store evidence makes this guard decline; it does not prove every
location, polarity or other claim in that evidence. Delivery and seller names
alone do not establish retail storefront presence or absence.
"""
from datetime import date
import re

_STORE=r'(?:stores?|shops?|outlets?|दुकान(?:ें|ों)?|स्टोर|आउटलेट|duka(?:a)?n(?:e|on)?)'
_QUERY=re.compile(r'\b(?:where|physical|offline|locations?|have|operate|exist|near|in|at)\b|is\s+there|are\s+there|कहाँ|कहां|में|कहीं|\b(?:kahan|kahaan|mein|me|hai|hain)\b',re.I)
_CLAIM=re.compile(
    r'\bno\s+(?:(?:physical|retail|offline|local|any)\s+)*'+_STORE+r'\b|'
    r'\b(?:we|they|ZentroMart)\s+(?:do\s+not|don.t)\s+(?:have|operate)\s+(?:(?:a|any|physical|retail|offline)\s+)*'+_STORE+r'\b|'
    r'\b(?:we|they|ZentroMart)\s+(?:have|operate)\s+(?:(?:a|an|any|physical|retail|offline)\s+)*'+_STORE+r'\b|'
    r'\bthere\s+(?:is|are)\s+(?:(?:a|an|no|any|physical|retail|offline)\s+)*'+_STORE+r'\b|'
    +_STORE+r'\s+(?:नहीं\s+)?है(?:ं)?(?=\s|[.,;!?।]|$)|'
    +_STORE+r'\s+(?:nahi\s+|nahin\s+)?(?:hai|hain)\b',re.I)
_UNKNOWN=re.compile(r"(?:no|not\s+enough|lack\s+of)\s+(?:information|evidence)|(?:cannot|can.t|unable\s+to)\s+(?:confirm|verify|tell)|जानकारी.{0,20}नहीं|पता\s+नहीं|पुष्टि.{0,20}नहीं|\b(?:pata|jaankari|jankari).{0,20}\b(?:nahi|nahin)\b",re.I)
_EXPLICIT_PHYSICAL=re.compile(
    r'\b(?:physical|offline|retail|brick.and.mortar)\s+'+_STORE+r'\b|'
    r'\b(?:we|ZentroMart)\s+(?:(?:do\s+not|don.t)\s+)?(?:have|operate)\s+(?:(?:a|an|any|no)\s+)*'+_STORE+r'\b|'
    r'\bno\s+(?:physical\s+|retail\s+|offline\s+)?'+_STORE+r'\b|'
    +_STORE+r'\s+(?:नहीं\s+)?है(?:ं)?(?=\s|[.,;!?।]|$)',re.I)


def check_store_presence_claim(answer, query, sources, reference_date):
    pickup=bool(re.search(r'pick[ -]?up|collect\w*|पिकअप',query,re.I))
    if not re.search(_STORE,query,re.I) or not (_QUERY.search(query) or pickup):
        return
    today=date.fromisoformat(str(reference_date)[:10])
    for source in sources:
        if source.get('doc_type') not in {'policy','help','faq','meta','agent_guide'} or source.get('status')!='current':
            continue
        try:
            if source.get('effective_from') and date.fromisoformat(source['effective_from'])>today:
                continue
        except (TypeError,ValueError):
            continue
        text=source.get('text','')
        if isinstance(text,str):
            if pickup:
                explicit_pickup=re.search(r'\bstore\s+pick[ -]?up\s+(?:is\s+)?(?:available|unavailable|not\s+(?:available|offered|supported))\b|\bwe\s+(?:(?:do\s+not|don.t)\s+)?offer\s+store\s+pick[ -]?up\b',text,re.I)
                if explicit_pickup:return
            elif _EXPLICIT_PHYSICAL.search(text):
                return
    for clause in re.split(r'[,.!?;।\n]+|\b(?:and|but|however|aur|lekin|magar|because)\b|लेकिन|और|क्योंकि',answer,flags=re.I):
        if not clause.strip() or _UNKNOWN.search(clause):
            continue
        if _CLAIM.search(clause) or re.match(r'^\s*(?:yes|no|haan|han|nahi|nahin|हाँ|हां|नहीं)(?:\b|[ ,])',clause,re.I):
            raise ValueError('unsupported_physical_store_claim')
