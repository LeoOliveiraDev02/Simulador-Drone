#include "PredioGameMode.h"
#include "PredioDrone.h"
#include "DronePawn.h"
#include "DroneHUD.h"
#include "AjustesDrone.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "GameFramework/PlayerController.h"
#include "Components/LightComponent.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"
#include "Misc/App.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformFileManager.h"
#include "UnrealClient.h"
#include "RHI.h"
#include "RenderCore.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Kismet/GameplayStatics.h"
#include "Components/AudioComponent.h"
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
	PrimaryActorTick.bTickEvenWhenPaused = true; // o menu funciona com o jogo pausado
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

	FAjustesDrone& Cfg = FAjustesDrone::Get();
	Cfg.AplicarGraficos();

	if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
	{
		FInputModeGameOnly Modo;
		PC->SetInputMode(Modo);
		PC->bShowMouseCursor = false;
	}

	ColetarAtores();
	AtualizarAndares(true);

	// Limites de voo (cm, eixos do Unreal: X = x do Blender, Y = -y). O drone fica DENTRO do prédio:
	// as fachadas ficam em x = 0,15 / 23,85 e y = 0,15 / 15,85 m (blocos de 14 cm); o centro do drone
	// para 45 cm para dentro delas, em todos os andares (no 2º as paredes são baixas e no 3º/cobertura
	// não há parede — o limite segura do mesmo jeito). Teto: 15,9 m (a tela vai até 16,6 m).
	LimitesVoo = FBox(FVector(45.f, -1555.f, -500.f), FVector(2355.f, -45.f, 1590.f));
	if (ADronePawn* D = Drone())
	{
		D->Limites = LimitesVoo;
		D->bUsarLimites = true;
	}

	bTour = FParse::Param(FCommandLine::Get(), TEXT("tour"));
	if (!FParse::Value(FCommandLine::Get(), TEXT("pastatestes="), PastaTestes))
	{
		PastaTestes = FPaths::ProjectSavedDir() / TEXT("Testes");
	}
	if (bTour)
	{
		NivelAjuste = 0;
		SetInt(TEXT("r.FidelityFX.FSR.QualityMode"), 1);
		SetInt(TEXT("r.FidelityFX.FI.Enabled"), 1);
		SetInt(TEXT("r.VSync"), 0);
		SetInt(TEXT("r.Lumen.HardwareRayTracing"), 1);
		if (ADronePawn* D = Drone()) D->bModoTour = true;
		TourPontos.Reset();
		TourFotoNoPonto.Reset();
		if (ADronePawn* D = Drone()) { TourPontos.Add(D->GetActorLocation()); TourFotoNoPonto.Add(1); }
		for (const TPair<int32, FTransform>& R : Rota)
		{
			const FVector C = R.Value.GetLocation();
			const FVector F = R.Value.GetRotation().GetForwardVector();
			TourPontos.Add(C - F * 120.f);
			TourFotoNoPonto.Add(1);
			TourPontos.Add(C + F * 120.f);
			TourFotoNoPonto.Add(0);
		}
		IPlatformFile& PF = FPlatformFileManager::Get().GetPlatformFile();
		PF.CreateDirectoryTree(*PastaTestes);
		TourLinhas.Add(FString::Printf(TEXT("TOUR %s  resolução da tela: %dx%d"), *FDateTime::Now().ToString(),
			GEngine && GEngine->GameViewport ? (int32)GEngine->GameViewport->Viewport->GetSizeXY().X : 0,
			GEngine && GEngine->GameViewport ? (int32)GEngine->GameViewport->Viewport->GetSizeXY().Y : 0));
		TourEspera = 3.0f;
	}
	else
	{
		AplicarNivelAjuste();
	}
	UE_LOG(LogPredio, Log, TEXT("Predio: %d andares, %d pontos de rota, %d conexoes, tour=%d, ajustes em %s"),
		NumAndares, Rota.Num(), Conexoes.Num(), bTour ? 1 : 0, *FAjustesDrone::Arquivo());
}

void APredioGameMode::ColetarAtores()
{
	Grupos.Reset();
	Conexoes.Reset();
	Rota.Reset();
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
			else if (T.StartsWith(TEXT("Rota_")))
			{
				Rota.Add(TPair<int32, FTransform>(FCString::Atoi(*T.RightChop(5)), A->GetActorTransform()));
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
	Rota.Sort([](const TPair<int32, FTransform>& A, const TPair<int32, FTransform>& B) { return A.Key < B.Key; });
	NumAndares = MaiorAndar + 1;
}

void APredioGameMode::AtualizarAndares(bool bForcar)
{
	const ADronePawn* D = Drone();
	if (!D) return;
	const FVector P = D->GetActorLocation();

	const float Rel = (P.Z - CotaTerreo) / AlturaAndar;
	AndarAtual = FMath::Clamp(FMath::FloorToInt(Rel + 0.02f), 0, NumAndares - 1);
	const float Frac = Rel - AndarAtual;

	TSet<int32> Visiveis;
	Visiveis.Add(AndarAtual);
	// na cobertura (último andar) o andar de baixo fica sempre desenhado: dá para ver pelos buracos
	if (AndarAtual == NumAndares - 1 && AndarAtual > 0) Visiveis.Add(AndarAtual - 1);
	if (Frac < 0.25f && AndarAtual > 0) Visiveis.Add(AndarAtual - 1);
	if (Frac > 0.70f && AndarAtual < NumAndares - 1) Visiveis.Add(AndarAtual + 1);
	// perto de uma ligação vertical (poço do elevador, escada, buraco): o vizinho
	// já está desenhado antes de dar para enxergar por ela
	for (const FConexao& C : Conexoes)
	{
		if (FVector::Dist2D(C.Posicao, P) > C.Raio) continue;
		if (C.AndarDeBaixo == AndarAtual) Visiveis.Add(AndarAtual + 1);
		if (C.AndarDeBaixo + 1 == AndarAtual) Visiveis.Add(AndarAtual - 1);
	}

	// segura cada andar aceso por 1,5 s depois que deixou de ser preciso: sem isso, voando
	// perto da altura de troca o andar vizinho (e as luzes dele) liga/desliga sem parar
	const double Agora = FPlatformTime::Seconds();
	for (int32 K : Visiveis) AndarPedido.Add(K, Agora);
	for (const TPair<int32, double>& Ped : AndarPedido)
	{
		if (Agora - Ped.Value < 1.5) Visiveis.Add(Ped.Key);
	}

	for (TPair<FName, FGrupoVisivel>& Par : Grupos)
	{
		const FString Nome = Par.Key.ToString();
		bool bVer = false;
		if (Nome.StartsWith(TEXT("Andar")))
		{
			bVer = Visiveis.Contains(FCString::Atoi(*Nome.RightChop(5)));
		}
		else // LajeK = piso do andar K e teto do andar K-1; a laje de baixo também fica (vista pelos buracos)
		{
			const int32 K = FCString::Atoi(*Nome.RightChop(4));
			bVer = Visiveis.Contains(K) || Visiveis.Contains(K - 1) || Visiveis.Contains(K + 1);
		}
		if (bForcar || bVer != Par.Value.bVisivel)
		{
			Par.Value.bVisivel = bVer;
			for (const TWeakObjectPtr<AActor>& A : Par.Value.Atores)
			{
				if (!A.IsValid()) continue;
				A->SetActorHiddenInGame(!bVer);
				TArray<ULightComponent*> Luzes;
				A->GetComponents(Luzes);
				for (ULightComponent* L : Luzes) L->SetVisibility(bVer);
			}
		}
	}
}


// ------------------------------------------------------------------ teclas

static const FKey TeclasVigiadas[] = {
	EKeys::Escape, EKeys::Gamepad_Special_Right, EKeys::Gamepad_Special_Left, EKeys::Gamepad_FaceButton_Right,
	EKeys::Gamepad_FaceButton_Bottom, EKeys::BackSpace, EKeys::Enter, EKeys::SpaceBar,
	EKeys::Up, EKeys::Down, EKeys::Left, EKeys::Right, EKeys::W, EKeys::S, EKeys::A, EKeys::D,
	EKeys::Gamepad_DPad_Up, EKeys::Gamepad_DPad_Down, EKeys::Gamepad_DPad_Left, EKeys::Gamepad_DPad_Right,
	EKeys::Gamepad_LeftShoulder, EKeys::Gamepad_RightShoulder, EKeys::Q, EKeys::E, EKeys::Tab,
	EKeys::LeftMouseButton, EKeys::RightMouseButton,
	EKeys::F1, EKeys::F2, EKeys::F3, EKeys::F4, EKeys::F5, EKeys::F6 };

void APredioGameMode::AtualizarTeclas()
{
	TeclaAgora.Reset();
	APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
	if (!PC) return;
	for (const FKey& K : TeclasVigiadas)
	{
		const bool bDown = PC->IsInputKeyDown(K);
		const bool bAntes = TeclaAntes.FindRef(K);
		if (bDown && !bAntes) TeclaAgora.Add(K);
		TeclaAntes.Add(K, bDown);
	}
}

bool APredioGameMode::Apertou(const FKey& K) const
{
	return TeclaAgora.Contains(K);
}

void APredioGameMode::Registrar(const FString& Linha) const
{
	const FString Arq = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir()) / TEXT("menu_log.txt");
	FFileHelper::SaveStringToFile(FString::Printf(TEXT("%s  %s\r\n"), *FDateTime::Now().ToString(TEXT("%H:%M:%S")), *Linha),
		*Arq, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM, &IFileManager::Get(), FILEWRITE_Append);
}

// ------------------------------------------------------------------ menu

ECategoriaMenu APredioGameMode::CategoriaDoItem(int32 I)
{
	switch ((EItemMenu)I)
	{
	case EItemMenu::Continuar: return ECategoriaMenu::Continuar;
	case EItemMenu::ModoVoo: case EItemMenu::VoltarInicio: return ECategoriaMenu::Jogabilidade;
	case EItemMenu::Sensibilidade: case EItemMenu::Expo: return ECategoriaMenu::Sensibilidade;
	case EItemMenu::ModoFSR: case EItemMenu::Gerador: case EItemMenu::VSync: case EItemMenu::Painel: case EItemMenu::AjusteAuto:
		return ECategoriaMenu::Video;
	case EItemMenu::Volume: return ECategoriaMenu::Audio;
	case EItemMenu::InvFrente: case EItemMenu::InvSubir: case EItemMenu::InvGiro: case EItemMenu::InvLados:
		return ECategoriaMenu::Controles;
	case EItemMenu::EscalaHUD: return ECategoriaMenu::Acessibilidade;
	case EItemMenu::Padrao: return ECategoriaMenu::Avancado;
	default: return ECategoriaMenu::Sair;
	}
}

int32 APredioGameMode::PrimeiroItemDa(ECategoriaMenu C)
{
	for (int32 i = 0; i < (int32)EItemMenu::Total; ++i)
	{
		if (CategoriaDoItem(i) == C) return i;
	}
	return 0;
}

FString APredioGameMode::NomeCategoria(ECategoriaMenu C)
{
	switch (C)
	{
	case ECategoriaMenu::Continuar: return TEXT("CONTINUAR");
	case ECategoriaMenu::Jogabilidade: return TEXT("JOGABILIDADE");
	case ECategoriaMenu::Sensibilidade: return TEXT("SENSIBILIDADE");
	case ECategoriaMenu::Video: return TEXT("VÍDEO");
	case ECategoriaMenu::Audio: return TEXT("ÁUDIO");
	case ECategoriaMenu::Controles: return TEXT("CONTROLES");
	case ECategoriaMenu::Acessibilidade: return TEXT("ACESSIBILIDADE");
	case ECategoriaMenu::Avancado: return TEXT("AVANÇADO");
	default: return TEXT("SAIR DO JOGO");
	}
}

FString APredioGameMode::NomeItem(int32 I) const
{
	switch ((EItemMenu)I)
	{
	case EItemMenu::Continuar:     return TEXT("Continuar voando");
	case EItemMenu::ModoVoo:       return TEXT("Modo de voo");
	case EItemMenu::VoltarInicio:  return TEXT("Voltar ao início");
	case EItemMenu::Sensibilidade: return TEXT("Sensibilidade dos analógicos");
	case EItemMenu::Expo:          return TEXT("Suavidade no centro (expo)");
	case EItemMenu::ModoFSR:       return TEXT("AMD FSR 4 (IA)");
	case EItemMenu::Gerador:       return TEXT("Gerador de quadros AMD");
	case EItemMenu::VSync:         return TEXT("VSync");
	case EItemMenu::Painel:        return TEXT("Painel de FPS");
	case EItemMenu::AjusteAuto:    return TEXT("Ajuste automático (60 FPS)");
	case EItemMenu::Volume:        return TEXT("Volume do drone");
	case EItemMenu::InvFrente:     return TEXT("Inverter frente / trás");
	case EItemMenu::InvSubir:      return TEXT("Inverter subir / descer");
	case EItemMenu::InvGiro:       return TEXT("Inverter giro");
	case EItemMenu::InvLados:      return TEXT("Inverter lados");
	case EItemMenu::EscalaHUD:     return TEXT("Tamanho da interface");
	case EItemMenu::Padrao:        return TEXT("Restaurar padrões");
	case EItemMenu::Sair:          return TEXT("Sair do jogo");
	default: return FString();
	}
}

FString APredioGameMode::DescricaoItem(int32 I) const
{
	switch ((EItemMenu)I)
	{
	case EItemMenu::Continuar:     return TEXT("Volta para o voo (o simulador está pausado)");
	case EItemMenu::ModoVoo:       return TEXT("Estabilizado nivela sozinho; Acro é manual");
	case EItemMenu::VoltarInicio:  return TEXT("Recoloca o drone no ponto de partida");
	case EItemMenu::Sensibilidade: return TEXT("Velocidade e giro máximos dos analógicos");
	case EItemMenu::Expo:          return TEXT("Deixa o centro do analógico mais suave");
	case EItemMenu::ModoFSR:       return TEXT("Upscaling por IA da AMD (Qualidade = mais nítido)");
	case EItemMenu::Gerador:       return TEXT("Cria quadros intermediários com IA (quase dobra o FPS)");
	case EItemMenu::VSync:         return TEXT("Sincroniza com o monitor (evita rasgos na imagem)");
	case EItemMenu::Painel:        return TEXT("Mostra FPS, GPU e o modo do FSR na tela");
	case EItemMenu::AjusteAuto:    return TEXT("Alivia o FSR sozinho se o FPS de base cair de 60");
	case EItemMenu::Volume:        return TEXT("Volume do som dos motores e das batidas");
	case EItemMenu::InvFrente:     return TEXT("Inverte o analógico direito para frente e para trás");
	case EItemMenu::InvSubir:      return TEXT("Inverte o acelerador (subir e descer)");
	case EItemMenu::InvGiro:       return TEXT("Inverte o giro no próprio eixo (esquerda / direita)");
	case EItemMenu::InvLados:      return TEXT("Inverte o deslize para os lados");
	case EItemMenu::EscalaHUD:     return TEXT("Tamanho dos textos do OSD durante o voo");
	case EItemMenu::Padrao:        return TEXT("Volta todas as opções para o padrão de fábrica");
	case EItemMenu::Sair:          return TEXT("Fecha o simulador");
	default: return FString();
	}
}

ETipoValor APredioGameMode::TipoItem(int32 I) const
{
	switch ((EItemMenu)I)
	{
	case EItemMenu::Gerador: case EItemMenu::VSync: case EItemMenu::Painel: case EItemMenu::AjusteAuto:
		return ETipoValor::Chave;
	case EItemMenu::Continuar: return ETipoValor::Nenhum;
	case EItemMenu::VoltarInicio: case EItemMenu::Padrao: case EItemMenu::Sair:
		return ETipoValor::Acao;
	default: return ETipoValor::Texto;
	}
}

bool APredioGameMode::ChaveLigada(int32 I) const
{
	const FAjustesDrone& C = FAjustesDrone::Get();
	switch ((EItemMenu)I)
	{
	case EItemMenu::Gerador: return C.bGerador;
	case EItemMenu::VSync: return C.bVSync;
	case EItemMenu::Painel: return C.bPainel;
	case EItemMenu::AjusteAuto: return C.bAjusteAuto;
	default: return false;
	}
}

FString APredioGameMode::ValorItem(int32 I) const
{
	const FAjustesDrone& C = FAjustesDrone::Get();
	const ADronePawn* D = Drone();
	auto SN = [](bool b) { return FString(b ? TEXT("Sim") : TEXT("Não")); };
	auto LD = [](bool b) { return FString(b ? TEXT("Ligado") : TEXT("Desligado")); };
	switch ((EItemMenu)I)
	{
	case EItemMenu::ModoVoo:       return (D && D->Modo == EModoVoo::Acro) ? TEXT("ACRO") : TEXT("ESTABILIZADO");
	case EItemMenu::Sensibilidade: return FString::Printf(TEXT("%d%%"), FMath::RoundToInt(C.Sensibilidade * 100.f));
	case EItemMenu::Expo:          return FString::Printf(TEXT("%d%%"), FMath::RoundToInt(C.Expo * 100.f));
	case EItemMenu::ModoFSR:       return NomesModo[FMath::Clamp(C.ModoFSR, 0, 3)];
	case EItemMenu::Gerador:       return LD(C.bGerador);
	case EItemMenu::VSync:         return LD(C.bVSync);
	case EItemMenu::Painel:        return LD(C.bPainel);
	case EItemMenu::AjusteAuto:    return LD(C.bAjusteAuto);
	case EItemMenu::Volume:        return FString::Printf(TEXT("%d%%"), FMath::RoundToInt(C.Volume * 100.f));
	case EItemMenu::InvFrente:     return SN(C.bInvArfagem);
	case EItemMenu::InvSubir:      return SN(C.bInvAcelerador);
	case EItemMenu::InvGiro:       return SN(C.bInvGuinada);
	case EItemMenu::InvLados:      return SN(C.bInvRolagem);
	case EItemMenu::EscalaHUD:     return FString::Printf(TEXT("%d%%"), FMath::RoundToInt(C.EscalaInterface * 100.f));
	case EItemMenu::VoltarInicio: case EItemMenu::Padrao: case EItemMenu::Sair: return TEXT("—");
	default: return FString();
	}
}

void APredioGameMode::AbrirMenu(bool bAbrir)
{
	if (bMenuAberto == bAbrir) return;
	bMenuAberto = bAbrir;
	MenuMudouEm = FPlatformTime::Seconds();
	bMenuJaDesenhado = false;
	if (!bTour) Registrar(bAbrir ? TEXT("menu ABERTO") : TEXT("menu fechado"));
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	ADronePawn* D = Drone();
	if (bAbrir)
	{
		MenuIndice = 0;
	}
	else
	{
		FAjustesDrone::Get().Salvar();
	}
	// pausa de verdade: física, tempo de voo, bateria e som param
	UGameplayStatics::SetGamePaused(this, bAbrir);
	if (D)
	{
		D->bCongelado = bAbrir;
		if (D->Audio) D->Audio->SetPaused(bAbrir);
	}
	if (PC)
	{
		PC->bShowMouseCursor = bAbrir;
		if (bAbrir)
		{
			FInputModeGameAndUI Modo;
			Modo.SetHideCursorDuringCapture(false);
			Modo.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
			PC->SetInputMode(Modo);
			float MX = 0.f, MY = 0.f;
			PC->GetMousePosition(MX, MY);
			UltimoMouse = FVector2D(MX, MY);
		}
		else
		{
			PC->SetInputMode(FInputModeGameOnly());
		}
	}
	RepeticaoV = RepeticaoH = 0.3f;
}

void APredioGameMode::MudarItem(int32 Dir, bool bConfirmar)
{
	FAjustesDrone& C = FAjustesDrone::Get();
	ADronePawn* D = Drone();
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	const int32 Passo = Dir != 0 ? Dir : 1;
	auto Ciclo = [](float V, float Passo, float Min, float Max)
	{
		const float N = V + Passo;
		if (N > Max + 0.001f) return Min;
		if (N < Min - 0.001f) return Max;
		return FMath::Clamp(N, Min, Max);
	};
	switch ((EItemMenu)MenuIndice)
	{
	case EItemMenu::Continuar:
		if (bConfirmar) AbrirMenu(false);
		return;
	case EItemMenu::Sensibilidade:
		C.Sensibilidade = Ciclo(C.Sensibilidade, 0.05f * Passo, 0.30f, 2.00f);
		break;
	case EItemMenu::Expo:
		C.Expo = Ciclo(C.Expo, 0.05f * Passo, 0.f, 0.80f);
		break;
	case EItemMenu::InvFrente: C.bInvArfagem = !C.bInvArfagem; break;
	case EItemMenu::InvSubir:  C.bInvAcelerador = !C.bInvAcelerador; break;
	case EItemMenu::InvGiro:   C.bInvGuinada = !C.bInvGuinada; break;
	case EItemMenu::InvLados:  C.bInvRolagem = !C.bInvRolagem; break;
	case EItemMenu::ModoVoo:
		if (D)
		{
			D->TrocarModo();
			C.bComecarAcro = D->Modo == EModoVoo::Acro;
		}
		break;
	case EItemMenu::Volume:
		C.Volume = Ciclo(C.Volume, 0.05f * Passo, 0.f, 1.f);
		break;
	case EItemMenu::EscalaHUD:
		C.EscalaInterface = Ciclo(C.EscalaInterface, 0.1f * Passo, 0.7f, 1.6f);
		break;
	case EItemMenu::ModoFSR:
		C.ModoFSR = (C.ModoFSR + Passo + 4) % 4;
		NivelAjuste = 0;
		C.AplicarGraficos();
		AplicarNivelAjuste();
		break;
	case EItemMenu::Gerador:
		C.bGerador = !C.bGerador;
		C.AplicarGraficos();
		break;
	case EItemMenu::VSync:
		C.bVSync = !C.bVSync;
		C.AplicarGraficos();
		break;
	case EItemMenu::Painel:
		C.bPainel = !C.bPainel;
		break;
	case EItemMenu::AjusteAuto:
		C.bAjusteAuto = !C.bAjusteAuto;
		NivelAjuste = 0;
		AplicarNivelAjuste();
		break;
	case EItemMenu::VoltarInicio:
		if (bConfirmar && D)
		{
			D->Recomecar(D->Inicio);
			AbrirMenu(false);
			D->MostrarMensagem(TEXT("Voltou para o início"));
		}
		return;
	case EItemMenu::Padrao:
		if (bConfirmar)
		{
			C = FAjustesDrone();
			C.AplicarGraficos();
			NivelAjuste = 0;
			AplicarNivelAjuste();
			if (D && D->Modo == EModoVoo::Acro) D->TrocarModo();
		}
		break;
	case EItemMenu::Sair:
		if (bConfirmar)
		{
			C.Salvar();
			UGameplayStatics::SetGamePaused(this, false);
			UKismetSystemLibrary::QuitGame(this, PC, EQuitPreference::Quit, false);
		}
		return;
	default: break;
	}
	C.Salvar();
}

void APredioGameMode::TickMenu(float Dt)
{
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (!PC) return;
	auto Apertou = [this](std::initializer_list<FKey> Teclas)
	{
		for (const FKey& K : Teclas) if (this->Apertou(K)) return true;
		return false;
	};
	// logo depois de abrir, ignora as teclas de fechar (o mesmo toque não fecha o menu)
	const bool bPodeFechar = FPlatformTime::Seconds() - MenuMudouEm > 0.3;

	if (bPodeFechar && Apertou({ EKeys::Escape, EKeys::Gamepad_Special_Right, EKeys::Gamepad_FaceButton_Right, EKeys::BackSpace }))
	{
		Registrar(TEXT("fechar pedido por Esc / Start / B"));
		AbrirMenu(false);
		return;
	}

	const int32 N = (int32)EItemMenu::Total;
	const int32 NC = (int32)ECategoriaMenu::Total;

	// troca de categoria: LB / RB (ou Q / E, Tab)
	int32 Cat = 0;
	if (Apertou({ EKeys::Gamepad_LeftShoulder, EKeys::Q })) Cat = -1;
	if (Apertou({ EKeys::Gamepad_RightShoulder, EKeys::E, EKeys::Tab })) Cat = 1;
	if (Cat != 0)
	{
		const int32 Atual = (int32)CategoriaDoItem(MenuIndice);
		MenuIndice = PrimeiroItemDa((ECategoriaMenu)((Atual + Cat + NC) % NC));
	}

	int32 V = 0, Hz = 0;
	if (Apertou({ EKeys::Up, EKeys::W, EKeys::Gamepad_DPad_Up })) V = -1;
	if (Apertou({ EKeys::Down, EKeys::S, EKeys::Gamepad_DPad_Down })) V = 1;
	if (Apertou({ EKeys::Left, EKeys::A, EKeys::Gamepad_DPad_Left })) Hz = -1;
	if (Apertou({ EKeys::Right, EKeys::D, EKeys::Gamepad_DPad_Right })) Hz = 1;

	// analógico esquerdo com repetição ao segurar
	const float SY = PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftY);
	const float SX = PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftX);
	const int32 DirV = SY > 0.6f ? -1 : (SY < -0.6f ? 1 : 0);
	const int32 DirH = SX > 0.6f ? 1 : (SX < -0.6f ? -1 : 0);
	if (DirV != 0)
	{
		if (DirV != UltimaDirVert) { V = DirV; RepeticaoV = 0.35f; }
		else if ((RepeticaoV -= Dt) <= 0.f) { V = DirV; RepeticaoV = 0.12f; }
	}
	if (DirH != 0)
	{
		if (DirH != UltimaDirHoriz) { Hz = DirH; RepeticaoH = 0.35f; }
		else if ((RepeticaoH -= Dt) <= 0.f) { Hz = DirH; RepeticaoH = 0.10f; }
	}
	UltimaDirVert = DirV;
	UltimaDirHoriz = DirH;

	if (V != 0) MenuIndice = (MenuIndice + V + N) % N;
	if (Hz != 0) MudarItem(Hz, false);
	if (bPodeFechar && Apertou({ EKeys::Enter, EKeys::SpaceBar, EKeys::Gamepad_FaceButton_Bottom }))
	{
		MudarItem(0, true);
		if (!bMenuAberto) return;
	}

	// mouse: passar por cima escolhe, clique esquerdo muda/confirma, direito volta, roda ajusta
	float MX = 0.f, MY = 0.f;
	if (PC->GetMousePosition(MX, MY))
	{
		const FVector2D M(MX, MY);
		const bool bMexeu = FVector2D::Distance(M, UltimoMouse) > 1.5f;
		UltimoMouse = M;
		int32 Sob = INDEX_NONE;
		for (int32 i = 0; i < AreaItens.Num(); ++i)
		{
			if (AreaItens[i].bIsValid && AreaItens[i].IsInside(M)) { Sob = i; break; }
		}
		if (Sob != INDEX_NONE && bMexeu) MenuIndice = Sob;
		if (bPodeFechar && this->Apertou(EKeys::LeftMouseButton))
		{
			if (AreaFechar.bIsValid && AreaFechar.IsInside(M))
			{
				AbrirMenu(false);
				return;
			}
			for (int32 c = 0; c < AreaCategorias.Num(); ++c)
			{
				if (AreaCategorias[c].bIsValid && AreaCategorias[c].IsInside(M))
				{
					MenuIndice = PrimeiroItemDa((ECategoriaMenu)c);
					if ((ECategoriaMenu)c == ECategoriaMenu::Continuar) { AbrirMenu(false); return; }
				}
			}
			if (Sob != INDEX_NONE)
			{
				MenuIndice = Sob;
				MudarItem(1, true);
				if (!bMenuAberto) return;
			}
		}
		if (Sob != INDEX_NONE && this->Apertou(EKeys::RightMouseButton))
		{
			MenuIndice = Sob;
			MudarItem(-1, false);
		}
		if (Sob != INDEX_NONE && TipoItem(Sob) == ETipoValor::Texto)
		{
			if (PC->WasInputKeyJustPressed(EKeys::MouseScrollUp)) { MenuIndice = Sob; MudarItem(1, false); }
			if (PC->WasInputKeyJustPressed(EKeys::MouseScrollDown)) { MenuIndice = Sob; MudarItem(-1, false); }
		}
	}
}

void APredioGameMode::TeclasAtalho()
{
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	ADronePawn* D = Drone();
	if (!PC || !D) return;
	FAjustesDrone& C = FAjustesDrone::Get();

	if ((Apertou(EKeys::Escape) || Apertou(EKeys::Gamepad_Special_Right)) && FPlatformTime::Seconds() - MenuMudouEm > 0.3)
	{
		bMostrarAjuda = false;
		Registrar(Apertou(EKeys::Escape) ? TEXT("Esc apertado") : TEXT("Start apertado"));
		AbrirMenu(true);
		return;
	}
	if (Apertou(EKeys::F1) || Apertou(EKeys::Gamepad_Special_Left))
	{
		bMostrarAjuda = !bMostrarAjuda;
	}
	if (Apertou(EKeys::F2))
	{
		C.ModoFSR = (C.ModoFSR + 1) % 4;
		C.AplicarGraficos();
		NivelAjuste = 0;
		AplicarNivelAjuste();
		C.Salvar();
		D->MostrarMensagem(FString::Printf(TEXT("FSR 4: %s"), NomesModo[C.ModoFSR]));
	}
	if (Apertou(EKeys::F3))
	{
		C.bGerador = !C.bGerador;
		C.AplicarGraficos();
		C.Salvar();
		D->MostrarMensagem(C.bGerador ? TEXT("Gerador de quadros AMD LIGADO") : TEXT("Gerador de quadros AMD desligado"));
	}
	if (Apertou(EKeys::F4))
	{
		const bool bNovo = !FSRLigado();
		SetInt(TEXT("r.FidelityFX.FSR.Enabled"), bNovo ? 1 : 0);
		D->MostrarMensagem(bNovo ? TEXT("FSR 4 (IA) LIGADO") : TEXT("FSR desligado — usando o TSR do Unreal para comparar"));
	}
	if (Apertou(EKeys::F5))
	{
		C.bPainel = !C.bPainel;
		C.Salvar();
	}
	if (Apertou(EKeys::F6))
	{
		C.bAjusteAuto = !C.bAjusteAuto;
		NivelAjuste = 0;
		AplicarNivelAjuste();
		C.Salvar();
		D->MostrarMensagem(C.bAjusteAuto ? TEXT("Ajuste automático para 60 FPS LIGADO") : TEXT("Ajuste automático desligado"));
	}
}

// ------------------------------------------------------------------ desempenho

void APredioGameMode::AplicarNivelAjuste()
{
	// 0: modo do FSR escolhido no menu + Lumen com ray tracing de hardware
	// 1: FSR no mínimo Equilibrado
	// 2: FSR no mínimo Desempenho
	// 3: + Lumen por software
	// 4: + sombras e névoa um pouco mais leves
	const int32 Base = FMath::Clamp(FAjustesDrone::Get().ModoFSR, 0, 3);
	const int32 N = FMath::Clamp(NivelAjuste, 0, 4);
	const int32 Modo = N == 0 ? Base : FMath::Max(Base, N == 1 ? 2 : 3);
	SetInt(TEXT("r.FidelityFX.FSR.QualityMode"), Modo);
	SetInt(TEXT("r.Lumen.HardwareRayTracing"), N >= 3 ? 0 : 1);
	SetInt(TEXT("r.Shadow.Virtual.ResolutionLodBiasDirectional"), N >= 4 ? 1 : -1);
	SetInt(TEXT("r.VolumetricFog.GridPixelSize"), N >= 4 ? 16 : 8);
}

void APredioGameMode::AjusteAutomatico(float Dt)
{
	if (!FAjustesDrone::Get().bAjusteAuto || bTour || bMenuAberto) return;
	if (FPSBase < 57.f) { AcumBaixo += Dt; AcumAlto = 0.f; }
	else if (FPSBase > 88.f) { AcumAlto += Dt; AcumBaixo = 0.f; }
	else { AcumBaixo = FMath::Max(0.f, AcumBaixo - Dt); AcumAlto = FMath::Max(0.f, AcumAlto - Dt); }

	if (AcumBaixo > 4.f && NivelAjuste < 4)
	{
		++NivelAjuste;
		AplicarNivelAjuste();
		AcumBaixo = 0.f;
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
	AtualizarTeclas();
	if (bTour)
	{
		TickTour(DeltaSeconds);
		return;
	}
	if (bMenuAberto)
	{
		TickMenu(DtReal);
	}
	else
	{
		TeclasAtalho();
	}
	AjusteAutomatico(DeltaSeconds);
}

// ------------------------------------------------------------------ voo de teste

void APredioGameMode::TickTour(float Dt)
{
	ADronePawn* D = Drone();
	if (!D || TourPontos.Num() < 2) return;

	// depois do percurso: foto do menu (jogo pausado) e sai
	if (TourFase > 0)
	{
		TourFimT += FApp::GetDeltaTime();
		if (TourFase == 1 && TourFimT > 1.5f)
		{
			FScreenshotRequest::RequestScreenshot(PastaTestes / TEXT("tour_menu.png"), true, false);
			TourFase = 2;
			TourFimT = 0.f;
		}
		else if (TourFase == 2 && TourFimT > 1.5f)
		{
			FPlatformMisc::RequestExit(false);
			bTour = false;
		}
		return;
	}

#if WITH_EDITOR
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
	TourS += Dt * 260.f / Comprimento;
	if (TourS >= N - 1)
	{
		SalvarResultadoTour();
		AbrirMenu(true);
		TourFase = 1;
		TourFimT = 0.f;
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
