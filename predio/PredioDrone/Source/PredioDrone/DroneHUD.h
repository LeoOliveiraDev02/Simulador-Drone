#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "DroneHUD.generated.h"

/** OSD dos óculos FPV + painel de desempenho (FSR / gerador de quadros / FPS). */
UCLASS()
class PREDIODRONE_API ADroneHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

private:
	void Texto(const FString& S, float X, float Y, float Escala, const FLinearColor& Cor, bool bCentro = false, bool bDireita = false);
	void Caixa(float X, float Y, float W, float H, const FLinearColor& Cor);
};
