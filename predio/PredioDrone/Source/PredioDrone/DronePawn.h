#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "DronePawn.generated.h"

class USphereComponent;
class UCameraComponent;

UENUM(BlueprintType)
enum class EModoVoo : uint8
{
	Estabilizado,
	Acro
};

/**
 * Drone FPV (visão dos óculos). Física própria em sub-passos de 240 Hz:
 * 4 motores com atraso, empuxo pelo eixo do drone, arrasto, efeito solo,
 * modo estabilizado (nivela sozinho, trava altura, soltou = para no ar) e
 * modo acro (taxas, como um FPV de verdade). Colisão com quique e queda.
 */
UCLASS()
class PREDIODRONE_API ADronePawn : public APawn
{
	GENERATED_BODY()

public:
	ADronePawn();

	virtual void Tick(float DeltaSeconds) override;
	virtual void BeginPlay() override;

	// --- estado lido pelo HUD ---
	EModoVoo Modo = EModoVoo::Estabilizado;
	FVector Velocidade = FVector::ZeroVector;     // cm/s (mundo)
	float Bateria = 4.20f;                        // volts por célula (simulado)
	float TempoVoo = 0.f;
	float Acelerador = 0.f;                       // 0..1 (média dos motores)
	bool bArmado = true;
	bool bCaido = false;
	float TempoCaido = 0.f;
	FString Mensagem;
	float TempoMensagem = 0.f;

	// voo automático para teste de desempenho/prints (linha de comando -tour)
	bool bModoTour = false;

	void Recomecar(const FTransform& Onde);
	void MostrarMensagem(const FString& Texto, float Segundos = 2.5f);
	FTransform UltimoCheckpoint;

	UPROPERTY(VisibleAnywhere)
	TObjectPtr<USphereComponent> Corpo;

	UPROPERTY(VisibleAnywhere)
	TObjectPtr<UCameraComponent> Camera;

private:
	void LerControles(float Dt);
	void PassoFisica(float h);
	void MoverComColisao(float h);
	void AtualizarCamera(float Dt);

	// entradas normalizadas
	float InAcel = 0.f;   // -1..1 (estab: subir/descer; acro: 0..1 após mapear)
	float InGuinada = 0.f;
	float InArfagem = 0.f;
	float InRolagem = 0.f;

	// física
	FQuat Orientacao = FQuat::Identity;
	FVector TaxaCorpo = FVector::ZeroVector;      // graus/s (X=rolagem, Y=arfagem, Z=guinada)
	float Motores[4] = { 0.f, 0.f, 0.f, 0.f };    // 0..1
	float Massa = 0.25f;                          // kg (classe E88/cinewhoop leve)
	float EmpuxoMax = 0.f;                        // N (calculado)
	float Acumulador = 0.f;
	float AlturaAlvo = 0.f;                       // cm, trava de altitude
	bool bTravaAltura = true;
	float TremorFase = 0.f;
	float UltimoImpacto = 0.f;
};
