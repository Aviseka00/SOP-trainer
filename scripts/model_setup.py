"""Inspect optional runtime readiness; deliberately does not download model weights."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sop_studio.llm import models
from sop_studio.diagnostics import diagnose

if __name__ == '__main__':
    print(json.dumps(diagnose(Path.cwd()), indent=2))
    try:
        print('Installed Ollama models:', models())
    except RuntimeError as exc:
        print(exc)
    print('No model downloads performed. Read docs/MODEL_RESEARCH.md before installing any model.')
    print('Model storage, voice licensing and a verified download manager remain future work.')
