# dashboard/app.py
"""Streamlit dashboard: ranked leads, signals, link-analysis graph, and metrics from outputs/ (M10, reduced)."""
import json
from pathlib import Path

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

OUT = Path("outputs")
PREVIEW = Path("preview")

st.set_page_config(page_title="V.E.C.T.O.R", layout="wide")
st.title("V.E.C.T.O.R: ranked leads (prototype, synthetic data)")
st.caption("Prototype on synthetic data. Not a measure of real-world detection performance.")

src = PREVIEW if (PREVIEW / "leads.csv").exists() else OUT
leads = pd.read_csv(src / "leads.csv", dtype={"entity_id": str, "pattern_type": str, "evidence": str})
metrics = json.loads((src / "metrics.json").read_text())

st.subheader("Metrics (from metrics.json)")
st.json(metrics)

st.subheader("Top leads")
cols = ["rank", "entity_id", "lead_score", "anomaly_score", "cluster_deviation",
        "pattern_hits", "propagated_risk", "total_out", "unique_counterparties", "label", "pattern_type"]
st.dataframe(leads[[c for c in cols if c in leads.columns]].head(100), width="stretch")

st.subheader("Inspect lead")
sel = st.selectbox("Lead address", leads["entity_id"].head(100))
detail = leads[leads["entity_id"] == sel].astype(str).T
detail.columns = ["value"]
st.table(detail)

st.subheader("Link analysis: 1-hop neighbourhood of selected lead")
ep = src / "edges.csv" if (src / "edges.csv").exists() else OUT / "edges.csv"
if ep.exists():
    edges = pd.read_csv(ep, dtype=str)
    nb = edges[(edges["src"] == sel) | (edges["dst"] == sel)]
    G = nx.DiGraph()
    G.add_edges_from(zip(nb["src"], nb["dst"]))
    if G.number_of_nodes():
        pos = nx.spring_layout(G, seed=42)
        lab = dict(zip(leads["entity_id"], leads["label"]))
        ex, ey = [], []
        for a, b in G.edges():
            ex += [pos[a][0], pos[b][0], None]
            ey += [pos[a][1], pos[b][1], None]
        nodes = list(G.nodes())
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ex, y=ey, mode="lines", line=dict(width=1, color="#888"), hoverinfo="none", showlegend=False))
        groups = {
            "Selected lead": [n for n in nodes if n == sel],
            "Planted illicit (synthetic label)": [n for n in nodes if n != sel and lab.get(n) == 1],
            "Other wallet": [n for n in nodes if n != sel and lab.get(n) != 1],
        }
        colors = {"Selected lead": "#ff7f0e", "Planted illicit (synthetic label)": "#d62728", "Other wallet": "#1f77b4"}
        for name, grp in groups.items():
            if grp:
                fig.add_trace(go.Scatter(
                    x=[pos[n][0] for n in grp], y=[pos[n][1] for n in grp], mode="markers", name=name,
                    marker=dict(size=18 if name == "Selected lead" else 10, color=colors[name]),
                    text=grp, hoverinfo="text"))
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          showlegend=True, legend=dict(orientation="h", y=1.08, x=0),
                          height=500, margin=dict(l=0, r=0, t=40, b=0),
                          xaxis=dict(visible=False), yaxis=dict(visible=False))
        st.plotly_chart(fig)
    else:
        st.info("No neighbours found for this lead.")
else:
    st.info("edges.csv not found. Run the pipeline first.")
