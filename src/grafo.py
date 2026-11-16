"""Cenários de nós e grafo de alcance.

Um cenário é uma lista de posições (x, y, z) em metros. O grafo de alcance
tem um vértice por nó e uma aresta {u, v} quando cada um consegue decodificar
o outro, isto é, quando a potência recebida (RSSI) é pelo menos a
sensibilidade do rádio no preset usado.

O RSSI é calculado com as mesmas funções do simulador
(`NodeConfig.compute_rssi_and_pathloss_to`, modelo de perda de percurso 5,
"3GPP suburbano"), para o grafo e a simulação concordarem.
"""

import random

import networkx as nx
import yaml

import sim_base


def gerar_cenario(n, semente, area_m=sim_base.AREA_M):
    """Sorteia n posições numa área quadrada de lado area_m.

    Usa o gerador do próprio simulador (`find_random_position`): cada nó novo
    cai dentro do alcance de pelo menos um nó já colocado, e a pelo menos
    10 m de todos. Isso tende a produzir uma rede conectada.
    Devolve uma lista de tuplas (x, y, z).
    """
    conf = sim_base.carregar()
    sim_base.configurar(conf, area_m=area_m)
    from lib.common import find_random_position
    from lib.point import Point

    class _Ponto:  # o gerador só precisa do atributo .position
        def __init__(self, p):
            self.position = p

    random.seed(semente)
    colocados = []
    for _ in range(n):
        x, y = find_random_position(conf, colocados)
        colocados.append(_Ponto(Point(x, y, conf.HM)))
    return [(p.position.x, p.position.y, p.position.z) for p in colocados]


def _configs_do_simulador(posicoes, papeis=None):
    """Converte posições (e papéis) nos objetos NodeConfig do simulador."""
    conf = sim_base.carregar()
    from lib.node import NodeConfig, MESHTASTIC_ROLE
    from lib.point import Point

    papeis = papeis or {}
    configs = []
    for i, (x, y, z) in enumerate(posicoes):
        papel = MESHTASTIC_ROLE[papeis.get(i, "CLIENT")]
        configs.append(NodeConfig(i, Point(x, y, z), conf.PERIOD, conf.PTX,
                                  conf.FREQ, papel, conf.GL, conf.hopLimit))
    return configs


def grafo_alcance(posicoes, margem_db=0.0):
    """Monta o grafo de alcance de um cenário.

    margem_db exige um enlace mais forte que o mínimo (RSSI >= sensibilidade
    + margem). Com margem 0 o critério é o mesmo do simulador.
    Cada vértice guarda a posição (atributo 'pos') e cada aresta o RSSI e a
    folga do enlace (RSSI menos a sensibilidade, em dB).
    """
    conf = sim_base.carregar()
    sens = conf.current_preset["sensitivity"]
    configs = _configs_do_simulador(posicoes)

    G = nx.Graph()
    for c in configs:
        G.add_node(c.node_id, pos=(c.position.x, c.position.y))
    for a in configs:
        for b in configs:
            if a.node_id < b.node_id:
                rssi, _ = a.compute_rssi_and_pathloss_to(b, conf)
                if rssi >= sens + margem_db:
                    G.add_edge(a.node_id, b.node_id, rssi=rssi, folga=rssi - sens)
    return G


def salvar_yaml(posicoes, papeis, arquivo):
    """Grava o cenário no formato do simulador (`loraMesh.py --from-file`).

    papeis: dicionário nó -> "ROUTER", "CLIENT" ou "CLIENT_MUTE"
    (nós ausentes ficam como CLIENT).
    """
    conf = sim_base.carregar()
    dados = {}
    for i, (x, y, z) in enumerate(posicoes):
        papel = papeis.get(i, "CLIENT")
        dados[i] = {
            "x": float(x), "y": float(y), "z": float(z),
            "isRouter": papel == "ROUTER",
            "isRepeater": False,
            "isClientMute": papel == "CLIENT_MUTE",
            "antennaGain": conf.GL,
            "hopLimit": conf.hopLimit,
            "neighborInfo": False,
        }
    with open(arquivo, "w", encoding="utf-8") as f:
        yaml.safe_dump(dados, f, sort_keys=False)


def ler_yaml(arquivo):
    """Lê um cenário no formato do simulador. Devolve (posicoes, papeis)."""
    with open(arquivo, encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    posicoes, papeis = [], {}
    for i, nd in sorted(dados.items()):
        posicoes.append((nd["x"], nd["y"], nd["z"]))
        if nd.get("isRouter"):
            papeis[i] = "ROUTER"
        elif nd.get("isClientMute"):
            papeis[i] = "CLIENT_MUTE"
        else:
            papeis[i] = "CLIENT"
    return posicoes, papeis


def resumo(G):
    """Números básicos do grafo, usados nas tabelas do relatório."""
    graus = [d for _, d in G.degree()]
    conexo = nx.is_connected(G)
    return {
        "nos": G.number_of_nodes(),
        "arestas": G.number_of_edges(),
        "grau_medio": sum(graus) / len(graus),
        "grau_min": min(graus),
        "conexo": conexo,
        "diametro": nx.diameter(G) if conexo else None,
    }


if __name__ == "__main__":
    # Teste rápido: python src/grafo.py
    for n in (20, 40, 60):
        for s in (1, 2, 3):
            G = grafo_alcance(gerar_cenario(n, s))
            print(n, s, resumo(G))
