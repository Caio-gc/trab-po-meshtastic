"""Escolha dos nós roteadores: problema, métodos e verificação.

Problema (conjunto k-dominante conectado). Dado o grafo de alcance G = (V, E),
escolher o menor conjunto R de roteadores tal que:
  (a) dominação: todo nó comum v (fora de R) tem pelo menos k vizinhos em R
      (ou todos os seus vizinhos, se o grau de v for menor que k);
  (b) conexão: os roteadores formam um subgrafo conectado G[R].
Com k = 1 é o conjunto dominante conectado clássico (CDS). Com k = 2 é a
versão resiliente: cada nó comum continua coberto se um roteador vizinho cair.

Variante "rota mínima" (rota=True), o MOC-CDS de Ding et al. (2010):
  (c) todo par de nós não vizinhos com um vizinho em comum tem pelo menos um
      vizinho em comum que é roteador.
Ding et al. provam que (c) equivale a: entre quaisquer dois nós existe um
caminho mais curto do grafo cujos nós intermediários são todos roteadores.
Assim, se só os roteadores retransmitirem, nenhuma mensagem precisa de mais
saltos do que precisaria com todos retransmitindo, o que importa porque o
Meshtastic limita o número de retransmissões (3 por padrão).

Variante "limite de saltos" (saltos=H), proposta neste trabalho:
  (d) entre quaisquer dois nós existe um caminho de no máximo H enlaces cujos
      nós intermediários são todos roteadores.
Com o limite padrão do Meshtastic (3 retransmissões), H = 4. É mais fraca
que (c): não exige o caminho mais curto, só um caminho curto o bastante.
Como há uma condição por par de nós, ela entra na PLI sob demanda (cortes).

Margem de cobertura (margem=m dB): na dominação (a), só contam os vizinhos
ligados por um enlace com folga >= m dB acima da sensibilidade. Assim cada nó
comum é coberto por um enlace forte, que não falha com o ruído de cada pacote.
O artigo-base recomenda m = 5 dB. Um nó sem nenhum vizinho com essa folga
volta a contar todos os vizinhos (senão o problema ficaria inviável).

Métodos:
  regra_grau     escolhe os nós de maior grau até cobrir todos (comparação);
  aleatorio      sorteia m nós (comparação);
  pli            programação linear inteira exata (PuLP + HiGHS), com a
                 conexão garantida por fluxo a partir de uma raiz escolhida;
  grasp          GRASP: construção gulosa aleatorizada + busca local.

Este módulo usa só networkx e PuLP; não depende do simulador.
"""

import random
import time

import networkx as nx
import pulp


# ----------------------------------------------------------------------------
# Verificação
# ----------------------------------------------------------------------------

def vizinhos_cobertura(G, v, margem=0.0):
    """Vizinhos que podem cobrir v: os ligados com folga >= margem dB
    (ou todos, se nenhum tiver essa folga)."""
    if margem <= 0:
        return list(G[v])
    fortes = [u for u in G[v] if G[v][u].get("folga", float("inf")) >= margem]
    return fortes or list(G[v])


def exigencia(G, v, k, margem=0.0):
    """Quantos vizinhos roteadores o nó comum v precisa ter."""
    return min(k, len(vizinhos_cobertura(G, v, margem)))


def deficits(G, R, k, margem=0.0):
    """Para cada nó comum, quantos vizinhos roteadores ainda faltam."""
    falta = {}
    for v in G:
        if v in R:
            continue
        viz = vizinhos_cobertura(G, v, margem)
        d = min(k, len(viz)) - sum(1 for u in viz if u in R)
        if d > 0:
            falta[v] = d
    return falta


def pares_2_saltos(G):
    """Pares (u, v) não vizinhos com vizinho em comum -> conjunto desses vizinhos."""
    pares = {}
    for w in G:
        viz = sorted(G[w])
        for i, u in enumerate(viz):
            for v in viz[i + 1:]:
                if not G.has_edge(u, v):
                    pares.setdefault((u, v), set()).add(w)
    return pares


def pares_descobertos(pares, R):
    """Pares a 2 saltos que ainda não têm um vizinho comum roteador."""
    return {p for p, meio in pares.items() if not (meio & R)}


def e_viavel(G, R, k=1, rota=False, pares=None, saltos=None, margem=0.0):
    """True se R domina com ordem k, induz subgrafo conectado, cobre todos os
    pares a 2 saltos (rota=True) e respeita o limite de saltos (saltos=H)."""
    if not R:
        return False
    if deficits(G, R, k, margem):
        return False
    if rota:
        if pares is None:
            pares = pares_2_saltos(G)
        if pares_descobertos(pares, R):
            return False
    if not nx.is_connected(G.subgraph(R)):
        return False
    if saltos is not None and pares_violados(G, R, saltos):
        return False
    return True


def distancias_via_roteadores(G, R, origem):
    """Enlaces necessários para a mensagem de `origem` chegar a cada nó quando
    só a origem e os roteadores retransmitem (busca em largura)."""
    dist = {origem: 0}
    fila = [origem]
    for u in fila:
        if u != origem and u not in R:
            continue
        for w in G[u]:
            if w not in dist:
                dist[w] = dist[u] + 1
                fila.append(w)
    return dist


def pares_violados(G, R, H):
    """Pares (u, v), u < v, sem caminho de até H enlaces passando só por roteadores."""
    violados = []
    for u in G:
        dist = distancias_via_roteadores(G, R, u)
        for v in G:
            if u < v and dist.get(v, H + 1) > H:
                violados.append((u, v))
    return violados


def saltos_via_roteadores(G, R):
    """Maior número de enlaces que uma mensagem precisa percorrer, entre todos
    os pares de nós, quando só os nós de R retransmitem.

    Com o limite de saltos padrão (3 retransmissões), o máximo útil é 4.
    Devolve None se algum par não tiver caminho.
    """
    pior = 0
    for origem in G:
        # Busca em largura: a origem transmite; daí em diante só roteadores
        # repassam a mensagem.
        dist = {origem: 0}
        fila = [origem]
        for u in fila:
            if u != origem and u not in R:
                continue
            for w in G[u]:
                if w not in dist:
                    dist[w] = dist[u] + 1
                    fila.append(w)
        if len(dist) < G.number_of_nodes():
            return None
        pior = max(pior, max(dist.values()))
    return pior


# ----------------------------------------------------------------------------
# Métodos de comparação
# ----------------------------------------------------------------------------

def regra_grau(G, k=1):
    """Regra simples: inclui os nós de maior grau até todos estarem cobertos.

    Não garante que os roteadores fiquem conectados (é justamente uma das
    diferenças para os métodos de otimização).
    """
    R = set()
    for v in sorted(G, key=lambda v: (-G.degree(v), v)):
        if not deficits(G, R, k):
            break
        R.add(v)
    return R


def aleatorio(G, m, semente):
    """Sorteia m roteadores."""
    rng = random.Random(semente)
    return set(rng.sample(sorted(G), m))


# ----------------------------------------------------------------------------
# PLI exata
# ----------------------------------------------------------------------------

def _resolvedor(limite_s):
    disponiveis = pulp.listSolvers(onlyAvailable=True)
    if "HiGHS" in disponiveis:
        return pulp.HiGHS(msg=False, timeLimit=limite_s)
    if "PULP_CBC_CMD" in disponiveis:
        return pulp.PULP_CBC_CMD(msg=False, timeLimit=limite_s)
    raise RuntimeError("Nenhum resolvedor de PLI encontrado (instale highspy).")


def pli(G, k=1, rota=False, saltos=None, limite_s=300, margem=0.0):
    """Resolve o conjunto k-dominante conectado mínimo por PLI.

    Variáveis:
      x[v] = 1 se v é roteador;
      y[v] = 1 se v é a raiz do fluxo (exatamente uma, e precisa ser roteador);
      g[v] >= 0 fluxo que sai de uma fonte artificial e entra pela raiz;
      f[u,v] >= 0 fluxo no arco u -> v (para cada aresta, os dois sentidos).

    Conexão por fluxo: a fonte envia uma unidade para cada roteador; o fluxo
    só pode passar por arcos entre dois roteadores. Se todo roteador recebe a
    sua unidade, todos estão ligados à raiz, logo G[R] é conectado.

    Com rota=True, acrescenta para cada par (u, v) a 2 saltos:
      soma de x[w] sobre os vizinhos comuns w de u e v >= 1.

    Com saltos=H, resolve por geração de cortes: resolve o modelo, procura
    pares (u, v) sem caminho de até H enlaces passando só por roteadores e,
    para cada um, acrescenta o corte
      soma de x[w] sobre W(u, v) fora de R >= 1,
    em que W(u, v) = {w : d(u, w) + d(w, v) <= H} contém todos os nós que
    podem estar no meio de um caminho curto de u a v, e R é a solução atual.
    O corte é válido: toda solução viável tem um caminho curto de u a v só
    com roteadores, e algum nó desse caminho não está em R (senão R já o
    teria). Repete até não haver par violado.

    Para reduzir as rodadas, entram desde o início desigualdades válidas para
    os pares a exatamente H saltos no grafo: qualquer caminho de até H enlaces
    entre eles é um caminho mínimo, então para cada posição i = 1..H-1 algum
    nó w com d(u, w) = i e d(w, v) = H - i precisa ser roteador.

    Devolve um dicionário com R, status, valor, limitante inferior e tempo.
    """
    n = G.number_of_nodes()
    V = list(G)
    arcos = [(u, v) for u, v in G.edges()] + [(v, u) for u, v in G.edges()]

    m = pulp.LpProblem("roteadores", pulp.LpMinimize)
    x = pulp.LpVariable.dicts("x", V, cat="Binary")
    y = pulp.LpVariable.dicts("y", V, cat="Binary")
    g = pulp.LpVariable.dicts("g", V, lowBound=0)
    f = pulp.LpVariable.dicts("f", arcos, lowBound=0)

    m += pulp.lpSum(x[v] for v in V)                       # objetivo

    for v in V:
        cobre = vizinhos_cobertura(G, v, margem)
        viz = pulp.lpSum(x[u] for u in cobre)
        if k == 1:
            m += x[v] + viz >= 1                           # dominação
        else:
            m += viz >= exigencia(G, v, k, margem) * (1 - x[v])  # k-dominação

    if rota:
        for meio in pares_2_saltos(G).values():
            m += pulp.lpSum(x[w] for w in meio) >= 1       # rota mínima

    m += pulp.lpSum(y[v] for v in V) == 1                  # uma raiz
    for v in V:
        m += y[v] <= x[v]
        m += g[v] <= n * y[v]
        entra = g[v] + pulp.lpSum(f[(u, v)] for u in G[v])
        sai = pulp.lpSum(f[(v, u)] for u in G[v])
        m += entra - sai == x[v]                           # cada roteador consome 1
    for (u, v) in arcos:
        m += f[(u, v)] <= (n - 1) * x[u]                   # só entre roteadores
        m += f[(u, v)] <= (n - 1) * x[v]

    t0 = time.perf_counter()
    dist = dict(nx.all_pairs_shortest_path_length(G)) if saltos else None
    rodadas, cortes = 0, 0
    if saltos:
        for u in V:
            for v in V:
                if u < v and dist[u][v] == saltos:
                    for i in range(1, saltos):
                        camada = [w for w in V if dist[u][w] == i and dist[w][v] == saltos - i]
                        m += pulp.lpSum(x[w] for w in camada) >= 1
                        cortes += 1
    while True:
        restante = max(1.0, limite_s - (time.perf_counter() - t0))
        m.solve(_resolvedor(restante))
        rodadas += 1
        R = {v for v in V if x[v].value() is not None and x[v].value() > 0.5}
        if not saltos or pulp.LpStatus[m.status] != "Optimal":
            break
        violados = pares_violados(G, R, saltos)
        if not violados or time.perf_counter() - t0 > limite_s:
            break
        for (u, v) in violados:
            W = [w for w in V if w not in (u, v) and w not in R
                 and dist[u][w] + dist[w][v] <= saltos]
            if not W:
                raise ValueError(f"Par {u}-{v} está a mais de {saltos} saltos no próprio grafo.")
            m += pulp.lpSum(x[w] for w in W) >= 1
            cortes += 1
    tempo = time.perf_counter() - t0
    limitante = None
    try:  # HiGHS informa o limitante inferior (útil se estourar o tempo)
        limitante = m.solverModel.getInfo().mip_dual_bound
    except Exception:
        pass
    return {
        "R": R,
        "status": pulp.LpStatus[m.status],
        "otimo": (pulp.LpStatus[m.status] == "Optimal" and tempo < limite_s
                  and e_viavel(G, R, k, rota, saltos=saltos, margem=margem)),
        "rodadas": rodadas,
        "cortes": cortes,
        "valor": len(R),
        "limitante": limitante,
        "tempo_s": tempo,
    }


# ----------------------------------------------------------------------------
# GRASP
# ----------------------------------------------------------------------------

def _construcao(G, k, alfa, rng, pares=None, saltos=None, dist=None, margem=0.0):
    """Construção gulosa aleatorizada que mantém os roteadores conectados.

    Começa por um nó sorteado entre os de maior grau. A cada passo, os
    candidatos são os nós vizinhos dos roteadores já escolhidos (assim o
    conjunto continua conectado). O ganho de um candidato é quanto ele reduz
    a soma dos déficits de cobertura. A lista restrita de candidatos (LRC)
    guarda os de ganho >= gmax - alfa * (gmax - gmin), e um deles é sorteado.
    """
    graus = sorted({G.degree(v) for v in G})
    corte = graus[-1] - alfa * (graus[-1] - graus[0])
    R = {rng.choice([v for v in G if G.degree(v) >= corte])}
    falta = deficits(G, R, k, margem)
    cobre = {v: set(vizinhos_cobertura(G, v, margem)) for v in G}
    abertos = pares_descobertos(pares, R) if pares else set()

    while falta or abertos:
        candidatos = {w for r in R for w in G[r]} - R
        ganho = {}
        for c in candidatos:
            ganho[c] = falta.get(c, 0) + sum(1 for w in G[c] if w in falta and c in cobre[w])
            if abertos:
                ganho[c] += sum(1 for p in abertos if c in pares[p])
        positivos = {c: gc for c, gc in ganho.items() if gc > 0}
        if positivos:
            gmax, gmin = max(positivos.values()), min(positivos.values())
            lrc = [c for c, gc in positivos.items() if gc >= gmax - alfa * (gmax - gmin)]
            escolhido = rng.choice(sorted(lrc))
        else:
            # Nenhum vizinho ajuda diretamente: anda em direção ao nó
            # descoberto mais próximo (primeiro passo do caminho mais curto).
            alvos = set(falta) | {w for p in abertos for w in pares[p]}
            alvo = min(alvos, key=lambda v: (min(nx.shortest_path_length(G, r, v) for r in R), v))
            caminhos = [nx.shortest_path(G, r, alvo) for r in R]
            escolhido = min(caminhos, key=len)[1]
        R.add(escolhido)
        falta = deficits(G, R, k, margem)
        abertos = pares_descobertos(pares, R) if pares else set()

    # Limite de saltos: acrescenta nós (sempre vizinhos de R, porque R já
    # domina) até nenhum par violar o limite. Ganho de um candidato = número
    # de pares violados para os quais ele pode estar no caminho curto.
    while saltos:
        violados = pares_violados(G, R, saltos)
        if not violados:
            break
        ganho = {}
        for (u, v) in violados:
            for w in G:
                if w not in R and w not in (u, v) and dist[u][w] + dist[w][v] <= saltos:
                    ganho[w] = ganho.get(w, 0) + 1
        gmax, gmin = max(ganho.values()), min(ganho.values())
        lrc = [c for c, gc in ganho.items() if gc >= gmax - alfa * (gmax - gmin)]
        R.add(rng.choice(sorted(lrc)))
    return R


def _busca_local(G, R, k, rng, pares=None, saltos=None, margem=0.0):
    """Busca local com dois movimentos, aplicados até não haver melhora:
      remoção: tira um roteador se a solução continua viável;
      troca 2-por-1: tira dois roteadores próximos e põe um nó vizinho deles.
    Ambos reduzem o número de roteadores em 1.
    """
    R = set(R)
    melhorou = True
    while melhorou:
        melhorou = False
        # 1) remoção, tentando primeiro os de menor grau
        ordem = sorted(R, key=lambda v: (G.degree(v), rng.random()))
        for r in ordem:
            if e_viavel(G, R - {r}, k, bool(pares), pares, saltos, margem):
                R.remove(r)
                melhorou = True
        if melhorou:
            continue
        # 2) troca 2-por-1 entre roteadores a até 2 saltos um do outro
        lista = sorted(R)
        rng.shuffle(lista)
        for i, a in enumerate(lista):
            for b in lista[i + 1:]:
                if b not in G[a] and not (set(G[a]) & set(G[b])):
                    continue
                for c in (set(G[a]) | set(G[b])) - R:
                    novo = (R - {a, b}) | {c}
                    if e_viavel(G, novo, k, bool(pares), pares, saltos, margem):
                        R = novo
                        melhorou = True
                        break
                if melhorou:
                    break
            if melhorou:
                break
    return R


def grasp(G, k=1, rota=False, saltos=None, iteracoes=100, alfa=0.3, semente=0, margem=0.0):
    """GRASP para o conjunto k-dominante conectado mínimo (com ou sem rota mínima).

    Devolve um dicionário com a melhor solução, o tempo e o histórico do
    melhor valor por iteração (para o gráfico de convergência).
    """
    rng = random.Random(semente)
    pares = pares_2_saltos(G) if rota else None
    dist = dict(nx.all_pairs_shortest_path_length(G)) if saltos else None
    t0 = time.perf_counter()
    melhor, historico = None, []
    for _ in range(iteracoes):
        R = _construcao(G, k, alfa, rng, pares, saltos, dist, margem)
        R = _busca_local(G, R, k, rng, pares, saltos, margem)
        if melhor is None or len(R) < len(melhor):
            melhor = R
        historico.append(len(melhor))
    return {
        "R": melhor,
        "valor": len(melhor),
        "tempo_s": time.perf_counter() - t0,
        "historico": historico,
    }


if __name__ == "__main__":
    # Teste rápido: python src/modelos.py
    import grafo
    variantes = [  # (nome, k, rota, saltos)
        ("CDS", 1, False, None), ("CDS-2", 2, False, None),
        ("CDS-H", 1, False, 4), ("CDS-2H", 2, False, 4), ("MOC-CDS", 1, True, None),
    ]
    for n in (20, 40, 60):
        G = grafo.grafo_alcance(grafo.gerar_cenario(n, 1))
        for nome, k, rota, saltos in variantes:
            p = pli(G, k, rota, saltos, limite_s=120)
            h = grasp(G, k, rota, saltos, iteracoes=20, semente=1)
            print(f"n={n} {nome:8s} | PLI {p['valor']:2d} {p['status']} {p['tempo_s']:5.1f}s rodadas {p['rodadas']}"
                  f" viável {e_viavel(G, p['R'], k, rota, saltos=saltos)} saltos {saltos_via_roteadores(G, p['R'])}"
                  f" | GRASP {h['valor']:2d} {h['tempo_s']:5.1f}s viável {e_viavel(G, h['R'], k, rota, saltos=saltos)}")
