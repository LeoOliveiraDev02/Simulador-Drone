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
#include "Camera/PlayerCameraManager.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Sound/SoundBase.h"
#include "Materials/MaterialInstanceDynamic.h"
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

int32 APredioGameMode::CartaoDoMapa = (int32)ECartaoMapa::Predio;

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

	// -mapa=Campo na linha de comando (testes): o jogo sempre abre no prédio; daqui pula para a fazenda
	FString MapaCmd;
	if (FParse::Value(FCommandLine::Get(), TEXT("mapa="), MapaCmd) && !UGameplayStatics::HasOption(OptionsString, TEXT("jogo"))
		&& (MapaCmd.Equals(TEXT("Campo"), ESearchCase::IgnoreCase) || MapaCmd.Equals(TEXT("Vitrine"), ESearchCase::IgnoreCase)
			|| MapaCmd.Equals(TEXT("Usina"), ESearchCase::IgnoreCase))
		&& !GetWorld()->GetMapName().Contains(MapaCmd))
	{
		bTrocandoMapa = true;
		const FString Destino = MapaCmd.Equals(TEXT("Vitrine"), ESearchCase::IgnoreCase) ? TEXT("/Game/Mapas/Vitrine")
			: (MapaCmd.Equals(TEXT("Usina"), ESearchCase::IgnoreCase) ? TEXT("/Game/Mapas/Usina") : TEXT("/Game/Mapas/Campo"));
		UGameplayStatics::OpenLevel(this, FName(*Destino), true, TEXT("jogo"));
		return;
	}

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
	bEhVitrine = GetWorld()->GetMapName().Contains(TEXT("Vitrine"));
	bEhCampo = bEhVitrine || GetWorld()->GetMapName().Contains(TEXT("Campo"));
	bEhUsina = GetWorld()->GetMapName().Contains(TEXT("Usina"));
	FBox LimitesMapa(ForceInit);
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		for (const FName& Tag : It->Tags)
		{
			TArray<FString> V;
			const FString T = Tag.ToString();
			if (!T.StartsWith(TEXT("Limites_"))) continue;
			T.RightChop(8).ParseIntoArray(V, TEXT("_"));
			if (V.Num() == 5)
			{
				LimitesMapa = FBox(FVector(FCString::Atof(*V[0]), FCString::Atof(*V[1]), -5000.f), FVector(FCString::Atof(*V[2]), FCString::Atof(*V[3]), FCString::Atof(*V[4])));
			}
		}
	}
	CartaoDoMapa = (int32)(bEhUsina ? ECartaoMapa::Usina : (bEhCampo ? ECartaoMapa::Campo : ECartaoMapa::Predio));
	LimitesVoo = bEhCampo
		? FBox(FVector(-48000.f, -48000.f, -5000.f), FVector(48000.f, 48000.f, 9000.f)) // fazenda: 480 m para cada lado, 90 m de teto
		: FBox(FVector(45.f, -1555.f, -500.f), FVector(2355.f, -45.f, 1590.f));
	if (bEhUsina && LimitesMapa.IsValid) LimitesVoo = LimitesMapa;   // usina: tag Limites_ do mapa
	else if (bEhUsina) LimitesVoo = FBox(FVector(-16000.f, -10000.f, -5000.f), FVector(16000.f, 11000.f, 7500.f));
	if (ADronePawn* D = Drone())
	{
		D->Limites = LimitesVoo;
		D->bUsarLimites = true;
		D->AjustarLuz(bEhCampo, bEhUsina);
	}
	for (const TCHAR* Nome : { TEXT("/Game/UI/S_Coleta.S_Coleta"), TEXT("/Game/UI/S_Foto.S_Foto"), TEXT("/Game/UI/S_Blip.S_Blip"), TEXT("/Game/UI/S_Vitoria.S_Vitoria") })
	{
		Sons.Add(LoadObject<USoundBase>(nullptr, Nome));
	}
	// vegetação com vento (tag "Vento"): cada material vira dinâmico e recebe o vento todo quadro
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		if (!It->ActorHasTag(TEXT("Vento"))) continue;
		if (UStaticMeshComponent* C = It->FindComponentByClass<UStaticMeshComponent>())
		{
			for (int32 i = 0; i < C->GetNumMaterials(); ++i)
			{
				if (UMaterialInstanceDynamic* MID = C->CreateDynamicMaterialInstance(i)) MatVento.Add(MID);
			}
		}
	}
	// água: material com ondas que o vento mexe (parâmetros "Ondas" e "Desloc")
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		if (!It->ActorHasTag(TEXT("Agua"))) continue;
		if (UStaticMeshComponent* C = It->FindComponentByClass<UStaticMeshComponent>())
		{
			if (UMaterialInstanceDynamic* MID = C->CreateDynamicMaterialInstance(0)) MatAgua.Add(MID);
		}
	}

	MontarPercurso();
	MontarAros();
	if (bEhCampo)
	{
		EspalharMilho();
		EspalharGrama();
	}
	if (bEhCampo || bEhUsina)
	{
		CaixaAtor = CriarAtorMalha(MalhaCaixa, FTransform(FVector(0, 0, -100000)));
	}

	bTour = FParse::Param(FCommandLine::Get(), TEXT("tour"));
	bFotoMenu = FParse::Param(FCommandLine::Get(), TEXT("fotomenu"));
	bTestePouso = FParse::Param(FCommandLine::Get(), TEXT("testepouso"));
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
	bUsinaExiste = FPackageName::DoesPackageExist(TEXT("/Game/Mapas/Usina"));
	const bool bJogo = UGameplayStatics::HasOption(OptionsString, TEXT("jogo"));
	const FString OpModo = UGameplayStatics::ParseOption(OptionsString, TEXT("modo"));
	EObjetivo Inicial = ((bEhCampo && !bEhVitrine) || bEhUsina) ? EObjetivo::ArosOrdem : EObjetivo::Livre;
	if (!OpModo.IsEmpty())
	{
		Inicial = (EObjetivo)FMath::Clamp(FCString::Atoi(*OpModo), 0, (int32)EObjetivo::Ferraduras);
		if (!ObjetivosDoMapa().Contains(Inicial)) Inicial = ObjetivosDoMapa()[0];
	}
	if (ADronePawn* D = Drone()) UltimosReinicios = D->Reinicios;
	if (!bTour && !bJogo && !bEhCampo && !bEhUsina && !bTestePouso)
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
	TArray<TPair<int32, TPair<FVector, FString>>> Entregas, Fotos;
	TArray<TPair<int32, TWeakObjectPtr<AActor>>> Ferrs;
	UStaticMesh* MalhaFarol = nullptr;
	Giratorios.Reset();

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
			else if (T == TEXT("Coleta"))
			{
				PontoColeta = A->GetActorLocation();
				bTemColeta = true;
			}
			else if (T.StartsWith(TEXT("Entrega_")) || T.StartsWith(TEXT("Foto_")))
			{
				FString Nome;
				for (const FName& T2 : A->Tags)
				{
					if (T2.ToString().StartsWith(TEXT("Nome:"))) Nome = T2.ToString().RightChop(5);
				}
				const bool bEntrega = T.StartsWith(TEXT("Entrega_"));
				(bEntrega ? Entregas : Fotos).Add(TPair<int32, TPair<FVector, FString>>(FCString::Atoi(*T.RightChop(bEntrega ? 8 : 5)), TPair<FVector, FString>(A->GetActorLocation(), Nome)));
			}
			else if (T.StartsWith(TEXT("Ferradura_")))
			{
				Ferrs.Add(TPair<int32, TWeakObjectPtr<AActor>>(FCString::Atoi(*T.RightChop(10)), A));
			}
			else if (T.StartsWith(TEXT("Gira_")))
			{
				Giratorios.Add(TPair<TWeakObjectPtr<AActor>, float>(A, FCString::Atof(*T.RightChop(5))));
			}
			else if (T.StartsWith(TEXT("Roca_")))
			{
				TArray<FString> V;
				T.RightChop(5).ParseIntoArray(V, TEXT("_"));
				if (V.Num() == 4)
				{
					Roca = FBox2D(FVector2D(FCString::Atof(*V[0]), FCString::Atof(*V[1])), FVector2D(FCString::Atof(*V[2]), FCString::Atof(*V[3])));
				}
			}
			else if (T == TEXT("ModeloCaixa") || T == TEXT("ModeloFarol"))
			{
				if (const UStaticMeshComponent* C = A->FindComponentByClass<UStaticMeshComponent>())
				{
					if (T == TEXT("ModeloCaixa")) MalhaCaixa = C->GetStaticMesh();
					else MalhaFarol = C->GetStaticMesh();
				}
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

	auto PorIndice = [](const auto& A, const auto& B) { return A.Key < B.Key; };
	Entregas.Sort(PorIndice);
	Fotos.Sort(PorIndice);
	Ferrs.Sort(PorIndice);
	PontosEntrega.Reset(); NomesEntrega.Reset();
	for (const auto& E : Entregas) { PontosEntrega.Add(E.Value.Key); NomesEntrega.Add(E.Value.Value); }
	PontosFoto.Reset(); NomesFoto.Reset();
	for (const auto& F : Fotos) { PontosFoto.Add(F.Value.Key); NomesFoto.Add(F.Value.Value); }
	Ferraduras.Reset();
	for (const auto& F : Ferrs) Ferraduras.Add(F.Value);
	FotoFeita.Init(false, PontosFoto.Num());
	FerraduraPega.Init(false, Ferraduras.Num());
	if (MalhaFarol && !Farol.IsValid())
	{
		// criado depois de percorrer os atores (criar no meio da varredura atrapalha o iterador)
		Farol = CriarAtorMalha(MalhaFarol, FTransform(FVector(0, 0, -100000)));
		if (AActor* F = Farol.Get()) F->SetActorHiddenInGame(true);
	}
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
				if (A.IsValid()) FilaVisibilidade.Add(TPair<TWeakObjectPtr<AActor>, bool>(A, bVer));
			}
		}
	}
	// aplica aos poucos (no máximo ~1,2 ms por quadro): mostrar/esconder um andar inteiro de uma vez
	// recriava centenas de objetos no mesmo quadro e dava um tranco na troca de andar.
	// O andar vizinho já é pedido antes de precisar (margem de altura e 1,5 s), então não aparece buraco.
	const double Inicio = FPlatformTime::Seconds();
	int32 Feitos = 0;
	while (Feitos < FilaVisibilidade.Num())
	{
		const TPair<TWeakObjectPtr<AActor>, bool>& Item = FilaVisibilidade[Feitos++];
		if (AActor* A = Item.Key.Get())
		{
			A->SetActorHiddenInGame(!Item.Value);
			TArray<ULightComponent*> Luzes;
			A->GetComponents(Luzes);
			for (ULightComponent* L : Luzes) L->SetVisibility(Item.Value);
		}
		if (!bForcar && FPlatformTime::Seconds() - Inicio > 0.0012) break;
	}
	FilaVisibilidade.RemoveAt(0, Feitos, EAllowShrinking::No);
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
		if (bDown && !bAntes)
		{
			TeclaAgora.Add(K);
			if (!K.IsMouseButton()) Dispositivo = K.IsGamepadKey() ? 1 : 0;
		}
		TeclaAntes.Add(K, bDown);
	}
	// analógicos mexidos = controle; teclas de voo do teclado = teclado
	for (const FKey& K : { EKeys::Gamepad_LeftX, EKeys::Gamepad_LeftY, EKeys::Gamepad_RightX, EKeys::Gamepad_RightY })
	{
		if (FMath::Abs(PC->GetInputAnalogKeyState(K)) > 0.35f) Dispositivo = 1;
	}
	for (const FKey& K : { EKeys::I, EKeys::J, EKeys::K, EKeys::L, EKeys::M, EKeys::R, EKeys::LeftControl })
	{
		if (PC->IsInputKeyDown(K)) Dispositivo = 0;
	}
}

FString APredioGameMode::NomeDispositivo(int32 D)
{
	return D == 1 ? TEXT("CONTROLE (Xbox / PlayStation)") : TEXT("TECLADO E MOUSE");
}

void APredioGameMode::TocarSom(int32 Qual)
{
	if (bTour || !Sons.IsValidIndex(Qual) || !Sons[Qual]) return;
	const float V = FAjustesDrone::Get().VolumeEfeitos;
	if (V <= 0.01f) return;
	UGameplayStatics::PlaySound2D(this, Sons[Qual], V);
}

void APredioGameMode::AtualizarVentoVegetacao()
{
	if (MatVento.Num() == 0) return;
	const ADronePawn* D = Drone();
	if (!D) return;
	const FVector W = D->VentoAtual;   // m/s
	const float F = FMath::Clamp(W.Size2D() / 11.f, 0.f, 1.3f);      // 1 = 40 km/h
	const FVector2D Dir = W.Size2D() > 0.05f ? FVector2D(W.X, W.Y).GetSafeNormal() : FVector2D(1.f, 0.f);
	const FVector P = D->GetActorLocation();
	const float Helices = D->bMotores ? FMath::Clamp(D->Acelerador * 1.4f, 0.f, 1.f) : 0.f;
	for (UMaterialInstanceDynamic* M : MatVento)
	{
		if (!M) continue;
		M->SetScalarParameterValue(TEXT("VentoForca"), F);
		M->SetScalarParameterValue(TEXT("VentoRajada"), D->VentoRajada);
		M->SetVectorParameterValue(TEXT("VentoDir"), FLinearColor(Dir.X, Dir.Y, 0.f, 0.f));
		M->SetVectorParameterValue(TEXT("DronePos"), FLinearColor(P.X, P.Y, P.Z, 0.f));
		M->SetScalarParameterValue(TEXT("DroneForca"), Helices);
	}
}

void APredioGameMode::AtualizarAgua(float Dt)
{
	if (MatAgua.Num() == 0) return;
	const ADronePawn* D = Drone();
	const FVector W = D ? D->VentoAtual : FVector::ZeroVector;   // m/s
	const float F = W.Size2D();
	// ondas: quase lisa sem vento, crespa com vento forte (11 m/s = 40 km/h)
	OndasAgua = FMath::FInterpTo(OndasAgua, FMath::Clamp(0.08f + F / 11.f, 0.08f, 1.f), Dt, 1.5f);
	const FVector2D Dir = F > 0.05f ? FVector2D(W.X, W.Y) / F : FVector2D(1.f, 0.f);
	// as duas camadas de ondas andam a favor do vento (a segunda mais devagar e um pouco de lado)
	const float Vel = 0.01f + 0.035f * FMath::Min(F / 11.f, 1.f);
	DeslocAgua.R += Dir.X * Vel * Dt;
	DeslocAgua.G += Dir.Y * Vel * Dt;
	DeslocAgua.B += (Dir.X * 0.8f - Dir.Y * 0.4f) * Vel * 0.6f * Dt;
	DeslocAgua.A += (Dir.Y * 0.8f + Dir.X * 0.4f) * Vel * 0.6f * Dt;
	for (UMaterialInstanceDynamic* M : MatAgua)
	{
		if (!M) continue;
		M->SetScalarParameterValue(TEXT("Ondas"), OndasAgua);
		M->SetVectorParameterValue(TEXT("Desloc"), DeslocAgua);
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
	case EItemMenu::Objetivo: case EItemMenu::ModoVoo: case EItemMenu::VoltarInicio: case EItemMenu::Vento: case EItemMenu::Rajadas:
		return ECategoriaMenu::Jogabilidade;
	case EItemMenu::Sensibilidade: case EItemMenu::Expo: case EItemMenu::VelMax: return ECategoriaMenu::Sensibilidade;
	case EItemMenu::ModoFSR: case EItemMenu::Gerador: case EItemMenu::VSync:
		return ECategoriaMenu::Video;
	case EItemMenu::Volume: case EItemMenu::Efeitos: return ECategoriaMenu::Audio;
	case EItemMenu::Comandos: case EItemMenu::InvFrente: case EItemMenu::InvSubir: case EItemMenu::InvGiro: case EItemMenu::InvLados:
		return ECategoriaMenu::Controles;
	case EItemMenu::EscalaHUD: return ECategoriaMenu::Acessibilidade;
	case EItemMenu::Painel: case EItemMenu::MetaFPS: case EItemMenu::AjusteAuto: case EItemMenu::Padrao: return ECategoriaMenu::Avancado;
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
	case ECategoriaMenu::Jogabilidade: return TEXT("Objetivo, modo de voo, volta ao início e vento");
	case ECategoriaMenu::Sensibilidade: return TEXT("Quanto o drone responde aos comandos e a velocidade máxima");
	case ECategoriaMenu::Video: return TEXT("AMD FSR 4, gerador de quadros e V-Sync");
	case ECategoriaMenu::Audio: return TEXT("Som do motor e dos efeitos");
	case ECategoriaMenu::Controles: return TEXT("Lista de comandos e inverter os eixos");
	case ECategoriaMenu::Acessibilidade: return TEXT("Tamanho do painel de voo na tela");
	case ECategoriaMenu::Avancado: return TEXT("Painel de desempenho, meta de FPS, ajuste automático e padrões");
	default: return TEXT("Voltar ao menu principal ou fechar o simulador (as configurações ficam salvas)");
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
	case ECategoriaMenu::Sair: return TEXT("SAIR");
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
	case EItemMenu::MenuPrincipal: return TEXT("Voltar ao menu principal");
	case EItemMenu::Vento:         return TEXT("Força do vento");
	case EItemMenu::Rajadas:       return TEXT("Rajadas de vento");
	case EItemMenu::VelMax:        return TEXT("Velocidade máxima");
	case EItemMenu::Efeitos:       return TEXT("Volume dos efeitos");
	case EItemMenu::Comandos:      return TEXT("Ver lista de comandos");
	case EItemMenu::MetaFPS:       return TEXT("Meta de FPS");
	case EItemMenu::Sensibilidade: return TEXT("Sensibilidade dos analógicos");
	case EItemMenu::Expo:          return TEXT("Suavidade no centro (expo)");
	case EItemMenu::ModoFSR:       return TEXT("AMD FSR 4 (IA)");
	case EItemMenu::Gerador:       return TEXT("Gerador de quadros AMD");
	case EItemMenu::VSync:         return TEXT("VSync");
	case EItemMenu::Painel:        return TEXT("Painel de FPS");
	case EItemMenu::AjusteAuto:    return TEXT("Ajuste automático da qualidade");
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
	case EItemMenu::MenuPrincipal: return TEXT("Sai do mapa e volta para a escolha de mapas e desafios");
	case EItemMenu::Vento:         return TEXT("Também no voo: + / −  ou  D-pad ↑ ↓   (V ou RB muda a direção)");
	case EItemMenu::Rajadas:       return TEXT("O vento sobe e desce de força e vira um pouco (G ou LB no voo)");
	case EItemMenu::VelMax:        return TEXT("Até onde o drone acelera no modo estabilizado");
	case EItemMenu::Efeitos:       return TEXT("Sons de pegar itens, tirar foto, passar no aro e vitória");
	case EItemMenu::Comandos:      return TEXT("Teclado e controle: voo, vento, câmera e atalhos");
	case EItemMenu::MetaFPS:       return TEXT("Trava o FPS nesse valor (com o gerador, metade vem da IA)");
	case EItemMenu::Sensibilidade: return TEXT("Velocidade e giro máximos dos analógicos");
	case EItemMenu::Expo:          return TEXT("Deixa o centro do analógico mais suave");
	case EItemMenu::ModoFSR:       return TEXT("Upscaling por IA da AMD (Qualidade = mais nítido)");
	case EItemMenu::Gerador:       return TEXT("Cria quadros intermediários com IA (quase dobra o FPS)");
	case EItemMenu::VSync:         return TEXT("Sincroniza com o monitor (evita rasgos na imagem)");
	case EItemMenu::Painel:        return TEXT("Mostra FPS, GPU e o modo do FSR na tela");
	case EItemMenu::AjusteAuto:    return TEXT("Alivia o FSR sozinho se não estiver alcançando a meta de FPS");
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
	case EItemMenu::Gerador: case EItemMenu::VSync: case EItemMenu::Painel: case EItemMenu::AjusteAuto: case EItemMenu::Rajadas:
		return ETipoValor::Chave;
	case EItemMenu::Continuar: return ETipoValor::Nenhum;
	case EItemMenu::VoltarInicio: case EItemMenu::MenuPrincipal: case EItemMenu::Padrao: case EItemMenu::Sair: case EItemMenu::Comandos:
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
	case EItemMenu::Rajadas: return C.bRajadas;
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
	case EItemMenu::Vento:         return C.VentoKmh <= 0.f ? FString(TEXT("Calmaria")) : FString::Printf(TEXT("%.0f km/h"), C.VentoKmh);
	case EItemMenu::Rajadas:       return LD(C.bRajadas);
	case EItemMenu::VelMax:        return FString::Printf(TEXT("%.0f km/h"), C.VelMaxKmh);
	case EItemMenu::Efeitos:       return FString::Printf(TEXT("%d%%"), FMath::RoundToInt(C.VolumeEfeitos * 100.f));
	case EItemMenu::MetaFPS:       return C.MetaFPS <= 0 ? FString(TEXT("Livre")) : FString::Printf(TEXT("%d FPS"), C.MetaFPS);
	case EItemMenu::VoltarInicio: case EItemMenu::MenuPrincipal: case EItemMenu::Padrao: case EItemMenu::Sair: case EItemMenu::Comandos: return TEXT("—");
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
			if (bEhCampo || bEhUsina)
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
	case EItemMenu::Vento:
		C.VentoKmh = Ciclo(C.VentoKmh, 5.f * Passo, 0.f, 40.f);
		break;
	case EItemMenu::Rajadas: C.bRajadas = !C.bRajadas; break;
	case EItemMenu::VelMax:
		C.VelMaxKmh = Ciclo(C.VelMaxKmh, 5.f * Passo, 25.f, 90.f);
		break;
	case EItemMenu::Efeitos:
		C.VolumeEfeitos = Ciclo(C.VolumeEfeitos, 0.05f * Passo, 0.f, 1.f);
		if (Dir != 0) TocarSom(0);
		break;
	case EItemMenu::Comandos:
		if (bConfirmar) { bVerComandos = true; MenuMudouEm = FPlatformTime::Seconds(); }
		return;
	case EItemMenu::MetaFPS:
	{
		int32 Idx = 0;
		for (int32 k = 0; k < FAjustesDrone::NumMetas; ++k) if (FAjustesDrone::MetasFPS[k] == C.MetaFPS) Idx = k;
		Idx = (Idx + Passo + FAjustesDrone::NumMetas) % FAjustesDrone::NumMetas;
		C.MetaFPS = FAjustesDrone::MetasFPS[Idx];
		C.AplicarGraficos();
		NivelAjuste = 0;
		AplicarNivelAjuste();
		break;
	}
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
			for (int32 i = 0; i < FAjustesDrone::NumObjetivos; ++i) { C.Recordes[i] = Antes.Recordes[i]; C.Medalhas[i] = Antes.Medalhas[i]; }
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

	// lista de comandos aberta: qualquer botão de confirmar/voltar (ou clique) fecha só ela
	if (bVerComandos)
	{
		if (bPodeFechar && Apertou({ EKeys::Escape, EKeys::Gamepad_FaceButton_Right, EKeys::BackSpace, EKeys::Enter,
			EKeys::SpaceBar, EKeys::Gamepad_FaceButton_Bottom, EKeys::Gamepad_Special_Right, EKeys::LeftMouseButton, EKeys::RightMouseButton }))
		{
			bVerComandos = false;
			MenuMudouEm = FPlatformTime::Seconds();
		}
		return;
	}

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
		D->MostrarMensagem(C.bAjusteAuto ? TEXT("Ajuste automático da qualidade LIGADO") : TEXT("Ajuste automático desligado"));
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
	const FAjustesDrone& CfgA = FAjustesDrone::Get();
	if (!CfgA.bAjusteAuto || bTour || bMenuAberto) return;
	// base que precisa ser alcançada: a meta (metade dela com o gerador de quadros); "livre" = 60 de base
	const float Alvo = CfgA.MetaFPS <= 0 ? 60.f : (GeradorLigado() ? CfgA.MetaFPS * 0.5f : (float)CfgA.MetaFPS);
	if (FPSBase < Alvo * 0.95f) { AcumBaixo += Dt; AcumAlto = 0.f; }
	else if (FPSBase > Alvo * 1.45f || (CfgA.MetaFPS > 0 && FPSBase >= Alvo * 0.98f && NivelAjuste > 0 && FPSBase > Alvo * 1.25f)) { AcumAlto += Dt; AcumBaixo = 0.f; }
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
	if (bTrocandoMapa) return;

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
		AtualizarVentoVegetacao();
		if (bEhCampo) AtualizarAgua(DeltaSeconds);
		return;
	}
	if (bTestePouso)
	{
		TickTestePouso(DtReal);
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
	if ((bEhCampo || bEhUsina) && !UGameplayStatics::IsGamePaused(this))
	{
		for (const TPair<TWeakObjectPtr<AActor>, float>& G : Giratorios)
		{
			if (AActor* A = G.Key.Get()) A->AddActorLocalRotation(FRotator(0.f, 0.f, G.Value * DeltaSeconds));
		}
		for (int32 i = 0; i < Ferraduras.Num(); ++i)
		{
			if (AActor* F = Ferraduras[i].Get()) F->AddActorWorldRotation(FRotator(0.f, 90.f * DeltaSeconds, 0.f));
		}
		MoverFarolECaixa();
		AtualizarAgua(DeltaSeconds);
	}
	AtualizarVentoVegetacao();
	Flash = FMath::Max(0.f, Flash - DtReal * 2.5f);
	if (bMenuPrincipal && bFotoMenu) TickFotosMenu(DtReal);
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
	TourAndarQ.Add(AndarAtual);
	TourDesdePausa.Add(QuadrosDesdePausa++);

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
		QuadrosDesdePausa = 0;
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
	// de onde vêm os quadros lentos (> 20 ms): logo depois de uma foto, numa troca de andar ou no meio do voo
	{
		int32 Lentos = 0, PosFoto = 0, Troca = 0;
		TMap<int32, int32> PorAndar;
		for (int32 i = 0; i < TourFrames.Num(); ++i)
		{
			if (TourFrames[i] <= 20.f) continue;
			++Lentos;
			if (TourDesdePausa.IsValidIndex(i) && TourDesdePausa[i] < 5) ++PosFoto;
			bool bTroca = false;
			for (int32 k = FMath::Max(0, i - 30); k <= FMath::Min(TourAndarQ.Num() - 1, i + 30); ++k)
			{
				if (TourAndarQ[k] != TourAndarQ[i]) { bTroca = true; break; }
			}
			if (bTroca) ++Troca;
			PorAndar.FindOrAdd(TourAndarQ.IsValidIndex(i) ? TourAndarQ[i] : -1)++;
		}
		FString Txt;
		for (const TPair<int32, int32>& P : PorAndar) Txt += FString::Printf(TEXT(" andar%d=%d"), P.Key, P.Value);
		TourLinhas.Add(FString::Printf(TEXT("quadros > 20 ms: %d  (logo depois de foto %d, perto de troca de andar %d)%s"), Lentos, PosFoto, Troca, *Txt));
		F.RemoveAll([](float V) { return false; });
		TArray<float> SemFoto;
		for (int32 i = 0; i < TourFrames.Num(); ++i) if (!TourDesdePausa.IsValidIndex(i) || TourDesdePausa[i] >= 5) SemFoto.Add(TourFrames[i]);
		SemFoto.Sort();
		if (SemFoto.Num())
		{
			const float P99b = SemFoto[FMath::Clamp(FMath::FloorToInt(SemFoto.Num() * 0.99f), 0, SemFoto.Num() - 1)];
			TourLinhas.Add(FString::Printf(TEXT("pior 1%% sem os quadros logo depois das fotos: %.2f ms (%.1f FPS)"), P99b, P99b > 0 ? 1000.f / P99b : 0.f));
		}
	}
	if (!DiagCampo.IsEmpty())
	{
		TArray<FString> L;
		DiagCampo.ParseIntoArrayLines(L);
		TourLinhas.Append(L);
	}
	TourLinhas.Add(FString::Printf(TEXT("missões: coleta %d, entregas %d, fotos %d, ferraduras %d, giratórios %d, farol %d, caixa %d"),
		bTemColeta ? 1 : 0, PontosEntrega.Num(), PontosFoto.Num(), Ferraduras.Num(), Giratorios.Num(), Farol.IsValid() ? 1 : 0, MalhaCaixa ? 1 : 0));
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
	case ECartaoMapa::Campo: return { EObjetivo::Entregas, EObjetivo::Pulverizar, EObjetivo::Fotos, EObjetivo::Ferraduras, EObjetivo::ArosOrdem, EObjetivo::ArosRelogio, EObjetivo::Livre };
	case ECartaoMapa::Predio: return { EObjetivo::Topo, EObjetivo::Livre };
	case ECartaoMapa::Usina: return { EObjetivo::Entregas, EObjetivo::Fotos, EObjetivo::Ferraduras, EObjetivo::ArosOrdem, EObjetivo::ArosRelogio, EObjetivo::Livre };
	default: return {};
	}
}

TArray<EObjetivo> APredioGameMode::ObjetivosDoMapa() const
{
	if (bEhVitrine) return { EObjetivo::Livre };
	return ObjetivosDoCartao((ECartaoMapa)CartaoDoMapa);
}

FString APredioGameMode::NomeObjetivo(EObjetivo O, int32 Cartao)
{
	if (Cartao < 0) Cartao = CartaoDoMapa;
	if (Cartao == (int32)ECartaoMapa::Usina)
	{
		switch (O)
		{
		case EObjetivo::Entregas: return TEXT("Cargas da usina");
		case EObjetivo::Fotos: return TEXT("Inspeção da usina");
		case EObjetivo::Ferraduras: return TEXT("Engrenagens douradas");
		default: break;
		}
	}
	switch (O)
	{
	case EObjetivo::Topo: return TEXT("Chegue ao topo");
	case EObjetivo::ArosOrdem: return TEXT("Aros em ordem");
	case EObjetivo::ArosRelogio: return TEXT("Contra o relógio");
	case EObjetivo::Entregas: return TEXT("Entregas da fazenda");
	case EObjetivo::Pulverizar: return TEXT("Pulverizar o milharal");
	case EObjetivo::Fotos: return TEXT("Inspeção com fotos");
	case EObjetivo::Ferraduras: return TEXT("Ferraduras douradas");
	default: return TEXT("Voo livre");
	}
}

FString APredioGameMode::DescricaoObjetivo(EObjetivo O, int32 Cartao)
{
	if (Cartao < 0) Cartao = CartaoDoMapa;
	if (Cartao == (int32)ECartaoMapa::Usina)
	{
		switch (O)
		{
		case EObjetivo::Entregas: return TEXT("Do pátio ao vagão, à ponte rolante, ao alto-forno, à esteira, aos silos e à chaminé");
		case EObjetivo::Fotos: return TEXT("7 alvos: chaminé rachada, gancho, conversor, válvula, bica, regenerador, locomotiva");
		case EObjetivo::Ferraduras: return TEXT("12 engrenagens escondidas pela usina — algumas dentro das máquinas");
		case EObjetivo::ArosOrdem: return TEXT("Por dentro do galpão, por baixo das pontes rolantes, em volta do alto-forno");
		default: break;
		}
	}
	switch (O)
	{
	case EObjetivo::Topo: return TEXT("Suba do térreo até a cobertura o mais rápido que puder");
	case EObjetivo::ArosOrdem: return TEXT("Passe por todos os aros na ordem — o próximo fica marcado");
	case EObjetivo::ArosRelogio: return TEXT("Cada aro dá mais tempo; se o relógio zerar, acabou");
	case EObjetivo::Entregas: return TEXT("Pegue a caixa no galpão e leve para a casa, a caixa d'água, a carreta e o píer");
	case EObjetivo::Pulverizar: return TEXT("Voe baixo (até 4 m) por cima do milho até cobrir 90% da roça");
	case EObjetivo::Fotos: return TEXT("Mire de perto: transformador, cata-vento, caixa d'água, galpão, silo e chaminé");
	case EObjetivo::Ferraduras: return TEXT("12 ferraduras escondidas pela fazenda — ache todas");
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
	return bEhUsina ? FString(TEXT("USINA")) : (bEhVitrine ? FString(TEXT("VITRINE")) : (bEhCampo ? FString(TEXT("FAZENDA")) : TextoAndar(AndarAtual)));
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
	if (Objetivo == EObjetivo::Entregas)
	{
		// ida e volta do galpão a cada destino + o tempo de pegar/soltar
		float L = 0.f;
		for (const FVector& E : PontosEntrega) L += 2.f * FVector::Dist(PontoColeta, E);
		const float Paradas = PontosEntrega.Num() * 2.f * 3.f;
		return M >= 3 ? Arred5(L / 800.f + Paradas) : (M == 2 ? Arred5(L / 560.f + Paradas * 1.5f) : Arred5(L / 380.f + Paradas * 2.f));
	}
	if (Objetivo == EObjetivo::Pulverizar)
	{
		// faixas de 5 m cobrindo 90% da roça
		const float L = Roca.bIsValid ? Roca.GetArea() / TamCelula * CoberturaMeta : 60000.f;
		return M >= 3 ? Arred5(L / 650.f + 20.f) : (M == 2 ? Arred5(L / 450.f + 40.f) : Arred5(L / 300.f + 60.f));
	}
	if (Objetivo == EObjetivo::Fotos) return bEhUsina ? (M >= 3 ? 150.f : (M == 2 ? 220.f : 330.f)) : (M >= 3 ? 120.f : (M == 2 ? 180.f : 270.f));
	if (Objetivo == EObjetivo::Ferraduras) return bEhUsina ? (M >= 3 ? 300.f : (M == 2 ? 450.f : 660.f)) : (M >= 3 ? 240.f : (M == 2 ? 360.f : 540.f));
	return 0.f;
}

float APredioGameMode::RecordeAtual() const
{
	const FAjustesDrone& C = FAjustesDrone::Get();
	const int32 S = SlotRec(Objetivo, CartaoDoMapa);
	return S < FAjustesDrone::NumObjetivos ? C.Recordes[S] : 0.f;
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
	// missões da fazenda
	EntregaAtual = 0;
	bComCaixa = false;
	TempoParado = 0.f;
	for (const TWeakObjectPtr<AActor>& C : CaixasEntregues) if (AActor* A = C.Get()) A->Destroy();
	CaixasEntregues.Reset();
	for (bool& B : FotoFeita) B = false;
	FotoMirando = INDEX_NONE;
	TempoMira = 0.f;
	for (int32 i = 0; i < Ferraduras.Num(); ++i)
	{
		FerraduraPega[i] = false;
		if (AActor* F = Ferraduras[i].Get()) F->SetActorHiddenInGame(false);
	}
	for (uint8& C : CelulaFeita) C = 0;
	bPulverizando = false;
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
		case EObjetivo::Entregas: Dica = bEhUsina ? TEXT("CARGAS — pegue a caixa na plataforma do pátio (siga a luz laranja)") : TEXT("ENTREGAS — pegue a caixa na plataforma do galpão (siga a luz laranja)"); break;
		case EObjetivo::Pulverizar: Dica = TEXT("PULVERIZAR — voe baixo por cima do milharal, em faixas"); break;
		case EObjetivo::Fotos: Dica = TEXT("INSPEÇÃO — chegue perto e mire cada alvo até a foto sair"); break;
		case EObjetivo::Ferraduras: Dica = bEhUsina ? TEXT("ENGRENAGENS — 12 escondidas; o painel diz quando está perto") : TEXT("FERRADURAS — 12 escondidas; o painel diz quando está perto"); break;
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
	if (bSucesso) TocarSom(3);
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
		const int32 Slot = FMath::Clamp(SlotRec(Objetivo, CartaoDoMapa), 0, FAjustesDrone::NumObjetivos - 1);
		int32* Med = &C.Medalhas[Slot];
		if (Medalha > *Med) { *Med = Medalha; C.Salvar(); }
		float* Rec = &C.Recordes[Slot];
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
	if (Objetivo == EObjetivo::Entregas || Objetivo == EObjetivo::Pulverizar || Objetivo == EObjetivo::Fotos || Objetivo == EObjetivo::Ferraduras)
	{
		TickMissoes(Dt, P);
	}
	else if (Objetivo == EObjetivo::Topo)
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
				TocarSom(2);
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
	case ECartaoMapa::Usina: return bUsinaExiste;
	default: return false;
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

int32 APredioGameMode::MedalhaDe(EObjetivo O, int32 Cartao) const
{
	const FAjustesDrone& C = FAjustesDrone::Get();
	const int32 S = SlotRec(O, Cartao < 0 ? CartaoCtx() : Cartao);
	return (O != EObjetivo::Livre && S < FAjustesDrone::NumObjetivos) ? C.Medalhas[S] : 0;
}

int32 APredioGameMode::MedalhasMapa(int32 Cartao, int32& Possiveis) const
{
	int32 Tem = 0;
	Possiveis = 0;
	for (const EObjetivo O : ObjetivosDoCartao((ECartaoMapa)Cartao))
	{
		if (O == EObjetivo::Livre) continue;
		Possiveis += 3;
		Tem += MedalhaDe(O, Cartao);
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
	if (LinhaEhObjetivo(L, O)) return NomeObjetivo(O, MPCartao);
	return TEXT("Voltar aos mapas");
}

FString APredioGameMode::DescricaoLinhaMP(int32 L) const
{
	EObjetivo O = EObjetivo::Livre;
	if (LinhaEhObjetivo(L, O)) return DescricaoObjetivo(O, MPCartao);
	return TEXT("Escolher outro mapa");
}

FString APredioGameMode::ExtraLinhaMP(int32 L) const
{
	EObjetivo O = EObjetivo::Livre;
	if (!LinhaEhObjetivo(L, O)) return FString();
	if (O == EObjetivo::Livre) return TEXT("sem cronômetro");
	const FAjustesDrone& C = FAjustesDrone::Get();
	const int32 S = SlotRec(O, MPCartao);
	const float R = S < FAjustesDrone::NumObjetivos ? C.Recordes[S] : 0.f;
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
	A->SetActorScale3D(FVector(2.6f)); // maior que o real para aparecer bem na abertura
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
	if ((ECartaoMapa)MPCartao == ECartaoMapa::Usina)
	{
		IrParaMapa(TEXT("/Game/Mapas/Usina"), FString::Printf(TEXT("jogo?modo=%d"), (int32)O));
		return;
	}
	if (bEhCampo || bEhUsina)
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
		const float SCam = FMath::Max(0.f, SDrone - 100.f / Comp(SDrone));
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
			const FVector Olhar = PosDrone + TD.GetRotation().GetForwardVector() * 60.f - TD.GetRotation().GetRightVector() * 45.f;
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

	if (bFotoMenu) return; // os prints de conferência cuidam do menu (TickFotosMenu)

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

void APredioGameMode::TickFotosMenu(float Dt)
{
	// prints de conferência (-fotomenu): abertura, mapas, desafios do campo, sai
	FotoMenuT += Dt;
	auto Foto = [this](const TCHAR* Nome) { FScreenshotRequest::RequestScreenshot(PastaTestes / Nome, true, false); };
	if (FotoMenuFase == 0 && FotoMenuT > 7.f) { Foto(TEXT("menu_1_abertura.png")); FotoMenuFase = 1; }
	else if (FotoMenuFase == 1 && FotoMenuT > 8.f) { IrParaTela(ETelaMP::Mapas); MPCartao = (int32)ECartaoMapa::Campo; FotoMenuFase = 2; }
	else if (FotoMenuFase == 2 && FotoMenuT > 10.f) { Foto(TEXT("menu_2_mapas.png")); FotoMenuFase = 3; }
	else if (FotoMenuFase == 3 && FotoMenuT > 11.f) { MPCartao = (int32)ECartaoMapa::Usina; FotoMenuFase = 4; }
	else if (FotoMenuFase == 4 && FotoMenuT > 12.5f) { Foto(TEXT("menu_3_usina.png")); FotoMenuFase = 5; }
	else if (FotoMenuFase == 5 && FotoMenuT > 13.5f) { MPCartao = (int32)ECartaoMapa::Usina; IrParaTela(ETelaMP::Desafios); FotoMenuFase = 6; }
	else if (FotoMenuFase == 6 && FotoMenuT > 15.f) { Foto(TEXT("menu_4_desafios.png")); FotoMenuFase = 7; }
	else if (FotoMenuFase == 7 && FotoMenuT > 16.f) { AbrirMenu(true); CategoriaSel = (int32)ECategoriaMenu::Video; FotoMenuFase = 8; }
	else if (FotoMenuFase == 8 && FotoMenuT > 17.5f) { Foto(TEXT("menu_5_secoes.png")); FotoMenuFase = 9; }
	else if (FotoMenuFase == 9 && FotoMenuT > 18.5f) { EntrarCategoria(ECategoriaMenu::Audio); FotoMenuFase = 10; }
	else if (FotoMenuFase == 10 && FotoMenuT > 20.f) { Foto(TEXT("menu_6_audio.png")); FotoMenuFase = 11; }
	else if (FotoMenuFase == 11 && FotoMenuT > 21.f) { FPlatformMisc::RequestExit(false); }
}

// ------------------------------------------------------------------ missões da fazenda

AActor* APredioGameMode::CriarAtorMalha(UStaticMesh* M, const FTransform& T)
{
	if (!M) return nullptr;
	AActor* A = GetWorld()->SpawnActor<AActor>(AActor::StaticClass(), T);
	if (!A) return nullptr;
	UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(A, TEXT("Malha"));
	C->SetMobility(EComponentMobility::Movable);
	C->SetStaticMesh(M);
	C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	A->SetRootComponent(C);
	C->RegisterComponent();
	A->AddInstanceComponent(C);
	A->SetActorTransform(T);
	return A;
}

float APredioGameMode::Cobertura() const
{
	if (CelulaFeita.Num() == 0) return 0.f;
	int32 N = 0;
	for (const uint8 C : CelulaFeita) N += C ? 1 : 0;
	return (float)N / (float)CelulaFeita.Num();
}

int32 APredioGameMode::Progresso() const
{
	switch (Objetivo)
	{
	case EObjetivo::ArosOrdem: case EObjetivo::ArosRelogio: return FMath::Min(ProximoAro, Aros.Num());
	case EObjetivo::Entregas: return EntregaAtual;
	case EObjetivo::Fotos: { int32 N = 0; for (const bool B : FotoFeita) N += B ? 1 : 0; return N; }
	case EObjetivo::Ferraduras: { int32 N = 0; for (const bool B : FerraduraPega) N += B ? 1 : 0; return N; }
	case EObjetivo::Pulverizar: return FMath::RoundToInt(Cobertura() * 100.f);
	default: return 0;
	}
}

int32 APredioGameMode::ProgressoTotal() const
{
	switch (Objetivo)
	{
	case EObjetivo::ArosOrdem: case EObjetivo::ArosRelogio: return Aros.Num();
	case EObjetivo::Entregas: return PontosEntrega.Num();
	case EObjetivo::Fotos: return PontosFoto.Num();
	case EObjetivo::Ferraduras: return Ferraduras.Num();
	case EObjetivo::Pulverizar: return FMath::RoundToInt(CoberturaMeta * 100.f);
	default: return 0;
	}
}

bool APredioGameMode::AlvoPrincipal(FVector& Out, FString& Rotulo) const
{
	if (Estado == EEstadoDesafio::Concluido || Estado == EEstadoDesafio::Falhou) return false;
	switch (Objetivo)
	{
	case EObjetivo::ArosOrdem: case EObjetivo::ArosRelogio:
		if (!Aros.IsValidIndex(ProximoAro)) return false;
		Out = Aros[ProximoAro].GetLocation();
		Rotulo = FString::Printf(TEXT("ARO %d"), ProximoAro + 1);
		return true;
	case EObjetivo::Entregas:
		if (!bComCaixa)
		{
			if (!bTemColeta) return false;
			Out = PontoColeta;
			Rotulo = TEXT("PEGAR A CAIXA");
			return true;
		}
		if (!PontosEntrega.IsValidIndex(EntregaAtual)) return false;
		Out = PontosEntrega[EntregaAtual];
		Rotulo = NomesEntrega.IsValidIndex(EntregaAtual) ? NomesEntrega[EntregaAtual].ToUpper() : TEXT("ENTREGA");
		return true;
	case EObjetivo::Pulverizar:
		if (!Roca.bIsValid) return false;
		Out = FVector(Roca.GetCenter(), ChaoCelula.Num() ? ChaoCelula[ChaoCelula.Num() / 2] + 300.f : 0.f);
		Rotulo = TEXT("MILHARAL");
		return !bPulverizando;
	default:
		return false;
	}
}

void APredioGameMode::MoverFarolECaixa()
{
	ADronePawn* D = Drone();
	// farol: coluna de luz no alvo principal (entregas / volta para a roça)
	if (AActor* F = Farol.Get())
	{
		FVector Alvo;
		FString R;
		const bool bMostra = !bMenuPrincipal && (Objetivo == EObjetivo::Entregas || Objetivo == EObjetivo::Pulverizar) && AlvoPrincipal(Alvo, R);
		F->SetActorHiddenInGame(!bMostra);
		if (bMostra) F->SetActorLocation(Alvo - FVector(0, 0, 20.f));
	}
	// caixa: na plataforma do galpão esperando, ou pendurada embaixo do drone
	if (AActor* C = CaixaAtor.Get())
	{
		const bool bVer = Objetivo == EObjetivo::Entregas && !bMenuPrincipal && Estado != EEstadoDesafio::Concluido && EntregaAtual < PontosEntrega.Num();
		C->SetActorHiddenInGame(!bVer);
		if (bComCaixa && D)
		{
			const float Balanco = FMath::Sin(GetWorld()->GetTimeSeconds() * 3.f) * 3.f;
			C->SetActorLocationAndRotation(D->GetActorLocation() - FVector(0, 0, 26.f) + D->GetActorRightVector() * Balanco, FRotator(0, D->GetActorRotation().Yaw, 0));
		}
		else
		{
			C->SetActorLocationAndRotation(PontoColeta + FVector(0, 0, 15.f), FRotator::ZeroRotator);
		}
	}
}

void APredioGameMode::TickMissoes(float Dt, const FVector& P)
{
	ADronePawn* D = Drone();
	if (!D) return;
	const float Vel = D->Velocidade.Size();

	if (Objetivo == EObjetivo::Entregas)
	{
		const FVector Alvo = bComCaixa ? (PontosEntrega.IsValidIndex(EntregaAtual) ? PontosEntrega[EntregaAtual] : P) : PontoColeta;
		const float DH = FVector::Dist2D(P, Alvo);
		const float DZ = P.Z - Alvo.Z;
		const bool bEmCima = DH < (bComCaixa ? 220.f : 160.f) && DZ > -40.f && DZ < (bComCaixa ? 180.f : 130.f) && Vel < 350.f;
		TempoParado = bEmCima ? TempoParado + Dt : FMath::Max(0.f, TempoParado - Dt * 2.f);
		if (TempoParado >= TempoParaSoltar)
		{
			TempoParado = 0.f;
			if (!bComCaixa)
			{
				bComCaixa = true;
				TocarSom(2);
				D->MostrarMensagem(FString::Printf(TEXT("Caixa presa! Leve para: %s"), NomesEntrega.IsValidIndex(EntregaAtual) ? *NomesEntrega[EntregaAtual] : TEXT("o destino")), 3.f);
			}
			else
			{
				bComCaixa = false;
				// deixa uma caixa no destino
				if (AActor* Deixada = CriarAtorMalha(MalhaCaixa, FTransform(FRotator(0, D->GetActorRotation().Yaw, 0), Alvo + FVector(0, 0, 15.f))))
				{
					CaixasEntregues.Add(Deixada);
				}
				++EntregaAtual;
				TocarSom(0);
				if (EntregaAtual >= PontosEntrega.Num())
				{
					ConcluirDesafio(true);
					return;
				}
				D->MostrarMensagem(bEhUsina ? FString::Printf(TEXT("Entregue! %d de %d — volte ao pátio de cargas"), EntregaAtual, PontosEntrega.Num())
					: FString::Printf(TEXT("Entregue! %d de %d — volte ao galpão"), EntregaAtual, PontosEntrega.Num()), 3.f);
			}
		}
	}
	else if (Objetivo == EObjetivo::Pulverizar)
	{
		bPulverizando = false;
		if (Roca.bIsValid && RocaNX > 0 && Roca.IsInside(FVector2D(P)))
		{
			const int32 IX = FMath::Clamp(FMath::FloorToInt((P.X - Roca.Min.X) / TamCelula), 0, RocaNX - 1);
			const int32 IY = FMath::Clamp(FMath::FloorToInt((P.Y - Roca.Min.Y) / TamCelula), 0, RocaNY - 1);
			const int32 I = IY * RocaNX + IX;
			const float Altura = P.Z - ChaoCelula[I];
			if (Altura < 400.f && Altura > 0.f)
			{
				bPulverizando = true;
				// o jato cobre ~5 m: marca a célula embaixo e as vizinhas que o drone toca de raspão
				for (int32 dy = -1; dy <= 1; ++dy)
				{
					for (int32 dx = -1; dx <= 1; ++dx)
					{
						const int32 X2 = IX + dx, Y2 = IY + dy;
						if (X2 < 0 || Y2 < 0 || X2 >= RocaNX || Y2 >= RocaNY) continue;
						const FVector2D Centro(Roca.Min.X + (X2 + 0.5f) * TamCelula, Roca.Min.Y + (Y2 + 0.5f) * TamCelula);
						if (FVector2D::Distance(Centro, FVector2D(P)) < TamCelula * 0.75f) CelulaFeita[Y2 * RocaNX + X2] = 1;
					}
				}
				if (Cobertura() >= CoberturaMeta)
				{
					ConcluirDesafio(true);
					return;
				}
			}
		}
	}
	else if (Objetivo == EObjetivo::Fotos)
	{
		const APlayerController* PC = GetWorld()->GetFirstPlayerController();
		if (!PC || !PC->PlayerCameraManager) return;
		const FVector CL = PC->PlayerCameraManager->GetCameraLocation();
		const FVector Frente = PC->PlayerCameraManager->GetCameraRotation().Vector();
		int32 Melhor = INDEX_NONE;
		float MelhorAng = 14.f;
		for (int32 i = 0; i < PontosFoto.Num(); ++i)
		{
			if (FotoFeita[i]) continue;
			const FVector Para = PontosFoto[i] - CL;
			const float Dist = Para.Size();
			if (Dist < 250.f || Dist > 2200.f) continue;
			const float Ang = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(Para / Dist, Frente), -1.f, 1.f)));
			if (Ang < MelhorAng) { MelhorAng = Ang; Melhor = i; }
		}
		if (Melhor != FotoMirando) { FotoMirando = Melhor; TempoMira = 0.f; }
		if (FotoMirando != INDEX_NONE)
		{
			TempoMira += Dt;
			if (TempoMira >= TempoParaFoto)
			{
				FotoFeita[FotoMirando] = true;
				TocarSom(1);
				Flash = 1.f;
				D->MostrarMensagem(FString::Printf(TEXT("Foto: %s (%d de %d)"), *NomesFoto[FotoMirando], Progresso(), PontosFoto.Num()), 2.5f);
				FotoMirando = INDEX_NONE;
				TempoMira = 0.f;
				if (Progresso() >= PontosFoto.Num())
				{
					ConcluirDesafio(true);
					return;
				}
			}
		}
	}
	else if (Objetivo == EObjetivo::Ferraduras)
	{
		DistFerradura = 1e9f;
		for (int32 i = 0; i < Ferraduras.Num(); ++i)
		{
			AActor* F = Ferraduras[i].Get();
			if (!F || FerraduraPega[i]) continue;
			const float Dist = FVector::Dist(P, F->GetActorLocation());
			if (Dist < 170.f)
			{
				FerraduraPega[i] = true;
				TocarSom(0);
				F->SetActorHiddenInGame(true);
				D->MostrarMensagem(bEhUsina ? FString::Printf(TEXT("Engrenagem! %d de %d"), Progresso(), Ferraduras.Num())
					: FString::Printf(TEXT("Ferradura! %d de %d"), Progresso(), Ferraduras.Num()), 2.5f);
				if (Progresso() >= Ferraduras.Num())
				{
					ConcluirDesafio(true);
					return;
				}
				continue;
			}
			DistFerradura = FMath::Min(DistFerradura, Dist / 100.f);
		}
	}
}

void APredioGameMode::EspalharMilho()
{
	if (!Roca.bIsValid) { DiagCampo += TEXT("milho: roça não achada (tag Roca_)\n"); return; }
	UStaticMesh* Malha = nullptr;
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		if (It->ActorHasTag(TEXT("ModeloMilho")))
		{
			if (const UStaticMeshComponent* C = It->FindComponentByClass<UStaticMeshComponent>()) Malha = C->GetStaticMesh();
		}
	}
	// grade da pulverização: altura do chão no meio de cada célula
	RocaNX = FMath::Max(1, FMath::FloorToInt(Roca.GetSize().X / TamCelula));
	RocaNY = FMath::Max(1, FMath::FloorToInt(Roca.GetSize().Y / TamCelula));
	ChaoCelula.SetNum(RocaNX * RocaNY);
	CelulaFeita.Init(0, RocaNX * RocaNY);
	FCollisionQueryParams Q(SCENE_QUERY_STAT(Roca), true);
	auto Chao = [this, &Q](const FVector2D& P, float& Z, AActor** Quem)
	{
		FHitResult Hit;
		if (!GetWorld()->LineTraceSingleByChannel(Hit, FVector(P, 30000.f), FVector(P, -30000.f), ECC_Visibility, Q)) return false;
		Z = Hit.ImpactPoint.Z;
		if (Quem) *Quem = Hit.GetActor();
		return true;
	};
	for (int32 y = 0; y < RocaNY; ++y)
	{
		for (int32 x = 0; x < RocaNX; ++x)
		{
			float Z = 0.f;
			Chao(FVector2D(Roca.Min.X + (x + 0.5f) * TamCelula, Roca.Min.Y + (y + 0.5f) * TamCelula), Z, nullptr);
			ChaoCelula[y * RocaNX + x] = Z;
		}
	}
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		if (It->ActorHasTag(TEXT("Milharal")))
		{
			DiagCampo += FString::Printf(TEXT("milho: milharal pronto no mapa (malha fixa), roça %dx%d células\n"), RocaNX, RocaNY);
			return;
		}
	}
	if (!Malha) { DiagCampo += TEXT("milho: SEM MALHA (ModeloMilho não achado)\n"); return; }
	AActor* Dono = GetWorld()->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity);
	if (!Dono) return;
	UInstancedStaticMeshComponent* H = NewObject<UInstancedStaticMeshComponent>(Dono, TEXT("Milho"));
	H->SetMobility(EComponentMobility::Movable);
	H->SetStaticMesh(Malha);
	H->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	H->SetCastShadow(true);
	Dono->SetRootComponent(H);
	H->RegisterComponent();
	Dono->AddInstanceComponent(H);
	FRandomStream R(77);
	TArray<FTransform> Ts;
	for (float X = Roca.Min.X + 60.f; X < Roca.Max.X - 30.f; X += 95.f)           // fileiras
	{
		for (float Y = Roca.Min.Y + 30.f; Y < Roca.Max.Y - 30.f; Y += 38.f)      // pés na fileira
		{
			const FVector2D P(X + R.FRandRange(-8.f, 8.f), Y + R.FRandRange(-6.f, 6.f));
			float Z = 0.f;
			AActor* Quem = nullptr;
			if (!Chao(P, Z, &Quem) || !Quem || !Quem->ActorHasTag(TEXT("Terreno"))) continue;
			const float E = R.FRandRange(0.85f, 1.15f);
			Ts.Add(FTransform(FRotator(R.FRandRange(-4.f, 4.f), R.FRand() * 360.f, R.FRandRange(-4.f, 4.f)), FVector(P, Z - 3.f), FVector(E, E, E * R.FRandRange(0.9f, 1.1f))));
		}
	}
	H->AddInstances(Ts, false, true);
	H->MarkRenderStateDirty();
	DiagCampo += FString::Printf(TEXT("milho: %d pés (malha %s), roça %dx%d células, chão no meio %.0f cm\n"), Ts.Num(), *Malha->GetName(), RocaNX, RocaNY, ChaoCelula.Num() ? ChaoCelula[ChaoCelula.Num() / 2] : 0.f);
	UE_LOG(LogPredio, Log, TEXT("Campo: %d pés de milho, roça %dx%d células"), Ts.Num(), RocaNX, RocaNY);
}

// ------------------------------------------------------------------ capim do campo (espalhado ao abrir o mapa)

void APredioGameMode::EspalharGrama()
{
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		if (It->ActorHasTag(TEXT("Pasto"))) { DiagCampo += TEXT("capim: pasto pronto no mapa (malha fixa)\n"); return; }
	}
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
	if (!Malha) { DiagCampo += TEXT("capim: SEM MALHA (ModeloGrama não achado)\n"); return; }
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
	UInstancedStaticMeshComponent* H = NewObject<UInstancedStaticMeshComponent>(Dono, TEXT("Capim"));
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
	int32 SemAcerto = 0;
	FString OutroAtor;
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
			if (Roca.bIsValid && Roca.ExpandBy(300.f).IsInside(P)) continue;
			if (Acude.Z > 0.f && FMath::Square((P.X - Acude.X) / Acude.Z) + FMath::Square((P.Y - Acude.Y) / Acude.W) < 1.f) continue;
			FHitResult Hit;
			if (!GetWorld()->LineTraceSingleByChannel(Hit, FVector(P, 30000.f), FVector(P, -30000.f), ECC_Visibility, Q)) { ++SemAcerto; continue; }
			if (!Hit.GetActor() || !Hit.GetActor()->ActorHasTag(TEXT("Terreno")))
			{
				if (Hit.GetActor() && OutroAtor.IsEmpty()) OutroAtor = Hit.GetActor()->GetName();
				continue; // em cima de pedra, árvore, base...
			}
			if (Hit.ImpactNormal.Z < 0.82f) continue;
			const float E = R.FRandRange(0.75f, 1.45f);
			Ts.Add(FTransform(FRotator(0.f, R.FRand() * 360.f, 0.f), Hit.ImpactPoint - FVector(0, 0, 4.f), FVector(E, E, E * R.FRandRange(0.85f, 1.25f))));
			++Feitos;
		}
	}
	DiagCampo += FString::Printf(TEXT("capim: traços sem acerto %d, primeiro outro ator atingido: %s\n"), SemAcerto, *OutroAtor);
	H->AddInstances(Ts, false, true);
	H->MarkRenderStateDirty();
	DiagCampo += FString::Printf(TEXT("capim: %d touceiras (malha %s, %d instâncias no componente)\n"), Ts.Num(), *Malha->GetName(), H->GetInstanceCount());
	UE_LOG(LogPredio, Log, TEXT("Campo: %d touceiras de capim"), Ts.Num());
}

// ------------------------------------------------------------------ teste de chão, decolagem e pouso (-testepouso)

void APredioGameMode::TickTestePouso(float Dt)
{
	ADronePawn* D = Drone();
	if (!D) return;
	TesteT += Dt;
	const FVector P = D->GetActorLocation();
	// chão logo abaixo (para ver se o drone afunda nele)
	float Chao = -1e9f;
	{
		FHitResult Hit;
		FCollisionQueryParams Q(SCENE_QUERY_STAT(TesteChao), true, D);
		if (GetWorld()->LineTraceSingleByChannel(Hit, P + FVector(0, 0, 20.f), P - FVector(0, 0, 3000.f), ECC_Visibility, Q)) Chao = Hit.ImpactPoint.Z;
	}
	const float Folga = P.Z - Chao;   // cm do centro do drone até o chão (raio do corpo = 11)
	if (TesteT > 0.5f) TesteMenorFolga = FMath::Min(TesteMenorFolga, Folga);
	TesteLog -= Dt;
	if (TesteLog <= 0.f)
	{
		TesteLog = 0.25f;
		TesteLinhas.Add(FString::Printf(TEXT("t %5.2f  z %8.1f  chão %8.1f  folga %6.1f  vz %6.1f  motores %d  decolando %d  pousando %d"),
			TesteT, P.Z, Chao, Folga, D->Velocidade.Z, D->bMotores ? 1 : 0, D->bDecolando ? 1 : 0, D->bPousando ? 1 : 0));
	}
	auto Foto = [this](const TCHAR* Nome) { FScreenshotRequest::RequestScreenshot(PastaTestes / Nome, true, false); };
	if (TesteFase == 0 && TesteT > 2.5f) { Foto(TEXT("pouso_1_parado_no_chao.png")); TesteFase = 1; }
	else if (TesteFase == 1 && TesteT > 3.5f) { D->AlternarDecolagem(); TesteLinhas.Add(TEXT("--- apertou DECOLAR")); TesteFase = 2; }
	else if (TesteFase == 2 && TesteT > 8.0f) { Foto(TEXT("pouso_2_no_ar.png")); TesteFase = 3; }
	else if (TesteFase == 3 && TesteT > 9.0f) { D->AlternarDecolagem(); TesteLinhas.Add(TEXT("--- apertou POUSAR")); TesteFase = 4; }
	else if (TesteFase == 4 && TesteT > 15.0f) { Foto(TEXT("pouso_3_pousou.png")); TesteFase = 5; }
	else if (TesteFase == 5 && TesteT > 16.0f)
	{
		TesteLinhas.Add(FString::Printf(TEXT("RESULTADO: menor folga até o chão %.1f cm (abaixo de ~8 = afundou)  motores no fim %d  batidas %d"),
			TesteMenorFolga, D->bMotores ? 1 : 0, D->Batidas));
		IPlatformFile& PF = FPlatformFileManager::Get().GetPlatformFile();
		PF.CreateDirectoryTree(*PastaTestes);
		FFileHelper::SaveStringArrayToFile(TesteLinhas, *(PastaTestes / TEXT("teste_pouso.txt")));
		TesteFase = 6;
		UKismetSystemLibrary::QuitGame(this, GetWorld()->GetFirstPlayerController(), EQuitPreference::Quit, false);
	}
}
