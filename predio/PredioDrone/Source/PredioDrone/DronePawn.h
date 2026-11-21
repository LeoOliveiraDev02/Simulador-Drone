#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include <atomic>
#include "DronePawn.generated.h"

class USphereComponent;
class UCameraComponent;
class UAudioComponent;
class USoundWaveProcedural;

UENUM(BlueprintType)
enum class EModoVoo : uint8
{
	Estabilizado,
	Acro
};

/**
 * Drone FPV (visão dos óculos). Física própria em sub-passos de 240 Hz,
 * modo estabilizado e acro, colisão com quique e queda, e som dos motores
 * gerado em tempo real (sobe e desce com o acelerador).
 */
UCLASS()
class PREDIODRONE_API ADronePawn : public APawn
{
	GENERATED_BODY()

public:
	ADronePawn();

	virtual void Tick(float DeltaSeconds) override;
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Motivo) override;

	// --- estado lido pelo HUD ---
	EModoVoo Modo = EModoVoo::Estabilizado;
	FVector Velocidade = FVector::ZeroVector;     // cm/s
	float Bateria = 4.20f;
	float TempoVoo = 0.f;
	float Acelerador = 0.f;
	bool bCaido = false;
	int32 Batidas = 0;            // batidas desde o último início (3 = quebra)
	int32 Reinicios = 0;          // quantas vezes voltou ao início (o desafio recomeça junto)
	static constexpr int32 MaxBatidas = 3;
	float TempoCaido = 0.f;
	FString Mensagem;
	float TempoMensagem = 0.f;

	bool bModoTour = false;
	bool bCongelado = false; // menu aberto

	// caixa onde o drone pode voar (por dentro da tela de proteção, abaixo do teto)
	FBox Limites = FBox(ForceInit);
	bool bUsarLimites = false;

	// vento (m/s, no mundo). Direção em graus (0 = sopra para +X). O mapa pode enfraquecer (prédio = abrigado).
	FVector VentoAtual = FVector::ZeroVector;
	float DirVento = 35.f;
	float FatorVentoMapa = 1.f;
	void AjustarLuz(bool bCampo);   // pós-processo da câmera conforme o mapa (sombras menos pretas)

	void Recomecar(const FTransform& Onde);
	void MostrarMensagem(const FString& Texto, float Segundos = 2.5f);
	void TrocarModo();
	FTransform Inicio;

	UPROPERTY(VisibleAnywhere)
	TObjectPtr<USphereComponent> Corpo;

	UPROPERTY(VisibleAnywhere)
	TObjectPtr<UCameraComponent> Camera;

	UPROPERTY(VisibleAnywhere)
	TObjectPtr<UAudioComponent> Audio;

	UPROPERTY()
	TObjectPtr<USoundWaveProcedural> Onda;

private:
	void LerControles(float Dt);
	void PassoFisica(float h);
	void MoverComColisao(float h);
	void PrenderNosLimites();
	void AtualizarCamera(float Dt);
	void GerarAudio(USoundWaveProcedural* W, int32 Amostras);

	float InAcel = 0.f;
	float InGuinada = 0.f;
	float InArfagem = 0.f;
	float InRolagem = 0.f;

	FQuat Orientacao = FQuat::Identity;
	FVector TaxaCorpo = FVector::ZeroVector;
	float Motores[4] = { 0.f, 0.f, 0.f, 0.f };
	float Massa = 0.25f;
	float EmpuxoMax = 0.f;
	float Acumulador = 0.f;
	float AlturaAlvo = 0.f;
	float TremorFase = 0.f;
	float UltimoImpacto = 0.f;
	float UltimaBatida = -10.f;
	float TempoVento = 0.f;
	float AlturaSobreChao = 10.f;   // m (medida de tempos em tempos, o vento fica mais fraco rente ao chão)
	float ProxMedidaChao = 0.f;
	void AtualizarVento(float Dt);

	// áudio (thread de áudio)
	std::atomic<float> AudioAcel{ 0.f };
	std::atomic<float> AudioVolume{ 0.8f };
	std::atomic<int32> AudioImpacto{ 0 };
	double Fases[4] = { 0.0, 0.0, 0.0, 0.0 };
	float FiltroRuido = 0.f;
	float FiltroVento = 0.f;
	float EnvImpacto = 0.f;
	float AcelSuave = 0.f;
	uint32 Semente = 12345u;
	TArray<int16> BufferAudio;
};
