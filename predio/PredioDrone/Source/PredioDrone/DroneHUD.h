#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "Fonts/SlateFontInfo.h"
#include "DroneHUD.generated.h"

class APredioGameMode;
class UFont;

/** OSD dos óculos FPV + painel de desempenho + menu de configurações (pausa). */
UCLASS()
class PREDIODRONE_API ADroneHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

private:
	// OSD simples
	void Texto(const FString& S, float X, float Y, float Escala, const FLinearColor& Cor, bool bCentro = false, bool bDireita = false);
	void Caixa(float X, float Y, float W, float H, const FLinearColor& Cor);

	// menu
	void DesenharMenu(APredioGameMode* GM);
	void DesenharMenuPrincipal(APredioGameMode* GM);
	void Ilustracao(int32 Cartao, float X, float Y, float W, float H, bool bSel);
	void Imagem(class UTexture2D* Tex, float X, float Y, float W, float H, const FLinearColor& Cor);
	void Cadeado(FVector2D C, float S, const FLinearColor& Cor);
	void DesenharObjetivo(APredioGameMode* GM, const class ADronePawn* D, float E);
	void DesenharResultado(APredioGameMode* GM, float E);
	FSlateFontInfo Fonte(float Px, const TCHAR* Face) const;
	FVector2D Medir(const FString& S, const FSlateFontInfo& F) const;
	float T(const FString& S, float X, float Y, float Px, const TCHAR* Face, const FLinearColor& Cor, int32 Alinh = 0, float Espaco = 0.f);
	void Linha(FVector2D A, FVector2D B, float Esp, const FLinearColor& Cor);
	void Arco(FVector2D C, float R, float Esp, const FLinearColor& Cor, float A0 = 0.f, float A1 = 360.f, int32 Segs = 28);
	void Disco(FVector2D C, float R, const FLinearColor& Cor, int32 Segs = 20);
	void Tri(FVector2D A, FVector2D B, FVector2D C, const FLinearColor& Cor);
	void RetArred(float X, float Y, float W, float H, float R, const FLinearColor& CorEsq, const FLinearColor& CorDir);
	void ContornoArred(float X, float Y, float W, float H, float R, float Esp, const FLinearColor& Cor);
	void Seta(FVector2D De, FVector2D Para, float Esp, float Ponta, const FLinearColor& Cor);
	void Icone(int32 Tipo, FVector2D C, float S, const FLinearColor& Cor);

	UPROPERTY()
	TObjectPtr<UFont> Roboto;

	UPROPERTY()
	TObjectPtr<class UTexture2D> ImgUsina;
	bool bTentouUsina = false;

	float Esc = 1.f; // escala do menu (pixels por unidade de desenho)
};
