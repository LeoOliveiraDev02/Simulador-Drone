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
#include "Engine/Texture2D.h"

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
		IcAcessib, IcChave, IcDocumento, IcMonitorSync, IcBandeira, IcAro, IcRelogio, IcCasa, IcPlay
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
	case IcPlay:
		Arco(C, 0.95f * S, E, Cor, 0.f, 360.f, 24);
		Tri(P(-0.3f, -0.45f), P(-0.3f, 0.45f), P(0.5f, 0.f), Cor);
		break;
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
	const ECategoriaMenu CatSel = (ECategoriaMenu)FMath::Clamp(GM->CategoriaSel, 0, NC - 1);
	GM->AreaCategorias.SetNum(NC);
	for (int32 c = 0; c < NC; ++c)
	{
		const float CY = 150.f + c * 64.f;
		const bool bSel = (ECategoriaMenu)c == CatSel;
		if (bSel)
		{
			// seção aberta: azul forte quando o foco está nela; mais apagada quando está mexendo nas opções
			const uint8 Al = GM->bFocoItens ? 150 : 255;
			RetArred(X(22), Y(CY), 250 * e, 56 * e, 7 * e, Cor255(26, 102, 232, Al), Cor255(14, 58, 150, Al));
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

	// tela da seção escolhida: título grande + só as opções dela
	GM->AreaItens.Init(FBox2D(ForceInit), (int32)EItemMenu::Total);
	const float L0 = 300.f, L1 = 1228.f;
	{
		const FVector2D CI = Pt(L0 + 26, 172);
		Icone(IconeCategoria[(int32)CatSel], CI, 18 * e, AzulClaro);
		T(APredioGameMode::NomeCategoria(CatSel), X(L0 + 58), Y(146), 38 * e, TEXT("Bold Italic"), Branco);
		T(APredioGameMode::DescricaoCategoria(CatSel), X(L0 + 60), Y(194), 15 * e, TEXT("Italic"), AzulTexto);
		Linha(Pt(L0, 226), Pt(L1, 226), FMath::Max(1.f, e), Cor255(40, 70, 120, 200));
	}
	const TArray<int32> Itens = APredioGameMode::ItensDaCategoria(CatSel);
	const float Topo = 244.f, RH = 76.f;
	for (int32 k = 0; k < Itens.Num(); ++k)
	{
		const int32 i = Itens[k];
		const float RY = Topo + k * RH;
		const bool bSel = GM->bFocoItens && i == GM->MenuIndice;
		if (bSel)
		{
			RetArred(X(L0), Y(RY + 2), (L1 - L0) * e, (RH - 8) * e, 7 * e, Cor255(21, 87, 214), Cor255(11, 38, 92));
			ContornoArred(X(L0), Y(RY + 2), (L1 - L0) * e, (RH - 8) * e, 7 * e, FMath::Max(1.f, 1.4f * e), Cor255(76, 149, 255));
		}
		else
		{
			RetArred(X(L0), Y(RY + 2), (L1 - L0) * e, (RH - 8) * e, 6 * e, Cor255(13, 23, 39, 235), Cor255(11, 19, 33, 235));
		}
		const float CY = RY + (RH - 4) * 0.5f;
		Icone(IconeItem[i], Pt(L0 + 36, CY), 14 * e, bSel ? Branco : Cor255(205, 218, 238));
		T(GM->NomeItem(i), X(L0 + 74), Y(RY + 12), 21 * e, TEXT("Regular"), Branco);
		T(GM->DescricaoItem(i), X(L0 + 74), Y(RY + 40), 13.5f * e, TEXT("Regular"), bSel ? Cor255(170, 195, 235) : Cinza);

		const ETipoValor Tipo = GM->TipoItem(i);
		const FString Val = GM->ValorItem(i);
		if (Tipo != ETipoValor::Chave)
		{
			const FLinearColor CS = Tipo == ETipoValor::Acao ? Apagado : Branco;
			Linha(Pt(L1 - 28, CY - 7), Pt(L1 - 21, CY), 2.f * e, CS);
			Linha(Pt(L1 - 21, CY), Pt(L1 - 28, CY + 7), 2.f * e, CS);
			if (Tipo == ETipoValor::Texto && bSel)
			{
				// setinha para a esquerda também: dá para mudar nos dois sentidos
				const float LV = Medir(Val, Fonte(19 * e, TEXT("Regular"))).X;
				const float XS = X(L1 - 52) - LV - 18 * e;
				Linha(FVector2D(XS + 7 * e, Y(CY - 7)), FVector2D(XS, Y(CY)), 2.f * e, Branco);
				Linha(FVector2D(XS, Y(CY)), FVector2D(XS + 7 * e, Y(CY + 7)), 2.f * e, Branco);
			}
		}
		const float VY = CY - 12.f;
		switch (Tipo)
		{
		case ETipoValor::Nenhum:
		{
			RetArred(X(L1 - 156), Y(CY - 15), 100 * e, 30 * e, 15 * e, Cor255(40, 120, 255), Cor255(25, 90, 230));
			const FVector2D PC = Pt(L1 - 106, CY);
			Tri(PC + FVector2D(-6, -9) * e, PC + FVector2D(-6, 9) * e, PC + FVector2D(9, 0) * e, Branco);
			break;
		}
		case ETipoValor::Chave:
		{
			const bool bLig = GM->ChaveLigada(i);
			T(Val, X(L1 - 92), Y(VY), 19 * e, TEXT("Regular"), Branco, 2);
			const float SX0 = L1 - 76, SW = 50, SH = 26;
			RetArred(X(SX0), Y(CY - SH * 0.5f), SW * e, SH * e, SH * 0.5f * e,
				bLig ? Cor255(40, 125, 255) : Cor255(52, 62, 80),
				bLig ? Cor255(60, 145, 255) : Cor255(60, 70, 88));
			Disco(Pt(bLig ? SX0 + SW - SH * 0.5f : SX0 + SH * 0.5f, CY), (SH * 0.5f - 3) * e, Cor255(245, 249, 255), 16);
			break;
		}
		case ETipoValor::Acao:
			T(Val, X(L1 - 52), Y(VY), 19 * e, TEXT("Regular"), Cinza, 2);
			break;
		default:
			T(Val, X(L1 - 52), Y(VY), 19 * e, TEXT("Bold"), Branco, 2);
			break;
		}
		GM->AreaItens[i] = FBox2D(Pt(L0, RY), Pt(L1, RY + RH - 4));
	}
	if (!GM->bFocoItens)
	{
		T(TEXT("A / Enter  ou  →  para abrir esta seção"), X((L0 + L1) * 0.5f), Y(Topo + Itens.Num() * RH + 18), 15 * e, TEXT("Italic"), Cor255(120, 150, 200), 1);
	}

	// rodapé com os botões
	struct FDica { const TCHAR* Tecla; const TCHAR* Texto; };
	const FDica Dicas[] = {
		{ TEXT("↑↓"), TEXT("Selecionar") }, { TEXT("← →"), TEXT("Mudar") }, { TEXT("LB / RB"), TEXT("Seção") },
		{ TEXT("B / Esc"), TEXT("Voltar") }, { TEXT("A / Enter"), TEXT("Abrir / Confirmar") } };
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
	const bool bFim = GM->Estado == EEstadoDesafio::Concluido || GM->Estado == EEstadoDesafio::Falhou;

	const APlayerController* PCm = GetOwningPlayerController();
	// marca de um alvo no mundo: losango na tela, ou seta na borda quando ele está fora da vista
	auto Marcar = [&](const FVector& Alvo, const FString& Rotulo, const FLinearColor& Cor, bool bSetaFora)
	{
		if (!PCm || !PCm->PlayerCameraManager) return;
		const FVector CL = PCm->PlayerCameraManager->GetCameraLocation();
		const FRotator CR = PCm->PlayerCameraManager->GetCameraRotation();
		const FVector Local = CR.UnrotateVector(Alvo - CL);
		const float Metros = FVector::Dist(Alvo, D->GetActorLocation()) / 100.f;
		if (Local.X > 20.f)
		{
			const FVector S = Project(Alvo);
			if (S.X > 40.f && S.X < W - 40.f && S.Y > 40.f && S.Y < H - 40.f)
			{
				const float R = 16.f * E;
				const FVector2D C(S.X, S.Y);
				Linha(C + FVector2D(0, -R), C + FVector2D(R, 0), 2.5f * E, Cor);
				Linha(C + FVector2D(R, 0), C + FVector2D(0, R), 2.5f * E, Cor);
				Linha(C + FVector2D(0, R), C + FVector2D(-R, 0), 2.5f * E, Cor);
				Linha(C + FVector2D(-R, 0), C + FVector2D(0, -R), 2.5f * E, Cor);
				T(FString::Printf(TEXT("%s  •  %.0f m"), *Rotulo, Metros), C.X, C.Y + R + 4.f * E, 15.f * E, TEXT("Bold"), Cor, 1);
				return;
			}
		}
		if (!bSetaFora) return;
		FVector2D Dir(Local.Y, -Local.Z);
		if (Local.X <= 20.f && Dir.SizeSquared() < 1.f) Dir = FVector2D(0, 1); // bem atrás: aponta para baixo
		Dir.Normalize();
		const FVector2D Centro(W * 0.5f, H * 0.5f);
		const FVector2D Pt = Centro + FVector2D(Dir.X * W * 0.40f, Dir.Y * H * 0.38f);
		Seta(Pt - Dir * 30.f * E, Pt, 4.f * E, 16.f * E, Cor);
		T(FString::Printf(TEXT("%.0f m"), Metros), Pt.X - Dir.X * 52.f * E, Pt.Y - Dir.Y * 52.f * E - 10.f * E, 15.f * E, TEXT("Bold"), Cor, 1);
	};
	const FLinearColor Laranja = Cor255(255, 170, 40);
	if (!bFim)
	{
		FVector Alvo;
		FString Rotulo;
		if (GM->AlvoPrincipal(Alvo, Rotulo)) Marcar(Alvo, Rotulo, Laranja, true);
		if (GM->Objetivo == EObjetivo::Fotos)
		{
			for (int32 i = 0; i < GM->PontosFoto.Num(); ++i)
			{
				if (!GM->FotoFeita[i]) Marcar(GM->PontosFoto[i], GM->NomesFoto[i], i == GM->FotoMirando ? Branco : Cor255(120, 200, 255), false);
			}
			// moldura da câmera + anel de carregamento enquanto mira
			const FVector2D C(W * 0.5f, H * 0.5f);
			const float Q = 70.f * E, Ql = 22.f * E;
			const FLinearColor CM = GM->FotoMirando != INDEX_NONE ? Branco : Cor255(255, 255, 255, 110);
			for (int32 k = 0; k < 4; ++k)
			{
				const float SX = (k & 1) ? 1.f : -1.f, SY = (k & 2) ? 1.f : -1.f;
				const FVector2D Cn = C + FVector2D(SX * Q, SY * Q * 0.7f);
				Linha(Cn, Cn - FVector2D(SX * Ql, 0), 2.f * E, CM);
				Linha(Cn, Cn - FVector2D(0, SY * Ql), 2.f * E, CM);
			}
			if (GM->FotoMirando != INDEX_NONE)
			{
				const float Fr = FMath::Clamp(GM->TempoMira / APredioGameMode::TempoParaFoto, 0.f, 1.f);
				Arco(C, 30.f * E, 4.f * E, Cor255(120, 200, 255), 90.f, 90.f - 360.f * Fr, 32);
			}
		}
		if (GM->Objetivo == EObjetivo::Entregas && GM->TempoParado > 0.f)
		{
			const float Fr = FMath::Clamp(GM->TempoParado / APredioGameMode::TempoParaSoltar, 0.f, 1.f);
			const FVector2D C(W * 0.5f, H * 0.5f + 70.f * E);
			RetArred(C.X - 120.f * E, C.Y, 240.f * E, 10.f * E, 5.f * E, Cor255(30, 42, 62), Cor255(30, 42, 62));
			RetArred(C.X - 120.f * E, C.Y, FMath::Max(10.f * E, 240.f * E * Fr), 10.f * E, 5.f * E, Laranja, Cor255(255, 210, 90));
			T(GM->bComCaixa ? TEXT("SOLTANDO A CAIXA…") : TEXT("PRENDENDO A CAIXA…"), C.X, C.Y + 14.f * E, 15.f * E, TEXT("Bold"), Branco, 1);
		}
		if (GM->Objetivo == EObjetivo::Pulverizar && GM->RocaNX > 0)
		{
			// mapinha da roça: células feitas em verde, o drone como ponto
			const float MW = 230.f * E;
			const float CelW = MW / GM->RocaNX;
			const float MH = CelW * GM->RocaNY;
			const float MX0 = W - MW - 30.f * E, MY0 = 150.f * E;
			RetArred(MX0 - 8 * E, MY0 - 30 * E, MW + 16 * E, MH + 40 * E, 8 * E, Cor255(6, 12, 24, 190), Cor255(10, 22, 42, 190));
			T(FString::Printf(TEXT("ROÇA  %d%%"), FMath::RoundToInt(GM->Cobertura() * 100.f)), MX0, MY0 - 26 * E, 14 * E, TEXT("Bold"), AzulTexto, 0, 2.f * E);
			// a roça no Unreal: X vai para a direita, Y (sul) para baixo
			for (int32 y = 0; y < GM->RocaNY; ++y)
			{
				for (int32 x = 0; x < GM->RocaNX; ++x)
				{
					const bool bFeita = GM->CelulaFeita[y * GM->RocaNX + x] != 0;
					Caixa(MX0 + x * CelW + 0.5f, MY0 + y * CelW + 0.5f, CelW - 1.f, CelW - 1.f, bFeita ? Cor255(70, 200, 90, 230) : Cor255(110, 80, 45, 200));
				}
			}
			const FVector P = D->GetActorLocation();
			const float U = (P.X - GM->Roca.Min.X) / GM->Roca.GetSize().X, V = (P.Y - GM->Roca.Min.Y) / GM->Roca.GetSize().Y;
			if (U > -0.2f && U < 1.2f && V > -0.2f && V < 1.2f)
			{
				const FVector2D DP(MX0 + FMath::Clamp(U, 0.f, 1.f) * MW, MY0 + FMath::Clamp(V, 0.f, 1.f) * MH);
				Disco(DP, 5.f * E, Branco, 12);
				const float Yaw = FMath::DegreesToRadians(D->GetActorRotation().Yaw);
				Linha(DP, DP + FVector2D(FMath::Cos(Yaw), FMath::Sin(Yaw)) * 12.f * E, 2.f * E, Branco);
			}
			const bool bSobre = GM->Roca.IsInside(FVector2D(P));
			if (GM->bPulverizando)
			{
				T(TEXT("PULVERIZANDO"), W * 0.5f, H * 0.5f + 80.f * E, 22.f * E, TEXT("Bold Italic"), Cor255(110, 255, 140), 1, 3.f * E);
			}
			else if (bSobre)
			{
				T(TEXT("ALTO DEMAIS — desça até 4 m do chão"), W * 0.5f, H * 0.5f + 80.f * E, 18.f * E, TEXT("Bold"), Cor255(255, 190, 90), 1);
			}
		}
	}
	if (GM->Flash > 0.f) Caixa(0, 0, W, H, FLinearColor(1, 1, 1, GM->Flash * 0.75f));

	// painel do alto
	const float PW = 440.f * E, PH = 106.f * E;
	const float PX = W * 0.5f - PW * 0.5f, PY = 26.f * E;
	RetArred(PX, PY, PW, PH, 10.f * E, Cor255(6, 12, 24, 190), Cor255(10, 22, 42, 190));
	ContornoArred(PX, PY, PW, PH, 10.f * E, FMath::Max(1.f, 1.2f * E), Cor255(60, 120, 220, 170));
	FString Titulo = GM->NomeObjetivo(GM->Objetivo).ToUpper();
	if (GM->Objetivo == EObjetivo::Pulverizar) Titulo += FString::Printf(TEXT("   %d%% / %d%%"), GM->Progresso(), GM->ProgressoTotal());
	else if (GM->ProgressoTotal() > 0) Titulo += FString::Printf(TEXT("   %d/%d"), GM->Progresso(), GM->ProgressoTotal());
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
	else if (GM->Objetivo == EObjetivo::Entregas)
	{
		Rodape = GM->bComCaixa ? FString::Printf(TEXT("Leve a caixa para: %s"), GM->NomesEntrega.IsValidIndex(GM->EntregaAtual) ? *GM->NomesEntrega[GM->EntregaAtual] : TEXT("o destino"))
			: FString(TEXT("Pegue a caixa na plataforma do galpão (pare em cima dela)"));
		CorRodape = AzulTexto;
	}
	else if (GM->Objetivo == EObjetivo::Ferraduras && GM->DistFerradura < 1e8f)
	{
		const float Dm = GM->DistFerradura;
		Rodape = FString::Printf(TEXT("%s  —  a mais perto está a %.0f m"), Dm < 15.f ? TEXT("QUENTE!") : (Dm < 45.f ? TEXT("morno") : TEXT("frio")), Dm);
		CorRodape = Dm < 15.f ? Cor255(255, 120, 80) : (Dm < 45.f ? Cor255(255, 200, 90) : Cor255(140, 190, 255));
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
		Disco(P(0.86f, 0.24f), 16 * e, C(255, 236, 170), 24);                     // sol
		Tri(P(0.0f, 0.70f), P(0.30f, 0.50f), P(0.64f, 0.70f), C(122, 150, 84));   // morros
		Tri(P(0.42f, 0.70f), P(0.76f, 0.46f), P(1.0f, 0.70f), C(104, 132, 72));
		RetArred(X, Y + 0.68f * H, W, 0.32f * H, 2 * e, C(118, 150, 70), C(100, 132, 60)); // pasto
		for (int32 k = 0; k < 7; ++k)                                              // milharal em fileiras
		{
			const float U = 0.62f + k * 0.055f;
			Linha(P(U, 0.98f), P(U + 0.03f, 0.74f), 4 * e, C(70, 120, 40));
		}
		// casa com telhado vermelho
		RetArred(X + 0.08f * W, Y + 0.62f * H, 0.22f * W, 0.14f * H, 1 * e, C(235, 225, 205), C(220, 210, 190));
		Tri(P(0.06f, 0.63f), P(0.19f, 0.52f), P(0.32f, 0.63f), C(190, 80, 50));
		RetArred(X + 0.17f * W, Y + 0.68f * H, 0.04f * W, 0.08f * H, 1 * e, C(110, 70, 40), C(110, 70, 40));
		// caixa d'água azul na torre
		Linha(P(0.42f, 0.74f), P(0.44f, 0.46f), 2 * e, C(90, 90, 95));
		Linha(P(0.50f, 0.74f), P(0.48f, 0.46f), 2 * e, C(90, 90, 95));
		RetArred(X + 0.415f * W, Y + 0.36f * H, 0.09f * W, 0.11f * H, 3 * e, C(30, 90, 190), C(20, 70, 160));
		// cata-vento
		Linha(P(0.55f, 0.72f), P(0.57f, 0.40f), 2 * e, C(80, 80, 85));
		Linha(P(0.59f, 0.72f), P(0.57f, 0.40f), 2 * e, C(80, 80, 85));
		Arco(P(0.57f, 0.38f), 11 * e, 2.2f * e, C(200, 200, 205), 0.f, 360.f, 18);
		for (int32 k = 0; k < 6; ++k)
		{
			const float a = FMath::DegreesToRadians(k * 30.f);
			Linha(P(0.57f, 0.38f) + FVector2D(FMath::Cos(a), FMath::Sin(a)) * 11.f * e, P(0.57f, 0.38f) - FVector2D(FMath::Cos(a), FMath::Sin(a)) * 11.f * e, 1.5f * e, C(200, 200, 205));
		}
		Icone(IcDrone, P(0.30f, 0.26f), 9 * e, C(30, 36, 50));
		Disco(P(0.78f, 0.58f), 4 * e, C(255, 200, 40), 10);                       // ferradura dourada (brilho)
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

void ADroneHUD::Imagem(UTexture2D* Tex, float X, float Y, float W, float H, const FLinearColor& Cor)
{
	if (!Tex || !Tex->GetResource()) return;
	FCanvasTileItem Tile(FVector2D(X, Y), Tex->GetResource(), FVector2D(W, H), Cor);
	Tile.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Tile);
}

void ADroneHUD::Cadeado(FVector2D C, float S, const FLinearColor& Cor)
{
	Arco(C + FVector2D(0, -0.15f * S), 0.42f * S, 0.16f * S, Cor, 0.f, 180.f, 16);
	Linha(C + FVector2D(-0.42f * S, -0.15f * S), C + FVector2D(-0.42f * S, 0.1f * S), 0.16f * S, Cor);
	Linha(C + FVector2D(0.42f * S, -0.15f * S), C + FVector2D(0.42f * S, 0.1f * S), 0.16f * S, Cor);
	RetArred(C.X - 0.62f * S, C.Y + 0.05f * S, 1.24f * S, 0.95f * S, 0.12f * S, Cor, Cor);
	Disco(C + FVector2D(0, 0.45f * S), 0.12f * S, Cor255(20, 24, 34), 12);
}

static FLinearColor CorMedalha(int32 M)
{
	return M >= 3 ? Cor255(255, 196, 40) : (M == 2 ? Cor255(205, 215, 230) : (M == 1 ? Cor255(210, 130, 60) : Cor255(60, 72, 92)));
}

void ADroneHUD::DesenharMenuPrincipal(APredioGameMode* GM)
{
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	Esc = FMath::Min(W * 0.96f / 1280.f, H * 0.96f / 960.f);
	const float OX = (W - 1280.f * Esc) * 0.5f;
	const float OY = (H - 960.f * Esc) * 0.5f;
	auto X = [&](float V) { return OX + V * Esc; };
	auto Y = [&](float V) { return OY + V * Esc; };
	auto Pt = [&](float A, float B) { return FVector2D(X(A), Y(B)); };
	const float e = Esc;
	const float TT = GM->MPTelaDesde;
	auto Entrada = [TT](float Atraso) { const float t = FMath::Clamp((TT - Atraso) * 3.f, 0.f, 1.f); return 1.f - (1.f - t) * (1.f - t) * (1.f - t); };
	if (!ImgUsina && !bTentouUsina)
	{
		bTentouUsina = true;
		ImgUsina = LoadObject<UTexture2D>(nullptr, TEXT("/Game/UI/T_Usina.T_Usina"));
	}
	const int32 NCart = (int32)ECartaoMapa::Total;

	// faixas de cinema + escurecido da esquerda (onde fica o texto)
	const bool bTitulo = GM->TelaMP == ETelaMP::Titulo;
	if (bTitulo)
	{
		RetArred(0, 0, W * 0.62f, H, 0.f, Cor255(2, 6, 14, 215), Cor255(2, 6, 14, 0));
	}
	else
	{
		Caixa(0, 0, W, H, Cor255(2, 6, 14, 165));
	}
	Caixa(0, 0, W, H * 0.06f, Cor255(0, 0, 0, 200));
	Caixa(0, H * 0.94f, W, H * 0.06f, Cor255(0, 0, 0, 200));
	if (GM->MPEscuro > 0.f) Caixa(0, 0, W, H, FLinearColor(0, 0, 0, GM->MPEscuro));

	// rodapé com as teclas (muda conforme a tela)
	struct FDicaMP { const TCHAR* Key; const TCHAR* Value; };
	auto Rodape = [&](std::initializer_list<FDicaMP> Dicas)
	{
		const FSlateFontInfo FT = Fonte(14 * e, TEXT("Bold"));
		const FSlateFontInfo FL = Fonte(15.5f * e, TEXT("Regular"));
		float Total = 0.f;
		for (const auto& Dc : Dicas) Total += Medir(Dc.Key, FT).X + 24 * e + Medir(Dc.Value, FL).X + 34 * e;
		float FX = W - 40 * e - Total;
		const float FY = H * 0.97f - 13 * e;
		for (const auto& Dc : Dicas)
		{
			const float TW = Medir(Dc.Key, FT).X;
			ContornoArred(FX, FY - 2 * e, TW + 16 * e, 26 * e, 4 * e, FMath::Max(1.f, 1.2f * e), Cor255(190, 205, 230, 220));
			T(Dc.Key, FX + 8 * e, FY + 2 * e, 14 * e, TEXT("Bold"), Branco);
			FX += TW + 24 * e;
			T(Dc.Value, FX, FY + 1 * e, 15.5f * e, TEXT("Regular"), Cor255(220, 230, 250));
			FX += Medir(Dc.Value, FL).X + 34 * e;
		}
	};
	auto BotaoVoltar = [&]()
	{
		const float BX = 40 * e, BY = H * 0.97f - 15 * e;
		ContornoArred(BX, BY, 150 * e, 30 * e, 15 * e, FMath::Max(1.f, 1.3f * e), Cor255(120, 160, 230));
		Linha(FVector2D(BX + 22 * e, BY + 15 * e), FVector2D(BX + 32 * e, BY + 7 * e), 2.f * e, Branco);
		Linha(FVector2D(BX + 22 * e, BY + 15 * e), FVector2D(BX + 32 * e, BY + 23 * e), 2.f * e, Branco);
		T(TEXT("VOLTAR"), BX + 44 * e, BY + 5 * e, 16 * e, TEXT("Bold"), Branco, 0, 2.f * e);
		GM->AreaVoltarMP = FBox2D(FVector2D(BX, BY), FVector2D(BX + 150 * e, BY + 30 * e));
	};
	auto Barra = [&](float BX, float BY, float BW, float BH, float P, const FLinearColor& Cor)
	{
		RetArred(BX, BY, BW, BH, BH * 0.5f, Cor255(30, 42, 62), Cor255(30, 42, 62));
		if (P > 0.f) RetArred(BX, BY, FMath::Max(BH, BW * P), BH, BH * 0.5f, Cor, Cor255(120, 200, 255));
	};

	// ======================================================================= ABERTURA
	if (bTitulo)
	{
		GM->AreaVoltarMP = FBox2D(ForceInit);
		const float A1 = Entrada(0.1f), A2 = Entrada(0.35f), A3 = Entrada(0.6f);
		// mini drone com hélices girando ao lado do título
		{
			const FVector2D C = Pt(104 - (1.f - A1) * 60.f, 196);
			const float Ang = GM->MPRelogio * 1440.f;
			for (int32 k = 0; k < 4; ++k)
			{
				const FVector2D Off(((k & 1) ? 1.f : -1.f) * 22.f * e, ((k & 2) ? 1.f : -1.f) * 22.f * e);
				Linha(C, C + Off, 4.f * e, Cor255(220, 232, 255, (uint8)(255 * A1)));
				const FVector2D R = C + Off;
				Arco(R, 13.f * e, 1.2f * e, Cor255(120, 170, 255, (uint8)(180 * A1)), 0.f, 360.f, 18);
				const float a = FMath::DegreesToRadians(Ang + k * 45.f);
				const FVector2D Pa(FMath::Cos(a) * 12.f * e, FMath::Sin(a) * 12.f * e);
				Linha(R - Pa, R + Pa, 2.4f * e, Cor255(255, 255, 255, (uint8)(230 * A1)));
			}
			RetArred(C.X - 10 * e, C.Y - 8 * e, 20 * e, 16 * e, 4 * e, Cor255(40, 120, 255), Cor255(30, 90, 220));
		}
		T(TEXT("SIMULADOR"), X(150 - (1.f - A1) * 80.f), Y(150), 92 * e, TEXT("Bold Italic"), Cor255(255, 255, 255, (uint8)(255 * A1)));
		T(TEXT("DE DRONE"), X(150 - (1.f - A2) * 80.f), Y(244), 92 * e, TEXT("Bold Italic"), Cor255(94, 160, 255, (uint8)(255 * A2)));
		Linha(Pt(154, 362), Pt(154 + 300 * A3, 362), 2.4f * e, Cor255(70, 140, 255, 220));
		T(TEXT("VOE  •  EXPLORE  •  DOMINE"), X(156), Y(376), 17 * e, TEXT("Italic"), Cor255(160, 190, 235, (uint8)(255 * A3)), 0, 5.f * e);

		const TCHAR* Itens[] = { TEXT("JOGAR"), TEXT("CONFIGURAÇÕES"), TEXT("SAIR") };
		const TCHAR* Subs[] = { TEXT("Escolha o mapa e o desafio"), TEXT("Controle, vídeo (AMD FSR 4), áudio..."), TEXT("Fecha o simulador") };
		const int32 Icones[] = { IcPlay, IcEngrenagem, IcEnergia };
		GM->AreaTitulo.SetNum(3);
		for (int32 i = 0; i < 3; ++i)
		{
			const float Ai = Entrada(0.7f + i * 0.12f);
			const float BY = 500.f + i * 92.f;
			const float BX = 150.f - (1.f - Ai) * 60.f;
			const bool bSel = GM->MPTitulo == i;
			const float Pulso = bSel ? 0.5f + 0.5f * FMath::Sin(GM->MPRelogio * 4.f) : 0.f;
			if (bSel)
			{
				RetArred(X(BX), Y(BY), 470 * e, 76 * e, 10 * e, Cor255(26, 102, 232, (uint8)(235 * Ai)), Cor255(14, 40, 100, (uint8)(60 * Ai)));
				ContornoArred(X(BX), Y(BY), 470 * e, 76 * e, 10 * e, FMath::Max(1.f, 1.6f * e), Cor255(110, 175, 255, (uint8)(160 + 95 * Pulso)));
				Linha(Pt(BX + 440, BY + 28), Pt(BX + 450, BY + 38), 2.6f * e, Branco);
				Linha(Pt(BX + 450, BY + 38), Pt(BX + 440, BY + 48), 2.6f * e, Branco);
			}
			const FLinearColor Cor = bSel ? Branco : Cor255(170, 190, 225, (uint8)(255 * Ai));
			Icone(Icones[i], Pt(BX + 40, BY + 38), 16 * e, Cor);
			T(Itens[i], X(BX + 78), Y(BY + 9), (bSel ? 32.f : 28.f) * e, bSel ? TEXT("Bold Italic") : TEXT("Italic"), Cor);
			T(Subs[i], X(BX + 80), Y(BY + 47), 13.5f * e, TEXT("Regular"), bSel ? Cor255(190, 210, 245) : Cor255(110, 130, 165, (uint8)(255 * Ai)));
			GM->AreaTitulo[i] = FBox2D(Pt(BX, BY), Pt(BX + 470, BY + 76));
		}

		// canto de cima à direita: progresso geral
		{
			float Soma = 0.f;
			for (int32 c = 0; c < NCart; ++c) Soma += GM->ProgressoMapa(c);
			const float P = Soma / 2.f; // só os mapas liberados contam
			const float PX = W - 330 * e, PY = H * 0.06f + 26 * e;
			T(TEXT("PROGRESSO GERAL"), PX, PY, 14 * e, TEXT("Bold"), AzulTexto, 0, 2.5f * e);
			T(FString::Printf(TEXT("%d%%"), FMath::RoundToInt(P * 100.f)), W - 40 * e, PY - 6 * e, 30 * e, TEXT("Bold Italic"), Branco, 2);
			Barra(PX, PY + 34 * e, 290 * e, 8 * e, P, Cor255(40, 125, 255));
		}
		T(TEXT("Unreal Engine 5.8  •  AMD FSR 4 + gerador de quadros"), 40 * e, H * 0.97f - 10 * e, 13.5f * e, TEXT("Regular"), Cor255(120, 140, 175));
		Rodape({ { TEXT("↑↓"), TEXT("Escolher") }, { TEXT("A / Enter"), TEXT("Confirmar") } });
	}

	// ======================================================================= MAPAS
	else if (GM->TelaMP == ETelaMP::Mapas)
	{
		T(TEXT("ESCOLHA O MAPA"), X(40), Y(66), 54 * e, TEXT("Bold Italic"), Branco);
		T(TEXT("Mapas 1 e 2 liberados  •  o mapa 3 está em construção"), X(44), Y(130), 16 * e, TEXT("Italic"), AzulTexto, 0, 1.5f * e);

		// cantinho do progresso (em cima, à direita)
		{
			const float PX = 870.f, PY = 50.f, PW = 370.f;
			RetArred(X(PX), Y(PY), PW * e, 112 * e, 8 * e, Cor255(8, 16, 30, 220), Cor255(10, 22, 42, 220));
			T(TEXT("SEU PROGRESSO"), X(PX + 16), Y(PY + 10), 13 * e, TEXT("Bold"), AzulTexto, 0, 2.5f * e);
			for (int32 c = 0; c < NCart; ++c)
			{
				const float LY = PY + 34 + c * 25;
				const bool bLib = GM->CartaoDisponivel(c);
				T(FString::Printf(TEXT("%d  %s"), c + 1, *APredioGameMode::NomeMapa(c)), X(PX + 16), Y(LY), 14 * e, TEXT("Regular"), bLib ? Branco : Cinza);
				if (bLib)
				{
					const float P = GM->ProgressoMapa(c);
					Barra(X(PX + 210), Y(LY + 7), 100 * e, 6 * e, P, Cor255(40, 125, 255));
					T(FString::Printf(TEXT("%d%%"), FMath::RoundToInt(P * 100.f)), X(PX + PW - 14), Y(LY), 14 * e, TEXT("Bold"), Branco, 2);
				}
				else
				{
					Cadeado(Pt(PX + PW - 26, LY + 8), 9 * e, Cinza);
				}
			}
		}

		const TCHAR* Subs[] = { TEXT("Entregas, pulverização, fotos e ferraduras"), TEXT("Três andares em construção — voo por dentro"), TEXT("Siderúrgica desativada — entregas difíceis") };
		const float CW = 392.f, CH = 520.f, CG = 18.f, CX0 = (1280.f - (NCart * CW + (NCart - 1) * CG)) * 0.5f, CY0 = 200.f;
		GM->AreaCartoes.SetNum(NCart);
		for (int32 c = 0; c < NCart; ++c)
		{
			const float Ac = Entrada(0.05f + c * 0.1f);
			const bool bSel = c == GM->MPCartao;
			const bool bLib = GM->CartaoDisponivel(c);
			const float cx = CX0 + c * (CW + CG);
			const float cy = CY0 - (bSel ? 10.f : 0.f) + (1.f - Ac) * 50.f;
			RetArred(X(cx), Y(cy), CW * e, CH * e, 12 * e, bSel ? Cor255(12, 30, 66, 245) : Cor255(8, 15, 28, 230), bSel ? Cor255(10, 22, 48, 245) : Cor255(8, 14, 26, 230));
			ContornoArred(X(cx), Y(cy), CW * e, CH * e, 12 * e, FMath::Max(1.f, (bSel ? 2.6f : 1.1f) * e), bSel ? Cor255(90, 160, 255) : Cor255(40, 64, 104, 200));
			// figura do mapa (a usina usa a imagem renderizada)
			const float IX = X(cx + 12), IY = Y(cy + 12), IW = (CW - 24) * e, IHt = 230 * e;
			if ((ECartaoMapa)c == ECartaoMapa::Usina && ImgUsina)
			{
				Imagem(ImgUsina, IX, IY, IW, IHt, bSel ? FLinearColor(0.85f, 0.85f, 0.85f, 1) : FLinearColor(0.5f, 0.5f, 0.5f, 1));
			}
			else
			{
				Ilustracao(c, IX, IY, IW, IHt, bSel);
			}
			if (!bLib)
			{
				Caixa(IX, IY, IW, IHt, Cor255(0, 0, 0, 110));
				Cadeado(FVector2D(IX + IW * 0.5f, IY + IHt * 0.42f), 34 * e, Cor255(255, 190, 70));
				RetArred(IX + IW * 0.5f - 105 * e, IY + IHt * 0.7f, 210 * e, 34 * e, 17 * e, Cor255(230, 130, 30, 235), Cor255(240, 150, 40, 235));
				T(TEXT("EM CONSTRUÇÃO"), IX + IW * 0.5f, IY + IHt * 0.7f + 7 * e, 16 * e, TEXT("Bold"), Branco, 1, 2.f * e);
			}
			// etiqueta MAPA N
			const FString Tag = FString::Printf(TEXT("MAPA %d"), c + 1);
			const float TW = Medir(Tag, Fonte(13 * e, TEXT("Bold"))).X;
			RetArred(X(cx + 24), Y(cy + 24), TW + 20 * e, 24 * e, 12 * e, bLib ? Cor255(30, 110, 250, 235) : Cor255(70, 76, 90, 235), bLib ? Cor255(40, 125, 255, 235) : Cor255(80, 86, 100, 235));
			T(Tag, X(cx + 24) + 10 * e, Y(cy + 28), 13 * e, TEXT("Bold"), Branco);

			T(APredioGameMode::NomeMapa(c), X(cx + 24), Y(cy + 262), 30 * e, TEXT("Bold Italic"), bLib ? Branco : Cinza);
			T(Subs[c], X(cx + 24), Y(cy + 306), 14 * e, TEXT("Regular"), bSel ? Cor255(175, 200, 240) : Cinza);
			Linha(Pt(cx + 24, cy + 342), Pt(cx + CW - 24, cy + 342), FMath::Max(1.f, e), Cor255(40, 64, 104, 200));
			if (bLib)
			{
				// progresso do mapa: barra + medalhas de cada desafio
				int32 Poss = 0;
				const int32 Tem = GM->MedalhasMapa(c, Poss);
				const float P = Poss ? (float)Tem / Poss : 0.f;
				T(TEXT("PROGRESSO"), X(cx + 24), Y(cy + 358), 13 * e, TEXT("Bold"), AzulTexto, 0, 2.f * e);
				T(FString::Printf(TEXT("%d%%"), FMath::RoundToInt(P * 100.f)), X(cx + CW - 24), Y(cy + 352), 22 * e, TEXT("Bold Italic"), Branco, 2);
				Barra(X(cx + 24), Y(cy + 386), (CW - 48) * e, 8 * e, P, Cor255(40, 125, 255));
				float MX = cx + 36;
				int32 NComMedalha = 0, NDesafios = 0;
				for (const EObjetivo O : APredioGameMode::ObjetivosDoCartao((ECartaoMapa)c))
				{
					if (O == EObjetivo::Livre) continue;
					const int32 Md = GM->MedalhaDe(O);
					++NDesafios;
					if (Md > 0) ++NComMedalha;
					Disco(Pt(MX, cy + 428), 12 * e, CorMedalha(Md), 20);
					if (Md > 0) Icone(IcEstrela, Pt(MX, cy + 428), 6.5f * e, Cor255(20, 24, 34));
					if (APredioGameMode::ObjetivosDoCartao((ECartaoMapa)c).Num() <= 3)
					{
						T(APredioGameMode::NomeObjetivo(O), X(MX + 20), Y(cy + 419), 14 * e, TEXT("Regular"), Cor255(205, 218, 238));
						MX += 30 + Medir(APredioGameMode::NomeObjetivo(O), Fonte(14 * e, TEXT("Regular"))).X / e + 18;
					}
					else
					{
						MX += 34;  // muitos desafios: só as medalhas
					}
				}
				T(FString::Printf(TEXT("%d de %d desafios com medalha"), NComMedalha, NDesafios), X(cx + 24), Y(cy + 458), 13 * e, TEXT("Italic"), Cinza);
				if (bSel)
				{
					RetArred(X(cx + CW - 150), Y(cy + CH - 52), 126 * e, 34 * e, 17 * e, Cor255(40, 120, 255), Cor255(25, 90, 230));
					T(TEXT("ABRIR"), X(cx + CW - 100), Y(cy + CH - 45), 16 * e, TEXT("Bold"), Branco, 1, 2.f * e);
					Tri(Pt(cx + CW - 56, cy + CH - 43), Pt(cx + CW - 56, cy + CH - 27), Pt(cx + CW - 44, cy + CH - 35), Branco);
				}
			}
			else
			{
				T(TEXT("Em breve: missões de pegar e entregar cargas"), X(cx + 24), Y(cy + 360), 14 * e, TEXT("Italic"), Cor255(240, 160, 70));
				T(TEXT("em pontes rolantes, esteiras e no alto-forno."), X(cx + 24), Y(cy + 382), 14 * e, TEXT("Italic"), Cor255(240, 160, 70));
			}
			GM->AreaCartoes[c] = FBox2D(Pt(cx, cy), Pt(cx + CW, cy + CH));
		}
		if (GM->MPAvisoT > 0.f && !GM->MPAviso.IsEmpty())
		{
			T(GM->MPAviso, W * 0.5f, Y(CY0 + CH + 20), 18 * e, TEXT("Bold"), Cor255(255, 170, 70, (uint8)(255 * FMath::Clamp(GM->MPAvisoT, 0.f, 1.f))), 1);
		}
		BotaoVoltar();
		Rodape({ { TEXT("← →"), TEXT("Mapa") }, { TEXT("A / Enter"), TEXT("Abrir") }, { TEXT("B / Esc"), TEXT("Voltar") } });
	}

	// ======================================================================= DESAFIOS DO MAPA
	else
	{
		const int32 c = GM->MPCartao;
		const float A1 = Entrada(0.f);
		T(FString::Printf(TEXT("MAPA %d"), c + 1), X(40), Y(64), 16 * e, TEXT("Bold"), AzulTexto, 0, 3.f * e);
		T(APredioGameMode::NomeMapa(c), X(40 - (1.f - A1) * 40.f), Y(84), 52 * e, TEXT("Bold Italic"), Branco);
		Ilustracao(c, X(40), Y(170), 470 * e, 270 * e, true);
		ContornoArred(X(40), Y(170), 470 * e, 270 * e, 6 * e, FMath::Max(1.f, 1.2f * e), Cor255(60, 110, 200));
		const float P = GM->ProgressoMapa(c);
		T(TEXT("PROGRESSO DO MAPA"), X(40), Y(462), 13 * e, TEXT("Bold"), AzulTexto, 0, 2.f * e);
		T(FString::Printf(TEXT("%d%%"), FMath::RoundToInt(P * 100.f)), X(510), Y(456), 22 * e, TEXT("Bold Italic"), Branco, 2);
		Barra(X(40), Y(490), 470 * e, 8 * e, P, Cor255(40, 125, 255));
		T(TEXT("Medalhas: ouro, prata e bronze por tempo."), X(40), Y(516), 14 * e, TEXT("Italic"), Cinza);
		T(TEXT("Voo livre: explore o mapa sem cronômetro."), X(40), Y(538), 14 * e, TEXT("Italic"), Cinza);

		const int32 NL = GM->NumLinhasMP();
		const float L0 = 560.f, L1 = 1240.f, LY0 = 170.f, LH = FMath::Min(86.f, 690.f / FMath::Max(1, NL));
		GM->AreaLinhas.SetNum(NL);
		for (int32 l = 0; l < NL; ++l)
		{
			const float Al = Entrada(0.1f + l * 0.08f);
			const float ly = LY0 + l * LH + (1.f - Al) * 40.f;
			const bool bSel = l == GM->MPLinha;
			EObjetivo O = EObjetivo::Livre;
			const bool bObj = GM->LinhaEhObjetivo(l, O);
			if (bSel)
			{
				RetArred(X(L0), Y(ly), (L1 - L0) * e, (LH - 10) * e, 8 * e, Cor255(21, 87, 214, 240), Cor255(11, 38, 92, 240));
				ContornoArred(X(L0), Y(ly), (L1 - L0) * e, (LH - 10) * e, 8 * e, FMath::Max(1.f, 1.4f * e), Cor255(76, 149, 255));
			}
			else
			{
				RetArred(X(L0), Y(ly), (L1 - L0) * e, (LH - 10) * e, 7 * e, Cor255(10, 18, 32, 220), Cor255(9, 16, 28, 220));
			}
			const float CY = ly + (LH - 10) * 0.5f;
			int32 Ic = IcRecarregar;
			if (bObj)
			{
				switch (O)
				{
				case EObjetivo::Topo: Ic = IcBandeira; break;
				case EObjetivo::ArosOrdem: Ic = IcAro; break;
				case EObjetivo::ArosRelogio: Ic = IcRelogio; break;
				case EObjetivo::Entregas: Ic = IcCasa; break;
				case EObjetivo::Pulverizar: Ic = IcSliders; break;
				case EObjetivo::Fotos: Ic = IcMonitor; break;
				case EObjetivo::Ferraduras: Ic = IcEstrela; break;
				default: Ic = IcOlho; break;
				}
			}
			Icone(Ic, Pt(L0 + 38, CY), 15 * e, bSel ? Branco : AzulTexto);
			T(GM->NomeLinhaMP(l), X(L0 + 78), Y(ly + 12), 23 * e, bObj ? TEXT("Regular") : TEXT("Italic"), Branco);
			T(GM->DescricaoLinhaMP(l), X(L0 + 78), Y(ly + 44), 13.5f * e, TEXT("Regular"), bSel ? Cor255(175, 200, 240) : Cinza);
			if (bObj && O != EObjetivo::Livre)
			{
				const int32 Md = GM->MedalhaDe(O);
				Disco(Pt(L1 - 40, CY), 15 * e, CorMedalha(Md), 22);
				if (Md > 0) Icone(IcEstrela, Pt(L1 - 40, CY), 8 * e, Cor255(20, 24, 34));
				T(GM->ExtraLinhaMP(l), X(L1 - 66), Y(CY - 10), 15 * e, TEXT("Italic"), AzulTexto, 2);
			}
			else if (bObj)
			{
				T(GM->ExtraLinhaMP(l), X(L1 - 30), Y(CY - 10), 15 * e, TEXT("Italic"), AzulTexto, 2);
			}
			GM->AreaLinhas[l] = FBox2D(Pt(L0, ly), Pt(L1, ly + LH - 10));
		}
		BotaoVoltar();
		Rodape({ { TEXT("↑↓"), TEXT("Desafio") }, { TEXT("A / Enter"), TEXT("Voar") }, { TEXT("B / Esc"), TEXT("Voltar") } });
	}

	if (GM->bCarregando)
	{
		Caixa(0, 0, W, H, FLinearColor(0, 0, 0, 0.88f));
		T(TEXT("CARREGANDO…"), W * 0.5f, H * 0.5f - 20 * e, 34 * e, TEXT("Bold Italic"), Branco, 1, 4.f * e);
	}
}
