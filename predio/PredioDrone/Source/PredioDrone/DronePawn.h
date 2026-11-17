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
	float TempoCaido = 0.f;
	FString Mensagem;
	float TempoMensagem = 0.f;

	bool bModoTour = false;
	bool bCongelado = false; // menu aberto

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
