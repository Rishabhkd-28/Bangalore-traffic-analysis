import nbformat as nbf
import os

def md(txt): return nbf.v4.new_markdown_cell(txt)
def code(src): return nbf.v4.new_code_cell(src)

NB_PATH = "notebook/05_visualization_improved.ipynb"
nb = nbf.v4.new_notebook()

SETUP = """\
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import folium
from sqlalchemy import create_engine
import numpy as np

DB_URL = "postgresql+psycopg2://postgres:prabhupada@localhost:5432/bangalore_traffic"
engine = create_engine(DB_URL)
sns.set_theme(style="whitegrid")
"""

nb.cells = [
    md("# 🚦 Bangalore Traffic Analysis - Improved Visuals"),
    code(SETUP),
    md("### Chart 1: Worst Junctions"),
    code("pd.read_sql('SELECT * FROM traffic_speeds_clean LIMIT 5', engine)"),
]

with open(NB_PATH, "w") as f:
    nbf.write(nb, f)
print(f"✅ Created {NB_PATH}")
