"""Query-first hybrid retrieval of policy sections and their source dependencies.

Only KB documents enter the index. Raw queries and narrowly expanded queries are
independent fusion channels; intent hints never select expected evidence IDs.
"""
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
import hashlib
import math
import os
import re
import unicodedata

import numpy as np

from .config import CACHE
from .kb import KnowledgeBase, Chunk, AUTHORITY

MODEL_ID = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
MODEL_DIR = CACHE / 'embedding_model'
STOP = set('the a an is are was were to of and or my i me you your it this that can could will would do does did how what when which in on at for with from have has be been please hai hain kya mera meri mujhe mein ko pe se ka ki ke tha ho hoon kar'.split())
STOP.update('these those why whether just get got need want tell may might also any something anything come received yesterday bought purchase sorted'.split())
FORMS = {
    'refunds': 'refund', 'refunded': 'refund', 'refunding': 'refund',
    'returns': 'return', 'returned': 'return', 'returning': 'return',
    'deliveries': 'delivery', 'delivered': 'delivery', 'deliver': 'delivery',
    'cancellation': 'cancel', 'cancellations': 'cancel', 'cancelled': 'cancel',
    'canceled': 'cancel', 'cancelling': 'cancel', 'shipped': 'ship', 'shipping': 'ship',
    'payments': 'payment', 'pay': 'payment', 'paid': 'payment',
    'initiated': 'initiate', 'initiation': 'initiate', 'initiates': 'initiate',
    'started': 'start', 'starting': 'start', 'days': 'day', 'hours': 'hour',
    'fees': 'fee', 'charges': 'charge', 'charged': 'charge',
    'collecting': 'collect', 'collected': 'collect', 'collections': 'collect',
    'damages': 'damage', 'damaged': 'damage', 'windows': 'window',
    'attempts': 'attempt', 'attempted': 'attempt', 'details': 'detail',
    'members': 'member', 'membership': 'member',
}

# Customer-language aliases, activated by query words rather than intent routing.
GLOSSARY = (
    (r'\b(not\s+(?:at\s+)?home|miss\w*\s+(?:the\s+)?courier|delivery\s+attempt)\b|घर.{0,8}नहीं|ghar.{0,8}nahi', 'delivery attempts missed courier SMS reschedule'),
    (r'\b(send(?:ing)?\b.{0,18}\bback|give\b.{0,10}\bback|take\b.{0,10}\bback|return\w*|laut\w*|wapas|vaapas)\b|लौटा|वापस', 'return'),
    (r'\b(refund\w*|money\s+back|returned\s+money|paise?\s+(?:wapas|vaapas)|paisa\s+(?:wapas|vaapas)|reimbursement)\b|रिफ़?ंड|पैसे\s*वापस', 'refund'),
    (r'\b(inspect\w*|qc|quality\s+check)\b', 'quality check QC'),
    (r'\b(start\w*|beg[au]n|initiat\w*|shuru)\b|शुरू', 'initiate start'),
    (r'\b(collect\w*|pick[ -]?up|lene\s+(?:nahi|nahin)|uthane)\b|पिकअप|उठाने', 'reverse pickup collect collection'),
    (r'\b(nobody|no[ -]?one|never)\b.{0,25}\b(came|arrived|collect)|\b(missed|skip\w*)\b.{0,15}\bpick', 'missed pickup reschedule'),
    (r'\b(cancel\w*|stop\s+(?:my|the|this)\s+order|radd)\b|कैंसिल|रद्द', 'cancel cancellation'),
    (r'\b(broken|crack\w*|torn|faulty|defect\w*|damage\w*|kharab|t[ou]+ta)\b|टूट|खराब', 'damaged defective'),
    (r'\b(wrong|incorrect|galat)\b|गलत', 'wrong item'),
    (r'\b(missing|not\s+received|never\s+arrived)\b|नहीं\s*मिला', 'missing received'),
    (r'\b(swap\w*|exchange\w*|badal\w*)\b|बदल', 'exchange size colour'),
    (r'\b(guarantee|warranty|assured|manufacturer.{0,4}\s+cover|brand\s+cover|extra\s+cover)\b|वारंटी|वॉरंटी|अश्योर्ड', 'warranty assured'),
    (r'\b(charg\w*|cost\w*|fee\w*|kitna|rupees|rs)\b|फ़ीस|फीस|शुल्क', 'fee cost charge'),
    (r'\b(deliver\w*|arriv\w*|pahunch\w*|aayega|aayegi|aana)\b|डिलीवरी|पहुँच|आएगा|आएगी', 'delivery'),
    (r'\b(ship\w*|dispatch\w*)\b|शिप', 'ship shipped'),
    (r'\b(delay\w*|late|der|express)\b|देर|लेट|एक्सप्रेस', 'late express delivery'),
    (r'\b(cash[ -]on[ -]delivery|cod)\b|कैश', 'cash on delivery COD'),
    (r'\b(card|credit|debit)\b|कार्ड', 'credit debit card'),
    (r'\b(net\s*banking|netbanking)\b|नेट\s*बैंकिंग', 'net banking'),
    (r'\b(wallet)\b|वॉलेट|वालेट', 'wallet'),
    (r'\b(plus|membership|member)\b|प्लस|सदस्य', 'Plus membership'),
    (r'\b(human|person|representative|insaa?n|colleague)\b|इंसान|मानव', 'human handover agent'),
    (r'\b(never\s+(?:placed|ordered)|did\s+not\s+(?:place|make)|didn.t\s+(?:order|make)|not\s+mine|unauthori[sz]ed|fraud)\b', 'unauthorized account activity customer did not make human'),
    (r'\b(phone\s+number|email|street\s+address|another\s+customer|other\s+customer|person\s+who\s+ordered)\b', 'customer privacy never share another customer details'),
    (r'\b(swell\w*|bulg\w*|smoke|sparks?|burn\w*|injur\w*)\b|धुआ|चिंगारी|फूल', 'product safety risk stop using human'),
    (r'\b(kitne|kitna|kab|when|how\s+(?:long|soon|fast)|by\s+which\s+date)\b|कितने|कब', 'time timeline'),
    (r'\b(shirt|dress|trouser\w*|jeans|shoe\w*|sandal\w*|bag\w*)\b', 'clothing footwear fashion'),
    (r'\b(phone|laptop|earbuds?|headphones?|speaker|watch|charger)\b', 'electronics'),
)


# These phrases name policy concepts across customer vocabulary. Keep them
# independent of intent labels so retrieval remains useful after a router miss.
GLOSSARY += (
    (r"\b(manufacturer(?:'s)?|brand)\s+(?:cover|guarantee)\b", 'brand warranty manufacturer service centre'),
    (r'\b(expired|out.of.date)\b', 'damaged expired wrong missing reporting'),
    (r'\brefund\b.{0,30}\bstages?\b|\bstages?\b.{0,30}\brefund\b|\bpickup.to.initiation\b', 'refund initiation pickup quality check'),
    (r'\b(remedy|remedies|resolution|replacement)\b', 'resolution refund replacement verification'),
    (r'\b(evidence|photos?|photographs?|pictures?)\b', 'photos item packaging reporting'),
    (r'\b(seller|marketplace|third.party)\b', 'marketplace seller'),
    (r'\b(postage|courier charges|battery replacement|international)\b', 'warranty exclusions cover'),
    (r'\b(trace|reference|rrn)\b.{0,35}\b(refund|bank)|\b(refund|bank)\b.{0,35}\b(trace|reference|rrn)\b', 'refund reference number bank trace'),
    (r'\b(pincode|postal code|metro|serviceable|prepaid)\b', 'delivery serviceable pincode cash on delivery express availability'),
    (r'\u0930\u093f\u091f\u0930\u094d\u0928|\u0932\u094c\u091f\u093e|\u0935\u093e\u092a\u0938', 'return'),
    (r'\u0938\u0940\u0932|\u0916\u094b\u0932|\u0907\u0938\u094d\u0924\u0947\u092e\u093e\u0932|\u0905\u0928\u0909\u092a\u092f\u094b\u0917', 'condition returned items unopened seal intact unused'),
    (r'\u0938\u0940\u0930\u092e|\u0938\u094c\u0902\u0926\u0930\u094d\u092f|\u0915\u0949\u0938\u094d\u092e\u0947\u091f\u093f\u0915', 'beauty personal care'),
)


def query_facets(query: str) -> list[str]:
    """Independent clauses stop a long question from hiding a shorter request.

    These are text-derived retrieval views, never a map from a question to IDs.
    Only content-bearing clauses receive a view, and the original remains the
    strongest channel. This is useful for both unfamiliar and compound wording.
    """
    pieces = re.split(r'[?;\n]|\b(?:and|but|versus|whereas|including)\b', query, flags=re.I)
    facets = []
    for piece in pieces:
        piece = piece.strip(' ,.:')
        if len(tokenize(piece)) >= 3 and piece.casefold() != query.strip(' ,.:?;').casefold():
            facets.append(expand_query(piece))
    # Unfamiliar phrases can have no lexical overlap with their policy term.
    # Preserve that alias as its own view rather than letting generic words
    # such as 'shop' or 'cover' dilute it in the full expanded query.
    original_words = set(tokenize(query))
    for pattern, alias in GLOSSARY:
        if re.search(pattern, query, re.I) and not (set(tokenize(alias)) & original_words):
            facets.append(alias)
    return list(dict.fromkeys(facets))[:5]


def tokenize(text: str) -> list[str]:
    text = unicodedata.normalize('NFKC', text).casefold()
    # Python's \w alone drops Devanagari combining marks and fragments words.
    words = re.findall(r'[a-z0-9]+|[\u0900-\u097f]+|[^\W\d_]+', text, re.UNICODE)
    return [FORMS.get(w, w[:-1] if w.isascii() and len(w) > 4 and w.endswith('s') and not w.endswith('ss') else w)
            for w in words if w not in STOP]


def expand_query(query: str) -> str:
    """Retain the original utterance and append only matching language aliases."""
    aliases = [value for pattern, value in GLOSSARY if re.search(pattern, query, re.I)]
    # "How long" names different concepts in returns and refunds. Keep the
    # expanded channel about the customer's requested operation, rather than
    # letting a generic timeline word turn every return into a refund question.
    if 'return' in aliases and 'refund' not in aliases:
        aliases = [x for x in aliases if x != 'time timeline']
        aliases.append('return eligibility category window calendar days')
        if re.search(r'open\w*|unseal\w*|tried|worn|seal|tags?|packaging|खोल|खुल', query, re.I):
            aliases.append('condition returned items unused original tags packaging unopened seal intact')
    elif 'refund' in aliases and 'time timeline' in aliases:
        aliases.append('refund timelines after initiation payment method business days')
    if 'refund' in aliases and re.search(r'cash|cod|money\s+back|payment|paid', query, re.I):
        aliases.append('refund original payment method')
    return query + ('\n' + ' '.join(dict.fromkeys(aliases)) if aliases else '')


class Dense:
    def __init__(self):
        from tokenizers import Tokenizer
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 3
        opts.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(MODEL_DIR / 'model.onnx'), sess_options=opts, providers=['CPUExecutionProvider'])
        self.tokenizer = Tokenizer.from_file(str(MODEL_DIR / 'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=256)
        self.tokenizer.enable_padding(pad_id=0, pad_token='[PAD]')

    def encode(self, texts: list[str]) -> np.ndarray:
        rows = []
        for start in range(0, len(texts), 12):
            encoded = self.tokenizer.encode_batch(texts[start:start + 12])
            inputs = {'input_ids': np.array([x.ids for x in encoded], dtype=np.int64),
                      'attention_mask': np.array([x.attention_mask for x in encoded], dtype=np.int64),
                      'token_type_ids': np.array([x.type_ids for x in encoded], dtype=np.int64)}
            allowed = {x.name for x in self.session.get_inputs()}
            output = self.session.run(None, {k: v for k, v in inputs.items() if k in allowed})[0]
            if output.ndim == 3:
                mask = inputs['attention_mask'][..., None]
                output = (output * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
            output = output / np.maximum(np.linalg.norm(output, axis=1, keepdims=True), 1e-12)
            rows.extend(output)
        return np.asarray(rows, dtype=np.float32)


@lru_cache(maxsize=1)
def dense_model() -> Dense:
    return Dense()


class Retriever:
    def __init__(self, kb: KnowledgeBase, dense: bool | None = None):
        self.kb = kb
        self.chunks = list(kb.chunks.values())
        self.positions = {c.id: i for i, c in enumerate(self.chunks)}
        self.files = defaultdict(list)
        for i, c in enumerate(self.chunks):
            self.files[c.file].append(i)
        self.documents = [self._document_text(c) for c in self.chunks]
        self.summaries = [self._summary_text(c) for c in self.chunks]
        self.tokens = [Counter(tokenize(text)) for text in self.documents]
        self.titles = [Counter(tokenize(c.title)) for c in self.chunks]
        self.lengths = [sum(t.values()) for t in self.tokens]
        self.avg = max(1, sum(self.lengths) / max(1, len(self.lengths)))
        self.df = Counter(w for row in self.tokens for w in row)
        self.references = {i: [self.positions[x] for x in re.findall(r'\b[A-Z][A-Z0-9v]*(?:-[A-Z0-9]+)+(?:\.\d+)?\b', c.text)
                               if x in self.positions and x != c.id]
                           for i, c in enumerate(self.chunks)}
        self.dense_status = 'disabled'
        self.vectors = None
        self.model = None
        enabled = os.getenv('DENSE_ENABLED', 'true').lower() == 'true' if dense is None else dense
        if enabled and self.chunks and (MODEL_DIR / 'model.onnx').exists():
            self.model = dense_model()
            revision = MODEL_DIR / 'revision.txt'
            signature = '\n'.join(['query-first-v3-summary', revision.read_text() if revision.exists() else MODEL_ID] +
                                  [c.id + c.status + c.version + text for c, text in zip(self.chunks, self.documents)])
            fingerprint = hashlib.sha256(signature.encode()).hexdigest()[:20]
            file = CACHE / f'vectors-{fingerprint}.npy'
            if file.exists():
                try:
                    self.vectors = np.load(file, allow_pickle=False)
                except (OSError, ValueError):
                    self.vectors = None
            if self.vectors is None or self.vectors.ndim != 2 or len(self.vectors) != len(self.chunks) * 2:
                self.vectors = self.model.encode(self.documents + self.summaries)
                try:
                    np.save(file, self.vectors)
                except OSError:
                    pass  # Read-only deployments can still retrieve in memory.
            self.dense_status = 'multilingual MiniLM ONNX int8; raw/expanded hybrid fusion'
        elif enabled:
            self.dense_status = 'unavailable: run python setup.py --models'

    @staticmethod
    def _document_text(c: Chunk) -> str:
        topic = re.sub(r'^(?:pol|agent|help|faq|mkt)_', '', Path(c.file).stem)
        topic = re.sub(r'_v\d+.*$', '', topic).replace('_', ' ')
        # Preserve complete section and table headers; add document topic context.
        body = re.sub(r'^##\s*\[[^\]]+\]\s*', '', c.text)
        return topic + '\n' + body

    @staticmethod
    def _summary_text(c: Chunk) -> str:
        """A second representation keeps numeric tables from hiding the heading."""
        lines = [line for line in Retriever._document_text(c).splitlines() if not line.lstrip().startswith('|')]
        return ' '.join(' '.join(lines).split()[:100])

    def _similarities(self, encoded: np.ndarray) -> np.ndarray:
        n = len(self.chunks)
        # Tables keep their complete vector; prose/heading is a separate view.
        return np.maximum(self.vectors[:n] @ encoded, self.vectors[n:] @ encoded)

    def _bm25(self, query: str) -> np.ndarray:
        words = set(tokenize(query))
        scores = np.zeros(len(self.chunks))
        for i, (tf, length, title) in enumerate(zip(self.tokens, self.lengths, self.titles)):
            for word in words:
                if not tf[word]:
                    continue
                idf = math.log(1 + (len(self.tokens) - self.df[word] + .5) / (self.df[word] + .5))
                scores[i] += idf * (tf[word] * 2.5 / (tf[word] + 1.5 * (.25 + .75 * length / self.avg)) +
                                    .7 * min(1, title[word]))
        return scores

    def _dependencies(self, ranked: list[int], allowed: set[int], lexical: np.ndarray, query: str) -> dict[int, float]:
        """One-hop references and governing rules from retrieved source text."""
        additions: dict[int, float] = {}
        primary = ranked[:3]
        for i in primary:
            for target in self.references[i]:
                if target in allowed:
                    additions[target] = max(additions.get(target, 0), 1.10)
        # A named policy concept in a source is a cross-document reference even
        # when the author wrote "Plus members" instead of a section identifier.
        linked_sources = ranked[:5]
        source_words = set(tokenize(expand_query(query) + ' ' + ' '.join(self.chunks[i].text for i in linked_sources)))
        for file, positions in self.files.items():
            topic = re.sub(r'^(?:pol|agent|help|faq|mkt)_', '', Path(file).stem).replace('_', ' ')
            topic_words = set(tokenize(topic))
            if len(topic_words) < 2 or not topic_words <= source_words:
                continue
            targets = [i for i in positions if i in allowed and self.chunks[i].doc_type == 'policy']
            if not targets or any(i in primary for i in targets):
                continue
            context = query + ' ' + ' '.join(self.chunks[i].title + ' ' + self.chunks[i].text for i in linked_sources)
            related = self._bm25(context)
            target = max(targets, key=lambda i: (related[i], -i))
            additions[target] = max(additions.get(target, 0), .88)
        text = ' '.join(self.chunks[i].text for i in primary).casefold()
        temporal = re.search(r'\b(time|long|soon|fast|when|date|days?|hours?|start\w*|arriv\w*|reach\w*|credit\w*|pending|shuru|kab|kitne|business|\d{4})\b|दिन|कब|कितने', query, re.I)
        if temporal and 'business day' in text:
            for i in allowed:
                c = self.chunks[i]
                if c.doc_type == 'meta' and 'business day' in c.title.casefold():
                    additions[i] = 1.20
        # Competing lower-authority copy needs the document precedence instruction.
        conflict_named = re.search(r'\b(faq|old(?:er)?\s+(?:(?:returns?\s+)?page|policy)|superseded|overrid\w*|precedence|disagree|contradict\w*|which.+govern\w*)\b', query, re.I)
        relevant_lower = bool(conflict_named) or any(self.chunks[i].doc_type in {'faq', 'marketing'} and lexical[i] > 0 for i in ranked[:5])
        if relevant_lower and any(self.chunks[i].doc_type == 'policy' for i in primary):
            for i in allowed:
                c = self.chunks[i]
                if c.doc_type == 'meta' and re.search(r'precedence|document wins', c.title, re.I):
                    additions[i] = 1.30 if conflict_named else .92
        # Retrieve a policy's explicit exceptions before applying its normal rule.
        # This also makes thresholds available when a product's value is supplied
        # later by a verified/catalog lookup rather than by the initial question.
        primary_files = {self.chunks[i].file for i in primary if self.chunks[i].doc_type == 'policy'}
        for i in allowed:
            c = self.chunks[i]
            if c.file in primary_files and re.search(r'high.value|exceptions?|limitations?|not cover|exclusions?|reporting window', c.title, re.I):
                additions[i] = .97
        # Other current policies may narrow the same named entitlement. Their
        # exclusion must accompany the general rule even when the customer does
        # not know to ask about an exception (for example, a seller listing).
        primary_titles = set(tokenize(expand_query(query) + ' ' + ' '.join(self.chunks[i].title for i in primary)))
        for i in allowed:
            c = self.chunks[i]
            title_words = set(tokenize(c.title))
            if (c.doc_type == 'policy' and title_words and title_words <= primary_titles
                    and re.search(r"never applies|does not apply|do not apply|not eligible|only the", c.text, re.I)):
                additions[i] = max(additions.get(i, 0), 1.08)
        action_text = ' '.join(self.chunks[i].text for i in ranked[:8]).casefold()
        if re.search(r'hand\s*over|create a ticket', action_text):
            procedure_bm = self._bm25('when hand over human')
            procedures = [(float(procedure_bm[i]), i) for i in allowed if self.chunks[i].doc_type == 'agent_guide']
            for rank, (score, i) in enumerate(sorted(procedures, reverse=True)[:2]):
                if score > 0:
                    additions[i] = max(additions.get(i, 0), .81 - .01 * rank)
        return additions

    def search(self, query: str, k: int = 10, historical: bool = False, intent: str | None = None) -> list[dict]:
        if k <= 0 or not query.strip() or not self.chunks:
            return []
        allowed = {i for i, c in enumerate(self.chunks) if self.kb.allowed(c, historical)}
        if not allowed:
            return []
        expanded = expand_query(query)
        facets = query_facets(query)
        facet_scores = [self._bm25(facet) for facet in facets]
        raw_bm = self._bm25(query)
        expanded_bm = self._bm25(expanded)
        ranks = defaultdict(float)

        def fuse(values: np.ndarray, weight: float, threshold: float = 0):
            ordered = sorted((i for i in allowed if values[i] > threshold), key=lambda i: (-values[i], i))
            for rank, i in enumerate(ordered):
                ranks[i] += weight / (24 + rank)

        fuse(raw_bm, 1.0)
        fuse(expanded_bm, .65)
        for values in facet_scores:
            fuse(values, .24 / max(1, len(facet_scores)))
        # Weak label hint, gated on actual query evidence.
        if intent and intent not in {'unknown', 'greeting'}:
            hint_bm = self._bm25(intent.replace('_', ' '))
            fuse(np.where((raw_bm > 0) | (expanded_bm > 0), hint_bm, 0), .12)
        similarities = np.zeros(len(self.chunks))
        if self.model is not None:
            queries = [query, expanded, expanded.split('\n', 1)[1]] if expanded != query else [query]
            encoded = self.model.encode(queries)
            similarities = self._similarities(encoded[0])
            reliability = min(1., max(0., float(similarities.max())) / .45) ** 2
            fuse(similarities, 1.15 * reliability, .2)
            if len(encoded) > 1:
                fuse(self._similarities(encoded[1]), .45 * reliability, .2)
                fuse(self._similarities(encoded[2]), .80, .25)
        weights = {0: 1., 1: 1.10, 2: 1.06, 3: 1., 4: .95, 5: .70}
        base = {i: score * weights.get(AUTHORITY.get(self.chunks[i].doc_type, 3), 1.) for i, score in ranks.items()}
        ranked = sorted(base, key=lambda i: (-base[i], i))
        if not ranked:
            return []
        # Dense models can miss negation and proper product names. Retain the
        # strongest expanded lexical candidate as a separate retrieval channel
        # even when several weak semantic matches outvote it in rank fusion.
        lexical_best = max(allowed, key=lambda i: (expanded_bm[i], -i))
        if expanded != query and expanded_bm[lexical_best] > 0 and lexical_best not in ranked[:4]:
            ranked.remove(lexical_best)
            ranked.insert(3, lexical_best)
        # Leave a majority of the budget for direct query evidence. Larger bundles
        # can carry three operational dependencies instead of evicting one.
        limit = min(4, max(0, k - 6))
        dependencies = self._dependencies(ranked, allowed, raw_bm, query)
        # A short second clause may be absent from the aggregate ranking. Reserve
        # a bounded slot for its best current-policy match when lexical evidence
        # is meaningful, before using the remaining dependency budget.
        for values in facet_scores:
            relevant = [i for i in allowed if self.chunks[i].doc_type == 'policy' and values[i] > 0]
            if relevant:
                best = max(relevant, key=lambda i: (values[i], -i))
                dependencies[best] = max(dependencies.get(best, 0), 1.15)
        missing = sorted((i for i in dependencies if i not in ranked[:max(3, k - limit)]),
                         key=lambda i: (-dependencies[i], -base.get(i, 0), i))[:limit]
        selected = list(ranked[:max(0, k - len(missing))])
        selected.extend(i for i in missing if i not in selected)
        # A dependency may already fit the shortened direct list. Fill that
        # shared slot with the next direct result instead of returning < k rows.
        selected.extend(i for i in ranked if i not in selected)
        selected = selected[:k]
        result = []
        floor = min((base[i] for i in selected if i in base), default=base[ranked[0]] * .5)
        for i in selected:
            score = base.get(i, floor * .95)
            if result:
                score = min(score, result[-1]['score'] - .000001)
            result.append({'chunk': self.chunks[i], 'score': round(max(0, score), 6),
                           'dense_score': round(float(similarities[i]), 4)})
        return result
