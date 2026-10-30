"""Require explicitly named policy taxonomy labels to retain source spelling.

This implements the generation contract's technical-name rule. It does not
certify translations generally or decide which category applies to an item.
"""
from datetime import date
import json
import re
import unicodedata

_ASSIGNMENT=re.compile(
    r'(?:\bit\s+(?:is|falls|comes|belongs)\s+(?:in|under|to)\s+|\bthis\s+(?:item|product)\s+(?:is|falls|belongs)\s+(?:in|under|to)\s+)(?P<en>[^.!?;\n]{1,110}?)\s+category\b|'
    r'(?:यह|ये)\s+(?P<hi>[^.!?;।\n]{1,110}?)\s+(?:(?:की|के|का)\s+)?(?:श्रेणी|कैटेगरी|कैटेगिरी|वर्ग)\s+में\s+(?:शामिल|आत[ाीे]|है)',re.I)
_EXAMPLE=re.compile(r'(?:\bcategor(?:y|ies)\b|श्रेणियों|श्रेणी|कैटेगरी)[^.!?;।\n]{0,60}?(?:including|such\s+as|जैसे)\s+(?P<label>[^,.;!?।\n]{1,90})',re.I)


def _norm(value):
    value=unicodedata.normalize('NFKC',value).casefold().strip()
    value=re.sub(r'^(?:the|a|an)\s+','',value)
    value=re.sub(r'\s+(?:की|के|का)$','',value)
    return ' '.join(re.findall(r'[\w\u0900-\u097f]+',value))


def _first_example(value):return re.split(r'\b(?:and|or)\b|और|अथवा',value,maxsplit=1,flags=re.I)[0].strip()


def check_policy_category_labels(answer,sources,reference_date):
    labels=set();today=date.fromisoformat(str(reference_date)[:10])
    for source in sources:
        if source.get('doc_type')=='catalog' and source.get('status')=='current':
            try:
                row=json.loads(source.get('text',''))
                if isinstance(row,dict) and isinstance(row.get('return_category'),str):
                    labels.add(_norm(row['return_category']))
            except (TypeError,ValueError):pass
            continue
        if source.get('doc_type') not in {'policy','help'} or source.get('status')!='current':continue
        try:
            if source.get('effective_from') and date.fromisoformat(source['effective_from'])>today:continue
        except (TypeError,ValueError):continue
        text=source.get('text','')
        for line in text.splitlines():
            if '|' not in line:continue
            cells=[part.strip(' *`') for part in line.strip().strip('|').split('|')]
            if len(cells)==3 and (re.search(r'\d',cells[1]) or re.search(r'not\s+returnable',cells[1],re.I)):
                labels.update((_norm(cells[0]),_norm(cells[2])))
        for example in _EXAMPLE.finditer(text):labels.add(_norm(_first_example(example['label'])))
    labels.discard('')
    if not labels:return
    for match in _ASSIGNMENT.finditer(answer):
        label=match['en'] or match['hi']
        if _norm(label) not in labels:raise ValueError('unsupported_category_label')
    for match in _EXAMPLE.finditer(answer):
        if _norm(_first_example(match['label'])) not in labels:
            raise ValueError('unsupported_category_label')
