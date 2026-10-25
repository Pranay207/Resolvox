# Third-party components

- Official capstone dataset: synthetic teaching resource from C&A Club IIT Guwahati x Gnani.ai. Download separately; no redistribution is included in the repository or submission ZIP. Read the supplied dataset README and usage rules.
- Embedding model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, Apache-2.0, https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 . Revision pinned in setup.py. Weights downloaded separately.
- Ollama and Qwen3: separately installed local model/runtime; consult their licenses. We do not redistribute weights.
- Python dependencies and their licenses remain with their respective authors. Exact installed Windows versions are recorded in requirements-lock.txt; requirements.txt pins direct dependencies for other platforms.
- Speech: Gnani's official REST APIs only. Participant account/credits are required; no keys or voice recordings are redistributed.

- Translation: Meta NLLB-200 distilled 600M, [original model card](https://huggingface.co/facebook/nllb-200-distilled-600M), converted to quantized ONNX by [Xenova](https://huggingface.co/Xenova/nllb-200-distilled-600M). Weights are licensed [CC-BY-NC-4.0](https://creativecommons.org/licenses/by-nc/4.0/), used here for this noncommercial educational prototype. Meta describes this as a research model rather than a production release. Revision `261c31d1a5732c67cdd16d80e8d6088507c7ccea` and SHA-256 values are pinned in `src/translation.py`; setup records attribution beside downloaded weights. Approximately 907 MB is downloaded separately into ignored `.cache/translation/`; weights are excluded from Git and the ZIP. No remote Python model code is executed.
