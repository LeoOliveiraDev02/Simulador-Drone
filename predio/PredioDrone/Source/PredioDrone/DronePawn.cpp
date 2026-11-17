#include "DronePawn.h"
#include "PredioDrone.h"
#include "Components/SphereComponent.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/PlayerController.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "CollisionQueryParams.h"

namespace
{
	constexpr float G = 9.81f;               // m/s²
	constexpr float PassoFixo = 1.f / 240.f; // s
	constexpr float RaioCorpo = 11.f;        // cm

	float ZonaMorta(float V, float Z = 0.08f)
	{
		if (FMath::Abs(V) < Z) return 0.f;
		return FMath::Sign(V) * (FMath::Abs(V) - Z) / (1.f - Z);
	}

	float Expo(float V, float E)
	{
		return V * (1.f - E + E * V * V);
	}
}

ADronePawn::ADronePawn()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;

	Corpo = CreateDefaultSubobject<USphereComponent>(TEXT("Corpo"));
	Corpo->InitSphereRadius(RaioCorpo);
	Corpo->SetCollisionProfileName(TEXT("Pawn"));
	Corpo->SetSimulatePhysics(false);
	RootComponent = Corpo;

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("CameraFPV"));
	Camera->SetupAttachment(Corpo);
	Camera->SetRelativeLocation(FVector(6.f, 0.f, 2.f));
	Camera->SetFieldOfView(112.f);
	Camera->bUsePawnControlRotation = false;

	// visual de óculos FPV digital: pouca granulação, vinheta e aberração cromática leves
	FPostProcessSettings& PP = Camera->PostProcessSettings;
	PP.bOverride_VignetteIntensity = true;      PP.VignetteIntensity = 0.55f;
	PP.bOverride_SceneFringeIntensity = true;   PP.SceneFringeIntensity = 0.6f;
	PP.bOverride_FilmGrainIntensity = true;     PP.FilmGrainIntensity = 0.08f;
	PP.bOverride_MotionBlurAmount = true;       PP.MotionBlurAmount = 0.12f;
	PP.bOverride_MotionBlurMax = true;          PP.MotionBlurMax = 3.f;
	PP.bOverride_BloomIntensity = true;         PP.BloomIntensity = 0.35f;
	PP.bOverride_AutoExposureMinBrightness = true; PP.AutoExposureMinBrightness = -1.5f; // EV100 (faixa estendida)
	PP.bOverride_AutoExposureMaxBrightness = true; PP.AutoExposureMaxBrightness = 11.0f;
	PP.bOverride_AutoExposureSpeedUp = true;    PP.AutoExposureSpeedUp = 2.5f;
	PP.bOverride_AutoExposureSpeedDown = true;  PP.AutoExposureSpeedDown = 1.5f;

	AutoPossessPlayer = EAutoReceiveInput::Player0;
	EmpuxoMax = Massa * G / 0.42f; // paira com ~42% do acelerador
}

void ADronePawn::BeginPlay()
{
	Super::BeginPlay();
	Orientacao = GetActorQuat();
	AlturaAlvo = GetActorLocation().Z;
	UltimoCheckpoint = GetActorTransform();
	MostrarMensagem(TEXT("Empurre o analógico esquerdo (ou W) para decolar  •  F1 ajuda"), 6.f);
}

void ADronePawn::MostrarMensagem(const FString& Texto, float Segundos)
{
	Mensagem = Texto;
	TempoMensagem = Segundos;
}

void ADronePawn::Recomecar(const FTransform& Onde)
{
	SetActorLocation(Onde.GetLocation(), false, nullptr, ETeleportType::TeleportPhysics);
	const FRotator R = Onde.Rotator();
	Orientacao = FRotator(0.f, R.Yaw, 0.f).Quaternion();
	SetActorRotation(Orientacao);
	Velocidade = FVector::ZeroVector;
	TaxaCorpo = FVector::ZeroVector;
	Acelerador = 0.f;
	for (float& M : Motores) M = 0.f;
	AlturaAlvo = Onde.GetLocation().Z;
	bCaido = false;
	TempoCaido = 0.f;
	Modo = EModoVoo::Estabilizado;
}

void ADronePawn::LerControles(float Dt)
{
	APlayerController* PC = Cast<APlayerController>(GetController());
	if (!PC) return;

	// controle (modo 2): analógico esquerdo = acelerador/guinada, direito = arfagem/rolagem
	float A = ZonaMorta(PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftY));
	float G1 = ZonaMorta(PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftX));
	float P = ZonaMorta(PC->GetInputAnalogKeyState(EKeys::Gamepad_RightY));
	float R = ZonaMorta(PC->GetInputAnalogKeyState(EKeys::Gamepad_RightX));

	// teclado (reserva)
	auto Tecla = [PC](const FKey& K) { return PC->IsInputKeyDown(K) ? 1.f : 0.f; };
	A += Tecla(EKeys::W) - Tecla(EKeys::S) + Tecla(EKeys::SpaceBar) - Tecla(EKeys::LeftControl);
	G1 += Tecla(EKeys::D) - Tecla(EKeys::A);
	P += Tecla(EKeys::Up) - Tecla(EKeys::Down) + Tecla(EKeys::I) - Tecla(EKeys::K);
	R += Tecla(EKeys::Right) - Tecla(EKeys::Left) + Tecla(EKeys::L) - Tecla(EKeys::J);

	InAcel = FMath::Clamp(A, -1.f, 1.f);
	InGuinada = FMath::Clamp(G1, -1.f, 1.f);
	InArfagem = FMath::Clamp(P, -1.f, 1.f);
	InRolagem = FMath::Clamp(R, -1.f, 1.f);

	if (PC->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Top) || PC->WasInputKeyJustPressed(EKeys::M))
	{
		if (Modo == EModoVoo::Estabilizado)
		{
			Modo = EModoVoo::Acro;
			MostrarMensagem(TEXT("MODO ACRO (manual) — o drone não nivela sozinho"));
		}
		else
		{
			Modo = EModoVoo::Estabilizado;
			AlturaAlvo = GetActorLocation().Z;
			MostrarMensagem(TEXT("MODO ESTABILIZADO — soltou, ele para no ar"));
		}
	}
	if (PC->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Left) || PC->WasInputKeyJustPressed(EKeys::R))
	{
		Recomecar(UltimoCheckpoint);
		MostrarMensagem(TEXT("Voltou para o último portal"));
	}
}

void ADronePawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (TempoMensagem > 0.f) TempoMensagem -= DeltaSeconds;

	if (bModoTour)
	{
		AtualizarCamera(DeltaSeconds);
		return; // o GameMode move o drone no voo automático
	}

	LerControles(DeltaSeconds);

	if (bCaido)
	{
		TempoCaido += DeltaSeconds;
		if (TempoCaido > 2.2f)
		{
			Recomecar(UltimoCheckpoint);
			MostrarMensagem(TEXT("Drone recolocado no último portal"));
		}
	}
	else
	{
		TempoVoo += DeltaSeconds;
	}

	Acumulador += FMath::Min(DeltaSeconds, 0.1f);
	while (Acumulador >= PassoFixo)
	{
		PassoFisica(PassoFixo);
		Acumulador -= PassoFixo;
	}

	Bateria = FMath::Max(3.30f, Bateria - DeltaSeconds * (0.0004f + 0.0022f * Acelerador));
	AtualizarCamera(DeltaSeconds);
}

void ADronePawn::PassoFisica(float h)
{
	const FVector Pos = GetActorLocation();
	const FRotator Rot = Orientacao.Rotator();
	const float VelM = Velocidade.Size() / 100.f;

	float Comando = 0.f; // acelerador pedido 0..1

	if (bCaido)
	{
		Comando = 0.f;
		TaxaCorpo *= 0.995f;
	}
	else if (Modo == EModoVoo::Estabilizado)
	{
		// --- vertical: velocidade de subida pelo analógico, trava de altitude solto ---
		float VzAlvo;
		if (FMath::Abs(InAcel) > 0.02f)
		{
			VzAlvo = InAcel * 320.f;
			AlturaAlvo = Pos.Z;
		}
		else
		{
			VzAlvo = FMath::Clamp((AlturaAlvo - Pos.Z) * 2.2f, -150.f, 150.f);
		}
		const float AzAlvo = (VzAlvo - Velocidade.Z) / 100.f * 3.0f + G; // m/s²

		// --- horizontal: o analógico pede velocidade; solto = freia e para ---
		const FRotator SoGuinada(0.f, Rot.Yaw, 0.f);
		const FVector VLocal = SoGuinada.UnrotateVector(Velocidade) / 100.f; // m/s
		const float VMax = 6.5f;
		const float AxAlvo = FMath::Clamp((InArfagem * VMax - VLocal.X) * 2.4f, -7.f, 7.f);
		const float AyAlvo = FMath::Clamp((InRolagem * VMax - VLocal.Y) * 2.4f, -7.f, 7.f);
		const float MaxInc = 35.f;
		const float ArfAlvo = FMath::Clamp(-FMath::RadiansToDegrees(FMath::Atan2(AxAlvo, G)), -MaxInc, MaxInc);
		const float RolAlvo = FMath::Clamp(FMath::RadiansToDegrees(FMath::Atan2(AyAlvo, G)), -MaxInc, MaxInc);

		const float K = FMath::Min(1.f, h / 0.09f);
		float NovaArf = FMath::Lerp(Rot.Pitch, ArfAlvo, K);
		float NovaRol = FMath::Lerp(Rot.Roll, RolAlvo, K);
		float NovaGui = Rot.Yaw + Expo(InGuinada, 0.3f) * 170.f * h;
		Orientacao = FRotator(NovaArf, NovaGui, NovaRol).Quaternion();

		const float CosInc = FMath::Max(0.4f, Orientacao.GetUpVector().Z);
		Comando = FMath::Clamp(Massa * AzAlvo / CosInc / EmpuxoMax, 0.f, 1.f);
		if (Pos.Z - AlturaAlvo < 1.f && InAcel < -0.5f && Velocidade.Z > -5.f)
		{
			Comando *= 0.9f; // pousando
		}
	}
	else
	{
		// --- ACRO: taxas de rotação com expo, acelerador direto ---
		const float TaxaMax = 640.f;
		TaxaCorpo.X = Expo(InRolagem, 0.55f) * TaxaMax;
		TaxaCorpo.Y = -Expo(InArfagem, 0.55f) * TaxaMax; // analógico para frente = nariz para baixo
		TaxaCorpo.Z = Expo(InGuinada, 0.45f) * 420.f;
		const FQuat Delta = FRotator(TaxaCorpo.Y * h, TaxaCorpo.Z * h, TaxaCorpo.X * h).Quaternion();
		Orientacao = (Orientacao * Delta).GetNormalized();
		// analógico esquerdo: centro = ~meio acelerador
		Comando = FMath::Clamp(0.42f + InAcel * 0.58f, 0.f, 1.f);
	}

	// motores com atraso (inércia das hélices)
	for (int32 i = 0; i < 4; ++i)
	{
		const float Var = (i % 2 == 0 ? 1.f : -1.f) * 0.004f * FMath::Sin(TremorFase * (1.3f + i * 0.21f));
		Motores[i] += (FMath::Clamp(Comando + Var, 0.f, 1.f) - Motores[i]) * FMath::Min(1.f, h / 0.035f);
	}
	Acelerador = (Motores[0] + Motores[1] + Motores[2] + Motores[3]) * 0.25f;
	TremorFase += h * 60.f;

	// forças
	float Empuxo = Acelerador * EmpuxoMax; // N
	{
		// efeito solo
		FHitResult Chao;
		FCollisionQueryParams Q(SCENE_QUERY_STAT(EfeitoSolo), false, this);
		if (GetWorld()->LineTraceSingleByChannel(Chao, Pos, Pos - FVector(0, 0, 45.f), ECC_Visibility, Q))
		{
			Empuxo *= 1.f + 0.18f * (1.f - Chao.Distance / 45.f);
		}
	}
	const FVector Cima = Orientacao.GetUpVector();
	FVector Forca = Cima * Empuxo;                       // N
	Forca += FVector(0, 0, -Massa * G);
	const FVector Vms = Velocidade / 100.f;
	Forca -= Vms * (0.06f + 0.028f * VelM);               // arrasto
	if (bCaido) Forca -= Vms * 0.02f;

	const FVector Acel = Forca / Massa * 100.f;           // cm/s²
	Velocidade += Acel * h;

	MoverComColisao(h);
	SetActorRotation(Orientacao);
}

void ADronePawn::MoverComColisao(float h)
{
	FVector Delta = Velocidade * h;
	for (int32 Iter = 0; Iter < 3 && !Delta.IsNearlyZero(0.001f); ++Iter)
	{
		FHitResult Hit;
		AddActorWorldOffset(Delta, true, &Hit, ETeleportType::None);
		if (!Hit.bBlockingHit) break;

		const FVector N = Hit.ImpactNormal;
		const float Vn = FVector::DotProduct(Velocidade, N);
		if (Vn < 0.f)
		{
			const float Impacto = -Vn;
			Velocidade -= (1.f + 0.25f) * Vn * N;
			Velocidade *= 0.82f;
			const UWorld* W = GetWorld();
			const float Agora = W ? W->GetTimeSeconds() : 0.f;
			if (!bCaido && Impacto > 520.f && Agora - UltimoImpacto > 0.3f)
			{
				bCaido = true;
				TempoCaido = 0.f;
				MostrarMensagem(TEXT("BATEU! Hélice quebrada…"), 2.2f);
			}
			else if (Impacto > 150.f)
			{
				// pancada leve: desequilibra
				const FRotator Chute(FMath::FRandRange(-12.f, 12.f), FMath::FRandRange(-8.f, 8.f), FMath::FRandRange(-12.f, 12.f));
				Orientacao = (Orientacao * Chute.Quaternion()).GetNormalized();
			}
			UltimoImpacto = Agora;
		}
		Delta = FVector::VectorPlaneProject(Delta * (1.f - Hit.Time), N);
	}
}

void ADronePawn::AtualizarCamera(float Dt)
{
	if (bModoTour)
	{
		Camera->PostProcessSettings.MotionBlurAmount = 0.f; // prints nítidos no voo de teste
	}
	// câmera inclinada para cima como nos drones FPV (mais no acro)
	const float Inclinacao = (Modo == EModoVoo::Acro) ? 22.f : 6.f;
	// vibração das hélices (bem sutil) — aumenta com o acelerador
	const float Amp = bModoTour ? 0.f : (0.04f + 0.10f * Acelerador);
	const FRotator Tremor(
		Amp * FMath::Sin(TremorFase * 2.1f),
		Amp * 0.6f * FMath::Sin(TremorFase * 1.7f + 1.f),
		Amp * 0.8f * FMath::Sin(TremorFase * 2.9f + 2.f));
	Camera->SetRelativeRotation(FRotator(Inclinacao, 0.f, 0.f) + Tremor);
}
