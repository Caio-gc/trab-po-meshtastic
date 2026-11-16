"""Grava uma configuração de papéis no formato do simulador, para abrir na
interface gráfica do Meshtasticator (útil para demonstração).

  python src/exportar_yaml.py 60 1 CDS-2H mute

Grava <Meshtasticator>/out/<n>_<cenario>_<conjunto>_<modo>.yaml e mostra o
comando para abrir. Conjuntos: CDS, CDS-2, CDS-H, CDS-2H, MOC-CDS, grau,
aleatorio, ou "padrao" (todos CLIENT). Modo: client ou mute.

Observação: o loraMesh.py usa a configuração padrão do simulador, em que
cerca de 30% dos nós se movem; para a demonstração isso não atrapalha, mas os
números do trabalho vêm de src/experimentos.py (nós parados).
"""

import json
import os
import sys

import grafo
import sim_base

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    n, cenario, conjunto = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    modo = sys.argv[4] if len(sys.argv) > 4 else "mute"
    with open(os.path.join(REPO, "cenarios", "solucoes.json"), encoding="utf-8") as f:
        sol = next(s for s in json.load(f) if s["n"] == n and s["cenario"] == cenario)
    if conjunto == "padrao":
        papeis = {}
    else:
        R = set(sol["roteadores"][conjunto])
        resto = "CLIENT_MUTE" if modo == "mute" else "CLIENT"
        papeis = {v: ("ROUTER" if v in R else resto) for v in range(n)}

    sim_base.carregar()
    pasta_sim = next(p for p in sys.path if os.path.isfile(os.path.join(p, "lib", "config.py")))
    os.makedirs(os.path.join(pasta_sim, "out"), exist_ok=True)
    nome = f"{n}_{cenario}_{conjunto}_{modo}.yaml"
    grafo.salvar_yaml(sol["posicoes"], papeis, os.path.join(pasta_sim, "out", nome))
    print("Gravado em", os.path.join(pasta_sim, "out", nome))
    print(f'Para abrir: cd "{pasta_sim}" ; python loraMesh.py --from-file {nome}')
