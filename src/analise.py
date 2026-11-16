"""Tabelas e gráficos a partir dos CSV dos experimentos.

  python src/analise.py

Lê resultados/otimizacao.csv e resultados/brutos/simulacoes_*.csv e grava em
resultados/: tabelas .csv e .md e figuras .png usadas no relatório.
"""

import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(REPO, "resultados")

# Paleta categórica (ordem fixa) e cores de texto
COR = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
TINTA, TINTA2, GRADE = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": TINTA2, "axes.labelcolor": TINTA, "xtick.color": TINTA2,
    "ytick.color": TINTA2, "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "figure.dpi": 150, "savefig.bbox": "tight",
})

# Ordem e nomes das configurações nas tabelas
CONJUNTOS = ["aleatorio", "grau", "CDS", "CDS-2", "MOC-CDS", "CDS-H", "CDS-2H"]
NOME = {"aleatorio": "Aleatório", "grau": "Regra do grau", "CDS": "CDS", "CDS-2": "CDS-2",
        "MOC-CDS": "MOC-CDS", "CDS-H": "CDS-H", "CDS-2H": "CDS-2H"}
QUEDAS = ["nenhuma", "aleat10", "aleat20", "hubs10"]
NOME_QUEDA = {"nenhuma": "sem queda", "aleat10": "10% aleatórios", "aleat20": "20% aleatórios",
              "hubs10": "10% de maior grau"}


def _md(df, arq, casas=2):
    """Grava uma tabela em Markdown (para colar no relatório)."""
    df = df.copy()
    with open(arq, "w", encoding="utf-8") as f:
        cols = [str(c) for c in df.columns]
        f.write("| " + " | ".join(cols) + " |\n")
        f.write("|" + "---|" * len(cols) + "\n")
        for _, linha in df.iterrows():
            vals = []
            for v in linha:
                vals.append(f"{v:.{casas}f}" if isinstance(v, float) else str(v))
            f.write("| " + " | ".join(vals) + " |\n")


def nome_config(c):
    if c == "padrao":
        return "Padrão (todos CLIENT)"
    conj, modo = c.split("/")
    return f"{NOME[conj]} + {'resto CLIENT' if modo == 'client' else 'resto MUTE'}"


# ----------------------------------------------------------------------------
# Otimização
# ----------------------------------------------------------------------------

def tabela_otimizacao():
    d = pd.read_csv(os.path.join(RES, "otimizacao.csv"))
    linhas = []
    for (n, var), g in d.groupby(["n", "variante"]):
        linha = {"n": n, "variante": NOME.get(var, var),
                 "roteadores": g["usado"].mean(),
                 "% dos nós": 100 * g["usado"].mean() / n,
                 # vazio = algum par não se comunica só pelos roteadores
                 "enlaces máx.": ("sem caminho" if g["saltos_max"].isna().any()
                                  else int(g["saltos_max"].max()))}
        if var in ("CDS", "CDS-2", "CDS-H", "CDS-2H", "MOC-CDS"):
            linha.update({
                "PLI ótima": f"{int(g['pli_otimo'].sum())}/{len(g)}",
                "PLI tempo médio (s)": g["pli_tempo_s"].mean(),
                "PLI tempo máx. (s)": g["pli_tempo_s"].max(),
                "GRASP = ótimo": f"{int((g['grasp_valor'] == g['usado']).sum())}/{len(g)}",
                "GRASP tempo médio (s)": g["grasp_tempo_s"].mean(),
            })
        linhas.append(linha)
    t = pd.DataFrame(linhas)
    t["ordem"] = t["variante"].map({NOME[c]: i for i, c in enumerate(CONJUNTOS)})
    t = t.sort_values(["n", "ordem"]).drop(columns="ordem")
    t.to_csv(os.path.join(RES, "tabela_otimizacao.csv"), index=False)
    _md(t.fillna("—"), os.path.join(RES, "tabela_otimizacao.md"), casas=1)
    return t


def figura_roteadores(t):
    """Número de roteadores por variante e tamanho da rede."""
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    variantes = [NOME[c] for c in CONJUNTOS if c != "aleatorio"]
    ns = sorted(t["n"].unique())
    larg = 0.8 / len(variantes)
    for i, var in enumerate(variantes):
        ys = [t[(t["n"] == n) & (t["variante"] == var)]["roteadores"].iloc[0] for n in ns]
        xs = [j + (i - (len(variantes) - 1) / 2) * larg for j in range(len(ns))]
        ax.bar(xs, ys, width=larg * 0.9, color=COR[i], label=var)
    ax.set_xticks(range(len(ns)), [f"{n} nós" for n in ns])
    ax.set_ylabel("roteadores (média)")
    ax.grid(axis="x", visible=False)
    ax.legend(ncol=3, fontsize=8, loc="upper left")
    fig.savefig(os.path.join(RES, "fig_roteadores.png"))
    plt.close(fig)


# ----------------------------------------------------------------------------
# Simulação
# ----------------------------------------------------------------------------

def ler_simulacoes():
    arqs = glob.glob(os.path.join(RES, "brutos", "simulacoes_*.csv"))
    d = pd.concat([pd.read_csv(a) for a in arqs], ignore_index=True)
    d = d.drop_duplicates(["n", "cenario", "config", "queda", "semente"])
    d["conjunto"] = d["config"].str.split("/").str[0]
    d["modo"] = d["config"].str.split("/").str[1].fillna("padrao")
    return d


def tabela_desempenho(d):
    """Métricas sem queda de nós, média (e desvio-padrão do alcance) por n e configuração."""
    s = d[d["queda"] == "nenhuma"]
    g = s.groupby(["n", "config"]).agg(
        roteadores=("roteadores", "mean"),
        alcance=("alcance", "mean"), alcance_dp=("alcance", "std"),
        pacotes_msg=("pacotes_msg", "mean"), colisoes=("colisoes", "mean"),
        ocupacao=("ocupacao", "mean"), atraso_s=("atraso_ms", lambda x: x.mean() / 1000),
        rodadas=("alcance", "size")).reset_index()
    base = g[g["config"] == "padrao"].set_index("n")
    g["pacotes vs padrão (%)"] = [100 * (r.pacotes_msg / base.loc[r.n, "pacotes_msg"] - 1) for r in g.itertuples()]
    g["configuração"] = g["config"].map(nome_config)
    for c in ("alcance", "alcance_dp", "colisoes", "ocupacao"):
        g[c] = 100 * g[c]
    ordem = ["padrao"] + [f"{c}/{m}" for m in ("client", "mute") for c in CONJUNTOS]
    g["o"] = g["config"].map({c: i for i, c in enumerate(ordem)})
    g = g.sort_values(["n", "o"])
    t = g[["n", "configuração", "roteadores", "alcance", "alcance_dp", "pacotes_msg",
           "pacotes vs padrão (%)", "colisoes", "ocupacao", "atraso_s", "rodadas"]]
    t = t.rename(columns={"alcance": "alcance (%)", "alcance_dp": "dp (%)", "pacotes_msg": "pacotes/msg",
                          "colisoes": "colisões (%)", "ocupacao": "ocupação (%)", "atraso_s": "atraso (s)"})
    t.to_csv(os.path.join(RES, "tabela_desempenho.csv"), index=False)
    _md(t, os.path.join(RES, "tabela_desempenho.md"))
    return t


def tabela_resiliencia(d):
    """Alcance (%) por tipo de queda, nos maiores cenários."""
    g = d.groupby(["n", "config", "queda"])["alcance"].mean().mul(100).unstack("queda")[QUEDAS].reset_index()
    g["perda 20% (p.p.)"] = g["aleat20"] - g["nenhuma"]
    g["perda hubs (p.p.)"] = g["hubs10"] - g["nenhuma"]
    g["configuração"] = g["config"].map(nome_config)
    ordem = ["padrao"] + [f"{c}/{m}" for m in ("client", "mute") for c in CONJUNTOS]
    g["o"] = g["config"].map({c: i for i, c in enumerate(ordem)})
    g = g.sort_values(["n", "o"])
    t = g[["n", "configuração"] + QUEDAS + ["perda 20% (p.p.)", "perda hubs (p.p.)"]]
    t = t.rename(columns=NOME_QUEDA)
    t.to_csv(os.path.join(RES, "tabela_resiliencia.csv"), index=False)
    _md(t, os.path.join(RES, "tabela_resiliencia.md"), casas=1)
    return t


def figura_compromisso(d, n):
    """Alcance x transmissões por mensagem (sem queda), por configuração."""
    s = d[(d["queda"] == "nenhuma") & (d["n"] == n)]
    g = s.groupby(["conjunto", "modo"])[["alcance", "pacotes_msg"]].mean().reset_index()
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    pad = g[g["conjunto"] == "padrao"].iloc[0]
    ax.scatter(pad["pacotes_msg"], 100 * pad["alcance"], s=80, color=TINTA, marker="*", zorder=3)
    ax.annotate("Padrão", (pad["pacotes_msg"], 100 * pad["alcance"]), xytext=(6, 4),
                textcoords="offset points", fontsize=8, color=TINTA)
    for i, c in enumerate(CONJUNTOS):
        for modo, marca in (("client", "o"), ("mute", "s")):
            r = g[(g["conjunto"] == c) & (g["modo"] == modo)]
            if r.empty:
                continue
            r = r.iloc[0]
            ax.scatter(r["pacotes_msg"], 100 * r["alcance"], s=46, color=COR[i], marker=marca,
                       edgecolor="white", linewidth=1.5, zorder=3,
                       label=NOME[c] if modo == "mute" else None)
            if modo == "mute":
                ax.annotate(NOME[c], (r["pacotes_msg"], 100 * r["alcance"]), xytext=(6, -3),
                            textcoords="offset points", fontsize=8, color=TINTA2)
    ax.scatter([], [], marker="o", color=TINTA2, label="resto CLIENT (círculo)")
    ax.scatter([], [], marker="s", color=TINTA2, label="resto MUTE (quadrado)")
    ax.set_xlabel("transmissões por mensagem (menos é melhor)")
    ax.set_ylabel("alcance médio (%)")
    ax.legend(fontsize=7.5, loc="lower right", ncol=2)
    fig.savefig(os.path.join(RES, f"fig_compromisso_n{n}.png"))
    plt.close(fig)


def figura_resiliencia(d, configs):
    """Alcance por tipo de queda, um painel por tamanho de rede."""
    ns = sorted(d["n"].unique())
    fig, axs = plt.subplots(1, len(ns), figsize=(13, 3.8), sharey=True)
    larg = 0.8 / len(configs)
    for ax, n in zip(axs, ns):
        g = d[d["n"] == n].groupby(["config", "queda"])["alcance"].mean().mul(100).unstack("queda")
        for i, c in enumerate(configs):
            xs = [j + (i - (len(configs) - 1) / 2) * larg for j in range(len(QUEDAS))]
            cor = TINTA2 if c == "padrao" else COR[CONJUNTOS.index(c.split("/")[0])]
            ax.bar(xs, [g.loc[c, q] for q in QUEDAS], width=larg * 0.88, color=cor,
                   label=nome_config(c) if n == ns[0] else None)
        ax.set_xticks(range(len(QUEDAS)), ["sem\nqueda", "10%\naleatórios", "20%\naleatórios", "10% de\nmaior grau"],
                      fontsize=8)
        ax.set_title(f"{n} nós", fontsize=10, color=TINTA)
        ax.set_ylim(0, 100)
        ax.grid(axis="x", visible=False)
    axs[0].set_ylabel("alcance médio (%)")
    fig.legend(loc="upper center", ncol=len(configs), fontsize=8, bbox_to_anchor=(0.5, 1.06))
    fig.savefig(os.path.join(RES, "fig_resiliencia.png"))
    plt.close(fig)


def figura_mapa(n, cenario):
    """Mapa de um cenário com os roteadores de três variantes."""
    import networkx as nx
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import grafo
    with open(os.path.join(REPO, "cenarios", "solucoes.json"), encoding="utf-8") as f:
        sol = next(s for s in json.load(f) if s["n"] == n and s["cenario"] == cenario)
    G = grafo.grafo_alcance(sol["posicoes"])
    pos = {v: (x / 1000, y / 1000) for v, (x, y, _) in enumerate(sol["posicoes"])}
    variantes = ["CDS", "CDS-H", "CDS-2H", "MOC-CDS"]
    fig, axs = plt.subplots(1, len(variantes), figsize=(12, 3.4))
    for ax, var in zip(axs, variantes):
        R = set(sol["roteadores"][var])
        nx.draw_networkx_edges(G, pos, ax=ax, edge_color=GRADE, width=0.5)
        nx.draw_networkx_edges(G.subgraph(R), pos, ax=ax, edge_color=COR[0], width=1.5)
        nx.draw_networkx_nodes(G, pos, nodelist=[v for v in G if v not in R], ax=ax,
                               node_size=14, node_color="white", edgecolors=TINTA2, linewidths=0.8)
        nx.draw_networkx_nodes(G, pos, nodelist=sorted(R), ax=ax, node_size=40,
                               node_color=COR[1], edgecolors="white", linewidths=1)
        ax.set_title(f"{NOME[var]}: {len(R)} roteadores", fontsize=9, color=TINTA)
        ax.set_aspect("equal")
        ax.tick_params(left=True, bottom=True, labelleft=True, labelbottom=True, labelsize=7)
        ax.set_xlabel("km", fontsize=7)
    fig.savefig(os.path.join(RES, f"fig_mapa_n{n}_c{cenario}.png"))
    plt.close(fig)


if __name__ == "__main__":
    t = tabela_otimizacao()
    figura_roteadores(t)
    print(t.to_string(index=False))
    try:
        d = ler_simulacoes()
    except ValueError:
        print("Sem resultados de simulação ainda.")
    else:
        print(tabela_desempenho(d).to_string(index=False))
        print(tabela_resiliencia(d).to_string(index=False))
        for n in sorted(d["n"].unique()):
            figura_compromisso(d, n)
        figura_resiliencia(d, ["padrao", "CDS/mute", "CDS-H/mute", "CDS-2H/mute", "MOC-CDS/mute"])
    with open(os.path.join(REPO, "cenarios", "solucoes.json"), encoding="utf-8") as f:
        primeiro60 = next(s for s in json.load(f) if s["n"] == 60)
    figura_mapa(60, primeiro60["cenario"])
    print("Tabelas e figuras gravadas em", RES)
