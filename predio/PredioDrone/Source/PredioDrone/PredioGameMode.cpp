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
#include "Misc/PackageName.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
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
	bEhCampo = GetWorld()->GetMapName().Contains(TEXT("Campo"));
	LimitesVoo = bEhCampo
		? FBox(FVector(-48000.f, -48000.f, -5000.f), FVector(48000.f, 48000.f, 9000.f)) // fazenda: 480 m para cada lado, 90 m de teto
		: FBox(FVector(45.f, -1555.f, -500.f), FVector(2355.f, -45.f, 1590.f));
	if (ADronePawn* D = Drone())
	{
		D->Limites = LimitesVoo;
		D->bUsarLimites = true;
	}

	MontarPercurso();
	MontarAros();
	if (bEhCampo) EspalharGrama();

	bTour = FParse::Param(FCommandLine::Get(), TEXT("tour"));
	bFotoMenu = FParse::Param(FCommandLine::Get(), TEXT("fotomenu"));
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

	// jogo único: o mapa do prédio sem "?jogo" abre o menu principal (escolha do mapa);
	// "?jogo?modo=N" já começa voando com o objetivo N
	bCampoExiste = FPackageName::DoesPackageExist(TEXT("/Game/Mapas/Campo"));
	const bool bJogo = UGameplayStatics::HasOption(OptionsString, TEXT("jogo"));
	const FString OpModo = UGameplayStatics::ParseOption(OptionsString, TEXT("modo"));
	EObjetivo Inicial = bEhCampo ? EObjetivo::ArosOrdem : EObjetivo::Livre;
	if (!OpModo.IsEmpty())
	{
		Inicial = (EObjetivo)FMath::Clamp(FCString::Atoi(*OpModo), 0, (int32)EObjetivo::ArosRelogio);
		if (!ObjetivosDoMapa().Contains(Inicial)) Inicial = ObjetivosDoMapa()[0];
	}
	if (ADronePawn* D = Drone()) UltimosReinicios = D->Reinicios;
	if (!bTour && !bJogo && !bEhCampo)
	{
		EntrarMenuPrincipal();
	}
	else
	{
		IniciarObjetivo(bTour ? EObjetivo::Livre : Inicial, false);
	}
	UE_LOG(LogPredio, Log, TEXT("Predio: mapa %s, %d andares, %d pontos de rota, %d aros, %d conexoes, tour=%d, menu=%d, ajustes em %s"),
		*GetWorld()->GetMapName(), NumAndares, Rota.Num(), Aros.Num(), Conexoes.Num(), bTour ? 1 : 0, bMenuPrincipal ? 1 : 0, *FAjustesDrone::Arquivo());
}

void APredioGameMode::ColetarAtores()
{
	Grupos.Reset();
	Conexoes.Reset();
	Rota.Reset();
	AtoresAros.Reset();
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
			else if (T.StartsWith(TEXT("Aro_")))
			{
				AtoresAros.Add(TPair<int32, TWeakObjectPtr<AActor>>(FCString::Atoi(*T.RightChop(4)), A));
			}
			else if (T.StartsWith(TEXT("AroRaio_")))
			{
				RaioAro = FMath::Max(80.f, FCString::Atof(*T.RightChop(8)));
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
	case EItemMenu::Objetivo: case EItemMenu::ModoVoo: case EItemMenu::VoltarInicio: case EItemMenu::MenuPrincipal:
		return ECategoriaMenu::Jogabilidade;
	case EItemMenu::Sensibilidade: case EItemMenu::Expo: return ECategoriaMenu::Sensibilidade;
	case EItemMenu::ModoFSR: case EItemMenu::Gerador: case EItemMenu::VSync:
		return ECategoriaMenu::Video;
	case EItemMenu::Volume: return ECategoriaMenu::Audio;
	case EItemMenu::InvFrente: case EItemMenu::InvSubir: case EItemMenu::InvGiro: case EItemMenu::InvLados:
		return ECategoriaMenu::Controles;
	case EItemMenu::EscalaHUD: return ECategoriaMenu::Acessibilidade;
	case EItemMenu::Painel: case EItemMenu::AjusteAuto: case EItemMenu::Padrao: return ECategoriaMenu::Avancado;
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

TArray<int32> APredioGameMode::ItensDaCategoria(ECategoriaMenu C)
{
	TArray<int32> R;
	for (int32 i = 0; i < (int32)EItemMenu::Total; ++i)
	{
		if (CategoriaDoItem(i) == C) R.Add(i);
	}
	return R;
}

FString APredioGameMode::DescricaoCategoria(ECategoriaMenu C)
{
	switch (C)
	{
	case ECategoriaMenu::Continuar: return TEXT("Volta para o voo");
	case ECategoriaMenu::Jogabilidade: return TEXT("Objetivo, modo de voo e volta ao início");
	case ECategoriaMenu::Sensibilidade: return TEXT("Quanto o drone responde aos comandos");
	case ECategoriaMenu::Video: return TEXT("AMD FSR 4, gerador de quadros e V-Sync");
	case ECategoriaMenu::Audio: return TEXT("Som do motor do drone");
	case ECategoriaMenu::Controles: return TEXT("Inverter os eixos dos comandos");
	case ECategoriaMenu::Acessibilidade: return TEXT("Tamanho do painel de voo na tela");
	case ECategoriaMenu::Avancado: return TEXT("Painel de desempenho, ajuste automático e padrões");
	default: return TEXT("Fecha o simulador (as configurações ficam salvas)");
	}
}

void APredioGameMode::EntrarCategoria(ECategoriaMenu C)
{
	CategoriaSel = (int32)C;
	if (C == ECategoriaMenu::Continuar)
	{
		AbrirMenu(false);
		return;
	}
	bFocoItens = true;
	MenuIndice = PrimeiroItemDa(C);
	MenuMudouEm = FPlatformTime::Seconds();
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
	case EItemMenu::Continuar:     return bMenuPrincipal ? TEXT("Voltar ao menu principal") : TEXT("Continuar voando");
	case EItemMenu::Objetivo:      return TEXT("Objetivo");
	case EItemMenu::ModoVoo:       return TEXT("Modo de voo");
	case EItemMenu::VoltarInicio:  return TEXT("Voltar ao início");
	case EItemMenu::MenuPrincipal: return TEXT("Menu principal");
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
	case EItemMenu::Continuar:     return bMenuPrincipal ? TEXT("Fecha as configurações") : TEXT("Volta para o voo (o simulador está pausado)");
	case EItemMenu::Objetivo:      return DescricaoObjetivo(Objetivo);
	case EItemMenu::ModoVoo:       return TEXT("Estabilizado nivela sozinho; Acro é manual");
	case EItemMenu::VoltarInicio:  return TEXT("Recoloca o drone no ponto de partida (o desafio recomeça)");
	case EItemMenu::MenuPrincipal: return TEXT("Escolher outro mapa");
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
	case EItemMenu::VoltarInicio: case EItemMenu::MenuPrincipal: case EItemMenu::Padrao: case EItemMenu::Sair:
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
	case EItemMenu::Objetivo:      return NomeObjetivo(Objetivo).ToUpper();
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
	case EItemMenu::VoltarInicio: case EItemMenu::MenuPrincipal: case EItemMenu::Padrao: case EItemMenu::Sair: return TEXT("—");
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
		CategoriaSel = 0;
		bFocoItens = false;
	}
	else
	{
		FAjustesDrone::Get().Salvar();
	}
	// pausa de verdade: física, tempo de voo, bateria e som param
	UGameplayStatics::SetGamePaused(this, bAbrir);
	if (D)
	{
		D->bCongelado = bAbrir || bMenuPrincipal;
		if (D->Audio) D->Audio->SetPaused(bAbrir || bMenuPrincipal);
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
		else if (bMenuPrincipal)
		{
			PC->bShowMouseCursor = true; // fechou as configurações: volta para os cartões
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
	case EItemMenu::Objetivo:
	{
		if (bMenuPrincipal) return; // escolhido nos cartões do menu principal
		const TArray<EObjetivo> Lista = ObjetivosDoMapa();
		if (Lista.Num() < 2) return;
		const int32 Atual = FMath::Max(0, Lista.IndexOfByKey(Objetivo));
		IniciarObjetivo(Lista[(Atual + Passo + Lista.Num()) % Lista.Num()], true);
		return;
	}
	case EItemMenu::MenuPrincipal:
		if (bConfirmar && !bMenuPrincipal)
		{
			C.Salvar();
			if (bEhCampo)
			{
				IrParaMapa(TEXT("/Game/Mapas/Predio"), FString());
			}
			else
			{
				AbrirMenu(false);
				EntrarMenuPrincipal();
			}
		}
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
		if (D && !bMenuPrincipal)
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
		if (bConfirmar && D && !bMenuPrincipal)
		{
			D->Recomecar(D->Inicio);
			AbrirMenu(false);
			D->MostrarMensagem(TEXT("Voltou para o início"));
		}
		return;
	case EItemMenu::Padrao:
		if (bConfirmar)
		{
			const FAjustesDrone Antes = C;
			C = FAjustesDrone();
			// recordes e medalhas não são "opções"
			C.RecordeTopo = Antes.RecordeTopo; C.RecordeAros = Antes.RecordeAros; C.RecordeRelogio = Antes.RecordeRelogio;
			C.MedalhaTopo = Antes.MedalhaTopo; C.MedalhaAros = Antes.MedalhaAros; C.MedalhaRelogio = Antes.MedalhaRelogio;
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

	const int32 NC = (int32)ECategoriaMenu::Total;
	const ECategoriaMenu Cat = (ECategoriaMenu)FMath::Clamp(CategoriaSel, 0, NC - 1);

	// Start fecha de qualquer lugar; Esc / B / Backspace voltam uma tela (das opções para as seções, das seções fecha)
	if (bPodeFechar && Apertou({ EKeys::Gamepad_Special_Right }))
	{
		AbrirMenu(false);
		return;
	}
	if (bPodeFechar && Apertou({ EKeys::Escape, EKeys::Gamepad_FaceButton_Right, EKeys::BackSpace }))
	{
		if (bFocoItens)
		{
			bFocoItens = false;
			MenuMudouEm = FPlatformTime::Seconds();
			return;
		}
		Registrar(TEXT("fechar pedido por Esc / B"));
		AbrirMenu(false);
		return;
	}

	// troca de seção: LB / RB (ou Q / E, Tab)
	int32 Pulo = 0;
	if (Apertou({ EKeys::Gamepad_LeftShoulder, EKeys::Q })) Pulo = -1;
	if (Apertou({ EKeys::Gamepad_RightShoulder, EKeys::E, EKeys::Tab })) Pulo = 1;
	if (Pulo != 0)
	{
		CategoriaSel = (CategoriaSel + Pulo + NC) % NC;
		if ((ECategoriaMenu)CategoriaSel == ECategoriaMenu::Continuar) CategoriaSel = (CategoriaSel + Pulo + NC) % NC;
		if (bFocoItens) MenuIndice = PrimeiroItemDa((ECategoriaMenu)CategoriaSel);
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

	if (!bFocoItens)
	{
		// coluna das seções
		if (V != 0) CategoriaSel = (CategoriaSel + V + NC) % NC;
		if (Hz > 0 || (bPodeFechar && Apertou({ EKeys::Enter, EKeys::SpaceBar, EKeys::Gamepad_FaceButton_Bottom })))
		{
			EntrarCategoria((ECategoriaMenu)CategoriaSel);
			if (!bMenuAberto) return;
		}
	}
	else
	{
		// opções da seção aberta
		const TArray<int32> Itens = ItensDaCategoria(Cat);
		int32 Pos = FMath::Max(0, Itens.IndexOfByKey(MenuIndice));
		if (!Itens.Contains(MenuIndice) && Itens.Num()) MenuIndice = Itens[0];
		if (V != 0 && Itens.Num()) { Pos = (Pos + V + Itens.Num()) % Itens.Num(); MenuIndice = Itens[Pos]; }
		const ETipoValor Tipo = TipoItem(MenuIndice);
		if (Hz < 0 && (Tipo == ETipoValor::Acao || Tipo == ETipoValor::Nenhum))
		{
			bFocoItens = false; // seta para a esquerda num botão: volta para as seções
		}
		else if (Hz != 0)
		{
			MudarItem(Hz, false);
		}
		if (bPodeFechar && Apertou({ EKeys::Enter, EKeys::SpaceBar, EKeys::Gamepad_FaceButton_Bottom }))
		{
			MudarItem(0, true);
			if (!bMenuAberto) return;
		}
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
		if (Sob != INDEX_NONE && bMexeu) { MenuIndice = Sob; bFocoItens = true; }
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
					EntrarCategoria((ECategoriaMenu)c);
					if (!bMenuAberto) return;
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
	else if (bMenuPrincipal)
	{
		TickMenuPrincipal(DtReal);
	}
	else
	{
		TeclasAtalho();
		if (!bMenuAberto && !bMenuPrincipal) TickObjetivo(DeltaSeconds);
	}
	if (bMenuPrincipal) MPRelogio += DtReal;
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

// ------------------------------------------------------------------ percurso (voo de teste e fundo do menu principal)

void APredioGameMode::MontarPercurso()
{
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
}

FTransform APredioGameMode::PontoNoPercurso(float S) const
{
	const int32 N = TourPontos.Num();
	if (N == 0) return FTransform::Identity;
	if (N == 1) return FTransform(TourPontos[0]);
	S = FMath::Clamp(S, 0.f, (float)(N - 1) - 0.001f);
	const int32 I = FMath::Clamp(FMath::FloorToInt(S), 0, N - 2);
	const float T = S - I;
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
	FVector Dir = CR(P0, P1, P2, P3, FMath::Min(T + 0.05f, 1.f)) - Pos;
	if (Dir.IsNearlyZero()) Dir = P2 - P1;
	FRotator Rot = Dir.Rotation();
	Rot.Pitch = FMath::Clamp(Rot.Pitch * 0.5f, -25.f, 25.f);
	Rot.Roll = 0.f;
	return FTransform(Rot, Pos);
}

// ------------------------------------------------------------------ objetivos

TArray<EObjetivo> APredioGameMode::ObjetivosDoCartao(ECartaoMapa C)
{
	switch (C)
	{
	case ECartaoMapa::Campo: return { EObjetivo::ArosOrdem, EObjetivo::ArosRelogio, EObjetivo::Livre };
	case ECartaoMapa::Predio: return { EObjetivo::Topo, EObjetivo::Livre };
	default: return {};
	}
}

TArray<EObjetivo> APredioGameMode::ObjetivosDoMapa() const
{
	return ObjetivosDoCartao(bEhCampo ? ECartaoMapa::Campo : ECartaoMapa::Predio);
}

FString APredioGameMode::NomeObjetivo(EObjetivo O)
{
	switch (O)
	{
	case EObjetivo::Topo: return TEXT("Chegue ao topo");
	case EObjetivo::ArosOrdem: return TEXT("Aros em ordem");
	case EObjetivo::ArosRelogio: return TEXT("Contra o relógio");
	default: return TEXT("Voo livre");
	}
}

FString APredioGameMode::DescricaoObjetivo(EObjetivo O)
{
	switch (O)
	{
	case EObjetivo::Topo: return TEXT("Suba do térreo até a cobertura o mais rápido que puder");
	case EObjetivo::ArosOrdem: return TEXT("Passe por todos os aros na ordem — o próximo fica marcado");
	case EObjetivo::ArosRelogio: return TEXT("Cada aro dá mais tempo; se o relógio zerar, acabou");
	default: return TEXT("Sem cronômetro: explore o mapa à vontade");
	}
}

FString APredioGameMode::TextoTempo(float Segundos, bool bDecimos)
{
	Segundos = FMath::Max(0.f, Segundos);
	const int32 Min = FMath::FloorToInt(Segundos / 60.f);
	const float Seg = Segundos - Min * 60.f;
	if (bDecimos)
	{
		const int32 Dec = FMath::Clamp(FMath::FloorToInt((Seg - FMath::FloorToInt(Seg)) * 10.f), 0, 9);
		return FString::Printf(TEXT("%d:%02d.%d"), Min, FMath::FloorToInt(Seg), Dec);
	}
	return FString::Printf(TEXT("%d:%02d"), Min, FMath::FloorToInt(Seg));
}

FString APredioGameMode::NomeMedalha(int32 M)
{
	switch (M)
	{
	case 3: return TEXT("OURO");
	case 2: return TEXT("PRATA");
	case 1: return TEXT("BRONZE");
	default: return TEXT("SEM MEDALHA");
	}
}

FString APredioGameMode::TextoLocal() const
{
	return bEhCampo ? FString(TEXT("CAMPO BAIANO")) : TextoAndar(AndarAtual);
}

float APredioGameMode::AlturaTopo() const
{
	return CotaTerreo + (NumAndares - 1) * AlturaAndar + 60.f;
}

float APredioGameMode::ComprimentoCircuito() const
{
	const ADronePawn* D = Drone();
	FVector Ant = D ? D->Inicio.GetLocation() : (Aros.Num() ? Aros[0].GetLocation() : FVector::ZeroVector);
	float L = 0.f;
	for (const FTransform& A : Aros)
	{
		L += FVector::Dist(Ant, A.GetLocation());
		Ant = A.GetLocation();
	}
	return L;
}

float APredioGameMode::BonusDoAro(int32 I) const
{
	// tempo folgado: média de 6 m/s entre um aro e outro + uma sobra fixa
	if (!Aros.IsValidIndex(I)) return 0.f;
	const ADronePawn* D = Drone();
	const FVector De = I == 0 ? (D ? D->Inicio.GetLocation() : Aros[0].GetLocation()) : Aros[I - 1].GetLocation();
	const float Dist = FVector::Dist(De, Aros[I].GetLocation());
	return FMath::RoundToFloat(Dist / 600.f + (I == 0 ? 10.f : 4.f));
}

float APredioGameMode::LimiteMedalha(int32 M) const
{
	auto Arred5 = [](float V) { return FMath::CeilToFloat(V / 5.f) * 5.f; };
	if (Objetivo == EObjetivo::Topo)
	{
		return M >= 3 ? 80.f : (M == 2 ? 120.f : 180.f); // 1:20 / 2:00 / 3:00 (folgados, como combinado)
	}
	if (Objetivo == EObjetivo::ArosOrdem)
	{
		const float L = ComprimentoCircuito();
		return M >= 3 ? Arred5(L / 900.f + 8.f) : (M == 2 ? Arred5(L / 650.f + 15.f) : Arred5(L / 420.f + 25.f));
	}
	return 0.f;
}

float APredioGameMode::RecordeAtual() const
{
	const FAjustesDrone& C = FAjustesDrone::Get();
	switch (Objetivo)
	{
	case EObjetivo::Topo: return C.RecordeTopo;
	case EObjetivo::ArosOrdem: return C.RecordeAros;
	case EObjetivo::ArosRelogio: return C.RecordeRelogio;
	default: return 0.f;
	}
}

void APredioGameMode::MontarAros()
{
	AtoresAros.Sort([](const TPair<int32, TWeakObjectPtr<AActor>>& A, const TPair<int32, TWeakObjectPtr<AActor>>& B) { return A.Key < B.Key; });
	Aros.Reset();
	for (const TPair<int32, TWeakObjectPtr<AActor>>& P : AtoresAros)
	{
		if (P.Value.IsValid()) Aros.Add(P.Value->GetActorTransform());
	}
}

void APredioGameMode::MostrarAros()
{
	const bool bDesafioAros = Objetivo == EObjetivo::ArosOrdem || Objetivo == EObjetivo::ArosRelogio;
	for (int32 i = 0; i < AtoresAros.Num(); ++i)
	{
		AActor* A = AtoresAros[i].Value.Get();
		if (!A) continue;
		// aro já passado some (e para de colidir) até o desafio recomeçar
		const bool bVer = !(bDesafioAros && Estado == EEstadoDesafio::Correndo && i < ProximoAro);
		A->SetActorHiddenInGame(!bVer);
		A->SetActorEnableCollision(bVer);
	}
}

void APredioGameMode::ReiniciarDesafio()
{
	Estado = EEstadoDesafio::Pronto;
	TempoDesafio = 0.f;
	ProximoAro = 0;
	Medalha = 0;
	bNovoRecorde = false;
	TempoNoResultado = 0.f;
	TempoDesdeAro = 99.f;
	BonusUltimoAro = 0.f;
	TempoRestante = BonusDoAro(0);
	MostrarAros();
	if (const ADronePawn* D = Drone()) UltimaPosDrone = D->GetActorLocation();
}

void APredioGameMode::IniciarObjetivo(EObjetivo O, bool bRecolocar)
{
	if (!ObjetivosDoMapa().Contains(O)) O = EObjetivo::Livre;
	Objetivo = O;
	ADronePawn* D = Drone();
	if (bRecolocar && D)
	{
		D->Recomecar(D->Inicio);
	}
	if (D) UltimosReinicios = D->Reinicios;
	ReiniciarDesafio();
	if (D && !bTour)
	{
		FString Dica;
		switch (O)
		{
		case EObjetivo::Topo: Dica = TEXT("CHEGUE AO TOPO — o cronômetro começa quando você decolar"); break;
		case EObjetivo::ArosOrdem: Dica = TEXT("AROS EM ORDEM — siga a marca do próximo aro"); break;
		case EObjetivo::ArosRelogio: Dica = TEXT("CONTRA O RELÓGIO — cada aro dá mais tempo"); break;
		default: Dica = TEXT("VOO LIVRE"); break;
		}
		D->MostrarMensagem(Dica, 4.f);
	}
	Registrar(FString::Printf(TEXT("objetivo: %s"), *NomeObjetivo(O)));
}

void APredioGameMode::ConcluirDesafio(bool bSucesso)
{
	Estado = bSucesso ? EEstadoDesafio::Concluido : EEstadoDesafio::Falhou;
	TempoNoResultado = 0.f;
	Medalha = 0;
	bNovoRecorde = false;
	if (bSucesso)
	{
		FAjustesDrone& C = FAjustesDrone::Get();
		if (Objetivo == EObjetivo::ArosRelogio)
		{
			Medalha = TempoRestante >= 20.f ? 3 : (TempoRestante >= 10.f ? 2 : 1);
		}
		else
		{
			for (int32 M = 3; M >= 1; --M)
			{
				if (TempoDesafio <= LimiteMedalha(M)) { Medalha = M; break; }
			}
		}
		int32* Med = Objetivo == EObjetivo::Topo ? &C.MedalhaTopo : (Objetivo == EObjetivo::ArosOrdem ? &C.MedalhaAros : &C.MedalhaRelogio);
		if (Medalha > *Med) { *Med = Medalha; C.Salvar(); }
		float* Rec = Objetivo == EObjetivo::Topo ? &C.RecordeTopo : (Objetivo == EObjetivo::ArosOrdem ? &C.RecordeAros : &C.RecordeRelogio);
		if (*Rec <= 0.f || TempoDesafio < *Rec)
		{
			*Rec = TempoDesafio;
			bNovoRecorde = true;
			C.Salvar();
		}
	}
	MostrarAros();
	Registrar(FString::Printf(TEXT("desafio %s: %s  tempo %s  medalha %d  recorde novo %d"),
		*NomeObjetivo(Objetivo), bSucesso ? TEXT("concluido") : TEXT("falhou"), *TextoTempo(TempoDesafio), Medalha, bNovoRecorde ? 1 : 0));
}

void APredioGameMode::TickObjetivo(float Dt)
{
	ADronePawn* D = Drone();
	if (!D) return;
	const FVector P = D->GetActorLocation();

	// voltou ao início (R / X, quebrou o drone, menu): o desafio recomeça
	if (D->Reinicios != UltimosReinicios)
	{
		UltimosReinicios = D->Reinicios;
		const bool bEstava = Estado == EEstadoDesafio::Correndo;
		ReiniciarDesafio();
		if (bEstava && Objetivo != EObjetivo::Livre) D->MostrarMensagem(TEXT("Desafio recomeçou"), 2.f);
		UltimaPosDrone = D->GetActorLocation();
		return;
	}
	TempoDesdeAro += Dt;

	if (Estado == EEstadoDesafio::Concluido || Estado == EEstadoDesafio::Falhou)
	{
		TempoNoResultado += Dt;
		if (TempoNoResultado > 1.f && (Apertou(EKeys::Enter) || Apertou(EKeys::Gamepad_FaceButton_Bottom)))
		{
			D->Recomecar(D->Inicio); // o desafio recomeça no próximo quadro
		}
		UltimaPosDrone = P;
		return;
	}
	if (Objetivo == EObjetivo::Livre)
	{
		UltimaPosDrone = P;
		return;
	}
	if (Estado == EEstadoDesafio::Pronto && FVector::Dist(P, D->Inicio.GetLocation()) > 150.f)
	{
		Estado = EEstadoDesafio::Correndo;
		TempoDesafio = 0.f;
		MostrarAros();
	}
	if (Estado != EEstadoDesafio::Correndo)
	{
		UltimaPosDrone = P;
		return;
	}

	TempoDesafio += Dt;
	if (Objetivo == EObjetivo::Topo)
	{
		if (AndarAtual == NumAndares - 1 && P.Z > AlturaTopo())
		{
			ConcluirDesafio(true);
		}
	}
	else if (Aros.IsValidIndex(ProximoAro))
	{
		// passou pelo plano do aro, por dentro do círculo (vale nos dois sentidos)
		const FTransform& A = Aros[ProximoAro];
		const FVector N = A.GetRotation().GetForwardVector();
		const FVector C = A.GetLocation();
		const float D0 = FVector::DotProduct(UltimaPosDrone - C, N);
		const float D1 = FVector::DotProduct(P - C, N);
		if ((D0 < 0.f) != (D1 < 0.f) && FVector::Dist(UltimaPosDrone, P) < 600.f)
		{
			const float T = D0 / (D0 - D1);
			const FVector X = UltimaPosDrone + (P - UltimaPosDrone) * T;
			if (FVector::Dist(X, C) < RaioAro)
			{
				++ProximoAro;
				TempoDesdeAro = 0.f;
				BonusUltimoAro = 0.f;
				if (Objetivo == EObjetivo::ArosRelogio && Aros.IsValidIndex(ProximoAro))
				{
					BonusUltimoAro = BonusDoAro(ProximoAro);
					TempoRestante += BonusUltimoAro;
				}
				MostrarAros();
				if (ProximoAro >= Aros.Num())
				{
					ConcluirDesafio(true);
					UltimaPosDrone = P;
					return;
				}
			}
		}
		if (Objetivo == EObjetivo::ArosRelogio)
		{
			TempoRestante -= Dt;
			if (TempoRestante <= 0.f)
			{
				TempoRestante = 0.f;
				ConcluirDesafio(false);
			}
		}
	}
	UltimaPosDrone = P;
}

// ------------------------------------------------------------------ menu principal (jogo único)
//  ABERTURA (drone E88 voando pelo prédio, câmera perseguindo)  ->  MAPAS (cartões + progresso)  ->  DESAFIOS do mapa

bool APredioGameMode::CartaoDisponivel(int32 C) const
{
	switch ((ECartaoMapa)C)
	{
	case ECartaoMapa::Predio: return true;
	case ECartaoMapa::Campo: return bCampoExiste;
	default: return false; // usina: em construção
	}
}

FString APredioGameMode::NomeMapa(int32 Cartao)
{
	switch ((ECartaoMapa)Cartao)
	{
	case ECartaoMapa::Campo: return TEXT("FAZENDA");
	case ECartaoMapa::Predio: return TEXT("PRÉDIO EM OBRA");
	default: return TEXT("USINA ABANDONADA");
	}
}

int32 APredioGameMode::MedalhaDe(EObjetivo O) const
{
	const FAjustesDrone& C = FAjustesDrone::Get();
	switch (O)
	{
	case EObjetivo::Topo: return C.MedalhaTopo;
	case EObjetivo::ArosOrdem: return C.MedalhaAros;
	case EObjetivo::ArosRelogio: return C.MedalhaRelogio;
	default: return 0;
	}
}

int32 APredioGameMode::MedalhasMapa(int32 Cartao, int32& Possiveis) const
{
	int32 Tem = 0;
	Possiveis = 0;
	for (const EObjetivo O : ObjetivosDoCartao((ECartaoMapa)Cartao))
	{
		if (O == EObjetivo::Livre) continue;
		Possiveis += 3;
		Tem += MedalhaDe(O);
	}
	return Tem;
}

float APredioGameMode::ProgressoMapa(int32 Cartao) const
{
	int32 P = 0;
	const int32 T = MedalhasMapa(Cartao, P);
	return P > 0 ? (float)T / (float)P : 0.f;
}

int32 APredioGameMode::NumLinhasMP() const
{
	return ObjetivosDoCartao((ECartaoMapa)MPCartao).Num() + 1; // + Voltar
}

bool APredioGameMode::LinhaEhObjetivo(int32 L, EObjetivo& Out) const
{
	const TArray<EObjetivo> O = ObjetivosDoCartao((ECartaoMapa)MPCartao);
	if (!O.IsValidIndex(L)) return false;
	Out = O[L];
	return true;
}

FString APredioGameMode::NomeLinhaMP(int32 L) const
{
	EObjetivo O = EObjetivo::Livre;
	if (LinhaEhObjetivo(L, O)) return NomeObjetivo(O);
	return TEXT("Voltar aos mapas");
}

FString APredioGameMode::DescricaoLinhaMP(int32 L) const
{
	EObjetivo O = EObjetivo::Livre;
	if (LinhaEhObjetivo(L, O)) return DescricaoObjetivo(O);
	return TEXT("Escolher outro mapa");
}

FString APredioGameMode::ExtraLinhaMP(int32 L) const
{
	EObjetivo O = EObjetivo::Livre;
	if (!LinhaEhObjetivo(L, O)) return FString();
	if (O == EObjetivo::Livre) return TEXT("sem cronômetro");
	const FAjustesDrone& C = FAjustesDrone::Get();
	const float R = O == EObjetivo::Topo ? C.RecordeTopo : (O == EObjetivo::ArosOrdem ? C.RecordeAros : C.RecordeRelogio);
	return R > 0.f ? FString::Printf(TEXT("recorde %s"), *TextoTempo(R)) : FString(TEXT("sem recorde ainda"));
}

void APredioGameMode::IrParaTela(ETelaMP T)
{
	TelaMP = T;
	MPTelaDesde = 0.f;
	MenuMudouEm = FPlatformTime::Seconds();
	if (T == ETelaMP::Desafios) MPLinha = 0;
	Registrar(FString::Printf(TEXT("menu principal: tela %d"), (int32)T));
}

void APredioGameMode::CriarDroneTitulo()
{
	if (DroneTitulo.IsValid()) return;
	UStaticMesh* Corpo = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Drone/E88_Corpo.E88_Corpo"));
	UStaticMesh* Helice = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Drone/E88_Helice.E88_Helice"));
	if (!Corpo) return; // sem o modelo: a abertura fica só com o voo da câmera
	AActor* A = GetWorld()->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity);
	if (!A) return;
	USceneComponent* Raiz = NewObject<USceneComponent>(A, TEXT("Raiz"));
	Raiz->SetMobility(EComponentMobility::Movable);
	A->SetRootComponent(Raiz);
	Raiz->RegisterComponent();
	auto Peca = [A, Raiz](UStaticMesh* M, const TCHAR* Nome, const FVector& Pos)
	{
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(A, Nome);
		C->SetMobility(EComponentMobility::Movable);
		C->SetStaticMesh(M);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetupAttachment(Raiz);
		C->SetRelativeLocation(Pos);
		C->RegisterComponent();
		A->AddInstanceComponent(C);
		return C;
	};
	Peca(Corpo, TEXT("Corpo"), FVector::ZeroVector);
	HelicesTitulo.Reset();
	if (Helice)
	{
		const FVector Eixos[] = { FVector(9.15f, 9.31f, 1.43f), FVector(9.16f, -9.31f, 1.43f), FVector(-9.14f, 9.34f, 1.43f), FVector(-9.17f, -9.34f, 1.43f) };
		const TCHAR* Nomes[] = { TEXT("Helice0"), TEXT("Helice1"), TEXT("Helice2"), TEXT("Helice3") };
		for (int32 i = 0; i < 4; ++i) HelicesTitulo.Add(Peca(Helice, Nomes[i], Eixos[i]));
	}
	A->SetActorScale3D(FVector(2.4f)); // maior que o real para aparecer bem na abertura
	DroneTitulo = A;
}

void APredioGameMode::DestruirDroneTitulo()
{
	if (AActor* A = DroneTitulo.Get()) A->Destroy();
	DroneTitulo.Reset();
	HelicesTitulo.Reset();
}

void APredioGameMode::EntrarMenuPrincipal()
{
	bMenuPrincipal = true;
	MPRelogio = 0.f;
	MPVooS = 0.f;
	MPLinha = 0;
	MPTitulo = 0;
	MPAviso.Reset();
	IrParaTela(ETelaMP::Titulo);
	Objetivo = EObjetivo::Livre;
	ReiniciarDesafio();
	MenuMudouEm = FPlatformTime::Seconds();
	if (ADronePawn* D = Drone())
	{
		D->bModoTour = true;   // câmera livre, sem som e sem OSD: o drone vira a câmera do voo de fundo
		D->bCongelado = true;
		if (D->Audio) D->Audio->SetPaused(true);
	}
	CriarDroneTitulo();
	if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
	{
		FInputModeGameAndUI Modo;
		Modo.SetHideCursorDuringCapture(false);
		Modo.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
		PC->SetInputMode(Modo);
		PC->bShowMouseCursor = true;
	}
	Registrar(TEXT("menu principal"));
}

void APredioGameMode::SairDoMenuPrincipal()
{
	bMenuPrincipal = false;
	DestruirDroneTitulo();
	if (ADronePawn* D = Drone())
	{
		D->bModoTour = false;
		D->bCongelado = false;
		if (D->Audio) D->Audio->SetPaused(false);
	}
	if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
	{
		PC->bShowMouseCursor = false;
		PC->SetInputMode(FInputModeGameOnly());
	}
	MenuMudouEm = FPlatformTime::Seconds();
}

void APredioGameMode::IrParaMapa(const FString& Mapa, const FString& Opcoes)
{
	bCarregando = true;
	Registrar(FString::Printf(TEXT("abrindo %s %s"), *Mapa, *Opcoes));
	FAjustesDrone::Get().Salvar();
	UGameplayStatics::SetGamePaused(this, false);
	UGameplayStatics::OpenLevel(this, FName(*Mapa), true, Opcoes);
}

void APredioGameMode::ConfirmarMenuPrincipal()
{
	if (TelaMP == ETelaMP::Titulo)
	{
		if (MPTitulo == 0) { IrParaTela(ETelaMP::Mapas); return; }
		if (MPTitulo == 1)
		{
			AbrirMenu(true);
			CategoriaSel = (int32)ECategoriaMenu::Sensibilidade;
			return;
		}
		FAjustesDrone::Get().Salvar();
		UKismetSystemLibrary::QuitGame(this, GetWorld()->GetFirstPlayerController(), EQuitPreference::Quit, false);
		return;
	}
	if (TelaMP == ETelaMP::Mapas)
	{
		if (!CartaoDisponivel(MPCartao))
		{
			MPAviso = (ECartaoMapa)MPCartao == ECartaoMapa::Usina ? TEXT("A usina ainda está sendo construída — em breve!") : TEXT("Esse mapa ainda não foi instalado nesta versão");
			MPAvisoT = 3.f;
			return;
		}
		IrParaTela(ETelaMP::Desafios);
		return;
	}
	// desafios
	EObjetivo O = EObjetivo::Livre;
	if (!LinhaEhObjetivo(MPLinha, O))
	{
		IrParaTela(ETelaMP::Mapas);
		return;
	}
	if ((ECartaoMapa)MPCartao == ECartaoMapa::Campo)
	{
		IrParaMapa(TEXT("/Game/Mapas/Campo"), FString::Printf(TEXT("jogo?modo=%d"), (int32)O));
		return;
	}
	if (bEhCampo)
	{
		IrParaMapa(TEXT("/Game/Mapas/Predio"), FString::Printf(TEXT("jogo?modo=%d"), (int32)O));
		return;
	}
	// prédio: já estamos nele, começa aqui mesmo
	SairDoMenuPrincipal();
	IniciarObjetivo(O, true);
	AtualizarAndares(true);
}

void APredioGameMode::TickMenuPrincipal(float Dt)
{
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	ADronePawn* D = Drone();
	if (MPAvisoT > 0.f) MPAvisoT -= Dt;
	MPTelaDesde += Dt;

	// voo de fundo: o E88 voa pelo percurso do prédio e a câmera vai atrás dele
	if (D && TourPontos.Num() >= 2)
	{
		const int32 N = TourPontos.Num();
		auto Comp = [this, N](float S)
		{
			const int32 I = FMath::Clamp(FMath::FloorToInt(S), 0, N - 2);
			return FMath::Max(50.f, (float)FVector::Dist(TourPontos[I], TourPontos[I + 1]));
		};
		MPVooS += Dt * 150.f / Comp(MPVooS);
		bool bVolta = false;
		if (MPVooS >= N - 1) { MPVooS = 0.35f; bVolta = true; }
		const float SDrone = MPVooS;
		const float SCam = FMath::Max(0.f, SDrone - 135.f / Comp(SDrone));
		const FTransform TD = PontoNoPercurso(SDrone);
		const FTransform TC = PontoNoPercurso(SCam);
		const float Bal = FMath::Sin(MPRelogio * 1.7f) * 4.f;
		FVector PosDrone = TD.GetLocation() + FVector(0, 0, 8.f + Bal);
		FVector PosCam = TC.GetLocation() + FVector(0, 0, 32.f);
		if (AActor* A = DroneTitulo.Get())
		{
			const FRotator Antes = A->GetActorRotation();
			FRotator Alvo = TD.Rotator();
			const float GiroYaw = FMath::FindDeltaAngleDegrees(Antes.Yaw, Alvo.Yaw);
			Alvo.Pitch = -9.f + Alvo.Pitch * 0.5f;                       // inclinado para a frente (está voando)
			Alvo.Roll = FMath::Clamp(GiroYaw * 2.5f, -28.f, 28.f);      // deita nas curvas
			const FRotator R = bVolta ? Alvo : FMath::RInterpTo(Antes, Alvo, Dt, 3.5f);
			A->SetActorLocationAndRotation(PosDrone, R);
			AnguloHelices = FMath::Fmod(AnguloHelices + Dt * 2600.f, 360.f);
			for (int32 i = 0; i < HelicesTitulo.Num(); ++i)
			{
				if (UStaticMeshComponent* H = HelicesTitulo[i].Get()) H->SetRelativeRotation(FRotator(0.f, (i == 0 || i == 3) ? AnguloHelices : -AnguloHelices, 0.f));
			}
			// a câmera olha para o drone, um pouco à frente dele (ele fica no terço direito da tela)
			const FVector Olhar = PosDrone + TD.GetRotation().GetForwardVector() * 60.f - TD.GetRotation().GetRightVector() * 22.f;
			const FRotator RC = (Olhar - PosCam).Rotation();
			D->SetActorLocationAndRotation(PosCam, bVolta ? RC : FMath::RInterpTo(D->GetActorRotation(), RC, Dt, 4.f));
		}
		else
		{
			const FRotator R = bVolta ? TD.Rotator() : FMath::RInterpTo(D->GetActorRotation(), TD.Rotator(), Dt, 2.f);
			D->SetActorLocationAndRotation(TD.GetLocation(), R);
		}
		const float Fim = (N - 1) - MPVooS;
		MPEscuro = FMath::Clamp(FMath::Max(1.f - (MPVooS - 0.35f) / 0.3f, 1.f - Fim / 0.35f), 0.f, 1.f);
	}
	else
	{
		MPEscuro = 0.f;
	}

	// prints de conferência (-fotomenu): abertura, mapas, desafios do campo, sai
	if (bFotoMenu)
	{
		FotoMenuT += Dt;
		auto Foto = [this](const TCHAR* Nome) { FScreenshotRequest::RequestScreenshot(PastaTestes / Nome, true, false); };
		if (FotoMenuFase == 0 && FotoMenuT > 7.f) { Foto(TEXT("menu_1_abertura.png")); FotoMenuFase = 1; }
		else if (FotoMenuFase == 1 && FotoMenuT > 8.f) { IrParaTela(ETelaMP::Mapas); MPCartao = (int32)ECartaoMapa::Campo; FotoMenuFase = 2; }
		else if (FotoMenuFase == 2 && FotoMenuT > 10.f) { Foto(TEXT("menu_2_mapas.png")); FotoMenuFase = 3; }
		else if (FotoMenuFase == 3 && FotoMenuT > 11.f) { MPCartao = (int32)ECartaoMapa::Usina; FotoMenuFase = 4; }
		else if (FotoMenuFase == 4 && FotoMenuT > 12.5f) { Foto(TEXT("menu_3_usina.png")); FotoMenuFase = 5; }
		else if (FotoMenuFase == 5 && FotoMenuT > 13.5f) { MPCartao = (int32)ECartaoMapa::Campo; IrParaTela(ETelaMP::Desafios); FotoMenuFase = 6; }
		else if (FotoMenuFase == 6 && FotoMenuT > 15.f) { Foto(TEXT("menu_4_desafios.png")); FotoMenuFase = 7; }
		else if (FotoMenuFase == 7 && FotoMenuT > 16.f) { AbrirMenu(true); CategoriaSel = (int32)ECategoriaMenu::Video; FotoMenuFase = 8; }
		else if (FotoMenuFase == 8 && FotoMenuT > 17.5f) { Foto(TEXT("menu_5_secoes.png")); FotoMenuFase = 9; }
		else if (FotoMenuFase == 9 && FotoMenuT > 18.5f) { EntrarCategoria(ECategoriaMenu::Audio); FotoMenuFase = 10; }
		else if (FotoMenuFase == 10 && FotoMenuT > 20.f) { Foto(TEXT("menu_6_audio.png")); FotoMenuFase = 11; }
		else if (FotoMenuFase == 11 && FotoMenuT > 21.f) { FPlatformMisc::RequestExit(false); }
		return;
	}

	if (!PC || bCarregando) return;
	if (FPlatformTime::Seconds() - MenuMudouEm < 0.3) return;
	auto Apertou = [this](std::initializer_list<FKey> Teclas)
	{
		for (const FKey& K : Teclas) if (this->Apertou(K)) return true;
		return false;
	};
	int32 V = 0, Hz = 0;
	if (Apertou({ EKeys::Up, EKeys::W, EKeys::Gamepad_DPad_Up })) V = -1;
	if (Apertou({ EKeys::Down, EKeys::S, EKeys::Gamepad_DPad_Down })) V = 1;
	if (Apertou({ EKeys::Left, EKeys::A, EKeys::Gamepad_DPad_Left, EKeys::Gamepad_LeftShoulder, EKeys::Q })) Hz = -1;
	if (Apertou({ EKeys::Right, EKeys::D, EKeys::Gamepad_DPad_Right, EKeys::Gamepad_RightShoulder, EKeys::E })) Hz = 1;
	const float SY = PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftY);
	const float SX = PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftX);
	const int32 DirV = SY > 0.6f ? -1 : (SY < -0.6f ? 1 : 0);
	const int32 DirH = SX > 0.6f ? 1 : (SX < -0.6f ? -1 : 0);
	if (DirV != 0)
	{
		if (DirV != UltimaDirVert) { V = DirV; RepeticaoV = 0.35f; }
		else if ((RepeticaoV -= Dt) <= 0.f) { V = DirV; RepeticaoV = 0.14f; }
	}
	if (DirH != 0 && DirH != UltimaDirHoriz) Hz = DirH;
	UltimaDirVert = DirV;
	UltimaDirHoriz = DirH;
	const bool bConfirma = Apertou({ EKeys::Enter, EKeys::SpaceBar, EKeys::Gamepad_FaceButton_Bottom });
	const bool bVolta = Apertou({ EKeys::Escape, EKeys::Gamepad_FaceButton_Right, EKeys::BackSpace });
	const bool bStart = Apertou({ EKeys::Gamepad_Special_Right });

	switch (TelaMP)
	{
	case ETelaMP::Titulo:
		if (V != 0) MPTitulo = (MPTitulo + V + 3) % 3;
		if (bVolta) MPTitulo = 2;
		if (bStart) { MPTitulo = 1; ConfirmarMenuPrincipal(); return; }
		break;
	case ETelaMP::Mapas:
		if (Hz != 0) MPCartao = (MPCartao + Hz + (int32)ECartaoMapa::Total) % (int32)ECartaoMapa::Total;
		if (bVolta) { IrParaTela(ETelaMP::Titulo); return; }
		break;
	case ETelaMP::Desafios:
		if (V != 0) { const int32 NL = NumLinhasMP(); MPLinha = (MPLinha + V + NL) % NL; }
		if (bVolta) { IrParaTela(ETelaMP::Mapas); return; }
		break;
	}
	if (bConfirma)
	{
		ConfirmarMenuPrincipal();
		return;
	}

	// mouse
	float MX = 0.f, MY = 0.f;
	if (PC->GetMousePosition(MX, MY))
	{
		const FVector2D M(MX, MY);
		const bool bMexeu = FVector2D::Distance(M, UltimoMouse) > 1.5f;
		UltimoMouse = M;
		const bool bClique = this->Apertou(EKeys::LeftMouseButton);
		if (this->Apertou(EKeys::RightMouseButton) && TelaMP != ETelaMP::Titulo)
		{
			IrParaTela(TelaMP == ETelaMP::Desafios ? ETelaMP::Mapas : ETelaMP::Titulo);
			return;
		}
		if (bClique && AreaVoltarMP.bIsValid && AreaVoltarMP.IsInside(M) && TelaMP != ETelaMP::Titulo)
		{
			IrParaTela(TelaMP == ETelaMP::Desafios ? ETelaMP::Mapas : ETelaMP::Titulo);
			return;
		}
		const TArray<FBox2D>& Areas = TelaMP == ETelaMP::Titulo ? AreaTitulo : (TelaMP == ETelaMP::Mapas ? AreaCartoes : AreaLinhas);
		for (int32 i = 0; i < Areas.Num(); ++i)
		{
			if (!Areas[i].bIsValid || !Areas[i].IsInside(M)) continue;
			int32& Sel = TelaMP == ETelaMP::Titulo ? MPTitulo : (TelaMP == ETelaMP::Mapas ? MPCartao : MPLinha);
			if (bMexeu || bClique) Sel = i;
			if (bClique)
			{
				ConfirmarMenuPrincipal();
				return;
			}
		}
	}
}

// ------------------------------------------------------------------ capim do campo (espalhado ao abrir o mapa)

void APredioGameMode::EspalharGrama()
{
	UStaticMesh* Malha = nullptr;
	TArray<TPair<int32, FVector>> PontosEstrada;
	FVector4 Acude(0, 0, 0, 0); // centro x, y e raios x, y (cm)
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		for (const FName& Tag : It->Tags)
		{
			const FString T = Tag.ToString();
			if (T == TEXT("ModeloGrama"))
			{
				if (const UStaticMeshComponent* C = It->FindComponentByClass<UStaticMeshComponent>()) Malha = C->GetStaticMesh();
			}
			else if (T.StartsWith(TEXT("Estrada_")))
			{
				PontosEstrada.Add(TPair<int32, FVector>(FCString::Atoi(*T.RightChop(8)), It->GetActorLocation()));
			}
			else if (T.StartsWith(TEXT("Acude_")))
			{
				TArray<FString> P;
				T.RightChop(6).ParseIntoArray(P, TEXT("_"));
				if (P.Num() == 4) Acude = FVector4(FCString::Atof(*P[0]), FCString::Atof(*P[1]), FCString::Atof(*P[2]), FCString::Atof(*P[3]));
			}
		}
	}
	if (!Malha) return;
	PontosEstrada.Sort([](const TPair<int32, FVector>& A, const TPair<int32, FVector>& B) { return A.Key < B.Key; });

	auto DistEstrada = [&PontosEstrada](const FVector2D& P)
	{
		float Melhor = 1e9f;
		for (int32 i = 0; i + 1 < PontosEstrada.Num(); ++i)
		{
			const FVector2D A(PontosEstrada[i].Value), B(PontosEstrada[i + 1].Value);
			const FVector2D AB = B - A;
			const float T = FMath::Clamp(FVector2D::DotProduct(P - A, AB) / FMath::Max(1.f, AB.SizeSquared()), 0.f, 1.f);
			Melhor = FMath::Min(Melhor, FVector2D::Distance(P, A + AB * T));
		}
		return Melhor;
	};

	AActor* Dono = GetWorld()->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity);
	if (!Dono) return;
	UHierarchicalInstancedStaticMeshComponent* H = NewObject<UHierarchicalInstancedStaticMeshComponent>(Dono, TEXT("Capim"));
	H->SetMobility(EComponentMobility::Movable);
	H->SetStaticMesh(Malha);
	H->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	H->SetCastShadow(false);           // milhares de touceiras: sem sombra própria (o FPS agradece)
	H->SetCullDistances(0, 14000);
	Dono->SetRootComponent(H);
	H->RegisterComponent();
	Dono->AddInstanceComponent(H);

	FRandomStream R(2026);
	TArray<FTransform> Ts;
	FCollisionQueryParams Q(SCENE_QUERY_STAT(Capim), true);
	struct FFaixa { float R0, R1; int32 N; };
	const FFaixa Faixas[] = { { 600.f, 4500.f, 9000 }, { 4500.f, 13000.f, 11000 } };
	for (const FFaixa& F : Faixas)
	{
		int32 Feitos = 0;
		for (int32 Tent = 0; Tent < F.N * 3 && Feitos < F.N; ++Tent)
		{
			const float Ang = R.FRand() * 2.f * PI;
			const float Rad = FMath::Sqrt(FMath::Lerp(F.R0 * F.R0, F.R1 * F.R1, R.FRand()));
			const FVector2D P(FMath::Cos(Ang) * Rad, FMath::Sin(Ang) * Rad);
			if (DistEstrada(P) < 480.f) continue;
			if (Acude.Z > 0.f && FMath::Square((P.X - Acude.X) / Acude.Z) + FMath::Square((P.Y - Acude.Y) / Acude.W) < 1.f) continue;
			FHitResult Hit;
			if (!GetWorld()->LineTraceSingleByChannel(Hit, FVector(P, 30000.f), FVector(P, -30000.f), ECC_Visibility, Q)) continue;
			if (!Hit.GetActor() || !Hit.GetActor()->ActorHasTag(TEXT("Terreno"))) continue; // em cima de pedra, árvore, base...
			if (Hit.ImpactNormal.Z < 0.82f) continue;
			const float E = R.FRandRange(0.75f, 1.45f);
			Ts.Add(FTransform(FRotator(0.f, R.FRand() * 360.f, 0.f), Hit.ImpactPoint - FVector(0, 0, 4.f), FVector(E, E, E * R.FRandRange(0.85f, 1.25f))));
			++Feitos;
		}
	}
	H->AddInstances(Ts, false, true);
	UE_LOG(LogPredio, Log, TEXT("Campo: %d touceiras de capim"), Ts.Num());
}
