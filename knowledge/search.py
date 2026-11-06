import html
import math
import re
from collections import Counter

WORD = re.compile(r"\w+")
STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from", "has", "have",
    "how", "i", "in", "is", "it", "of", "on", "or", "our", "that", "the", "their", "there", "this", "to",
    "was", "we", "what", "when", "where", "which", "who", "will", "with", "you", "your",
}


def stem(word):
    """Very light stemming so 'refunds' and 'refunded' match 'refund'."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 5 and word.endswith("ing"):
        return word[:-3]
    if len(word) > 4 and word.endswith("ed"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokens(text):
    return [stem(w) for w in WORD.findall(text.lower()) if w not in STOP and len(w) > 1]


def rank(query, passages, top=10, k1=1.5, b=0.75):
    """BM25 ranking. passages is a list of (id, text). Returns [(id, score)], best first."""
    terms = set(tokens(query))
    if not terms or not passages:
        return []
    docs = []
    for pid, text in passages:
        toks = tokens(text)
        docs.append((pid, Counter(toks), len(toks)))
    n = len(docs)
    avg = (sum(length for _, _, length in docs) / n) or 1
    df = {t: sum(1 for _, tf, _ in docs if t in tf) for t in terms}
    scored = []
    for pid, tf, length in docs:
        score = 0.0
        for t in terms:
            f = tf.get(t, 0)
            if f:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                score += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * length / avg))
        if score > 0:
            scored.append((pid, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:top]


def highlight(text, query):
    """Return HTML-safe text with query words wrapped in <mark>."""
    terms = set(tokens(query))
    out, last = [], 0
    for m in WORD.finditer(text):
        if stem(m.group().lower()) in terms:
            out.append(html.escape(text[last:m.start()]))
            out.append("<mark>" + html.escape(m.group()) + "</mark>")
            last = m.end()
    out.append(html.escape(text[last:]))
    return "".join(out)