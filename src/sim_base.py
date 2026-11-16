"""Acesso ao simulador Meshtasticator.

O simulador fica fora do repositório. Este módulo encontra a pasta dele,
coloca-a no caminho de importação do Python e aplica as configurações
usadas em todo o trabalho (área, tráfego, tempo simulado, sem movimento).

Ordem de busca da pasta do simulador:
  1. argumento `caminho` de `carregar()`;
  2. variável de ambiente MESHTASTICATOR_DIR;
  3. pastas vizinhas ao repositório: ../Meshtasticator e ../../Meshtasticator.
"""

import os
import sys

# Parâmetros comuns a todos os experimentos (ver a seção de metodologia do relatório)
AREA_M = 5000            # lado da área quadrada, em metros
PRESET = "LONG_FAST"     # preset padrão do Meshtastic
HOP_LIMIT = 3            # limite de saltos padrão do Meshtastic
PERIODO_S = 300          # intervalo médio entre mensagens de cada nó, em segundos
TEMPO_SIM_S = 20 * 60    # duração de cada simulação, em segundos

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_carregado = None


def _candidatos(caminho):
    if caminho:
        yield caminho
    if os.environ.get("MESHTASTICATOR_DIR"):
        yield os.environ["MESHTASTICATOR_DIR"]
    yield os.path.join(_REPO, "..", "Meshtasticator")
    yield os.path.join(_REPO, "..", "..", "Meshtasticator")


def carregar(caminho=None):
    """Importa o simulador e devolve o objeto de configuração global (CONFIG).

    Pode ser chamada várias vezes; só importa na primeira.
    """
    global _carregado
    if _carregado is not None:
        return _carregado

    for pasta in _candidatos(caminho):
        pasta = os.path.abspath(pasta)
        if os.path.isfile(os.path.join(pasta, "lib", "config.py")):
            break
    else:
        raise FileNotFoundError(
            "Simulador não encontrado. Defina a variável MESHTASTICATOR_DIR "
            "com a pasta do Meshtasticator."
        )

    if pasta not in sys.path:
        sys.path.insert(0, pasta)

    # O simulador escreve avisos de enlace assimétrico no log a cada pacote;
    # silenciamos para a saída ficar legível.
    import logging
    logging.getLogger("lib").setLevel(logging.ERROR)

    from lib.config import CONFIG
    configurar(CONFIG)
    _carregado = CONFIG
    return CONFIG


def configurar(conf, area_m=AREA_M, periodo_s=PERIODO_S, tempo_sim_s=TEMPO_SIM_S):
    """Aplica ao CONFIG do simulador os parâmetros do trabalho."""
    conf.XSIZE = area_m
    conf.YSIZE = area_m
    conf.MODEM_PRESET = PRESET
    conf.hopLimit = HOP_LIMIT
    conf.PERIOD = int(periodo_s * 1000)
    conf.SIMTIME = int(tempo_sim_s * 1000)
    # Nós parados: o grafo de alcance só vale se as posições não mudam.
    conf.MOVEMENT_ENABLED = False
    # Sem janelas nem gráficos do próprio simulador.
    conf.GUI_ENABLED = False
    conf.PLOT = False
    return conf
