#include "DroneHUD.h"
#include "DronePawn.h"
#include "PredioGameMode.h"
#include "AjustesDrone.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "CanvasItem.h"
#include "GameFramework/PlayerController.h"

void ADroneHUD::Texto(const FString& S, float X, float Y, float Escala, const FLinearColor& Cor, bool bCentro, bool bDireita)
{
	UFont* Fonte = GEngine->GetLargeFont();
	float W = 0.f, H = 0.f;
	Canvas->StrLen(Fonte, S, W, H);
	W *= Escala;
	if (bCentro) X -= W * 0.5f;
	if (bDireita) X -= W;
	FCanvasTextItem Item(FVector2D(X, Y), FText::FromString(S), Fonte, Cor);
	Item.Scale = FVector2D(Escala, Escala);
	Item.EnableShadow(FLinearColor(0, 0, 0, 0.85f), FVector2D(1.5f, 1.5f));
	Item.bOutlined = true;
	Item.OutlineColor = FLinearColor(0, 0, 0, 0.6f);
	Canvas->DrawItem(Item);
}

void ADroneHUD::Caixa(float X, float Y, float W, float H, const FLinearColor& Cor)
{
	FCanvasTileItem Tile(FVector2D(X, Y), FVector2D(W, H), Cor);
	Tile.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Tile);
}

void ADroneHUD::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas) return;

	const APlayerController* PC = GetOwningPlayerController();
	const ADronePawn* D = PC ? Cast<ADronePawn>(PC->GetPawn()) : nullptr;
	const APredioGameMode* GM = GetWorld() ? Cast<APredioGameMode>(GetWorld()->GetAuthGameMode()) : nullptr;
	if (!D || !GM) return;
	if (D->bModoTour) return; // prints limpos no voo de teste

	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const float E = FMath::Clamp(H / 1080.f, 0.6f, 2.f); // escala da interface
	const FLinearColor Branco(1, 1, 1, 0.95f);
	const FLinearColor Amarelo(1.f, 0.85f, 0.2f, 1.f);
	const FLinearColor Vermelho(1.f, 0.25f, 0.2f, 1.f);
	const FLinearColor Verde(0.35f, 1.f, 0.45f, 1.f);

	// --- OSD estilo óculos FPV ---
	const float M = 40.f * E;
	Texto(D->Modo == EModoVoo::Acro ? TEXT("ACRO") : TEXT("ESTAB"), M, M, 1.0f * E, D->Modo == EModoVoo::Acro ? Amarelo : Branco);
	const float V = D->Bateria;
	Texto(FString::Printf(TEXT("%.2fV"), V), M, M + 34.f * E, 1.0f * E, V < 3.5f ? Vermelho : Branco);
	Texto(GM->TextoAndar(GM->AndarAtual), W - M, M, 1.0f * E, Branco, false, true);
	const int32 Min = FMath::FloorToInt(D->TempoVoo / 60.f), Seg = FMath::FloorToInt(D->TempoVoo) % 60;
	Texto(FString::Printf(TEXT("%02d:%02d"), Min, Seg), W - M, M + 34.f * E, 1.0f * E, Branco, false, true);

	const float Kmh = D->Velocidade.Size() * 0.036f;
	const float Alt = (D->GetActorLocation().Z) / 100.f;
	Texto(FString::Printf(TEXT("%3.0f km/h"), Kmh), M, H - M - 30.f * E, 1.0f * E, Branco);
	Texto(FString::Printf(TEXT("ALT %.1f m"), Alt), W - M, H - M - 30.f * E, 1.0f * E, Branco, false, true);
	Texto(FString::Printf(TEXT("ACEL %d%%"), FMath::RoundToInt(D->Acelerador * 100.f)), W * 0.5f, H - M - 30.f * E, 0.9f * E, Branco, true);

	// mira central
	const FLinearColor Mira(1, 1, 1, 0.55f);
	Caixa(W * 0.5f - 14.f * E, H * 0.5f - 1.f * E, 10.f * E, 2.f * E, Mira);
	Caixa(W * 0.5f + 4.f * E, H * 0.5f - 1.f * E, 10.f * E, 2.f * E, Mira);
	Caixa(W * 0.5f - 1.f * E, H * 0.5f + 4.f * E, 2.f * E, 8.f * E, Mira);

	// mensagens
	if (D->TempoMensagem > 0.f && !D->Mensagem.IsEmpty())
	{
		const float Alfa = FMath::Clamp(D->TempoMensagem * 2.f, 0.f, 1.f);
		Texto(D->Mensagem, W * 0.5f, H * 0.30f, 1.05f * E, FLinearColor(1, 1, 1, Alfa), true);
	}
	if (D->bCaido)
	{
		Caixa(0, 0, W, H, FLinearColor(0.f, 0.f, 0.f, FMath::Clamp(D->TempoCaido * 0.45f, 0.f, 0.85f)));
	}

	// --- painel de desempenho (F5) ---
	if (FAjustesDrone::Get().bPainel && !GM->bMenuAberto)
	{
		const bool bFG = APredioGameMode::GeradorLigado();
		const bool bFSR = APredioGameMode::FSRLigado();
		const float X = M, Y = M + 90.f * E;
		Caixa(X - 8.f * E, Y - 6.f * E, 430.f * E, 112.f * E, FLinearColor(0, 0, 0, 0.35f));
		const FLinearColor CorFPS = GM->FPSBase >= 59.f ? Verde : (GM->FPSBase >= 50.f ? Amarelo : Vermelho);
		FString L1 = FString::Printf(TEXT("FPS base %.0f"), GM->FPSBase);
		if (bFG) L1 += FString::Printf(TEXT("  →  ~%.0f com gerador"), GM->FPSBase * 2.f);
		Texto(L1, X, Y, 0.75f * E, CorFPS);
		Texto(FString::Printf(TEXT("GPU %.1f ms   jogo %.1f ms"), GM->MsGPU, GM->MsJogo), X, Y + 24.f * E, 0.7f * E, Branco);
		Texto(bFSR ? FString::Printf(TEXT("AMD FSR 4 (IA): %s"), *APredioGameMode::NomeModoFSR()) : FString(TEXT("FSR desligado (TSR)")), X, Y + 48.f * E, 0.7f * E, bFSR ? Verde : Amarelo);
		Texto(FString::Printf(TEXT("Gerador de quadros AMD: %s   Ajuste 60 FPS: %s"), bFG ? TEXT("LIGADO") : TEXT("desligado"), FAjustesDrone::Get().bAjusteAuto ? TEXT("auto") : TEXT("manual")), X, Y + 72.f * E, 0.7f * E, bFG ? Verde : Branco);
	}

	// --- ajuda (F1) ---
	if (GM->bMostrarAjuda)
	{
		Caixa(W * 0.18f, H * 0.16f, W * 0.64f, H * 0.68f, FLinearColor(0, 0, 0, 0.72f));
		const TCHAR* Linhas[] = {
			TEXT("CONTROLES — mapa do prédio em construção"),
			TEXT(""),
			TEXT("Controle (modo 2):  analógico esquerdo ↑↓ sobe/desce (acelerador no ACRO), ←→ gira"),
			TEXT("                    analógico direito ↑↓ frente/trás, ←→ lados"),
			TEXT("                    Y troca ESTABILIZADO/ACRO    X volta ao início"),
			TEXT("                    START abre o MENU (sensibilidade, inverter eixos, som, AMD)"),
			TEXT("Teclado:  W/S sobe/desce   A/D gira   setas (ou I J K L) frente/trás/lados"),
			TEXT("          M modo   R volta ao início   Esc menu   F1 esta ajuda"),
			TEXT(""),
			TEXT("AMD:  F2 modo do FSR 4   F3 gerador de quadros   F4 FSR liga/desliga (comparar)"),
			TEXT("      F5 painel de FPS   F6 ajuste automático para manter 60 FPS de base"),
			TEXT(""),
			TEXT("Voe pelos corredores, pelo poço do elevador, pela escada e pelos buracos na laje."),
			TEXT("Só o andar onde você está é desenhado — o vizinho aparece quando chega perto"),
			TEXT("do poço, da escada ou de um buraco. Bateu forte = hélice quebra e volta ao início."),
		};

		float Y = H * 0.19f;
		for (const TCHAR* L : Linhas)
		{
			Texto(L, W * 0.21f, Y, 0.8f * E, Branco);
			Y += 30.f * E;
		}
	}

	// --- menu (Start / Esc) ---
	if (GM->bMenuAberto)
	{
		Caixa(0, 0, W, H, FLinearColor(0, 0, 0, 0.45f));
		const int32 N = (int32)EItemMenu::Total;
		const float Lh = 36.f * E;
		const float Lw = 760.f * E;
		const float X0 = W * 0.5f - Lw * 0.5f;
		const float Y0 = H * 0.5f - (N * Lh + 110.f * E) * 0.5f;
		Caixa(X0 - 20.f * E, Y0 - 20.f * E, Lw + 40.f * E, N * Lh + 150.f * E, FLinearColor(0.02f, 0.02f, 0.025f, 0.86f));
		Texto(TEXT("MENU"), W * 0.5f, Y0, 1.15f * E, Amarelo, true);
		float Y = Y0 + 56.f * E;
		for (int32 i = 0; i < N; ++i)
		{
			const bool bSel = i == GM->MenuIndice;
			if (bSel) Caixa(X0 - 8.f * E, Y - 3.f * E, Lw + 16.f * E, Lh - 2.f * E, FLinearColor(1.f, 0.75f, 0.1f, 0.22f));
			const FLinearColor Cor = bSel ? Amarelo : Branco;
			Texto(GM->NomeItem(i), X0 + 6.f * E, Y, 0.8f * E, Cor);
			const FString Val = GM->ValorItem(i);
			if (!Val.IsEmpty())
			{
				Texto(bSel ? FString::Printf(TEXT("<  %s  >"), *Val) : Val, X0 + Lw - 6.f * E, Y, 0.8f * E, Cor, false, true);
			}
			Y += Lh;
		}
		Texto(TEXT("↑↓ escolhe    ←→ muda    A / Enter confirma    B / Start / Esc fecha"), W * 0.5f, Y + 14.f * E, 0.65f * E, FLinearColor(1, 1, 1, 0.7f), true);
	}
}
