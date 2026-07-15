"""
Launcher de análisis — misma convención que main.py.
Uso:
    python analysis.py                          # última corrida
    python analysis.py inicial_seed42_XXXXXX    # corrida específica
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from analysis.__main__ import main

if __name__ == "__main__":
    main()
