#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "PredioGameMode.generated.h"

class ADronePawn;

struct FGrupoVisivel
{
	TArray<TWeakObjectPtr<AActor>> Atores;
	bool bVisivel = true;
};

struct FConexao
{
	int32 AndarDeBaixo = 0;   // liga AndarDeBaixo e AndarDeBaixo+1
	FVector Posicao = FVector::ZeroVector;
	float Raio = 700.f;
};

/** Itens do menu (Start / Esc), agrupados pelas categorias da coluna da esquerda. */
enum class EItemMenu : uint8
{
	Continuar,      // CONTINUAR
	ModoVoo,        // JOGABILIDADE
	VoltarInicio,
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
	int32 MenuIndice = 0;
	FString NomeItem(int32 I) const;
	FString DescricaoItem(int32 I) const;
	FString ValorItem(int32 I) const;
	ETipoValor TipoItem(int32 I) const;
	bool ChaveLigada(int32 I) const;
	static ECategoriaMenu CategoriaDoItem(int32 I);
	static int32 PrimeiroItemDa(ECategoriaMenu C);
	static FString NomeCategoria(ECategoriaMenu C);

	// áreas clicáveis do menu (o HUD preenche ao desenhar; o mouse usa no quadro seguinte)
	TArray<FBox2D> AreaItens;
	TArray<FBox2D> AreaCategorias;
	FBox2D AreaFechar = FBox2D(ForceInit);

	// limites de voo: por dentro da tela de proteção e abaixo da borda de cima dela
	FBox LimitesVoo;

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

	ADronePawn* Drone() const;

	TMap<FName, FGrupoVisivel> Grupos;   // "Andar0", "Laje1", ...
	TArray<FConexao> Conexoes;
	TMap<int32, double> AndarPedido; // última vez que cada andar precisou aparecer (evita pisca-pisca)
	TArray<TPair<int32, FTransform>> Rota; // pontos invisíveis do voo de teste
	float AlturaAndar = 300.f;
	float CotaTerreo = 0.f;

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
