# Escolha ótima de roteadores em redes LoRa mesh off-grid (Meshtastic)

Trabalho final de Pesquisa Operacional (UFF).

**Pergunta:** numa rede Meshtastic, quais nós devem ter o papel de ROUTER (retransmitem com prioridade e são menos suprimidos) para que as mensagens cheguem a todos, com o mínimo de roteadores, respeitando o limite de saltos do protocolo e tolerando a queda de nós?

**Como:** a rede é modelada como um grafo de alcance e o problema é resolvido como um conjunto dominante conectado. Além das variantes da literatura (CDS, CDS 2-dominante, MOC-CDS), o trabalho propõe o **CDS com limite de saltos** (CDS-H e CDS-2H), em que toda mensagem precisa caber nos 4 enlaces que o Meshtastic permite (3 retransmissões). As variantes são resolvidas por programação linear inteira (com geração de cortes para o limite de saltos) e por GRASP, e as soluções são avaliadas no simulador oficial do Meshtastic (Meshtasticator), comparadas com a configuração de fábrica e com regras simples, inclusive sob queda de nós.

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `src/` | código (grafo de alcance, modelos de otimização, simulação, experimentos, análise) |
| `cenarios/` | `solucoes.json`: posições dos nós e roteadores escolhidos por cada método, para cada cenário |
| `resultados/` | tabelas (`.csv`, `.md`) e figuras (`.png`); `brutos/` guarda uma linha por simulação (não versionado) |
| `docs/` | referências |
| `scripts/` | instalação no Windows |

| Módulo | Função |
| --- | --- |
| `src/sim_base.py` | localiza o simulador e aplica os parâmetros fixos (área, preset, tráfego, tempo) |
| `src/grafo.py` | gera cenários e monta o grafo de alcance com o mesmo modelo de propagação do simulador |
| `src/modelos.py` | regra do grau, aleatório, PLI (PuLP + HiGHS, cortes de limite de saltos) e GRASP |
| `src/simular.py` | roda uma configuração de papéis no Meshtasticator (nós parados, queda de nós) |
| `src/experimentos.py` | fase `otimizar` e fase `simular` (paralela e retomável) |
| `src/analise.py` | tabelas (inclusive comparações por cenário, violações do limite, margem e ablação) e figuras |
| `src/exportar_yaml.py` | grava uma configuração no formato do simulador, para abrir na interface gráfica |

O simulador e o ambiente Python ficam fora do repositório, numa pasta de trabalho escolhida na instalação.

## Instalação (Windows, PowerShell)

Requisitos: Git e Python 3.10+ (com "tcl/tk" marcado no instalador, para a interface gráfica do simulador).

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1 -Base "E:\caminho\da\pasta\de\trabalho"
```

O script clona o simulador numa versão fixa (commit `17ceb82`), cria o ambiente Python e instala as dependências. O PuLP fica fixado abaixo da versão 4 (a 4 mudou a API) e o resolvedor usado é o HiGHS (`highspy`).

## Como reproduzir

```powershell
& "<pasta de trabalho>\venv-lora\Scripts\Activate.ps1"
$env:MESHTASTICATOR_DIR = "<pasta de trabalho>\Meshtasticator"

python src\grafo.py                      # teste: resumo de alguns grafos
python src\modelos.py                    # teste: PLI x GRASP em três cenários
python src\experimentos.py otimizar      # cenários + soluções (cerca de 20 min)
python src\experimentos.py simular       # 1.800 simulações (cerca de 1 h com 4 núcleos)
python src\experimentos.py margem        # teste de sensibilidade: margem de 5 dB na cobertura
python src\experimentos.py camadas       # ablação das desigualdades por camadas na PLI
python src\analise.py                    # tabelas e figuras em resultados\
```

Para ver uma solução na interface gráfica do simulador:

```powershell
python src\exportar_yaml.py 60 1 CDS-2H mute
```

## Referências

Ver `docs/REFERENCIAS.md`.
