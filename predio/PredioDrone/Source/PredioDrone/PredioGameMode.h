#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "PredioGameMode.generated.h"

class ADronePawn;
class UMaterialInstanceDynamic;

struct FGrupoVisivel
{
	TArray<TWeakObjectPtr<AActor>> Atores;
	bool bVisivel = true;
};

struct FConexao
{
	int32 AndarDeBaixo = 0;   // liga AndarDeBaixo e AndarDeBaixo+1
	FVector Posicao = FVector::ZeroVector;
	float Raio = 450.f;
};

struct FPortal
{
	TWeakObjectPtr<AActor> Ator;
	TArray<UMaterialInstanceDynamic*> Materiais;
	int32 Numero = 0;
	bool bPassou = false;
};

/**
 * Regras do mapa do prédio:
 *  - só renderiza o andar onde o drone está (+ o vizinho quando ele chega perto
 *    do poço do elevador, da escada ou de um buraco na laje) — troca instantânea,
 *    tudo já está carregado na memória de vídeo;
 *  - portais de treino com cronômetro;
 *  - atalhos das tecnologias AMD (FSR 4 + gerador de quadros + Anti-Lag 2);
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
	int32 ProximoPortal = 1;
	int32 TotalPortais = 0;
	bool bCronometroLigado = false;
	float Cronometro = 0.f;
	float MelhorTempo = 0.f;
	float FPSBase = 0.f;
	float MsGPU = 0.f;
	float MsJogo = 0.f;
	bool bAjusteAuto = true;
	bool bMostrarAjuda = false;
	bool bMostrarDesempenho = true;
	int32 NivelAjuste = 0;   // 0 = máximo; sobe quando precisa aliviar

	static FString NomeModoFSR();
	static bool FSRLigado();
	static bool GeradorLigado();
	static FString TextoAndar(int32 Andar);

private:
	void ColetarAtores();
	void AtualizarAndares(bool bForcar);
	void AtualizarPortais();
	void TeclasAtalho();
	void AjusteAutomatico(float Dt);
	void AplicarNivelAjuste();
	void TickTour(float Dt);
	void SalvarResultadoTour();

	ADronePawn* Drone() const;

	TMap<FName, FGrupoVisivel> Grupos;   // "Andar0", "Laje1", ...
	TArray<FConexao> Conexoes;
	TArray<FPortal> Portais;
	float AlturaAndar = 300.f;
	float CotaTerreo = 0.f;

	// desempenho
	float AcumBaixo = 0.f;
	float AcumAlto = 0.f;
	float SuavDt = 1.f / 60.f;
	float TempoAteSair = -1.f;

	// tour
	bool bTour = false;
	TArray<FVector> TourPontos;
	TArray<int32> TourFotoNoPonto;
	float TourS = 0.f;          // posição ao longo do caminho (índice + fração)
	float TourEspera = 0.f;
	int32 TourFotos = 0;
	TArray<float> TourFrames;   // ms
	TArray<FString> TourLinhas;
	FString PastaTestes;
	int32 UltimoPontoFoto = -1;
};
