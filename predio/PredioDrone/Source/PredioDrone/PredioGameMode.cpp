#include "PredioGameMode.h"
#include "PredioDrone.h"
#include "DronePawn.h"
#include "DroneHUD.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerStart.h"
#include "Components/PrimitiveComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/LightComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/App.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformFileManager.h"
#include "UnrealClient.h"
#include "RHI.h"
#include "RenderCore.h"
#include "Kismet/KismetSystemLibrary.h"
#if WITH_EDITOR
#include "ShaderCompiler.h"
#endif

namespace
{
	IConsoleVariable* CVar(const TCHAR* Nome)
	{
		return IConsoleManager::Get().FindConsoleVariable(Nome);
	}
	void SetInt(const TCHAR* Nome, int32 V)
	{
		if (IConsoleVariable* C = CVar(Nome)) C->Set(V, ECVF_SetByConsole);
	}
	int32 GetInt(const TCHAR* Nome, int32 Padrao = 0)
	{
		if (IConsoleVariable* C = CVar(Nome)) return C->GetInt();
		return Padrao;
	}
	const TCHAR* NomesModo[] = { TEXT("AA Nativo"), TEXT("Qualidade"), TEXT("Equilibrado"), TEXT("Desempenho"), TEXT("Ultra Desempenho") };
}

APredioGameMode::APredioGameMode()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostPhysics;
	DefaultPawnClass = ADronePawn::StaticClass();
	HUDClass = ADroneHUD::StaticClass();
}

FString APredioGameMode::NomeModoFSR()
{
	const int32 M = FMath::Clamp(GetInt(TEXT("r.FidelityFX.FSR.QualityMode"), 1), 0, 4);
	return NomesModo[M];
}

bool APredioGameMode::FSRLigado()   { return GetInt(TEXT("r.FidelityFX.FSR.Enabled"), 0) != 0; }
bool APredioGameMode::GeradorLigado() { return GetInt(TEXT("r.FidelityFX.FI.Enabled"), 0) != 0; }

FString APredioGameMode::TextoAndar(int32 Andar)
{
	if (Andar <= 0) return TEXT("TÉRREO");
	return FString::Printf(TEXT("%dº ANDAR"), Andar);
}

ADronePawn* APredioGameMode::Drone() const
{
	const UWorld* W = GetWorld();
	if (!W) return nullptr;
	const APlayerController* PC = W->GetFirstPlayerController();
	return PC ? Cast<ADronePawn>(PC->GetPawn()) : nullptr;
}

void APredioGameMode::BeginPlay()
{
	Super::BeginPlay();

	// tecnologias AMD ligadas por padrão (também ficam no DefaultEngine.ini)
	SetInt(TEXT("r.FidelityFX.FSR.Enabled"), 1);
	SetInt(TEXT("r.FidelityFX.FI.Enabled"), 1);

	if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
	{
		FInputModeGameOnly Modo;
		PC->SetInputMode(Modo);
		PC->bShowMouseCursor = false;
	}

	ColetarAtores();
	AtualizarAndares(true);

	bTour = FParse::Param(FCommandLine::Get(), TEXT("tour"));
	if (!FParse::Value(FCommandLine::Get(), TEXT("pastatestes="), PastaTestes))
	{
		PastaTestes = FPaths::ProjectSavedDir() / TEXT("Testes");
	}
	if (bTour)
	{
		bAjusteAuto = false;
		NivelAjuste = 0;
		AplicarNivelAjuste();
		if (ADronePawn* D = Drone()) D->bModoTour = true;
		TourPontos.Reset();
		TourFotoNoPonto.Reset();
		if (ADronePawn* D = Drone()) { TourPontos.Add(D->GetActorLocation()); TourFotoNoPonto.Add(1); }
		for (const FPortal& P : Portais)
		{
			if (P.Ator.IsValid())
			{
				const FVector C = P.Ator->GetActorLocation();
				const FVector F = P.Ator->GetActorForwardVector();
				TourPontos.Add(C - F * 120.f);
				TourFotoNoPonto.Add(1);
				TourPontos.Add(C + F * 120.f);
				TourFotoNoPonto.Add(0);
			}
		}
		IPlatformFile& PF = FPlatformFileManager::Get().GetPlatformFile();
		PF.CreateDirectoryTree(*PastaTestes);
		TourLinhas.Add(FString::Printf(TEXT("TOUR %s  resolução da tela: %dx%d"), *FDateTime::Now().ToString(),
			GEngine && GEngine->GameViewport ? (int32)GEngine->GameViewport->Viewport->GetSizeXY().X : 0,
			GEngine && GEngine->GameViewport ? (int32)GEngine->GameViewport->Viewport->GetSizeXY().Y : 0));
		TourEspera = 3.0f; // deixa os shaders/streaming assentarem
	}
	UE_LOG(LogPredio, Log, TEXT("Predio: %d andares, %d portais, %d conexoes, tour=%d"), NumAndares, TotalPortais, Conexoes.Num(), bTour ? 1 : 0);
}

void APredioGameMode::ColetarAtores()
{
	Grupos.Reset();
	Conexoes.Reset();
	Portais.Reset();
	int32 MaiorAndar = 0;

	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		AActor* A = *It;
		for (const FName& Tag : A->Tags)
		{
			const FString T = Tag.ToString();
			if (T.StartsWith(TEXT("Andar")) || T.StartsWith(TEXT("Laje")))
			{
				Grupos.FindOrAdd(Tag).Atores.Add(A);
				if (T.StartsWith(TEXT("Andar")))
				{
					MaiorAndar = FMath::Max(MaiorAndar, FCString::Atoi(*T.RightChop(5)));
				}
			}
			else if (T.StartsWith(TEXT("Conexao_")))
			{
				FConexao C;
				C.AndarDeBaixo = FCString::Atoi(*T.RightChop(8));
				C.Posicao = A->GetActorLocation();
				Conexoes.Add(C);
			}
			else if (T.StartsWith(TEXT("Portal_")))
			{
				FPortal P;
				P.Ator = A;
				P.Numero = FCString::Atoi(*T.RightChop(7));
				TArray<UStaticMeshComponent*> Comps;
				A->GetComponents(Comps);
				for (UStaticMeshComponent* SM : Comps)
				{
					for (int32 i = 0; i < SM->GetNumMaterials(); ++i)
					{
						if (UMaterialInstanceDynamic* MID = SM->CreateAndSetMaterialInstanceDynamic(i))
						{
							P.Materiais.Add(MID);
						}
					}
				}
				Portais.Add(P);
			}
			else if (T.StartsWith(TEXT("AlturaAndar_")))
			{
				AlturaAndar = FCString::Atof(*T.RightChop(12));
			}
			else if (T.StartsWith(TEXT("CotaTerreo_")))
			{
				CotaTerreo = FCString::Atof(*T.RightChop(11));
			}
		}
	}
	Portais.Sort([](const FPortal& A, const FPortal& B) { return A.Numero < B.Numero; });
	TotalPortais = Portais.Num();
	NumAndares = MaiorAndar + 1;
	ProximoPortal = 1;
}

void APredioGameMode::AtualizarAndares(bool bForcar)
{
	const ADronePawn* D = Drone();
	if (!D) return;
	const FVector P = D->GetActorLocation();

	const float Rel = (P.Z - CotaTerreo) / AlturaAndar;
	AndarAtual = FMath::Clamp(FMath::FloorToInt(Rel + 0.02f), 0, NumAndares - 1);
	const float Frac = Rel - AndarAtual;

	// andares que devem aparecer
	TSet<int32> Visiveis;
	Visiveis.Add(AndarAtual);
	// atravessando a laje (dentro do buraco/poço): mostra os dois lados
	if (Frac < 0.18f && AndarAtual > 0) Visiveis.Add(AndarAtual - 1);
	if (Frac > 0.80f && AndarAtual < NumAndares - 1) Visiveis.Add(AndarAtual + 1);
	// perto de uma ligação vertical (poço do elevador, escada, buraco)
	for (const FConexao& C : Conexoes)
	{
		const float Dist2D = FVector::Dist2D(C.Posicao, P);
		if (Dist2D > C.Raio) continue;
		if (C.AndarDeBaixo == AndarAtual) Visiveis.Add(AndarAtual + 1);
		if (C.AndarDeBaixo + 1 == AndarAtual) Visiveis.Add(AndarAtual - 1);
	}

	for (TPair<FName, FGrupoVisivel>& Par : Grupos)
	{
		const FString Nome = Par.Key.ToString();
		bool bVer = false;
		if (Nome.StartsWith(TEXT("Andar")))
		{
			bVer = Visiveis.Contains(FCString::Atoi(*Nome.RightChop(5)));
		}
		else // LajeK = piso do andar K e teto do andar K-1
		{
			const int32 K = FCString::Atoi(*Nome.RightChop(4));
			bVer = Visiveis.Contains(K) || Visiveis.Contains(K - 1);
		}
		if (bForcar || bVer != Par.Value.bVisivel)
		{
			Par.Value.bVisivel = bVer;
			for (const TWeakObjectPtr<AActor>& A : Par.Value.Atores)
			{
				if (!A.IsValid()) continue;
				A->SetActorHiddenInGame(!bVer);
				// luzes do andar apagam junto (economiza sombra e iluminação)
				TArray<ULightComponent*> Luzes;
				A->GetComponents(Luzes);
				for (ULightComponent* L : Luzes) L->SetVisibility(bVer);
			}
		}
	}
}

void APredioGameMode::AtualizarPortais()
{
	ADronePawn* D = Drone();
	if (!D || Portais.Num() == 0) return;

	if (bCronometroLigado) Cronometro += GetWorld()->GetDeltaSeconds();

	const int32 Idx = ProximoPortal - 1;
	if (!Portais.IsValidIndex(Idx)) return;
	FPortal& P = Portais[Idx];
	if (!P.Ator.IsValid()) return;

	const FVector C = P.Ator->GetActorLocation();
	const FVector F = P.Ator->GetActorForwardVector();
	const FVector Rel = D->GetActorLocation() - C;
	const float AoLongo = FVector::DotProduct(Rel, F);
	const float Lateral = (Rel - F * AoLongo).Size();
	const float RaioPortal = 92.f * P.Ator->GetActorScale3D().Y; // aro de 92 cm na escala 1
	if (FMath::Abs(AoLongo) < 35.f && Lateral < RaioPortal * 0.95f)
	{
		P.bPassou = true;
		for (UMaterialInstanceDynamic* M : P.Materiais)
		{
			if (M) M->SetVectorParameterValue(TEXT("Cor"), FLinearColor(0.1f, 1.f, 0.25f));
		}
		D->UltimoCheckpoint = FTransform(F.Rotation(), C + F * 80.f);
		if (ProximoPortal == 1)
		{
			bCronometroLigado = true;
			Cronometro = 0.f;
		}
		if (ProximoPortal >= TotalPortais)
		{
			bCronometroLigado = false;
			if (MelhorTempo <= 0.f || Cronometro < MelhorTempo) MelhorTempo = Cronometro;
			D->MostrarMensagem(FString::Printf(TEXT("PERCURSO COMPLETO!  %.2f s"), Cronometro), 6.f);
			ProximoPortal = 1;
			for (FPortal& Q : Portais)
			{
				Q.bPassou = false;
				for (UMaterialInstanceDynamic* M : Q.Materiais)
				{
					if (M) M->SetVectorParameterValue(TEXT("Cor"), FLinearColor(1.f, 0.35f, 0.02f));
				}
			}
		}
		else
		{
			D->MostrarMensagem(FString::Printf(TEXT("PORTAL %d/%d"), ProximoPortal, TotalPortais), 1.2f);
			++ProximoPortal;
		}
	}
}

void APredioGameMode::TeclasAtalho()
{
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	ADronePawn* D = Drone();
	if (!PC || !D) return;

	if (PC->WasInputKeyJustPressed(EKeys::F1) || PC->WasInputKeyJustPressed(EKeys::Gamepad_Special_Right))
	{
		bMostrarAjuda = !bMostrarAjuda;
	}
	if (PC->WasInputKeyJustPressed(EKeys::F2))
	{
		int32 M = GetInt(TEXT("r.FidelityFX.FSR.QualityMode"), 1);
		M = (M + 1) % 4;
		SetInt(TEXT("r.FidelityFX.FSR.QualityMode"), M);
		bAjusteAuto = false;
		D->MostrarMensagem(FString::Printf(TEXT("FSR 4: %s  (ajuste automático desligado — F6 liga)"), NomesModo[M]));
	}
	if (PC->WasInputKeyJustPressed(EKeys::F3))
	{
		const bool bNovo = !GeradorLigado();
		SetInt(TEXT("r.FidelityFX.FI.Enabled"), bNovo ? 1 : 0);
		D->MostrarMensagem(bNovo ? TEXT("Gerador de quadros AMD LIGADO") : TEXT("Gerador de quadros AMD desligado"));
	}
	if (PC->WasInputKeyJustPressed(EKeys::F4))
	{
		const bool bNovo = !FSRLigado();
		SetInt(TEXT("r.FidelityFX.FSR.Enabled"), bNovo ? 1 : 0);
		D->MostrarMensagem(bNovo ? TEXT("FSR 4 (IA) LIGADO") : TEXT("FSR desligado — usando o TSR do Unreal para comparar"));
	}
	if (PC->WasInputKeyJustPressed(EKeys::F5))
	{
		bMostrarDesempenho = !bMostrarDesempenho;
	}
	if (PC->WasInputKeyJustPressed(EKeys::F6))
	{
		bAjusteAuto = !bAjusteAuto;
		D->MostrarMensagem(bAjusteAuto ? TEXT("Ajuste automático para 60 FPS LIGADO") : TEXT("Ajuste automático desligado"));
	}
	if (PC->WasInputKeyJustPressed(EKeys::Escape) || PC->WasInputKeyJustPressed(EKeys::Gamepad_Special_Left))
	{
		if (TempoAteSair > 0.f)
		{
			UKismetSystemLibrary::QuitGame(this, PC, EQuitPreference::Quit, false);
		}
		else
		{
			TempoAteSair = 2.5f;
			D->MostrarMensagem(TEXT("Aperte Esc (ou Back) de novo para sair"), 2.5f);
		}
	}
	if (TempoAteSair > 0.f) TempoAteSair -= GetWorld()->GetDeltaSeconds();
}

void APredioGameMode::AplicarNivelAjuste()
{
	// 0: FSR Qualidade + Lumen com ray tracing de hardware (máximo)
	// 1: FSR Equilibrado
	// 2: FSR Desempenho
	// 3: + Lumen por software
	// 4: + sombras e névoa um pouco mais leves
	const int32 N = FMath::Clamp(NivelAjuste, 0, 4);
	SetInt(TEXT("r.FidelityFX.FSR.QualityMode"), N == 0 ? 1 : (N == 1 ? 2 : 3));
	SetInt(TEXT("r.Lumen.HardwareRayTracing"), N >= 3 ? 0 : 1);
	SetInt(TEXT("r.Shadow.Virtual.ResolutionLodBiasDirectional"), N >= 4 ? 1 : -1);
	SetInt(TEXT("r.VolumetricFog.GridPixelSize"), N >= 4 ? 16 : 8);
}

void APredioGameMode::AjusteAutomatico(float Dt)
{
	if (!bAjusteAuto || bTour) return;
	if (FPSBase < 57.f) { AcumBaixo += Dt; AcumAlto = 0.f; }
	else if (FPSBase > 88.f) { AcumAlto += Dt; AcumBaixo = 0.f; }
	else { AcumBaixo = FMath::Max(0.f, AcumBaixo - Dt); AcumAlto = FMath::Max(0.f, AcumAlto - Dt); }

	ADronePawn* D = Drone();
	if (AcumBaixo > 4.f && NivelAjuste < 4)
	{
		++NivelAjuste;
		AplicarNivelAjuste();
		AcumBaixo = 0.f;
		if (D) D->MostrarMensagem(FString::Printf(TEXT("Mantendo 60 FPS: FSR 4 %s"), *NomeModoFSR()), 2.f);
	}
	else if (AcumAlto > 12.f && NivelAjuste > 0)
	{
		--NivelAjuste;
		AplicarNivelAjuste();
		AcumAlto = 0.f;
	}
}

void APredioGameMode::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	const float DtReal = FApp::GetDeltaTime(); // tempo do quadro de verdade (sem os quadros gerados)
	SuavDt = FMath::Lerp(SuavDt, (float)DtReal, 0.05f);
	FPSBase = SuavDt > 0.f ? 1.f / SuavDt : 0.f;
	MsGPU = FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles(0));
	MsJogo = FPlatformTime::ToMilliseconds(GGameThreadTime);

	AtualizarAndares(false);
	if (bTour)
	{
		TickTour(DeltaSeconds);
		return;
	}
	AtualizarPortais();
	TeclasAtalho();
	AjusteAutomatico(DeltaSeconds);
}

void APredioGameMode::TickTour(float Dt)
{
	ADronePawn* D = Drone();
	if (!D || TourPontos.Num() < 2) return;

#if WITH_EDITOR
	// no editor (-game) os shaders compilam na hora: espera terminar antes de medir/fotografar
	if (GShaderCompilingManager && GShaderCompilingManager->GetNumRemainingJobs() > 0)
	{
		TourEspera = FMath::Max(TourEspera, 4.f);
		return;
	}
#endif
	if (TourEspera > 0.f)
	{
		TourEspera -= Dt;
		return;
	}
	TourFrames.Add(FApp::GetDeltaTime() * 1000.f);

	const int32 N = TourPontos.Num();
	const int32 I = FMath::Clamp(FMath::FloorToInt(TourS), 0, N - 2);
	const float T = TourS - I;
	const FVector P0 = TourPontos[FMath::Max(I - 1, 0)];
	const FVector P1 = TourPontos[I];
	const FVector P2 = TourPontos[I + 1];
	const FVector P3 = TourPontos[FMath::Min(I + 2, N - 1)];
	auto CR = [](const FVector& A, const FVector& B, const FVector& C, const FVector& E, float t)
	{
		const float t2 = t * t, t3 = t2 * t;
		return 0.5f * ((2.f * B) + (-A + C) * t + (2.f * A - 5.f * B + 4.f * C - E) * t2 + (-A + 3.f * B - 3.f * C + E) * t3);
	};
	const FVector Pos = CR(P0, P1, P2, P3, T);
	const FVector Pos2 = CR(P0, P1, P2, P3, FMath::Min(T + 0.05f, 1.f));
	FVector Dir = (Pos2 - Pos);
	if (Dir.IsNearlyZero()) Dir = (P2 - P1);
	FRotator Rot = Dir.Rotation();
	Rot.Pitch = FMath::Clamp(Rot.Pitch * 0.6f, -35.f, 35.f);
	D->SetActorLocationAndRotation(Pos, Rot);

	// foto ao chegar em cada ponto marcado
	if (I != UltimoPontoFoto && TourFotoNoPonto.IsValidIndex(I) && TourFotoNoPonto[I] == 1 && T < 0.05f)
	{
		UltimoPontoFoto = I;
		const FString Arq = FString::Printf(TEXT("%s/tour_%02d_andar%d.png"), *PastaTestes, TourFotos, AndarAtual);
		FScreenshotRequest::RequestScreenshot(Arq, false, false);
		TourLinhas.Add(FString::Printf(TEXT("foto %02d andar %d  FPS base %.1f  GPU %.2f ms  FSR %s  FG %d"),
			TourFotos, AndarAtual, FPSBase, MsGPU, *NomeModoFSR(), GeradorLigado() ? 1 : 0));
		++TourFotos;
		TourEspera = 0.6f;
	}

	const float Comprimento = FMath::Max(50.f, FVector::Dist(P1, P2));
	TourS += Dt * 260.f / Comprimento; // ~2,6 m/s
	if (TourS >= N - 1)
	{
		SalvarResultadoTour();
		FPlatformMisc::RequestExit(false);
		bTour = false;
	}
}

void APredioGameMode::SalvarResultadoTour()
{
	TArray<float> F = TourFrames;
	F.Sort();
	float Soma = 0.f;
	for (float V : F) Soma += V;
	const float Media = F.Num() ? Soma / F.Num() : 0.f;
	const float P99 = F.Num() ? F[FMath::Clamp(FMath::FloorToInt(F.Num() * 0.99f), 0, F.Num() - 1)] : 0.f;
	TourLinhas.Add(FString::Printf(TEXT("QUADROS %d  media %.2f ms (%.1f FPS base)  pior 1%% %.2f ms (%.1f FPS)"),
		F.Num(), Media, Media > 0 ? 1000.f / Media : 0.f, P99, P99 > 0 ? 1000.f / P99 : 0.f));
	FFileHelper::SaveStringArrayToFile(TourLinhas, *(PastaTestes / TEXT("tour_resultado.txt")));
}
