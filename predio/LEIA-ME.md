# Mapa do PRÉDIO EM CONSTRUÇÃO (Unreal 5.8 + AMD FSR 4)

Executável separado do simulador (não mexe no voo do E88 em Godot).
Foco: gráfico bonito em visão FPV (óculos de drone), voando por dentro de um prédio em obra.

## Como jogar (no PC do Leonardo)
- Tudo do mapa fica em **`D:\DronePredio`** (nada no disco C): projeto, conteúdo, recursos, cache do
  Unreal (`DDC`), logs, testes e o jogo empacotado (`jogo\Windows`).
- `D:\DronePredio\JOGAR_PREDIO.bat` abre o jogo (com `-NotInstalled`, para os arquivos salvos ficarem no D).
- Controle (modo 2): esquerdo ↑↓ sobe/desce (acelerador no ACRO), ←→ gira; direito frente/trás/lados.
  Y troca ESTABILIZADO/ACRO, X volta ao início, **Start abre o MENU**, Back ajuda.
  Teclado: W/S, A/D, setas, M, R, Esc (menu), F1 (ajuda).
- MENU: sensibilidade, suavidade no centro (expo), inverter frente/trás (já vem invertido, como o
  controle do Leonardo pede), inverter subir/descer, giro e lados, modo de voo, volume do drone,
  modo do FSR 4, gerador de quadros, VSync, painel de FPS, ajuste automático, voltar ao início, sair.
  Fica salvo em `jogo\Windows\PredioDrone\Configuracoes_Drone.txt`.
- AMD: F2 modo do FSR 4, F3 gerador de quadros, F4 liga/desliga FSR (comparar com TSR),
  F5 painel de FPS, F6 ajuste automático para manter 60 FPS de base.

## O prédio
- 24 x 16 m, 4 andares + cobertura em obra, piso a piso 3 m, tela de proteção verde em volta
  (por fora só existe a tela e o andaime: a cidade não é desenhada).
- Térreo: canteiro (betoneira, areia, brita, blocos, sacos de cimento, gerador, H de pouso).
- 1º andar: alvenaria completa, eletrodutos, gambiarras; saída pela janela para o corredor do andaime.
- 2º andar: paredes pela metade, masseiras, cavaletes.
- 3º andar: floresta de escoras metálicas segurando as fôrmas da laje de cima (slalom).
- Cobertura: arranques de pilar com armadura, malhas de aço, buraco na laje para subir.
- Ligações verticais: poço do elevador (com fosso), escada em U, shaft hidráulico, buraco da cobertura.
- Sem aros/portais: o percurso é livre. Pontos de rota invisíveis (`Rota_N`) só guiam o voo de teste.
- Toda luz tem fonte visível: refletores de obra modelados (tripé + duas cúpulas com a lente acesa,
  o spot nasce na frente da lente) e lâmpadas da gambiarra.

## Só desenha onde o drone está
Cada andar é um grupo (`Andar0..4`) e cada laje outro (`Laje0..4`, piso de um andar e teto do de baixo).
O `PredioGameMode` mostra só o andar atual; o vizinho aparece quando o drone chega perto do poço,
da escada ou de um buraco (raio de 7 m) ou atravessa a laje. Cada andar fica aceso 1,5 s depois de
deixar de ser preciso (sem isso o vizinho e as luzes dele ligavam/desligavam e a tela piscava).
A laje de baixo também fica visível (vista pelos buracos). Tudo fica carregado na memória de vídeo,
então a troca é instantânea (não aparece "carregando"). As luzes de cada andar apagam junto.

## Tecnologias
- Lumen com ray tracing por hardware (RX 9060 XT), Nanite em tudo, sombras virtuais, névoa volumétrica.
- AMD FSR 4.1.2 (upscaling por IA) + gerador de quadros FSR 4 (IA, RDNA 4) + Anti-Lag 2 — plugin oficial
  da AMD instalado em `D:\JOGOS\UE_5.8\Engine\Plugins\Marketplace`.
- Gerador de quadros com `r.FidelityFX.FI.UIMode=1` (extração da interface): o HUD desenhado no
  Canvas não era redesenhado nos quadros gerados e piscava. Granulado de filme desligado.
- Som dos motores gerado em tempo real (4 hélices, tom sobe com o acelerador, chiado, batida).
- Ajuste automático: se o FPS de base cair abaixo de 57 por 4 s, desce o modo do FSR
  (Qualidade → Equilibrado → Desempenho) e depois o Lumen por hardware; volta a subir com folga.

## Como reconstruir
1. `blender/gerar_predio.py` (bpy 5.2) gera os FBX de cada andar + `layout.json` → `D:\DronePredio\conteudo`.
2. `BAIXAR_RECURSOS.bat` baixa as texturas 4K/modelos CC0 (Poly Haven + ambientCG) → `D:\DronePredio\recursos`.
3. `COMPILAR_E_CONSTRUIR.bat`: compila o C++ e roda `unreal/construir_mapa.py` no editor (materiais, malhas, mapa).
4. `EMPACOTAR_JOGO.bat`: gera o executável (Shipping).
5. `TESTE_TOUR.bat`: voo automático pelos pontos de rota, tira prints e mede FPS (`D:\DronePredio\testes`).
   `REFAZER_TUDO.bat` faz 3 + 4 + 5 de uma vez (~25 min).

## Observação do ambiente
O Unreal pedia o ".NET Framework SDK" só para um módulo do editor que já vem pronto. Em vez de instalar
(precisa de administrador), foi criada uma chave do usuário apontando para uma pasta vazia
(`CORRIGIR_E_COMPILAR.bat`). Para desfazer: `reg delete "HKCU\SOFTWARE\Microsoft\Microsoft SDKs\NETFXSDK\4.8" /f`.
O certo, quando der, é instalar o ".NET Framework 4.8.1 Developer Pack".

## Teste automático (17/11, 17:36) — executável Shipping, janela 1920x1080, RX 9060 XT
- FSR 4.1.2 (upscaling por IA, modo Qualidade) e gerador de quadros FSR 4.0.2 iniciados.
- FPS de base médio 80 (≈160 com o gerador), mínimo por foto 77; pior 1% dos quadros 50 (picos na troca de andar).
- Otimização que resolveu: lâmpadas da gambiarra sem sombra/névoa (só as luzes de obra fazem sombra).

## Teste automático (17/11, 18:47) — depois das correções do feedback 1
- FPS de base médio 84 (≈168 com o gerador), mínimo por foto 76; pior 1% dos quadros 64,7
  (antes 50: a histerese na troca de andar acabou com os picos). Tudo rodando de D:\DronePredio.

## Para melhorar depois (ideias)
- Tela de proteção ainda puxa para o azul na sombra (luz do céu); malha poderia ser mais fina.
- Partículas de poeira no ar, rádio via USB (só teclado e controle por enquanto).
- Pequenos travamentos (1%) na troca de andar: pré-aquecer o Lumen dos andares vizinhos.
