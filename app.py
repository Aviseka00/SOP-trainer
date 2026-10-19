"""Compatibility entry point; execute on every Streamlit rerun."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name('app_workspace.py')), run_name='__main__')
