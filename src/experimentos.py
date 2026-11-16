"""Experimentos do trabalho, em duas fases.

  python src/experimentos.py otimizar
      Gera os cenários, resolve cada variante por PLI e por GRASP e grava:
        cenarios/solucoes.json       posições e roteadores de cada configuração
        resultados/otimizacao.csv    tamanho e tempo de PLI e GRASP

  python src/experimentos.py margem [--processos 2]
      Análise de sensibilidade: CDS-H com cobertura só por enlaces com folga
      >= 5 dB (a margem recomendada pelo artigo-base), sem queda de nós.
      Grava resultados/margem.csv.

  python src/experimentos.py simular [--processos 2] [--parte 1/2]
      Simula todas as combinações (cenário x configuração x queda x semente)
      e acrescenta uma linha por rodada em resultados/brutos/simulacoes_*.csv.
      Pode ser interrompido e retomado: rodadas já gravadas são puladas.
      --parte i/k roda só a i-ésima de k fatias (para dividir entre máquinas).

Os parâmetros de rádio, área e tráfego estão em sim_base.py.
"""

import argparse
import csv
import glob
import json
import os
import random
import time
from multiprocessing import Pool

import networkx as nx

import grafo
import modelos
import sim_base

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQ_SOLUCOES = os.path.join(REPO, "cenarios", "solucoes.json")
ARQ_OTIMIZACAO = os.path.join(REPO, "resultados", "otimizacao.csv")
PASTA_BRUTOS = os.path.join(REPO, "resultados", "brutos")

TAMANHOS = (20, 40, 60)
CENARIOS_POR_TAMANHO = 5
SEMENTES_SIM = (1, 2)
SALTOS = sim_base.HOP_LIMIT + 1      # 3 retransmissões = até 4 enlaces
LIMITE_PLI_S = 300
ITERACOES_GRASP = 50

# Variantes do problema: nome -> (k, rota mínima, limite de saltos)
VARIANTES = {
    "CDS": (1, False, None),
    "CDS-2": (2, False, None),
    "CDS-H": (1, False, SALTOS),
    "CDS-2H": (2, False, SALTOS),
    "MOC-CDS": (1, True, None),
}

# Quedas de nós: nome -> função(G, semente) que devolve os nós que caem.
# Os mesmos nós caem em todas as configurações de um cenário.
def _queda_aleatoria(frac):
    def f(G, semente):
        rng = random.Random(1000 + semente)
        return sorted(rng.sample(sorted(G), round(frac * G.number_of_nodes())))
    return f


def _queda_hubs(frac):
    def f(G, semente):
        ordem = sorted(G, key=lambda v: (-G.degree(v), v))
        return ordem[:round(frac * G.number_of_nodes())]
    return f


QUEDAS = {
    "nenhuma": lambda G, s: [],
    "aleat10": _queda_aleatoria(0.10),
    "aleat20": _queda_aleatoria(0.20),
    "hubs10": _queda_hubs(0.10),
}


# ----------------------------------------------------------------------------
# Fase 1: otimização
# ----------------------------------------------------------------------------

def escolher_cenarios(n, quantos):
    """Primeiras `quantos` sementes cujo grafo é conectado e tem diâmetro
    <= SALTOS (senão nem a inundação completa alcança todos os nós)."""
    escolhidos, semente = [], 0
    while len(escolhidos) < quantos:
        semente += 1
        pos = grafo.gerar_cenario(n, semente)
        G = grafo.grafo_alcance(pos)
        if nx.is_connected(G) and nx.diameter(G) <= SALTOS:
            escolhidos.append((semente, pos, G))
    return escolhidos


def otimizar():
    os.makedirs(os.path.dirname(ARQ_SOLUCOES), exist_ok=True)
    os.makedirs(os.path.dirname(ARQ_OTIMIZACAO), exist_ok=True)
    solucoes, linhas = [], []

    for n in TAMANHOS:
        for semente, pos, G in escolher_cenarios(n, CENARIOS_POR_TAMANHO):
            info = grafo.resumo(G)
            conjuntos = {}
            for nome, (k, rota, saltos) in VARIANTES.items():
                p = modelos.pli(G, k, rota, saltos, limite_s=LIMITE_PLI_S)
                h = modelos.grasp(G, k, rota, saltos, iteracoes=ITERACOES_GRASP, semente=semente)
                # Usa a solução ótima da PLI; se a PLI não provou o ótimo no
                # tempo limite, usa a do GRASP (sempre viável).
                R = p["R"] if p["otimo"] else h["R"]
                assert modelos.e_viavel(G, R, k, rota, saltos=saltos)
                conjuntos[nome] = sorted(R)
                linhas.append({
                    "n": n, "cenario": semente, "variante": nome,
                    "pli_valor": p["valor"] if p["otimo"] else "",
                    "pli_otimo": p["otimo"], "pli_tempo_s": round(p["tempo_s"], 2),
                    "pli_rodadas": p["rodadas"], "pli_cortes": p["cortes"],
                    "grasp_valor": h["valor"], "grasp_tempo_s": round(h["tempo_s"], 2),
                    "grasp_iter_melhor": h["historico"].index(h["valor"]) + 1,
                    "usado": len(R), "saltos_max": modelos.saltos_via_roteadores(G, R),
                    "grau_medio": round(info["grau_medio"], 2), "diametro": info["diametro"],
                })
                print(f"n={n} cenário {semente} {nome:8s} PLI {p['valor']} ({p['tempo_s']:.1f}s, ótimo {p['otimo']})"
                      f" GRASP {h['valor']} ({h['tempo_s']:.1f}s)", flush=True)

            conjuntos["grau"] = sorted(modelos.regra_grau(G))
            conjuntos["aleatorio"] = sorted(modelos.aleatorio(G, len(conjuntos["CDS-2H"]), semente))
            for nome in ("grau", "aleatorio"):
                R = set(conjuntos[nome])
                linhas.append({"n": n, "cenario": semente, "variante": nome, "usado": len(R),
                               "saltos_max": modelos.saltos_via_roteadores(G, R),
                               "grau_medio": round(info["grau_medio"], 2), "diametro": info["diametro"]})

            solucoes.append({"n": n, "cenario": semente, "posicoes": pos, "roteadores": conjuntos})

    with open(ARQ_SOLUCOES, "w", encoding="utf-8") as f:
        json.dump(solucoes, f)
    campos = list(dict.fromkeys(c for linha in linhas for c in linha))
    with open(ARQ_OTIMIZACAO, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)
    print("Gravado:", ARQ_SOLUCOES, "e", ARQ_OTIMIZACAO)


# ----------------------------------------------------------------------------
# Fase 2: simulação
# ----------------------------------------------------------------------------

def configuracoes(sol):
    """Configurações de papéis de um cenário: nome -> {nó: papel}.

    "padrao": todos CLIENT (como vem de fábrica).
    "<conjunto>/client": roteadores do conjunto, demais CLIENT.
    "<conjunto>/mute":   roteadores do conjunto, demais CLIENT_MUTE
                         (só os roteadores retransmitem).
    """
    n = len(sol["posicoes"])
    confs = {"padrao": {}}
    for nome, R in sol["roteadores"].items():
        R = set(R)
        for modo, resto in (("client", "CLIENT"), ("mute", "CLIENT_MUTE")):
            confs[f"{nome}/{modo}"] = {v: ("ROUTER" if v in R else resto) for v in range(n)}
    return confs


def tarefas(solucoes):
    for sol in solucoes:
        G = grafo.grafo_alcance(sol["posicoes"])
        for queda, f in QUEDAS.items():
            falhos = f(G, sol["cenario"])
            for conf_nome in configuracoes(sol):
                for s in SEMENTES_SIM:
                    yield (sol["n"], sol["cenario"], conf_nome, queda, s, falhos)


def _rodar(tarefa, sol_por_chave):
    n, cen, conf_nome, queda, s, falhos = tarefa
    sol = sol_por_chave[(n, cen)]
    papeis = configuracoes(sol)[conf_nome]
    t0 = time.perf_counter()
    m = simular_mod.simular(sol["posicoes"], papeis, s, falhos)
    linha = {"n": n, "cenario": cen, "config": conf_nome, "queda": queda, "semente": s,
             "roteadores": sum(1 for p in papeis.values() if p == "ROUTER"),
             "roteadores_caidos": sum(1 for v in falhos if papeis.get(v) == "ROUTER")}
    linha.update({k: (float(v) if isinstance(v, float) else v) for k, v in m.items()})
    linha["tempo_s"] = round(time.perf_counter() - t0, 1)
    return linha


_SOL = None


def _init(solucoes):
    global _SOL, simular_mod
    import simular as simular_mod  # noqa: F401  (carrega o simulador em cada processo)
    sim_base.carregar()
    _SOL = {(s["n"], s["cenario"]): s for s in solucoes}


def _rodar_worker(tarefa):
    return _rodar(tarefa, _SOL)


def simular_tudo(processos, parte):
    with open(ARQ_SOLUCOES, encoding="utf-8") as f:
        solucoes = json.load(f)
    i, k = parte
    todas = list(tarefas(solucoes))
    minhas = [t for j, t in enumerate(todas) if j % k == i - 1]

    os.makedirs(PASTA_BRUTOS, exist_ok=True)
    arq = os.path.join(PASTA_BRUTOS, f"simulacoes_parte{i}de{k}.csv")
    # Rodadas já gravadas em qualquer parte (permite dividir entre máquinas).
    feitas = set()
    for outro in glob.glob(os.path.join(PASTA_BRUTOS, "simulacoes_*.csv")):
        with open(outro, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                feitas.add((int(r["n"]), int(r["cenario"]), r["config"], r["queda"], int(r["semente"])))
    pendentes = [t for t in minhas if t[:5] not in feitas]
    print(f"{len(todas)} rodadas no total; {len(minhas)} nesta parte; {len(pendentes)} pendentes.", flush=True)

    novo = not os.path.exists(arq)
    t0 = time.perf_counter()
    with open(arq, "a", newline="", encoding="utf-8") as f, \
            Pool(processos, initializer=_init, initargs=(solucoes,)) as pool:
        w = None
        for j, linha in enumerate(pool.imap_unordered(_rodar_worker, pendentes), 1):
            if w is None:
                w = csv.DictWriter(f, fieldnames=list(linha))
                if novo:
                    w.writeheader()
            w.writerow(linha)
            f.flush()
            if j % 20 == 0 or j == len(pendentes):
                gasto = time.perf_counter() - t0
                print(f"{j}/{len(pendentes)} feitas, {gasto / 60:.1f} min, "
                      f"faltam ~{gasto / j * (len(pendentes) - j) / 60:.1f} min", flush=True)


MARGEM_DB = 5.0


def _rodar_margem(tarefa):
    n, cen, nome, R, modo, semente = tarefa
    sol = _SOL[(n, cen)]
    resto = "CLIENT_MUTE" if modo == "mute" else "CLIENT"
    papeis = {v: ("ROUTER" if v in R else resto) for v in range(n)}
    m = simular_mod.simular(sol["posicoes"], papeis, semente)
    linha = {"n": n, "cenario": cen, "config": f"{nome}/{modo}", "semente": semente, "roteadores": len(R)}
    linha.update({k: (float(v) if isinstance(v, float) else v) for k, v in m.items()})
    return linha


def margem(processos):
    with open(ARQ_SOLUCOES, encoding="utf-8") as f:
        solucoes = json.load(f)
    tarefas_m = []
    for sol in solucoes:
        G = grafo.grafo_alcance(sol["posicoes"])
        p = modelos.pli(G, 1, saltos=SALTOS, margem=MARGEM_DB, limite_s=LIMITE_PLI_S)
        R = p["R"] if p["otimo"] else modelos.grasp(G, 1, saltos=SALTOS, margem=MARGEM_DB,
                                                     iteracoes=ITERACOES_GRASP, semente=sol["cenario"])["R"]
        assert modelos.e_viavel(G, R, 1, saltos=SALTOS, margem=MARGEM_DB)
        print(f"n={sol['n']} cenário {sol['cenario']}: CDS-H5 com {len(R)} roteadores", flush=True)
        for modo in ("mute", "client"):
            for s in SEMENTES_SIM:
                tarefas_m.append((sol["n"], sol["cenario"], "CDS-H5", sorted(R), modo, s))
    linhas = []
    with Pool(processos, initializer=_init, initargs=(solucoes,)) as pool:
        for linha in pool.imap_unordered(_rodar_margem, tarefas_m):
            linhas.append(linha)
    arq = os.path.join(REPO, "resultados", "margem.csv")
    with open(arq, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(sorted(linhas, key=lambda r: (r["n"], r["cenario"], r["config"], r["semente"])))
    print("Gravado:", arq)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fase", choices=["otimizar", "simular", "margem"])
    ap.add_argument("--processos", type=int, default=os.cpu_count())
    ap.add_argument("--parte", default="1/1", help="fatia i/k das rodadas (padrão 1/1 = todas)")
    a = ap.parse_args()
    sim_base.carregar()
    if a.fase == "otimizar":
        otimizar()
    elif a.fase == "margem":
        margem(a.processos)
    else:
        i, k = (int(x) for x in a.parte.split("/"))
        simular_tudo(a.processos, (i, k))
