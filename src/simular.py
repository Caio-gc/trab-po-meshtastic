"""Roda uma configuração de papéis no simulador e devolve as métricas.

Usa diretamente as classes do Meshtasticator (`DiscreteEventSim`), sem alterar
o simulador, para poder desligar o movimento dos nós e repetir rodadas com
sementes diferentes. A queda de nós é simulada retirando esses nós da rede
antes da rodada (eles não transmitem nem recebem).
"""

import random

import sim_base
from grafo import _configs_do_simulador


def simular(posicoes, papeis, semente, falhos=()):
    """Simula a rede e devolve um dicionário de métricas.

    posicoes  lista de (x, y, z) de todos os nós do cenário
    papeis    dicionário nó -> "ROUTER" / "CLIENT" / "CLIENT_MUTE"
    semente   semente aleatória da rodada (MAC, ruído dos enlaces)
    falhos    nós que caíram (são retirados da rede)

    Métricas (as que o simulador calcula; ver lib/discrete_event_sim.py):
      alcance       fração média dos nós vivos que recebem cada mensagem
      pacotes_msg   transmissões por mensagem criada
      colisoes      fração dos pacotes percebidos que colidiram
      ocupacao      fração do tempo em que cada nó, em média, transmite
      atraso_ms     atraso médio de recepção
    """
    conf = sim_base.carregar()
    from lib.discrete_event_sim import DiscreteEventSim

    falhos = set(falhos)
    vivos = [i for i in range(len(posicoes)) if i not in falhos]
    # O simulador usa o número do nó como índice de lista: renumeramos 0..m-1.
    pos_vivos = [posicoes[i] for i in vivos]
    papeis_vivos = {novo: papeis.get(antigo, "CLIENT") for novo, antigo in enumerate(vivos)}

    conf.NR_NODES = len(pos_vivos)
    conf.SEED = semente
    configs = _configs_do_simulador(pos_vivos, papeis_vivos)

    random.seed(semente)
    sim = DiscreteEventSim(conf, configs)
    sim.run_simulation()
    r = sim.get_results()

    msgs = r["messageSeq"]
    return {
        "nos_vivos": len(pos_vivos),
        "mensagens": msgs,
        "pacotes": r["sent"],
        "alcance": r["nodeReach"],
        "pacotes_msg": r["sent"] / msgs if msgs else float("nan"),
        "colisoes": r["collisionRate"],
        "ocupacao": r["txAirUtilizationRate"],
        "atraso_ms": r["meanDelay"],
    }


if __name__ == "__main__":
    # Teste rápido: python src/simular.py
    import time
    import grafo
    import modelos

    pos = grafo.gerar_cenario(40, 1)
    G = grafo.grafo_alcance(pos)
    R = modelos.pli(G, k=2, saltos=4)["R"]
    for nome, papeis in [
        ("todos CLIENT", {}),
        ("CDS-2H + MUTE", {v: ("ROUTER" if v in R else "CLIENT_MUTE") for v in G}),
    ]:
        t0 = time.perf_counter()
        m = simular(pos, papeis, semente=1)
        print(f"{nome:15s} {time.perf_counter() - t0:5.1f}s", {k: round(v, 3) for k, v in m.items()})
