# dashboard/app.py
"""V.E.C.T.O.R dashboard: investigation pages built only from pipeline outputs (M10, reduced)."""
import json
from pathlib import Path

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

OUT = Path("outputs")
PREVIEW = Path("preview")
TIERS = ["Critical", "High", "Medium", "Low"]
TIER_COLOR = {"Critical": "#ef4444", "High": "#f97316", "Medium": "#eab308", "Low": "#22c55e"}
PAGES = ["Overview", "Entity Explorer", "Risk Queue", "Transaction Graph",
         "Behavioral Clusters", "Investigations", "Model Performance", "Data Sources"]

st.set_page_config(page_title="V.E.C.T.O.R", layout="wide")
st.markdown("""<style>
.card{background:#111a2e;border:1px solid #1f2b44;border-radius:12px;padding:18px 20px;margin-bottom:12px}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600;border:1px solid;margin:2px 4px 2px 0}
.big{font-size:40px;font-weight:700;line-height:1.1}
.muted{color:#8a96ad;font-size:13px}
.mono{font-family:monospace;font-size:14px;word-break:break-all}
section[data-testid="stSidebar"] div[role="radiogroup"]{gap:2px}
section[data-testid="stSidebar"] div[role="radiogroup"] > label{padding:8px 12px;border-radius:8px;margin:0;width:100%;cursor:pointer}
section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child{display:none}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover{background:#1a2439}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked){background:#1f2b44}
section[data-testid="stSidebar"] div[role="radiogroup"] > label p{font-size:15px;margin:0}
</style>""", unsafe_allow_html=True)


def badge(text, color):
    return f'<span class="badge" style="color:{color};border-color:{color}">{text}</span>'


def short(addr):
    return f"{addr[:10]}...{addr[-6:]}" if isinstance(addr, str) and len(addr) > 16 else str(addr)


@st.cache_data
def load(path):
    leads = pd.read_csv(path / "leads.csv", dtype={"entity_id": str, "pattern_type": str, "evidence": str,
                                                    "evidence_text": str, "priority": str})
    metrics = json.loads((path / "metrics.json").read_text())
    ep = path / "edges.csv"
    edges = pd.read_csv(ep, dtype=str) if ep.exists() else pd.DataFrame(columns=["src", "dst"])
    return leads, metrics, edges


src = PREVIEW if (PREVIEW / "leads.csv").exists() else OUT
leads, metrics, edges = load(src)
top = leads.head(100)
labels = dict(zip(leads["entity_id"], leads["label"]))


def draw_graph(sel, height=460):
    nb = edges[(edges["src"] == sel) | (edges["dst"] == sel)]
    G = nx.DiGraph()
    G.add_edges_from(zip(nb["src"], nb["dst"]))
    if not G.number_of_nodes():
        st.info("No neighbours found for this lead.")
        return
    pos = nx.spring_layout(G, seed=42)
    nodes = list(G.nodes())
    ex, ey = [], []
    for a, b in G.edges():
        ex += [pos[a][0], pos[b][0], None]
        ey += [pos[a][1], pos[b][1], None]
    groups = {
        "Selected lead": [n for n in nodes if n == sel],
        "Planted illicit (synthetic label)": [n for n in nodes if n != sel and labels.get(n) == 1],
        "Other wallet": [n for n in nodes if n != sel and labels.get(n) != 1],
    }
    colors = {"Selected lead": "#f97316", "Planted illicit (synthetic label)": "#ef4444", "Other wallet": "#8b5cf6"}
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ex, y=ey, mode="lines", line=dict(width=1, color="#64748b"),
                             hoverinfo="none", showlegend=False))
    for name, grp in groups.items():
        if grp:
            fig.add_trace(go.Scatter(
                x=[pos[n][0] for n in grp], y=[pos[n][1] for n in grp], mode="markers", name=name,
                marker=dict(size=18 if name == "Selected lead" else 10, color=colors[name]),
                text=grp, hoverinfo="text"))
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      showlegend=True, legend=dict(orientation="h", y=1.08, x=0),
                      height=height, margin=dict(l=0, r=0, t=40, b=0),
                      xaxis=dict(visible=False), yaxis=dict(visible=False))
    st.plotly_chart(fig)


def entity_card(sel):
    r = leads.loc[leads["entity_id"] == sel].iloc[0]
    tier = r["priority"]
    tags = [t for t in str(r["evidence_text"]).split("; ") if t and t != "No strong signals"]
    tag_html = "".join(badge(t, "#60a5fa") for t in tags) or '<span class="muted">No strong signals</span>'
    score = f"{r['risk_score']:.1f}"
    vol_in, vol_out = f"{r['total_in']:,.2f}", f"{r['total_out']:,.2f}"
    txs_n = f"{int(r['tx_count']):,}"
    cps = f"{int(r['unique_counterparties']):,}"
    pt = f"{r['pass_through_ratio']:.2f}"
    first, last = str(r.get("first_seen", "")), str(r.get("last_seen", ""))
    cluster = str(int(r["cluster"])) if r["cluster"] >= 0 else "Noise"
    st.markdown(
        f'<div class="card"><div class="mono">{sel}</div>'
        f'<div style="margin-top:8px">{badge(tier + " risk", TIER_COLOR[tier])}'
        f'{badge("Cluster " + cluster, "#a78bfa")}</div>'
        f'<div style="display:flex;justify-content:space-between;margin-top:18px">'
        f'<div><div class="muted">Threat score</div><div class="big">{score}<span class="muted" style="font-size:20px"> /100</span></div></div>'
        f'<div><div class="muted">Total inflow (BTC)</div><div class="big" style="font-size:26px">{vol_in}</div></div>'
        f'<div><div class="muted">Total outflow (BTC)</div><div class="big" style="font-size:26px">{vol_out}</div></div>'
        f'</div><div class="muted" style="margin-top:18px">Behavioural signatures</div><div>{tag_html}</div></div>',
        unsafe_allow_html=True)
    c = st.columns(4)
    c[0].metric("Transactions", txs_n)
    c[1].metric("Unique counterparties", cps)
    c[2].metric("Pass-through ratio", pt)
    c[3].metric("First seen to last seen", f"{first} to {last}")
    st.caption(f"Synthetic label: {r['pattern_type']}. Shown for checking only; not used for scoring.")


st.sidebar.markdown("### V.E.C.T.O.R")
st.sidebar.caption("SIH26146 prototype on synthetic data. Not a measure of real-world detection performance.")
page = st.sidebar.radio("Menu", PAGES, label_visibility="collapsed")
st.sidebar.divider()
n_hot = int((leads["priority"].isin(["Critical", "High"])).sum())
st.sidebar.markdown(f'<div class="muted">Risk Queue</div><div class="big" style="font-size:28px">{n_hot}</div>'
                    f'<div class="muted">critical or high</div>', unsafe_allow_html=True)

if page == "Overview":
    st.title("Overview")
    tgt = top.iloc[0]["entity_id"]
    st.markdown(f'<div class="card"><span class="badge" style="color:#ef4444;border-color:#ef4444">'
                f'Top-ranked lead</span><div class="muted" style="margin-top:8px">The highest threat score in this run.</div></div>',
                unsafe_allow_html=True)
    entity_card(tgt)
    left, right = st.columns([2, 1])
    with left:
        st.subheader("Investigative graph neighbourhood (1 hop)")
        draw_graph(tgt, height=420)
    with right:
        st.subheader("Evidence")
        for item in str(leads.iloc[0]["evidence_text"]).split("; "):
            st.write(f"• {item}")
    st.subheader("Top 10 leads")
    st.dataframe(top.head(10)[["rank", "entity_id", "priority", "risk_score", "evidence_text"]],
                 hide_index=True, width="stretch")

elif page == "Entity Explorer":
    st.title("Entity Explorer")
    sel = st.selectbox("Address (top 100 leads)", top["entity_id"])
    entity_card(sel)
    st.subheader("Recent flows")
    outs = edges.loc[edges["src"] == sel, "dst"].head(5).tolist()
    ins = edges.loc[edges["dst"] == sel, "src"].head(5).tolist()
    for a in outs:
        st.write(f"→ Sends to {short(a)}")
    for a in ins:
        st.write(f"← Receives from {short(a)}")
    if not outs and not ins:
        st.write("No neighbours in the exported graph.")
    st.caption("Amounts per link are not exported yet, so flows show counterparties only.")

elif page == "Risk Queue":
    st.title("Risk Queue")
    choice = st.selectbox("Priority", ["All"] + TIERS)
    q = (leads if choice == "All" else leads[leads["priority"] == choice]).head(100)
    st.download_button("Export CSV", q.to_csv(index=False), "top_leads.csv", "text/csv")
    st.dataframe(
        q[["rank", "entity_id", "priority", "risk_score", "evidence_text"]],
        hide_index=True, width="stretch",
        column_config={
            "risk_score": st.column_config.ProgressColumn("Threat score", min_value=0, max_value=100, format="%.1f"),
            "evidence_text": st.column_config.TextColumn("Evidence", width="large"),
        })

elif page == "Transaction Graph":
    st.title("Transaction Graph")
    st.caption("1-hop neighbourhood of the selected entity, from edges.csv.")
    sel = st.selectbox("Entity address (top 100 leads)", top["entity_id"])
    draw_graph(sel)

elif page == "Behavioral Clusters":
    st.title("Behavioral Clusters")
    st.caption("HDBSCAN groups on standardised features. Clusters are numbered only. "
               "High-anomaly share is the fraction of members with anomaly score 0.5 or more.")
    cl = leads[leads["cluster"] >= 0]
    g = (cl.groupby("cluster")
         .agg(n=("entity_id", "size"), vol=("total_out", "sum"), anomaly=("anomaly_score", "mean"),
              hi=("anomaly_score", lambda s: (s >= 0.5).mean()))
         .sort_values("anomaly", ascending=False).head(8))
    cols = st.columns(4)
    for i, (cid, row) in enumerate(g.iterrows()):
        ps = set(cl.loc[cl["cluster"] == cid, "priority"])
        tier = next(t for t in TIERS if t in ps)
        n_txt, vol_txt = f"{int(row['n']):,}", f"{row['vol']:,.2f}"
        hi_txt, idx_txt = f"{row['hi'] * 100:.0f}%", f"{row['anomaly'] * 100:.0f}%"
        with cols[i % 4]:
            st.markdown(
                f'<div class="card"><div style="display:flex;justify-content:space-between">'
                f'<span class="muted mono">C-{int(cid)}</span>{badge(tier, TIER_COLOR[tier])}</div>'
                f'<div style="font-size:20px;font-weight:600;margin-top:12px">Cluster {int(cid)}</div>'
                f'<div class="muted">{n_txt} entities</div>'
                f'<div style="display:flex;justify-content:space-between;margin-top:18px">'
                f'<div><div class="muted">Total outflow (BTC)</div><div>{vol_txt}</div></div>'
                f'<div style="text-align:right"><div class="muted">High-anomaly share</div>'
                f'<div style="color:{TIER_COLOR[tier]}">{hi_txt}</div></div></div>'
                f'<div class="muted" style="margin-top:12px">Mean anomaly index {idx_txt}</div></div>',
                unsafe_allow_html=True)
    n_noise = int((leads["cluster"] == -1).sum())
    st.info(f"{n_noise:,} entities are unclustered (noise). They are scored against all entities.")

elif page == "Investigations":
    st.title("Investigations")
    st.caption("Case cards generated from the top 10 leads. Status is set by the pipeline, not by an analyst.")
    for rank, r in top.head(10).iterrows():
        tier = r["priority"]
        case = f"INV-2026-{int(r['rank']):03d}"
        notes = (f"Threat score {r['risk_score']:.1f}/100, cluster "
                 f"{int(r['cluster']) if r['cluster'] >= 0 else 'noise'}, "
                 f"{int(r['unique_counterparties']):,} counterparties.")
        st.markdown(
            f'<div class="card"><div>{badge(case, "#94a3b8")}{badge(tier + " priority", TIER_COLOR[tier])}'
            f'{badge("Status: Open", "#38bdf8")}</div>'
            f'<div style="font-size:18px;font-weight:600;margin-top:10px">Lead {short(r["entity_id"])}</div>'
            f'<div class="muted" style="margin-top:6px">{r["evidence_text"]}</div>'
            f'<div style="margin-top:10px;padding:10px;border-radius:8px;background:#0b1220">'
            f'<span class="muted">Pipeline notes: </span>{notes}</div></div>',
            unsafe_allow_html=True)

elif page == "Model Performance":
    st.title("Model Performance")
    st.caption("Every value below is read from metrics.json, produced by the pipeline run.")
    rows = [(k, v) for k, v in metrics.items() if k != "runtime_seconds"]
    st.dataframe(pd.DataFrame(rows, columns=["metric", "value"]), hide_index=True, width="stretch")
    st.caption("The cold-start holdout recall is 0 for the held-out fan_in_fan_out pattern. It is reported as measured.")

else:
    st.title("Data Sources")
    st.dataframe(pd.DataFrame([
        {"source": "leads.csv", "rows": f"{len(leads):,}", "used for": "Risk Queue, Entity Explorer, clusters, cases"},
        {"source": "edges.csv", "rows": f"{len(edges):,}", "used for": "Transaction Graph and flows"},
        {"source": "metrics.json", "rows": "1 file", "used for": "Model Performance"},
    ]), hide_index=True, width="stretch")
    st.caption(f"Read from: {src}")
