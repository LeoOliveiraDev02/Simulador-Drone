# Mapa do PRÉDIO EM CONSTRUÇÃO (Unreal 5.8 + AMD FSR 4)

Executável separado do simulador (não mexe no voo do E88 em Godot).
Foco: gráfico bonito em visão FPV (óculos de drone), voando por dentro de um prédio em obra.

## Como jogar (no PC do Leonardo)
- `C:\drone\predio\JOGAR_PREDIO.bat` abre o jogo (fica em `D:\JOGOS\UE_5.8\_PredioDrone_jogo\Windows`).
- Controle (modo 2): esquerdo ↑↓ sobe/desce (acelerador no ACRO), ←→ gira; direito frente/trás/lados.
  Y troca ESTABILIZADO/ACRO, X volta ao último portal, Start ajuda. Teclado: W/S, A/D, setas, M, R, F1.
- AMD: F2 modo do FSR 4, F3 gerador de quadros, F4 liga/desliga FSR (comparar com TSR),
  F5 painel de FPS, F6 ajuste automático para manter 60 FPS de base. Esc duas vezes sai.

## O prédio
- 24 x 16 m, 4 andares + cobertura em obra, piso a piso 3 m, tela de proteção verde em volta
  (por fora só existe a tela e o andaime: a cidade não é desenhada).
- Térreo: canteiro (betoneira, areia, brita, blocos, sacos de cimento, gerador, H de pouso).
- 1º andar: alvenaria completa, eletrodutos, gambiarras; saída pela janela para o corredor do andaime.
- 2º andar: paredes pela metade, masseiras, cavaletes.
- 3º andar: floresta de escoras metálicas segurando as fôrmas da laje de cima (slalom).
- Cobertura: arranques de pilar com armadura, malhas de aço, buraco na laje para subir.
- Ligações verticais: poço do elevador (com fosso), escada em U, shaft hidráulico, buraco da cobertura.
- 19 portais (percurso com cronômetro e recorde).

## Só desenha onde o drone está
Cada andar é um grupo (`Andar0..4`) e cada laje outro (`Laje0..4`, piso de um andar e teto do de baixo).
O `PredioGameMode` mostra só o andar atual; o vizinho aparece quando o drone chega perto do poço,
da escada ou de um buraco (raio de ~4 m) ou atravessa a laje. Tudo fica carregado na memória de vídeo,
então a troca é instantânea (não aparece "carregando"). As luzes de cada andar apagam junto.

## Tecnologias
- Lumen com ray tracing por hardware (RX 9060 XT), Nanite em tudo, sombras virtuais, névoa volumétrica.
- AMD FSR 4.1.2 (upscaling por IA) + gerador de quadros FSR 4 (IA, RDNA 4) + Anti-Lag 2 — plugin oficial
  da AMD instalado em `D:\JOGOS\UE_5.8\Engine\Plugins\Marketplace`.
- Ajuste automático: se o FPS de base cair abaixo de 57 por 4 s, desce o modo do FSR
  (Qualidade → Equilibrado → Desempenho) e depois o Lumen por hardware; volta a subir com folga.

## Como reconstruir
1. `blender/gerar_predio.py` (bpy 5.2) gera os FBX de cada andar + `layout.json` → `C:\drone\predio\conteudo`.
2. `BAIXAR_RECURSOS.bat` baixa as texturas 4K/modelos CC0 (Poly Haven + ambientCG) → `C:\drone\predio\recursos`.
3. `COMPILAR_E_CONSTRUIR.bat`: compila o C++ e roda `unreal/construir_mapa.py` no editor (materiais, malhas, mapa).
4. `EMPACOTAR_JOGO.bat`: gera o executável (Shipping).
5. `TESTE_TOUR.bat`: voo automático passando por todos os portais, tira prints e mede FPS (`C:\drone\predio\testes`).

## Observação do ambiente
O Unreal pedia o ".NET Framework SDK" só para um módulo do editor que já vem pronto. Em vez de instalar
(precisa de administrador), foi criada uma chave do usuário apontando para uma pasta vazia
(`CORRIGIR_E_COMPILAR.bat`). Para desfazer: `reg delete "HKCU\SOFTWARE\Microsoft\Microsoft SDKs\NETFXSDK\4.8" /f`.
O certo, quando der, é instalar o ".NET Framework 4.8.1 Developer Pack".
