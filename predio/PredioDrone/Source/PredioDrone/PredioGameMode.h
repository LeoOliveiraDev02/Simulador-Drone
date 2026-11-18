#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "PredioGameMode.generated.h"

class ADronePawn;
class UStaticMeshComponent;
class UStaticMesh;

struct FGrupoVisivel
{
	TArray<TWeakObjectPtr<AActor>> Atores;
	bool bVisivel = true;
};

struct FConexao
{
	int32 AndarDeBaixo = 0;   // liga AndarDeBaixo e AndarDeBaixo+1
	FVector Posicao = FVector::ZeroVector;
	float Raio = 1000.f;
};

/** Itens do menu (Start / Esc), agrupados pelas categorias da coluna da esquerda. */
enum class EItemMenu : uint8
{
	Continuar,      // CONTINUAR
	Objetivo,       // JOGABILIDADE
	ModoVoo,
	VoltarInicio,
	MenuPrincipal,
	Sensibilidade,  // SENSIBILIDADE
	Expo,
	ModoFSR,        // VÍDEO
	Gerador,
	VSync,
	Painel,
	AjusteAuto,
	Volume,         // ÁUDIO
	InvFrente,      // CONTROLES
	InvSubir,
	InvGiro,
	InvLados,
	EscalaHUD,      // ACESSIBILIDADE
	Padrao,         // AVANÇADO
	Sair,           // SAIR DO JOGO
	Total
};

enum class ECategoriaMenu : uint8
{
	Continuar, Jogabilidade, Sensibilidade, Video, Audio, Controles, Acessibilidade, Avancado, Sair, Total
};

/** Como o valor do item aparece no menu. */
enum class ETipoValor : uint8 { Acao, Texto, Chave, Nenhum };

/** Objetivo do voo (escolhido no menu principal ou no menu de pausa). */
enum class EObjetivo : uint8 { Livre, Topo, ArosOrdem, ArosRelogio, Entregas, Pulverizar, Fotos, Ferraduras };

/** Andamento do desafio. */
enum class EEstadoDesafio : uint8 { Pronto, Correndo, Concluido, Falhou };

/** Telas do menu principal: abertura -> mapas -> desafios do mapa. */
enum class ETelaMP : uint8 { Titulo, Mapas, Desafios };

/** Cartões do menu principal. */
enum class ECartaoMapa : uint8 { Campo, Predio, Usina, Total };

/**
 * Regras do mapa do prédio:
 *  - só renderiza o andar onde o drone está (+ o vizinho perto do poço do
 *    elevador, da escada ou de um buraco na laje) — troca instantânea;
 *  - menu de configurações (controle, sensibilidade, som, AMD);
 *  - tecnologias AMD (FSR 4 + gerador de quadros + Anti-Lag 2);
 *  - ajuste automático para manter 60 FPS de base;
 *  - voo automático de teste (-tour) que tira prints e mede o FPS.
 */
UCLASS()
class PREDIODRONE_API APredioGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	APredioGameMode();
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	// lidos pelo HUD
	int32 AndarAtual = 0;
	int32 NumAndares = 1;
	float FPSBase = 0.f;
	float MsGPU = 0.f;
	float MsJogo = 0.f;
	bool bMostrarAjuda = false;
	int32 NivelAjuste = 0;   // 0 = máximo; sobe quando precisa aliviar

	bool bMenuAberto = false;
	bool bMenuJaDesenhado = false;
	void Registrar(const FString& Linha) const;
	int32 MenuIndice = 0;
	FString NomeItem(int32 I) const;
	FString DescricaoItem(int32 I) const;
	FString ValorItem(int32 I) const;
	ETipoValor TipoItem(int32 I) const;
	bool ChaveLigada(int32 I) const;
	static ECategoriaMenu CategoriaDoItem(int32 I);
	static int32 PrimeiroItemDa(ECategoriaMenu C);
	static FString NomeCategoria(ECategoriaMenu C);
	static FString DescricaoCategoria(ECategoriaMenu C);
	static TArray<int32> ItensDaCategoria(ECategoriaMenu C);
	void EntrarCategoria(ECategoriaMenu C);
	int32 CategoriaSel = 0;     // seção escolhida na coluna da esquerda
	bool bFocoItens = false;    // false = escolhendo a seção; true = mexendo nas opções dela

	// áreas clicáveis do menu (o HUD preenche ao desenhar; o mouse usa no quadro seguinte)
	TArray<FBox2D> AreaItens;
	TArray<FBox2D> AreaCategorias;
	FBox2D AreaFechar = FBox2D(ForceInit);

	// limites de voo: por dentro da tela de proteção e abaixo da borda de cima dela
	FBox LimitesVoo;

	// ---------------------------------------------------------------- mapa e objetivo
	bool bEhCampo = false;
	EObjetivo Objetivo = EObjetivo::Livre;
	EEstadoDesafio Estado = EEstadoDesafio::Pronto;
	float TempoDesafio = 0.f;      // cronômetro (s), só corre com o jogo despausado
	float TempoRestante = 0.f;     // contra o relógio (s)
	float BonusUltimoAro = 0.f;    // segundos ganhos no último aro (mostrado na tela)
	float TempoDesdeAro = 99.f;
	int32 ProximoAro = 0;
	TArray<FTransform> Aros;       // na ordem do circuito
	float RaioAro = 220.f;         // raio de passagem (cm)
	int32 Medalha = 0;             // 0 nenhuma, 1 bronze, 2 prata, 3 ouro
	bool bNovoRecorde = false;
	float TempoNoResultado = 0.f;  // segundos desde o fim do desafio (painel de resultado)
	float AlturaTopo() const;

	// ---------------------------------------------------------------- missões da fazenda
	// entregas: pegar a caixa na plataforma do galpão e levar a cada destino
	FVector PontoColeta = FVector::ZeroVector;
	bool bTemColeta = false;
	TArray<FVector> PontosEntrega;
	TArray<FString> NomesEntrega;
	int32 EntregaAtual = 0;
	bool bComCaixa = false;
	float TempoParado = 0.f;          // segurando em cima do ponto (pegar/soltar)
	static constexpr float TempoParaSoltar = 0.8f;
	// fotos: mirar o alvo de perto por um instante
	TArray<FVector> PontosFoto;
	TArray<FString> NomesFoto;
	TArray<bool> FotoFeita;
	int32 FotoMirando = INDEX_NONE;
	float TempoMira = 0.f;
	float Flash = 0.f;
	static constexpr float TempoParaFoto = 1.2f;
	// ferraduras douradas escondidas
	TArray<TWeakObjectPtr<AActor>> Ferraduras;
	TArray<bool> FerraduraPega;
	float DistFerradura = 0.f;        // a mais perto (m), para a dica "quente/frio"
	// pulverizar a roça de milho (grade de células de 5 m)
	FBox2D Roca = FBox2D(ForceInit);
	int32 RocaNX = 0, RocaNY = 0;
	TArray<uint8> CelulaFeita;
	TArray<float> ChaoCelula;
	bool bPulverizando = false;
	float Cobertura() const;
	static constexpr float CoberturaMeta = 0.9f;
	static constexpr float TamCelula = 500.f;
	int32 Progresso() const;          // quantos já fez (aros, entregas, fotos, ferraduras)
	int32 ProgressoTotal() const;
	bool AlvoPrincipal(FVector& Out, FString& Rotulo) const;  // para onde ir agora (marca na tela e farol)
	float LimiteMedalha(int32 M) const;  // tempo máximo (s) para a medalha M (3 ouro, 2 prata, 1 bronze)
	float RecordeAtual() const;
	TArray<EObjetivo> ObjetivosDoMapa() const;
	static TArray<EObjetivo> ObjetivosDoCartao(ECartaoMapa C);
	static FString NomeObjetivo(EObjetivo O);
	static FString DescricaoObjetivo(EObjetivo O);
	static FString TextoTempo(float Segundos, bool bDecimos = true);
	static FString NomeMedalha(int32 M);
	FString TextoLocal() const;    // canto de cima à direita do OSD

	// ---------------------------------------------------------------- menu principal
	bool bMenuPrincipal = false;
	ETelaMP TelaMP = ETelaMP::Titulo;
	int32 MPTitulo = 0;                 // JOGAR / CONFIGURAÇÕES / SAIR
	float MPTelaDesde = 0.f;            // segundos desde que a tela atual abriu (animação de entrada)
	TArray<FBox2D> AreaTitulo;
	FBox2D AreaVoltarMP = FBox2D(ForceInit);
	int32 MedalhaDe(EObjetivo O) const;
	float ProgressoMapa(int32 Cartao) const;     // 0..1 (medalhas conquistadas / possíveis)
	int32 MedalhasMapa(int32 Cartao, int32& Possiveis) const;
	static FString NomeMapa(int32 Cartao);
	void IrParaTela(ETelaMP T);
	int32 MPCartao = (int32)ECartaoMapa::Campo;
	int32 MPLinha = 0;
	bool bCampoExiste = false;
	int32 NumLinhasMP() const;
	bool LinhaEhObjetivo(int32 L, EObjetivo& Out) const;
	FString NomeLinhaMP(int32 L) const;
	FString DescricaoLinhaMP(int32 L) const;
	FString ExtraLinhaMP(int32 L) const;   // recorde / aviso à direita
	bool CartaoDisponivel(int32 C) const;
	TArray<FBox2D> AreaCartoes;
	TArray<FBox2D> AreaLinhas;
	float MPRelogio = 0.f;          // segundos reais desde que o menu principal abriu (animações)
	float MPEscuro = 0.f;           // escurecimento do voo de fundo quando ele dá a volta
	FString MPAviso;                // aviso curto no menu principal
	float MPAvisoT = 0.f;
	bool bCarregando = false;       // trocando de mapa
	bool bTrocandoMapa = false;     // -mapa=Campo: pulando para a fazenda
	FString DiagCampo;              // diagnóstico (vai no resultado do voo de teste)
	float BonusDoAro(int32 I) const;          // contra o relógio: segundos para chegar ao aro I
	float ComprimentoCircuito() const;        // cm, do início passando por todos os aros

	static FString NomeModoFSR();
	static bool FSRLigado();
	static bool GeradorLigado();
	static FString TextoAndar(int32 Andar);

private:
	void ColetarAtores();
	void AtualizarAndares(bool bForcar);
	void TeclasAtalho();
	void AbrirMenu(bool bAbrir);
	void TickMenu(float Dt);
	void MudarItem(int32 Direcao, bool bConfirmar);
	void AjusteAutomatico(float Dt);
	void AplicarNivelAjuste();
	void TickTour(float Dt);
	void SalvarResultadoTour();

	void MontarPercurso();
	FTransform PontoNoPercurso(float S) const;
	void EntrarMenuPrincipal();
	void TickMenuPrincipal(float Dt);
	void ConfirmarMenuPrincipal();
	void IniciarObjetivo(EObjetivo O, bool bRecolocar);
	void ReiniciarDesafio();
	void TickObjetivo(float Dt);
	void ConcluirDesafio(bool bSucesso);
	void MontarAros();
	void MostrarAros();
	void IrParaMapa(const FString& Mapa, const FString& Opcoes);
	void EspalharGrama();
	void EspalharMilho();
	void TickMissoes(float Dt, const FVector& P);
	void MoverFarolECaixa();
	TWeakObjectPtr<AActor> Farol;
	TWeakObjectPtr<AActor> CaixaAtor;
	TArray<TWeakObjectPtr<AActor>> CaixasEntregues;
	TArray<TPair<TWeakObjectPtr<AActor>, float>> Giratorios;
	UStaticMesh* MalhaCaixa = nullptr;
	AActor* CriarAtorMalha(UStaticMesh* M, const FTransform& T);
	void CriarDroneTitulo();
	void DestruirDroneTitulo();
	void SairDoMenuPrincipal();
	void TickFotosMenu(float Dt);
	TWeakObjectPtr<AActor> DroneTitulo;
	TArray<TWeakObjectPtr<UStaticMeshComponent>> HelicesTitulo;
	float AnguloHelices = 0.f;
	TArray<TPair<int32, TWeakObjectPtr<AActor>>> AtoresAros;
	int32 UltimosReinicios = 0;
	FVector UltimaPosDrone = FVector::ZeroVector;
	float MPVooS = 0.f;
	bool bFotoMenu = false;
	float FotoMenuT = 0.f;
	int32 FotoMenuFase = 0;
	bool bConfigDoMenuPrincipal = false;

	ADronePawn* Drone() const;

	TMap<FName, FGrupoVisivel> Grupos;   // "Andar0", "Laje1", ...
	TArray<FConexao> Conexoes;
	TMap<int32, double> AndarPedido; // última vez que cada andar precisou aparecer (evita pisca-pisca)
	TArray<TPair<int32, FTransform>> Rota; // pontos invisíveis do voo de teste (no campo: os aros)
	float AlturaAndar = 300.f;
	float CotaTerreo = 0.f;

	// teclas: borda de apertar calculada aqui (estado atual x anterior), funciona igual com o jogo pausado
	void AtualizarTeclas();
	bool Apertou(const FKey& K) const;
	TMap<FKey, bool> TeclaAntes;
	TSet<FKey> TeclaAgora;
	double MenuMudouEm = -10.0;   // hora real da última abertura/fechamento (evita abrir e fechar no mesmo toque)

	// menu
	FVector2D UltimoMouse = FVector2D::ZeroVector;
	float RepeticaoV = 0.f;
	float RepeticaoH = 0.f;
	int32 UltimaDirVert = 0;
	int32 UltimaDirHoriz = 0;

	// desempenho
	float AcumBaixo = 0.f;
	float AcumAlto = 0.f;
	float SuavDt = 1.f / 60.f;

	// tour
	bool bTour = false;
	TArray<FVector> TourPontos;
	TArray<int32> TourFotoNoPonto;
	float TourS = 0.f;
	float TourEspera = 0.f;
	int32 TourFotos = 0;
	TArray<float> TourFrames;   // ms
	TArray<FString> TourLinhas;
	FString PastaTestes;
	int32 UltimoPontoFoto = -1;
	int32 TourFase = 0;      // 1 = fim do percurso, abre o menu para fotografar
	float TourFimT = 0.f;
};
