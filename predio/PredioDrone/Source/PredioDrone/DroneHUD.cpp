#include "DroneHUD.h"
#include "DronePawn.h"
#include "PredioGameMode.h"
#include "AjustesDrone.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "CanvasItem.h"
#include "GameFramework/PlayerController.h"
#include "Framework/Application/SlateApplication.h"
#include "Fonts/FontMeasure.h"
#include "Rendering/SlateRenderer.h"
#include "RenderUtils.h"
#include "Camera/PlayerCameraManager.h"

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
	APredioGameMode* GM = GetWorld() ? Cast<APredioGameMode>(GetWorld()->GetAuthGameMode()) : nullptr;
	if (!D || !GM) return;
	if (!Roboto)
	{
		Roboto = LoadObject<UFont>(nullptr, TEXT("/Engine/EngineFonts/Roboto.Roboto"));
	}
	if (GM->bMenuPrincipal && !GM->bMenuAberto)
	{
		DesenharMenuPrincipal(GM);
		return;
	}
	if (GM->bMenuAberto)
	{
		if (!GM->bMenuJaDesenhado && !D->bModoTour)
		{
			GM->bMenuJaDesenhado = true;
			GM->Registrar(TEXT("HUD desenhou o menu"));
		}
		DesenharMenu(GM);
		return;
	}
	if (D->bModoTour) return; // prints limpos no voo de teste

	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const float E = FMath::Clamp(H / 1080.f, 0.6f, 2.f) * FAjustesDrone::Get().EscalaInterface; // escala da interface
	const FLinearColor Branco(1, 1, 1, 0.95f);
	const FLinearColor Amarelo(1.f, 0.85f, 0.2f, 1.f);
	const FLinearColor Vermelho(1.f, 0.25f, 0.2f, 1.f);
	const FLinearColor Verde(0.35f, 1.f, 0.45f, 1.f);

	// --- OSD estilo óculos FPV ---
	const float M = 40.f * E;
	Texto(D->Modo == EModoVoo::Acro ? TEXT("ACRO") : TEXT("ESTAB"), M, M, 1.0f * E, D->Modo == EModoVoo::Acro ? Amarelo : Branco);
	const float V = D->Bateria;
	Texto(FString::Printf(TEXT("%.2fV"), V), M, M + 34.f * E, 1.0f * E, V < 3.5f ? Vermelho : Branco);
	{
		// estado das hélices: cada batida apaga uma; na terceira o drone quebra
		const int32 Restam = FMath::Max(0, ADronePawn::MaxBatidas - D->Batidas);
		const FString Hel = FString::Printf(TEXT("HÉLICES %d/%d"), Restam, ADronePawn::MaxBatidas);
		Texto(Hel, M, M + 62.f * E, 0.75f * E, Restam >= ADronePawn::MaxBatidas ? Branco : (Restam == 1 ? Vermelho : Amarelo));
	}
	Texto(GM->TextoLocal(), W - M, M, 1.0f * E, Branco, false, true);
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

	// objetivo (cronômetro, aros, resultado)
	DesenharObjetivo(GM, D, E);

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
	if (FAjustesDrone::Get().bPainel)
	{
		const bool bFG = APredioGameMode::GeradorLigado();
		const bool bFSR = APredioGameMode::FSRLigado();
		const float X = M, Y = M + 104.f * E;
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
			TEXT("                    START abre o MENU e pausa (sensibilidade, inverter eixos, som, AMD)"),
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
}

// =====================================================================================
// MENU — painel escuro com detalhes azuis, categorias à esquerda e opções à direita
// =====================================================================================
namespace
{
	enum EIcone
	{
		IcMonitor, IcMira, IcControle, IcSetasH, IcSetasV, IcGiro, IcLados, IcOlho, IcDrone, IcChip, IcQuadro,
		IcMedidor, IcEngrenagem, IcRecarregar, IcEstrela, IcEnergia, IcTexto, IcSliders, IcAltoFalante,
		IcAcessib, IcChave, IcDocumento, IcMonitorSync, IcBandeira, IcAro, IcRelogio, IcCasa
	};
	const int32 IconeItem[] = {
		IcMonitor,      // Continuar
		IcBandeira,     // Objetivo
		IcOlho,         // Modo de voo
		IcRecarregar,   // Voltar ao início
		IcCasa,         // Menu principal
		IcMira,         // Sensibilidade
		IcControle,     // Expo
		IcChip,         // FSR
		IcQuadro,       // Gerador
		IcMonitorSync,  // VSync
		IcMedidor,      // Painel
		IcEngrenagem,   // Ajuste automático
		IcDrone,        // Volume
		IcSetasH,       // Inverter frente/trás
		IcSetasV,       // Inverter subir/descer
		IcGiro,         // Inverter giro
		IcLados,        // Inverter lados
		IcTexto,        // Tamanho da interface
		IcEstrela,      // Restaurar padrões
		IcEnergia,      // Sair
	};
	const int32 IconeCategoria[] = { IcControle, IcSliders, IcMira, IcMonitor, IcAltoFalante, IcSetasH, IcAcessib, IcChave, IcDocumento };

	// cores escritas em sRGB (0–255, como num editor de imagem) e convertidas para o Canvas
	FLinearColor Cor255(uint8 R, uint8 G, uint8 B, uint8 A = 255) { return FLinearColor(FColor(R, G, B, A)); }
	const FLinearColor AzulClaro = Cor255(94, 160, 255);
	const FLinearColor AzulTexto = Cor255(143, 184, 255);
	const FLinearColor Branco = Cor255(236, 243, 255);
	const FLinearColor Cinza = Cor255(120, 140, 172);
	const FLinearColor Apagado = Cor255(80, 96, 122);

	FVector2D Polar(FVector2D C, float R, float Graus)
	{
		const float A = FMath::DegreesToRadians(Graus);
		return C + FVector2D(FMath::Cos(A), -FMath::Sin(A)) * R; // ângulo matemático, y da tela para baixo
	}
}

FSlateFontInfo ADroneHUD::Fonte(float Px, const TCHAR* Face) const
{
	UFont* F = Roboto ? Roboto.Get() : GEngine->GetLargeFont();
	return FSlateFontInfo(F, FMath::Max(4.f, Px * 0.75f), FName(Face));
}

FVector2D ADroneHUD::Medir(const FString& S, const FSlateFontInfo& F) const
{
	if (FSlateApplication::IsInitialized())
	{
		const TSharedRef<FSlateFontMeasure> M = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
		const FVector2D R = M->Measure(S, F);
		return R;
	}
	return FVector2D(S.Len() * F.Size * 0.7f, F.Size * 1.3f);
}

float ADroneHUD::T(const FString& S, float X, float Y, float Px, const TCHAR* Face, const FLinearColor& Cor, int32 Alinh, float Espaco)
{
	if (S.IsEmpty()) return 0.f;
	const FSlateFontInfo F = Fonte(Px, Face);
	if (Espaco <= 0.f)
	{
		const FVector2D Tam = Medir(S, F);
		if (Alinh == 1) X -= Tam.X * 0.5f;
		if (Alinh == 2) X -= Tam.X;
		FCanvasTextItem Item(FVector2D(X, Y), FText::FromString(S), F, Cor);
		Item.BlendMode = SE_BLEND_Translucent;
		Canvas->DrawItem(Item);
		return Tam.X;
	}
	// letras espaçadas (títulos)
	TArray<float> Larg;
	float Total = 0.f;
	for (int32 i = 0; i < S.Len(); ++i)
	{
		const float L = Medir(S.Mid(i, 1), F).X;
		Larg.Add(L);
		Total += L + (i + 1 < S.Len() ? Espaco : 0.f);
	}
	if (Alinh == 1) X -= Total * 0.5f;
	if (Alinh == 2) X -= Total;
	for (int32 i = 0; i < S.Len(); ++i)
	{
		FCanvasTextItem Item(FVector2D(X, Y), FText::FromString(S.Mid(i, 1)), F, Cor);
		Item.BlendMode = SE_BLEND_Translucent;
		Canvas->DrawItem(Item);
		X += Larg[i] + Espaco;
	}
	return Total;
}

void ADroneHUD::Linha(FVector2D A, FVector2D B, float Esp, const FLinearColor& Cor)
{
	FVector2D D = B - A;
	const float Len = D.Size();
	if (Len < 0.01f) return;
	D /= Len;
	const FVector2D N(-D.Y * Esp * 0.5f, D.X * Esp * 0.5f);
	Tri(A + N, B + N, B - N, Cor);
	Tri(A + N, B - N, A - N, Cor);
}

void ADroneHUD::Tri(FVector2D A, FVector2D B, FVector2D C, const FLinearColor& Cor)
{
	FCanvasUVTri T3;
	T3.V0_Pos = A; T3.V1_Pos = B; T3.V2_Pos = C;
	T3.V0_UV = T3.V1_UV = T3.V2_UV = FVector2D::ZeroVector;
	T3.V0_Color = T3.V1_Color = T3.V2_Color = Cor;
	FCanvasTriangleItem Item(T3, GWhiteTexture);
	Item.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Item);
}

void ADroneHUD::Arco(FVector2D C, float R, float Esp, const FLinearColor& Cor, float A0, float A1, int32 Segs)
{
	FVector2D Ant = Polar(C, R, A0);
	for (int32 i = 1; i <= Segs; ++i)
	{
		const FVector2D P = Polar(C, R, FMath::Lerp(A0, A1, (float)i / Segs));
		Linha(Ant, P, Esp, Cor);
		Ant = P;
	}
}

void ADroneHUD::Disco(FVector2D C, float R, const FLinearColor& Cor, int32 Segs)
{
	TArray<FCanvasUVTri> Lista;
	for (int32 i = 0; i < Segs; ++i)
	{
		FCanvasUVTri T3;
		T3.V0_Pos = C;
		T3.V1_Pos = Polar(C, R, 360.f * i / Segs);
		T3.V2_Pos = Polar(C, R, 360.f * (i + 1) / Segs);
		T3.V0_UV = T3.V1_UV = T3.V2_UV = FVector2D::ZeroVector;
		T3.V0_Color = T3.V1_Color = T3.V2_Color = Cor;
		Lista.Add(T3);
	}
	FCanvasTriangleItem Item(Lista, GWhiteTexture);
	Item.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Item);
}

static void PerimetroArred(TArray<FVector2D>& P, float X, float Y, float W, float H, float R)
{
	R = FMath::Min(R, FMath::Min(W, H) * 0.5f);
	const FVector2D Cs[4] = { {X + W - R, Y + R}, {X + R, Y + R}, {X + R, Y + H - R}, {X + W - R, Y + H - R} };
	for (int32 c = 0; c < 4; ++c)
	{
		for (int32 k = 0; k <= 6; ++k)
		{
			P.Add(Polar(Cs[c], R, c * 90.f + 90.f * k / 6.f));
		}
	}
}

void ADroneHUD::RetArred(float X, float Y, float W, float H, float R, const FLinearColor& CorEsq, const FLinearColor& CorDir)
{
	TArray<FVector2D> P;
	PerimetroArred(P, X, Y, W, H, R);
	const FVector2D C(X + W * 0.5f, Y + H * 0.5f);
	auto CorEm = [&](const FVector2D& Q) { return FMath::Lerp(CorEsq, CorDir, FMath::Clamp((Q.X - X) / FMath::Max(W, 1.f), 0.f, 1.f)); };
	TArray<FCanvasUVTri> Lista;
	for (int32 i = 0; i < P.Num(); ++i)
	{
		const FVector2D& A = P[i];
		const FVector2D& B = P[(i + 1) % P.Num()];
		FCanvasUVTri T3;
		T3.V0_Pos = C; T3.V1_Pos = A; T3.V2_Pos = B;
		T3.V0_UV = T3.V1_UV = T3.V2_UV = FVector2D::ZeroVector;
		T3.V0_Color = CorEm(C); T3.V1_Color = CorEm(A); T3.V2_Color = CorEm(B);
		Lista.Add(T3);
	}
	FCanvasTriangleItem Item(Lista, GWhiteTexture);
	Item.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Item);
}

void ADroneHUD::ContornoArred(float X, float Y, float W, float H, float R, float Esp, const FLinearColor& Cor)
{
	TArray<FVector2D> P;
	PerimetroArred(P, X, Y, W, H, R);
	for (int32 i = 0; i < P.Num(); ++i)
	{
		Linha(P[i], P[(i + 1) % P.Num()], Esp, Cor);
	}
}

void ADroneHUD::Seta(FVector2D De, FVector2D Para, float Esp, float Ponta, const FLinearColor& Cor)
{
	Linha(De, Para, Esp, Cor);
	FVector2D D = Para - De;
	if (D.IsNearlyZero()) return;
	D.Normalize();
	const FVector2D N(-D.Y, D.X);
	Tri(Para + D * Esp * 0.6f, Para - D * Ponta + N * Ponta * 0.75f, Para - D * Ponta - N * Ponta * 0.75f, Cor);
}

void ADroneHUD::Icone(int32 Tipo, FVector2D C, float S, const FLinearColor& Cor)
{
	const float E = FMath::Max(1.4f, S * 0.13f);
	auto P = [&](float X, float Y) { return C + FVector2D(X * S, Y * S); };
	auto Monitor = [&]()
	{
		ContornoArred(C.X - S, C.Y - 0.75f * S, 2.f * S, 1.25f * S, 0.12f * S, E, Cor);
		Linha(P(0, 0.5f), P(0, 0.78f), E, Cor);
		Linha(P(-0.45f, 0.82f), P(0.45f, 0.82f), E, Cor);
	};
	switch (Tipo)
	{
	case IcMonitor: Monitor(); break;
	case IcMonitorSync:
		Monitor();
		Arco(P(0, -0.12f), 0.3f * S, E, Cor, 30.f, 300.f, 14);
		Tri(Polar(P(0, -0.12f), 0.3f * S, 30.f) + FVector2D(0.18f * S, 0), Polar(P(0, -0.12f), 0.3f * S, 30.f) - FVector2D(0.12f * S, 0.0f), Polar(P(0, -0.12f), 0.3f * S, 30.f) + FVector2D(0.02f * S, 0.2f * S), Cor);
		break;
	case IcMira:
		Arco(C, 0.62f * S, E, Cor);
		Linha(P(0, -1), P(0, -0.32f), E, Cor); Linha(P(0, 0.32f), P(0, 1), E, Cor);
		Linha(P(-1, 0), P(-0.32f, 0), E, Cor); Linha(P(0.32f, 0), P(1, 0), E, Cor);
		Disco(C, 0.12f * S, Cor, 10);
		break;
	case IcControle:
		ContornoArred(C.X - S, C.Y - 0.58f * S, 2.f * S, 1.16f * S, 0.5f * S, E, Cor);
		Linha(P(-0.62f, 0), P(-0.18f, 0), E, Cor); Linha(P(-0.4f, -0.22f), P(-0.4f, 0.22f), E, Cor);
		Disco(P(0.35f, -0.12f), 0.1f * S, Cor, 8); Disco(P(0.58f, 0.12f), 0.1f * S, Cor, 8);
		break;
	case IcSetasH:
		Seta(P(-0.15f, 0), P(-1, 0), E, 0.38f * S, Cor); Seta(P(0.15f, 0), P(1, 0), E, 0.38f * S, Cor);
		Linha(P(-0.2f, 0), P(0.2f, 0), E, Cor);
		break;
	case IcSetasV:
		Seta(P(-0.35f, 0.85f), P(-0.35f, -0.85f), E, 0.36f * S, Cor);
		Seta(P(0.35f, -0.85f), P(0.35f, 0.85f), E, 0.36f * S, Cor);
		break;
	case IcGiro:
	case IcRecarregar:
	{
		const float A1 = Tipo == IcGiro ? 300.f : 330.f;
		Arco(C, 0.72f * S, E, Cor, 40.f, A1, 22);
		const FVector2D Fim = Polar(C, 0.72f * S, A1);
		const FVector2D Tang = Polar(FVector2D::ZeroVector, 1.f, A1 + 90.f);
		Seta(Fim - Tang * 0.05f * S, Fim + Tang * 0.25f * S, E, 0.32f * S, Cor);
		if (Tipo == IcRecarregar)
		{
			const FVector2D Ini = Polar(C, 0.72f * S, 40.f);
			const FVector2D Tang2 = Polar(FVector2D::ZeroVector, 1.f, 40.f - 90.f);
			Seta(Ini - Tang2 * 0.05f * S, Ini + Tang2 * 0.25f * S, E, 0.32f * S, Cor);
		}
		break;
	}
	case IcLados:
		Arco(C, 0.9f * S, E, Cor);
		Seta(P(-0.1f, 0), P(-0.55f, 0), E, 0.25f * S, Cor); Seta(P(0.1f, 0), P(0.55f, 0), E, 0.25f * S, Cor);
		Linha(P(-0.15f, 0), P(0.15f, 0), E, Cor);
		break;
	case IcOlho:
	{
		FVector2D Ant = P(1, 0);
		for (int32 i = 1; i <= 24; ++i)
		{
			const float A = 2.f * PI * i / 24.f;
			const FVector2D Q = P(FMath::Cos(A), 0.55f * FMath::Sin(A));
			Linha(Ant, Q, E, Cor);
			Ant = Q;
		}
		Arco(C, 0.3f * S, E, Cor, 0.f, 360.f, 16);
		Disco(C, 0.12f * S, Cor, 8);
		break;
	}
	case IcDrone:
		for (int32 sx = -1; sx <= 1; sx += 2)
			for (int32 sy = -1; sy <= 1; sy += 2)
			{
				Linha(P(0.18f * sx, 0.18f * sy), P(0.55f * sx, 0.55f * sy), E, Cor);
				Arco(P(0.62f * sx, 0.62f * sy), 0.33f * S, E, Cor, 0.f, 360.f, 14);
			}
		ContornoArred(C.X - 0.22f * S, C.Y - 0.22f * S, 0.44f * S, 0.44f * S, 0.08f * S, E, Cor);
		break;
	case IcChip:
		ContornoArred(C.X - 0.62f * S, C.Y - 0.62f * S, 1.24f * S, 1.24f * S, 0.12f * S, E, Cor);
		ContornoArred(C.X - 0.28f * S, C.Y - 0.28f * S, 0.56f * S, 0.56f * S, 0.05f * S, E, Cor);
		for (float k : { -0.35f, 0.f, 0.35f })
		{
			Linha(P(k, -0.62f), P(k, -0.95f), E, Cor); Linha(P(k, 0.62f), P(k, 0.95f), E, Cor);
			Linha(P(-0.62f, k), P(-0.95f, k), E, Cor); Linha(P(0.62f, k), P(0.95f, k), E, Cor);
		}
		break;
	case IcQuadro:
		for (int32 sx = -1; sx <= 1; sx += 2)
			for (int32 sy = -1; sy <= 1; sy += 2)
			{
				Linha(P(sx * 0.9f, sy * 0.9f), P(sx * 0.4f, sy * 0.9f), E, Cor);
				Linha(P(sx * 0.9f, sy * 0.9f), P(sx * 0.9f, sy * 0.4f), E, Cor);
			}
		Arco(C, 0.3f * S, E, Cor, 0.f, 360.f, 14);
		break;
	case IcMedidor:
		Arco(P(0, 0.2f), 0.85f * S, E, Cor, -20.f, 200.f, 22);
		Linha(P(0, 0.2f), Polar(P(0, 0.2f), 0.6f * S, 55.f), E, Cor);
		Disco(P(0, 0.2f), 0.13f * S, Cor, 10);
		break;
	case IcEngrenagem:
		Arco(C, 0.55f * S, E, Cor, 0.f, 360.f, 20);
		Arco(C, 0.2f * S, E, Cor, 0.f, 360.f, 12);
		for (int32 i = 0; i < 8; ++i)
		{
			Linha(Polar(C, 0.55f * S, i * 45.f), Polar(C, 0.9f * S, i * 45.f), E * 2.2f, Cor);
		}
		break;
	case IcEstrela:
	{
		TArray<FVector2D> Pt;
		for (int32 i = 0; i < 10; ++i) Pt.Add(Polar(C, (i % 2 == 0 ? 0.95f : 0.42f) * S, 90.f + i * 36.f));
		for (int32 i = 0; i < 10; ++i) Linha(Pt[i], Pt[(i + 1) % 10], E, Cor);
		break;
	}
	case IcEnergia:
		Arco(C, 0.72f * S, E, Cor, 125.f, 415.f, 22);
		Linha(P(0, -1.f), P(0, -0.1f), E, Cor);
		break;
	case IcTexto:
		T(TEXT("Aa"), C.X, C.Y - 0.85f * S, 1.6f * S, TEXT("Bold"), Cor, 1);
		break;
	case IcSliders:
		for (int32 i = 0; i < 3; ++i)
		{
			const float Y = (i - 1) * 0.6f;
			Linha(P(-1, Y), P(1, Y), E, Cor);
			Disco(P(i == 0 ? 0.45f : (i == 1 ? -0.35f : 0.15f), Y), 0.2f * S, Cor, 10);
		}
		break;
	case IcAltoFalante:
		Linha(P(-0.95f, -0.3f), P(-0.95f, 0.3f), E, Cor);
		Linha(P(-0.95f, -0.3f), P(-0.55f, -0.3f), E, Cor); Linha(P(-0.95f, 0.3f), P(-0.55f, 0.3f), E, Cor);
		Linha(P(-0.55f, -0.3f), P(-0.05f, -0.75f), E, Cor); Linha(P(-0.55f, 0.3f), P(-0.05f, 0.75f), E, Cor);
		Linha(P(-0.05f, -0.75f), P(-0.05f, 0.75f), E, Cor);
		Arco(P(0.0f, 0), 0.45f * S, E, Cor, -45.f, 45.f, 8);
		Arco(P(0.0f, 0), 0.82f * S, E, Cor, -50.f, 50.f, 10);
		break;
	case IcAcessib:
		Monitor();
		Disco(P(0, -0.42f), 0.12f * S, Cor, 8);
		Linha(P(-0.35f, -0.2f), P(0.35f, -0.2f), E, Cor);
		Linha(P(0, -0.25f), P(0, 0.05f), E, Cor);
		Linha(P(0, 0.05f), P(-0.2f, 0.32f), E, Cor); Linha(P(0, 0.05f), P(0.2f, 0.32f), E, Cor);
		break;
	case IcChave:
		Linha(P(-0.8f, 0.8f), P(0.15f, -0.15f), E * 1.8f, Cor);
		Arco(P(0.42f, -0.42f), 0.38f * S, E * 1.3f, Cor, 100.f, 350.f, 14);
		break;
	case IcBandeira:
		Linha(P(-0.6f, 1.f), P(-0.6f, -1.f), E, Cor);
		Tri(P(-0.6f, -1.f), P(0.85f, -0.62f), P(-0.6f, -0.22f), Cor);
		break;
	case IcAro:
		Arco(C, 0.85f * S, E * 1.6f, Cor, 0.f, 360.f, 24);
		Arco(C, 0.45f * S, E, Cor, 0.f, 360.f, 16);
		break;
	case IcRelogio:
		Arco(C, 0.85f * S, E, Cor, 0.f, 360.f, 24);
		Linha(C, P(0, -0.55f), E, Cor);
		Linha(C, P(0.4f, 0.1f), E, Cor);
		Linha(P(-0.25f, -1.05f), P(0.25f, -1.05f), E * 1.3f, Cor);
		break;
	case IcCasa:
		Linha(P(-0.95f, -0.05f), P(0, -0.9f), E, Cor); Linha(P(0, -0.9f), P(0.95f, -0.05f), E, Cor);
		Linha(P(-0.65f, -0.3f), P(-0.65f, 0.85f), E, Cor); Linha(P(0.65f, -0.3f), P(0.65f, 0.85f), E, Cor);
		Linha(P(-0.65f, 0.85f), P(0.65f, 0.85f), E, Cor);
		ContornoArred(C.X - 0.2f * S, C.Y + 0.25f * S, 0.4f * S, 0.6f * S, 0.05f * S, E, Cor);
		break;
	case IcDocumento:
		ContornoArred(C.X - 0.7f * S, C.Y - S, 1.4f * S, 2.f * S, 0.15f * S, E, Cor);
		for (float Y : { -0.45f, 0.f, 0.45f }) Linha(P(-0.38f, Y), P(0.38f, Y), E, Cor);
		break;
	default: break;
	}
}

void ADroneHUD::DesenharMenu(APredioGameMode* GM)
{
	if (!Roboto)
	{
		Roboto = LoadObject<UFont>(nullptr, TEXT("/Engine/EngineFonts/Roboto.Roboto"));
	}
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	// projeto em unidades de 1280 x 960 (painel 1280 x 900 + rodapé), centralizado na tela
	Esc = FMath::Min(W * 0.90f / 1280.f, H * 0.94f / 960.f);
	const float OX = (W - 1280.f * Esc) * 0.5f;
	const float OY = (H - 960.f * Esc) * 0.5f;
	auto X = [&](float V) { return OX + V * Esc; };
	auto Y = [&](float V) { return OY + V * Esc; };
	auto Pt = [&](float A, float B) { return FVector2D(X(A), Y(B)); };
	const float e = Esc;

	// escurece o simulador pausado
	Caixa(0, 0, W, H, Cor255(2, 5, 12, 150));

	// painel
	RetArred(X(0), Y(0), 1280 * e, 900 * e, 10 * e, Cor255(7, 13, 25, 246), Cor255(9, 20, 38, 246));
	ContornoArred(X(0), Y(0), 1280 * e, 900 * e, 10 * e, FMath::Max(1.f, 1.4f * e), Cor255(52, 104, 190, 170));
	// brilho azul no topo
	Linha(Pt(40, 1), Pt(620, 1), 2.f * e, Cor255(80, 150, 255, 140));

	// título
	Linha(Pt(22, 66), Pt(88, 66), 2.2f * e, Cor255(70, 140, 255, 220));
	T(TEXT("MENU"), X(96), Y(14), 76 * e, TEXT("Bold Italic"), Branco);
	T(TEXT("CONFIGURAÇÕES DO JOGO"), X(100), Y(104), 18 * e, TEXT("Italic"), AzulTexto, 0, 4.5f * e);

	// canto de cima: engrenagem + DESEMPENHO • QUALIDADE • CONTROLE + fechar
	{
		const float LargT = T(TEXT("DESEMPENHO • QUALIDADE • CONTROLE"), X(1232), Y(70), 14 * e, TEXT("Italic"), AzulTexto, 2, 3.2f * e);
		const float XB = X(1232) - LargT - 16 * e;
		Linha(FVector2D(XB, Y(64)), FVector2D(XB, Y(96)), 2.f * e, Cor255(70, 140, 255));
		Icone(IcEngrenagem, FVector2D(XB - 26 * e, Y(80)), 13 * e, AzulTexto);
	}
	{
		const FVector2D CF = Pt(1238, 40);
		Linha(CF + FVector2D(-11, -11) * e, CF + FVector2D(11, 11) * e, 2.4f * e, Branco);
		Linha(CF + FVector2D(-11, 11) * e, CF + FVector2D(11, -11) * e, 2.4f * e, Branco);
		GM->AreaFechar = FBox2D(CF - FVector2D(20, 20) * e, CF + FVector2D(20, 20) * e);
	}

	// coluna da esquerda: categorias
	const int32 NC = (int32)ECategoriaMenu::Total;
	const ECategoriaMenu CatSel = APredioGameMode::CategoriaDoItem(GM->MenuIndice);
	GM->AreaCategorias.SetNum(NC);
	for (int32 c = 0; c < NC; ++c)
	{
		const float CY = 150.f + c * 64.f;
		const bool bSel = (ECategoriaMenu)c == CatSel;
		if (bSel)
		{
			RetArred(X(22), Y(CY), 250 * e, 56 * e, 7 * e, Cor255(26, 102, 232), Cor255(14, 58, 150));
			ContornoArred(X(22), Y(CY), 250 * e, 56 * e, 7 * e, FMath::Max(1.f, 1.3f * e), Cor255(100, 165, 255));
			Linha(Pt(250, CY + 20), Pt(257, CY + 28), 2.f * e, Branco);
			Linha(Pt(257, CY + 28), Pt(250, CY + 36), 2.f * e, Branco);
		}
		else
		{
			Linha(Pt(30, CY + 60), Pt(268, CY + 60), FMath::Max(1.f, e), Cor255(30, 45, 70, 200));
		}
		const FLinearColor Cor = bSel ? Branco : AzulTexto;
		Icone(IconeCategoria[c], Pt(56, CY + 28), 13 * e, Cor);
		T(APredioGameMode::NomeCategoria((ECategoriaMenu)c), X(92), Y(CY + 15), 19 * e, TEXT("Regular"), Cor);
		GM->AreaCategorias[c] = FBox2D(Pt(22, CY), Pt(272, CY + 56));
	}

	// lema no canto de baixo
	Linha(Pt(40, 772), Pt(40, 858), 2.f * e, Cor255(70, 140, 255));
	T(TEXT("VOE"), X(58), Y(770), 16 * e, TEXT("Italic"), AzulTexto, 0, 5.f * e);
	T(TEXT("EXPLORE"), X(58), Y(797), 16 * e, TEXT("Italic"), AzulTexto, 0, 5.f * e);
	T(TEXT("DOMINE"), X(58), Y(824), 16 * e, TEXT("Italic"), AzulTexto, 0, 5.f * e);

	// lista de opções
	const int32 N = (int32)EItemMenu::Total;
	const float L0 = 300.f, L1 = 1228.f, Topo = 148.f, Base = 880.f;
	const float RH = (Base - Topo) / N;
	GM->AreaItens.SetNum(N);
	for (int32 i = 0; i < N; ++i)
	{
		const float RY = Topo + i * RH;
		const bool bSel = i == GM->MenuIndice;
		if (bSel)
		{
			RetArred(X(L0), Y(RY + 1), (L1 - L0) * e, (RH - 3) * e, 6 * e, Cor255(21, 87, 214), Cor255(11, 38, 92));
			ContornoArred(X(L0), Y(RY + 1), (L1 - L0) * e, (RH - 3) * e, 6 * e, FMath::Max(1.f, 1.4f * e), Cor255(76, 149, 255));
		}
		else
		{
			RetArred(X(L0), Y(RY + 1), (L1 - L0) * e, (RH - 3) * e, 5 * e, Cor255(13, 23, 39, 235), Cor255(11, 19, 33, 235));
		}
		const float CY = RY + (RH - 2) * 0.5f;
		Icone(IconeItem[i], Pt(L0 + 32, CY), 11.5f * e, bSel ? Branco : Cor255(205, 218, 238));
		T(GM->NomeItem(i), X(L0 + 66), Y(RY + 3), 16.5f * e, TEXT("Regular"), Branco);
		T(GM->DescricaoItem(i), X(L0 + 66), Y(RY + 21.5f), 11.5f * e, TEXT("Regular"), bSel ? Cor255(170, 195, 235) : Cinza);

		const ETipoValor Tipo = GM->TipoItem(i);
		const FString Val = GM->ValorItem(i);
		const bool bTemSeta = Tipo != ETipoValor::Chave;
		if (bTemSeta)
		{
			const FLinearColor CS = Tipo == ETipoValor::Acao ? Apagado : Branco;
			Linha(Pt(L1 - 26, CY - 6), Pt(L1 - 20, CY), 1.8f * e, CS);
			Linha(Pt(L1 - 20, CY), Pt(L1 - 26, CY + 6), 1.8f * e, CS);
		}
		const float VY = CY - 11.f;
		switch (Tipo)
		{
		case ETipoValor::Nenhum: // Continuar: botão de play
		{
			RetArred(X(L1 - 150), Y(CY - 13), 92 * e, 26 * e, 13 * e, Cor255(40, 120, 255), Cor255(25, 90, 230));
			const FVector2D PC = Pt(L1 - 104, CY);
			Tri(PC + FVector2D(-6, -8) * e, PC + FVector2D(-6, 8) * e, PC + FVector2D(8, 0) * e, Branco);
			break;
		}
		case ETipoValor::Chave:
		{
			const bool bLig = GM->ChaveLigada(i);
			T(Val, X(L1 - 88), Y(VY), 16.5f * e, TEXT("Regular"), Branco, 2);
			const float SX0 = L1 - 72, SW = 44, SH = 22;
			RetArred(X(SX0), Y(CY - SH * 0.5f), SW * e, SH * e, SH * 0.5f * e,
				bLig ? Cor255(40, 125, 255) : Cor255(52, 62, 80),
				bLig ? Cor255(60, 145, 255) : Cor255(60, 70, 88));
			Disco(Pt(bLig ? SX0 + SW - SH * 0.5f : SX0 + SH * 0.5f, CY), (SH * 0.5f - 3) * e, Cor255(245, 249, 255), 16);
			break;
		}
		case ETipoValor::Acao:
			T(Val, X(L1 - 48), Y(VY), 16.5f * e, TEXT("Regular"), Cinza, 2);
			break;
		default:
			T(Val, X(L1 - 48), Y(VY), 16.5f * e, TEXT("Regular"), Branco, 2);
			break;
		}
		GM->AreaItens[i] = FBox2D(Pt(L0, RY), Pt(L1, RY + RH));
	}
	// barra de rolagem (tudo cabe, mas mantém o visual)
	Linha(Pt(1244, Topo + 4), Pt(1244, Base - 4), 3.f * e, Cor255(25, 38, 60));
	Linha(Pt(1244, Topo + 4), Pt(1244, Base - 60), 3.f * e, Cor255(60, 135, 255));

	// rodapé com os botões
	struct FDica { const TCHAR* Tecla; const TCHAR* Texto; };
	const FDica Dicas[] = {
		{ TEXT("↑↓"), TEXT("Selecionar") }, { TEXT("← →"), TEXT("Mudar") }, { TEXT("LB / RB"), TEXT("Categoria") },
		{ TEXT("B / Esc"), TEXT("Voltar") }, { TEXT("A / Enter"), TEXT("Confirmar") } };
	const FSlateFontInfo FT = Fonte(14 * e, TEXT("Bold"));
	const FSlateFontInfo FL = Fonte(15.5f * e, TEXT("Regular"));
	float Total = 0.f;
	for (const FDica& Dc : Dicas) Total += Medir(Dc.Tecla, FT).X + 16 * e + 8 * e + Medir(Dc.Texto, FL).X + 34 * e;
	float FX = W * 0.5f - Total * 0.5f;
	const float FY = Y(918);
	for (const FDica& Dc : Dicas)
	{
		const float TW = Medir(Dc.Tecla, FT).X;
		ContornoArred(FX, FY - 2 * e, TW + 16 * e, 26 * e, 4 * e, FMath::Max(1.f, 1.2f * e), Cor255(190, 205, 230, 220));
		T(Dc.Tecla, FX + 8 * e, FY + 2 * e, 14 * e, TEXT("Bold"), Branco);
		FX += TW + 16 * e + 8 * e;
		T(Dc.Texto, FX, FY + 1 * e, 15.5f * e, TEXT("Regular"), Cor255(220, 230, 250));
		FX += Medir(Dc.Texto, FL).X + 34 * e;
	}
}

// =====================================================================================
// OBJETIVO — cronômetro no alto, marca do próximo aro e painel de resultado
// =====================================================================================
void ADroneHUD::DesenharObjetivo(APredioGameMode* GM, const ADronePawn* D, float E)
{
	if (GM->Objetivo == EObjetivo::Livre) return;
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const bool bAros = GM->Objetivo == EObjetivo::ArosOrdem || GM->Objetivo == EObjetivo::ArosRelogio;
	const bool bFim = GM->Estado == EEstadoDesafio::Concluido || GM->Estado == EEstadoDesafio::Falhou;

	// marca do próximo aro (losango na tela; seta na borda quando ele está fora da vista)
	if (bAros && !bFim && GM->Aros.IsValidIndex(GM->ProximoAro))
	{
		const APlayerController* PC = GetOwningPlayerController();
		if (PC && PC->PlayerCameraManager)
		{
			const FVector Alvo = GM->Aros[GM->ProximoAro].GetLocation();
			const FVector CL = PC->PlayerCameraManager->GetCameraLocation();
			const FRotator CR = PC->PlayerCameraManager->GetCameraRotation();
			const FVector Local = CR.UnrotateVector(Alvo - CL);
			const float Metros = FVector::Dist(Alvo, D->GetActorLocation()) / 100.f;
			const FLinearColor Laranja = Cor255(255, 170, 40);
			bool bNaTela = false;
			if (Local.X > 20.f)
			{
				const FVector S = Project(Alvo);
				if (S.X > 40.f && S.X < W - 40.f && S.Y > 40.f && S.Y < H - 40.f)
				{
					bNaTela = true;
					const float R = 16.f * E;
					const FVector2D C(S.X, S.Y);
					Linha(C + FVector2D(0, -R), C + FVector2D(R, 0), 2.5f * E, Laranja);
					Linha(C + FVector2D(R, 0), C + FVector2D(0, R), 2.5f * E, Laranja);
					Linha(C + FVector2D(0, R), C + FVector2D(-R, 0), 2.5f * E, Laranja);
					Linha(C + FVector2D(-R, 0), C + FVector2D(0, -R), 2.5f * E, Laranja);
					T(FString::Printf(TEXT("%d  •  %.0f m"), GM->ProximoAro + 1, Metros), C.X, C.Y + R + 4.f * E, 16.f * E, TEXT("Bold"), Laranja, 1);
				}
			}
			if (!bNaTela)
			{
				FVector2D Dir(Local.Y, -Local.Z);
				if (Local.X <= 20.f && Dir.SizeSquared() < 1.f) Dir = FVector2D(0, 1); // bem atrás: aponta para baixo
				Dir.Normalize();
				const FVector2D Centro(W * 0.5f, H * 0.5f);
				const FVector2D Pt = Centro + FVector2D(Dir.X * W * 0.40f, Dir.Y * H * 0.38f);
				Seta(Pt - Dir * 30.f * E, Pt, 4.f * E, 16.f * E, Laranja);
				T(FString::Printf(TEXT("%.0f m"), Metros), Pt.X - Dir.X * 52.f * E, Pt.Y - Dir.Y * 52.f * E - 10.f * E, 15.f * E, TEXT("Bold"), Laranja, 1);
			}
		}
	}

	// painel do alto
	const float PW = 440.f * E, PH = 106.f * E;
	const float PX = W * 0.5f - PW * 0.5f, PY = 26.f * E;
	RetArred(PX, PY, PW, PH, 10.f * E, Cor255(6, 12, 24, 190), Cor255(10, 22, 42, 190));
	ContornoArred(PX, PY, PW, PH, 10.f * E, FMath::Max(1.f, 1.2f * E), Cor255(60, 120, 220, 170));
	FString Titulo = GM->NomeObjetivo(GM->Objetivo).ToUpper();
	if (bAros) Titulo += FString::Printf(TEXT("   AROS %d/%d"), FMath::Min(GM->ProximoAro, GM->Aros.Num()), GM->Aros.Num());
	T(Titulo, W * 0.5f, PY + 8.f * E, 15.f * E, TEXT("Bold"), AzulTexto, 1, 2.f * E);

	const bool bRelogio = GM->Objetivo == EObjetivo::ArosRelogio;
	const float Mostrar = bRelogio ? GM->TempoRestante : GM->TempoDesafio;
	FLinearColor CorTempo = Branco;
	if (bRelogio && GM->TempoRestante < 5.f && !bFim)
	{
		CorTempo = FMath::Frac(GM->TempoRestante * 2.f) > 0.5f ? Cor255(255, 80, 70) : Cor255(255, 190, 180);
	}
	T(GM->TextoTempo(Mostrar), W * 0.5f, PY + 28.f * E, 44.f * E, TEXT("Bold Italic"), CorTempo, 1);

	FString Rodape;
	FLinearColor CorRodape = Cinza;
	if (GM->Estado == EEstadoDesafio::Pronto)
	{
		Rodape = GM->Objetivo == EObjetivo::Topo ? TEXT("Decole para começar — a meta é a cobertura") : TEXT("Decole para começar — siga o losango laranja");
		CorRodape = AzulTexto;
	}
	else if (bRelogio && GM->TempoDesdeAro < 1.6f && GM->BonusUltimoAro > 0.f)
	{
		Rodape = FString::Printf(TEXT("+%.0f s"), GM->BonusUltimoAro);
		CorRodape = Cor255(110, 255, 140);
	}
	else if (!bRelogio)
	{
		Rodape = FString::Printf(TEXT("Ouro %s   •   Prata %s   •   Bronze %s"),
			*GM->TextoTempo(GM->LimiteMedalha(3), false), *GM->TextoTempo(GM->LimiteMedalha(2), false), *GM->TextoTempo(GM->LimiteMedalha(1), false));
	}
	else
	{
		Rodape = TEXT("Cada aro dá mais tempo");
	}
	T(Rodape, W * 0.5f, PY + 82.f * E, 14.f * E, TEXT("Regular"), CorRodape, 1);

	if (bFim) DesenharResultado(GM, E);
}

void ADroneHUD::DesenharResultado(APredioGameMode* GM, float E)
{
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const bool bOk = GM->Estado == EEstadoDesafio::Concluido;
	const FString Dica = TEXT("A / Enter: tentar de novo      Start / Esc: menu");
	if (GM->TempoNoResultado > 10.f)
	{
		// depois de um tempo o painel encolhe para não atrapalhar o voo livre
		T(Dica, W * 0.5f, 142.f * E, 16.f * E, TEXT("Regular"), AzulTexto, 1);
		return;
	}
	const float Entrada = FMath::Clamp(GM->TempoNoResultado * 4.f, 0.f, 1.f);
	const float PW = 600.f * E, PH = 330.f * E;
	const float PX = W * 0.5f - PW * 0.5f, PY = H * 0.5f - PH * 0.5f + (1.f - Entrada) * 40.f * E;
	RetArred(PX, PY, PW, PH, 14.f * E, Cor255(6, 12, 24, 235), Cor255(12, 26, 50, 235));
	ContornoArred(PX, PY, PW, PH, 14.f * E, FMath::Max(1.f, 1.6f * E), bOk ? Cor255(80, 160, 255) : Cor255(255, 90, 80));
	T(bOk ? TEXT("CONCLUÍDO!") : TEXT("TEMPO ESGOTADO"), W * 0.5f, PY + 18.f * E, 46.f * E, TEXT("Bold Italic"), bOk ? Branco : Cor255(255, 120, 110), 1);
	T(GM->NomeObjetivo(GM->Objetivo).ToUpper(), W * 0.5f, PY + 78.f * E, 15.f * E, TEXT("Italic"), AzulTexto, 1, 3.f * E);

	if (bOk)
	{
		T(GM->TextoTempo(GM->TempoDesafio), PX + 190.f * E, PY + 112.f * E, 54.f * E, TEXT("Bold Italic"), Branco, 1);
		T(TEXT("tempo"), PX + 190.f * E, PY + 180.f * E, 14.f * E, TEXT("Regular"), Cinza, 1);
		const FLinearColor CorMed = GM->Medalha == 3 ? Cor255(255, 196, 40) : (GM->Medalha == 2 ? Cor255(205, 215, 230) : (GM->Medalha == 1 ? Cor255(210, 130, 60) : Cor255(90, 100, 120)));
		const FVector2D CM(PX + 430.f * E, PY + 150.f * E);
		Disco(CM, 44.f * E, CorMed, 32);
		Arco(CM, 36.f * E, 2.f * E, Cor255(255, 255, 255, 120), 0.f, 360.f, 32);
		Icone(IcEstrela, CM, 22.f * E, Cor255(20, 24, 34));
		T(GM->NomeMedalha(GM->Medalha), CM.X, CM.Y + 52.f * E, 16.f * E, TEXT("Bold"), CorMed, 1);
		const FString Rec = GM->bNovoRecorde ? FString(TEXT("NOVO RECORDE!")) : FString::Printf(TEXT("Recorde: %s"), *GM->TextoTempo(GM->RecordeAtual()));
		T(Rec, W * 0.5f, PY + 236.f * E, 20.f * E, TEXT("Bold"), GM->bNovoRecorde ? Cor255(110, 255, 140) : AzulTexto, 1);
	}
	else
	{
		T(FString::Printf(TEXT("Você passou por %d de %d aros"), GM->ProximoAro, GM->Aros.Num()), W * 0.5f, PY + 140.f * E, 24.f * E, TEXT("Regular"), Branco, 1);
		T(TEXT("Dica: corte caminho entre os aros e não perca altura"), W * 0.5f, PY + 186.f * E, 16.f * E, TEXT("Regular"), Cinza, 1);
	}
	T(Dica, W * 0.5f, PY + PH - 44.f * E, 16.f * E, TEXT("Regular"), Cor255(220, 230, 250), 1);
}

// =====================================================================================
// MENU PRINCIPAL — jogo único: escolha do mapa (cartões) e do desafio (lista)
// =====================================================================================
void ADroneHUD::Ilustracao(int32 Cartao, float X, float Y, float W, float H, bool bSel)
{
	const float e = Esc;
	auto P = [&](float U, float V) { return FVector2D(X + U * W, Y + V * H); };
	const float A = bSel ? 1.f : 0.75f;
	auto C = [&](uint8 R, uint8 G, uint8 B, uint8 Al = 255) { return Cor255(R, G, B, (uint8)(Al * A)); };
	switch ((ECartaoMapa)Cartao)
	{
	case ECartaoMapa::Campo:
	{
		RetArred(X, Y, W, H, 6 * e, C(120, 175, 235), C(250, 205, 140));        // céu de fim de tarde
		Disco(P(0.80f, 0.30f), 18 * e, C(255, 236, 170), 24);                     // sol
		Tri(P(0.0f, 0.78f), P(0.28f, 0.52f), P(0.62f, 0.78f), C(122, 150, 84));   // morros
		Tri(P(0.40f, 0.78f), P(0.74f, 0.48f), P(1.0f, 0.78f), C(104, 132, 72));
		RetArred(X, Y + 0.76f * H, W, 0.24f * H, 2 * e, C(170, 120, 70), C(150, 104, 60)); // terra vermelha
		Linha(P(0.10f, 1.0f), P(0.46f, 0.77f), 5 * e, C(196, 150, 100));          // estradinha
		RetArred(X + 0.08f * W, Y + 0.62f * H, 0.16f * W, 0.14f * H, 2 * e, C(200, 110, 80), C(180, 96, 70)); // galpão
		for (int32 i = 0; i < 3; ++i)                                             // aros
		{
			const FVector2D CA = P(0.42f + i * 0.17f, 0.50f - i * 0.06f);
			Arco(CA, (16 - i * 3) * e, 3.f * e, C(255, 150, 30), 0.f, 360.f, 22);
		}
		Icone(IcDrone, P(0.24f, 0.30f), 9 * e, C(30, 36, 50));
		break;
	}
	case ECartaoMapa::Predio:
	{
		RetArred(X, Y, W, H, 6 * e, C(70, 110, 170), C(170, 195, 225));
		RetArred(X, Y + 0.88f * H, W, 0.12f * H, 2 * e, C(110, 100, 90), C(95, 88, 80));
		const float BX0 = 0.22f, BX1 = 0.72f;
		for (int32 k = 0; k <= 4; ++k)                                             // lajes
		{
			const float V = 0.88f - k * 0.17f;
			Linha(P(BX0 - 0.02f, V), P(BX1 + 0.02f, V), 4 * e, C(200, 200, 195));
		}
		for (int32 k = 0; k <= 4; ++k)                                             // pilares
		{
			const float U = FMath::Lerp(BX0, BX1, k / 4.f);
			Linha(P(U, 0.88f), P(U, 0.20f), 3 * e, C(185, 185, 180));
		}
		RetArred(X + 0.23f * W, Y + 0.72f * H, 0.24f * W, 0.16f * H, 1 * e, C(160, 90, 60), C(150, 84, 56)); // tijolos no térreo
		Linha(P(0.84f, 0.88f), P(0.84f, 0.08f), 3 * e, C(255, 196, 40));           // grua
		Linha(P(0.50f, 0.10f), P(0.98f, 0.10f), 3 * e, C(255, 196, 40));
		Linha(P(0.60f, 0.10f), P(0.60f, 0.30f), 1.5f * e, C(40, 40, 40));
		Icone(IcDrone, P(0.47f, 0.47f), 8 * e, C(255, 255, 255));
		break;
	}
	default:
	{
		RetArred(X, Y, W, H, 6 * e, C(40, 34, 40), C(110, 70, 50));               // céu de poeira
		RetArred(X + 0.12f * W, Y + 0.18f * H, 0.07f * W, 0.62f * H, 1 * e, C(60, 54, 52), C(50, 45, 44)); // chaminés
		RetArred(X + 0.26f * W, Y + 0.30f * H, 0.06f * W, 0.50f * H, 1 * e, C(60, 54, 52), C(50, 45, 44));
		for (int32 i = 0; i < 4; ++i)                                             // telhado em serra
		{
			const float U = 0.40f + i * 0.14f;
			Tri(P(U, 0.80f), P(U, 0.50f), P(U + 0.14f, 0.80f), C(72, 62, 58));
		}
		RetArred(X, Y + 0.80f * H, W, 0.20f * H, 2 * e, C(46, 40, 38), C(40, 35, 34));
		T(TEXT("?"), X + 0.5f * W, Y + 0.16f * H, 46 * e, TEXT("Bold Italic"), C(255, 170, 60, 200), 1);
		break;
	}
	}
}

void ADroneHUD::DesenharMenuPrincipal(APredioGameMode* GM)
{
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	Esc = FMath::Min(W * 0.92f / 1280.f, H * 0.94f / 960.f);
	const float OX = (W - 1280.f * Esc) * 0.5f;
	const float OY = (H - 960.f * Esc) * 0.5f;
	auto X = [&](float V) { return OX + V * Esc; };
	auto Y = [&](float V) { return OY + V * Esc; };
	auto Pt = [&](float A, float B) { return FVector2D(X(A), Y(B)); };
	const float e = Esc;
	const float Anim = FMath::Clamp(GM->MPRelogio * 2.5f, 0.f, 1.f);

	// voo de fundo escurecido (mais escuro embaixo, onde ficam os cartões)
	Caixa(0, 0, W, H, Cor255(2, 6, 14, 120));
	Caixa(0, H * 0.45f, W, H * 0.55f, Cor255(2, 6, 14, 90));
	if (GM->MPEscuro > 0.f) Caixa(0, 0, W, H, FLinearColor(0, 0, 0, GM->MPEscuro));

	// título
	Icone(IcDrone, Pt(96, 92), 30 * e, AzulClaro);
	Linha(Pt(150, 132), Pt(220, 132), 2.2f * e, Cor255(70, 140, 255, 220));
	T(TEXT("SIMULADOR DE DRONE"), X(146), Y(46), 62 * e, TEXT("Bold Italic"), Branco);
	T(TEXT("ESCOLHA O MAPA E O DESAFIO"), X(230), Y(122), 17 * e, TEXT("Italic"), AzulTexto, 0, 4.f * e);

	// cartões dos mapas
	struct FInfo { const TCHAR* Tag; const TCHAR* Nome; const TCHAR* Sub; };
	const FInfo Info[] = {
		{ TEXT("MAPA 1"), TEXT("CAMPO BAIANO"), TEXT("Fazenda com açude, galpão e circuito de aros") },
		{ TEXT("MAPA 2"), TEXT("PRÉDIO EM OBRA"), TEXT("Três andares em construção — voo por dentro") },
		{ TEXT("MAPA 3"), TEXT("USINA ABANDONADA"), TEXT("Siderúrgica desativada — entregas difíceis") },
	};
	const int32 NCart = (int32)ECartaoMapa::Total;
	GM->AreaCartoes.SetNum(NCart);
	const float CW = 370.f, CH = 262.f, CG = 15.f, CX0 = (1280.f - (NCart * CW + (NCart - 1) * CG)) * 0.5f, CY0 = 186.f;
	for (int32 c = 0; c < NCart; ++c)
	{
		const bool bSel = c == GM->MPCartao;
		const bool bDisp = GM->CartaoDisponivel(c);
		const float cx = CX0 + c * (CW + CG);
		const float cy = CY0 - (bSel ? 8.f : 0.f) + (1.f - Anim) * (30.f + c * 12.f);
		RetArred(X(cx), Y(cy), CW * e, CH * e, 10 * e, bSel ? Cor255(12, 30, 66, 245) : Cor255(8, 15, 28, 230), bSel ? Cor255(10, 22, 48, 245) : Cor255(8, 14, 26, 230));
		ContornoArred(X(cx), Y(cy), CW * e, CH * e, 10 * e, FMath::Max(1.f, (bSel ? 2.4f : 1.1f) * e), bSel ? Cor255(90, 160, 255) : Cor255(40, 64, 104, 200));
		Ilustracao(c, X(cx + 10), Y(cy + 10), (CW - 20) * e, 140 * e, bSel);
		// etiqueta
		const TCHAR* Tag = bDisp ? Info[c].Tag : TEXT("EM BREVE");
		const float TW = Medir(Tag, Fonte(12 * e, TEXT("Bold"))).X;
		RetArred(X(cx + 20), Y(cy + 20), TW + 18 * e, 22 * e, 11 * e, bDisp ? Cor255(30, 110, 250, 230) : Cor255(230, 130, 30, 235), bDisp ? Cor255(40, 125, 255, 230) : Cor255(240, 150, 40, 235));
		T(Tag, X(cx + 20) + 9 * e, Y(cy + 23), 12 * e, TEXT("Bold"), Branco);
		T(Info[c].Nome, X(cx + 20), Y(cy + 160), 27 * e, TEXT("Bold Italic"), bDisp ? Branco : Cinza);
		T(Info[c].Sub, X(cx + 20), Y(cy + 200), 13.5f * e, TEXT("Regular"), bSel ? Cor255(175, 200, 240) : Cinza);
		if (bSel)
		{
			Linha(Pt(cx + 20, cy + 232), Pt(cx + 90, cy + 232), 3 * e, Cor255(70, 140, 255));
		}
		GM->AreaCartoes[c] = FBox2D(Pt(cx, cy), Pt(cx + CW, cy + CH));
	}

	// lista: desafios do mapa escolhido + configurações + sair
	const int32 NL = GM->NumLinhasMP();
	const float L0 = CX0, L1 = 1280.f - CX0, LY0 = 476.f, LH = 58.f;
	GM->AreaLinhas.SetNum(NL);
	for (int32 l = 0; l < NL; ++l)
	{
		const float ly = LY0 + l * LH + (1.f - Anim) * 40.f;
		const bool bSel = l == GM->MPLinha;
		EObjetivo O = EObjetivo::Livre;
		const bool bObj = GM->LinhaEhObjetivo(l, O);
		const bool bBloq = bObj && !GM->CartaoDisponivel(GM->MPCartao);
		if (bSel)
		{
			RetArred(X(L0), Y(ly), (L1 - L0) * e, (LH - 6) * e, 7 * e, Cor255(21, 87, 214, 240), Cor255(11, 38, 92, 240));
			ContornoArred(X(L0), Y(ly), (L1 - L0) * e, (LH - 6) * e, 7 * e, FMath::Max(1.f, 1.4f * e), Cor255(76, 149, 255));
		}
		else
		{
			RetArred(X(L0), Y(ly), (L1 - L0) * e, (LH - 6) * e, 6 * e, Cor255(10, 18, 32, 215), Cor255(9, 16, 28, 215));
		}
		int32 Ic = IcEngrenagem;
		if (bObj) Ic = O == EObjetivo::Topo ? IcBandeira : (O == EObjetivo::ArosOrdem ? IcAro : (O == EObjetivo::ArosRelogio ? IcRelogio : IcOlho));
		else if (l == NL - 1) Ic = IcEnergia;
		const float CY = ly + (LH - 6) * 0.5f;
		Icone(Ic, Pt(L0 + 34, CY), 12 * e, bSel ? Branco : AzulTexto);
		T(GM->NomeLinhaMP(l), X(L0 + 70), Y(ly + 5), 19 * e, TEXT("Regular"), bBloq ? Cinza : Branco);
		T(GM->DescricaoLinhaMP(l), X(L0 + 70), Y(ly + 28), 12.5f * e, TEXT("Regular"), bSel ? Cor255(175, 200, 240) : Cinza);
		const FString Extra = GM->ExtraLinhaMP(l);
		if (!Extra.IsEmpty())
		{
			T(Extra, X(L1 - 54), Y(ly + 15), 15 * e, TEXT("Italic"), bBloq ? Cor255(240, 150, 60) : AzulTexto, 2);
		}
		if (bSel)
		{
			// botão de play na linha escolhida
			const FVector2D PC = Pt(L1 - 28, CY);
			Tri(PC + FVector2D(-6, -8) * e, PC + FVector2D(-6, 8) * e, PC + FVector2D(8, 0) * e, Branco);
		}
		GM->AreaLinhas[l] = FBox2D(Pt(L0, ly), Pt(L1, ly + LH - 6));
	}

	if (GM->MPAvisoT > 0.f && !GM->MPAviso.IsEmpty())
	{
		T(GM->MPAviso, W * 0.5f, Y(LY0 + NL * LH + 8), 17 * e, TEXT("Bold"), Cor255(255, 170, 70, (uint8)(255 * FMath::Clamp(GM->MPAvisoT, 0.f, 1.f))), 1);
	}

	// lema e rodapé
	T(TEXT("VOE • EXPLORE • DOMINE"), W * 0.5f, Y(868), 14 * e, TEXT("Italic"), Cor255(110, 140, 190), 1, 5.f * e);
	struct FDica { const TCHAR* Tecla; const TCHAR* Texto; };
	const FDica Dicas[] = {
		{ TEXT("← →"), TEXT("Mapa") }, { TEXT("↑↓"), TEXT("Desafio") }, { TEXT("A / Enter"), TEXT("Voar") },
		{ TEXT("Start"), TEXT("Configurações") }, { TEXT("B / Esc"), TEXT("Sair") } };
	const FSlateFontInfo FT = Fonte(14 * e, TEXT("Bold"));
	const FSlateFontInfo FL = Fonte(15.5f * e, TEXT("Regular"));
	float Total = 0.f;
	for (const FDica& Dc : Dicas) Total += Medir(Dc.Tecla, FT).X + 16 * e + 8 * e + Medir(Dc.Texto, FL).X + 34 * e;
	float FX = W * 0.5f - Total * 0.5f;
	const float FY = Y(912);
	for (const FDica& Dc : Dicas)
	{
		const float TW = Medir(Dc.Tecla, FT).X;
		ContornoArred(FX, FY - 2 * e, TW + 16 * e, 26 * e, 4 * e, FMath::Max(1.f, 1.2f * e), Cor255(190, 205, 230, 220));
		T(Dc.Tecla, FX + 8 * e, FY + 2 * e, 14 * e, TEXT("Bold"), Branco);
		FX += TW + 16 * e + 8 * e;
		T(Dc.Texto, FX, FY + 1 * e, 15.5f * e, TEXT("Regular"), Cor255(220, 230, 250));
		FX += Medir(Dc.Texto, FL).X + 34 * e;
	}

	if (GM->bCarregando)
	{
		Caixa(0, 0, W, H, FLinearColor(0, 0, 0, 0.85f));
		T(TEXT("CARREGANDO…"), W * 0.5f, H * 0.5f - 20 * e, 34 * e, TEXT("Bold Italic"), Branco, 1, 4.f * e);
	}
}
