# Referências

## Artigo-base

- Hernandez Ortiz, G. A.; Quiroz Puentes, E. S.; Rugeles, J. J. **Resilience Analysis in Off-Grid LoRa Mesh Networks: Evaluation of Meshtastic Profiles in Long-Range Propagation Scenarios.** arXiv:2605.17063, 2026. https://arxiv.org/abs/2605.17063
  - Ensaio físico (Heltec WiFi LoRa 32 V3.2, RAK4631, atenuadores) dos 8 presets do Meshtastic.
  - Limites de atenuação por preset: SF7–8 falham em 110–120 dB; SF9–10 vão até 135–150 dB; Long Slow até ~180 dB.
  - Não otimiza nada; cita uma ferramenta de otimização da densidade de nós e a escalabilidade da inundação como trabalhos futuros. **É a lacuna que o nosso trabalho ataca.**
  - Não disponibiliza dados nem código.

## Simulador

- **Meshtasticator** — simulador de eventos discretos oficial do Meshtastic (Python, licença CC BY 4.0). https://github.com/meshtastic/Meshtasticator — versão usada: commit `17ceb8231079d87b070abc6132181e4c6b20202d` (28/07/2026). Documentação: https://meshtastic.org/docs/software/meshtasticator/
- Bor, M. C.; Roedig, U.; Voigt, T.; Alonso, J. M. **Do LoRa Low-Power Wide-Area Networks Scale?** MSWiM 2016. (Origem do código-base do simulador.)
- Meshtastic. **Why Meshtastic Uses Managed Flood Routing.** https://meshtastic.org/blog/why-meshtastic-uses-managed-flood-routing/

## Contexto e motivação

- CRISiSLab. Implantação do Meshtastic como rede de emergência em Wellington (Nova Zelândia): o relevo foi o principal limitante e o posicionamento estratégico dos nós foi decisivo. https://rda.sliit.lk/bitstreams/9bda1391-a1d3-4b73-b5d6-663be8cfed50/download
- Meshtastic-based LoRa Mesh System for Smart Campus Applications. arXiv:2605.20379, 2026. https://arxiv.org/abs/2605.20379
- Durand, T. G.; Booysen, M. J. **Performance Evaluation of a Mesh-Topology LoRa Network.** Sensors 25(5):1602, 2025. https://mdpi.com/1424-8220/25/5/1602
- Sciullo, L.; Trotta, A.; Di Felice, M. **Design and Performance Evaluation of a LoRa-Based Mobile Emergency Management System (LOCATE).** Ad Hoc Networks 96, 2020.
- **Optimizing Routing Protocol Design for Long-Range Distributed Multi-Hop Networks (LB-OLSR).** Electronics 13(19):3957, 2024. https://mdpi.com/2079-9292/13/19/3957 — seleção de retransmissores (MPR); não reproduzível (sem código e com condição do algoritmo não definida).

## Pesquisa operacional (teoria e métodos)

- Guha, S.; Khuller, S. **Approximation algorithms for connected dominating sets.** Algorithmica 20(4):374–387, 1998.
- Thai, M. T.; Zhang, N.; Tiwari, R.; Xu, X. **On approximation algorithms of k-connected m-dominating sets in disk graphs.** Theoretical Computer Science 385(1–3):49–59, 2007. https://doi.org/10.1016/j.tcs.2007.05.025 — versão tolerante a falhas (m-dominante).
- Ding, L.; Gao, X.; Wu, W.; Lee, W.; Zhu, X.; Du, D.-Z. **Distributed construction of connected dominating sets with minimum routing cost in wireless networks.** IEEE ICDCS 2010, p. 448–457. https://doi.org/10.1109/ICDCS.2010.17 — MOC-CDS; equivalência com a condição "todo par a 2 saltos tem vizinho comum no conjunto".
- Kim, D.; Wu, Y.; Li, Y.; Zou, F.; Du, D.-Z. **Constructing minimum connected dominating sets with bounded diameters in wireless networks.** IEEE Transactions on Parallel and Distributed Systems 20(2):147–157, 2009. https://doi.org/10.1109/TPDS.2008.74 — CDS com diâmetro limitado (as soluções do CDS-H deste trabalho têm diâmetro 2).
- Ni, S.-Y.; Tseng, Y.-C.; Chen, Y.-S.; Sheu, J.-P. **The broadcast storm problem in a mobile ad hoc network.** MobiCom 1999, p. 151–162. https://doi.org/10.1145/313451.313525 — redundância, disputa e colisões na inundação.
- Qayyum, A.; Viennot, L.; Laouiti, A. **Multipoint relaying for flooding broadcast messages in mobile wireless networks.** HICSS 2002, p. 3866–3875. https://doi.org/10.1109/HICSS.2002.994521 — retransmissores multiponto (MPR); mínimo é NP-completo.
- Wu, J.; Li, H. **On calculating connected dominating set for efficient routing in ad hoc wireless networks.** DIAL-M 1999 (ACM), p. 7–14. — algoritmo distribuído de CDS (cada nó decide sozinho); alternativa descentralizada citada nos trabalhos futuros.
- Fan, N.; Watson, J.-P. **Solving the connected dominating set problem and power dominating set problem by integer programming.** COCOA 2012, LNCS 7402, p. 371–383. https://doi.org/10.1007/978-3-642-31770-5_33 — formulações de PLI com fluxo para o CDS.
- Feo, T. A.; Resende, M. G. C. **Greedy randomized adaptive search procedures.** Journal of Global Optimization 6:109–133, 1995.
- Slides da disciplina (Prof. Luiz Satoru Ochi): GRASP, busca local, programação linear.

## Documentação do Meshtastic (papéis e limite de saltos)

- Choosing the right device role: https://meshtastic.org/blog/choosing-the-right-device-role/ — CLIENT_MUTE não retransmite.
- Configuration tips: https://meshtastic.org/docs/configuration/tips/ — recomenda CLIENT/CLIENT_MUTE; papéis de roteador mal usados congestionam a rede.
- Zero-cost hops for favorite routers: https://meshtastic.org/blog/zero-cost-hops-favorite-routers/ — limite máximo de 7 saltos; em firmware recente, saltos entre roteadores favoritos não contam (não modelado no simulador; ver limitações).
- Neighbor Info module usage: https://meshtastic.org/docs/configuration/module/neighbor-info — cada nó informa periodicamente os vizinhos diretos e o SNR de cada enlace (intervalo mínimo de 4 h); caminho para medir o grafo de alcance real.
- Remote node administration: https://meshtastic.org/docs/configuration/remote-admin/ — configuração (inclusive o papel) enviada pela própria malha; caminho para aplicar a escolha de roteadores.
