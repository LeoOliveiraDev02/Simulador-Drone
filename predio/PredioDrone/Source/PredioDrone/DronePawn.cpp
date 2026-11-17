#include "DronePawn.h"
#include "PredioDrone.h"
#include "AjustesDrone.h"
#include "Components/SphereComponent.h"
#include "Components/AudioComponent.h"
#include "Camera/CameraComponent.h"
#include "Sound/SoundWaveProcedural.h"
#include "GameFramework/PlayerController.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "CollisionQueryParams.h"

namespace
{
	constexpr float G = 9.81f;
	constexpr float PassoFixo = 1.f / 240.f;
	constexpr float RaioCorpo = 11.f;
	constexpr int32 TaxaAmostra = 48000;

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

	FPostProcessSettings& PP = Camera->PostProcessSettings;
	PP.bOverride_VignetteIntensity = true;      PP.VignetteIntensity = 0.55f;
	PP.bOverride_SceneFringeIntensity = true;   PP.SceneFringeIntensity = 0.5f;
	PP.bOverride_FilmGrainIntensity = true;     PP.FilmGrainIntensity = 0.0f; // granulado piscava junto com o gerador de quadros
	PP.bOverride_MotionBlurAmount = true;       PP.MotionBlurAmount = 0.12f;
	PP.bOverride_MotionBlurMax = true;          PP.MotionBlurMax = 3.f;
	PP.bOverride_BloomIntensity = true;         PP.BloomIntensity = 0.35f;
	PP.bOverride_AutoExposureMinBrightness = true; PP.AutoExposureMinBrightness = -1.5f; // EV100
	PP.bOverride_AutoExposureMaxBrightness = true; PP.AutoExposureMaxBrightness = 11.0f;
	PP.bOverride_AutoExposureSpeedUp = true;    PP.AutoExposureSpeedUp = 2.0f;
	PP.bOverride_AutoExposureSpeedDown = true;  PP.AutoExposureSpeedDown = 1.2f;

	Audio = CreateDefaultSubobject<UAudioComponent>(TEXT("SomMotores"));
	Audio->SetupAttachment(Corpo);
	Audio->bAutoActivate = false;
	Audio->bAllowSpatialization = false;
	Audio->bIsUISound = false;

	AutoPossessPlayer = EAutoReceiveInput::Player0;
	EmpuxoMax = Massa * G / 0.42f;
}

void ADronePawn::BeginPlay()
{
	Super::BeginPlay();
	Orientacao = GetActorQuat();
	AlturaAlvo = GetActorLocation().Z;
	Inicio = GetActorTransform();
	Modo = FAjustesDrone::Get().bComecarAcro ? EModoVoo::Acro : EModoVoo::Estabilizado;
	MostrarMensagem(TEXT("Analógico esquerdo para cima (ou W) decola  •  Start / Esc abre o menu"), 6.f);

	BufferAudio.SetNumZeroed(4096);
	Onda = NewObject<USoundWaveProcedural>(this);
	Onda->SetSampleRate(TaxaAmostra);
	Onda->NumChannels = 1;
	Onda->Duration = INDEFINITELY_LOOPING_DURATION;
	Onda->SoundGroup = SOUNDGROUP_Default;
	Onda->bLooping = false;
	Onda->VirtualizationMode = EVirtualizationMode::PlayWhenSilent;
	Onda->OnSoundWaveProceduralUnderflow = FOnSoundWaveProceduralUnderflow::CreateUObject(this, &ADronePawn::GerarAudio);
	Audio->SetSound(Onda);
	Audio->Play();
}

void ADronePawn::EndPlay(const EEndPlayReason::Type Motivo)
{
	if (Audio) Audio->Stop();
	if (Onda) Onda->OnSoundWaveProceduralUnderflow.Unbind();
	Super::EndPlay(Motivo);
}

void ADronePawn::GerarAudio(USoundWaveProcedural* W, int32 Amostras)
{
	if (!W) return;
	const int32 N = FMath::Clamp(Amostras, 256, 4096);
	if (BufferAudio.Num() < N) BufferAudio.SetNumZeroed(N);
	const float AcelAlvo = AudioAcel.load();
	const float Vol = AudioVolume.load();
	if (AudioImpacto.exchange(0) != 0) EnvImpacto = 1.f;

	for (int32 i = 0; i < N; ++i)
	{
		AcelSuave += (AcelAlvo - AcelSuave) * 0.0008f;
		float Tom = 0.f;
		for (int32 m = 0; m < 4; ++m)
		{
			// frequência de passagem das pás: sobe com a rotação de cada motor
			const float F = (95.f + 360.f * FMath::Pow(FMath::Max(AcelSuave, 0.f), 0.75f)) * (1.f + 0.011f * m);
			Fases[m] += F / TaxaAmostra;
			if (Fases[m] > 1.0) Fases[m] -= 1.0;
			const float P = (float)Fases[m];
			Tom += 0.55f * FMath::Sin(2.f * PI * P) + 0.28f * FMath::Sin(4.f * PI * P) + 0.14f * FMath::Sin(6.f * PI * P)
				+ 0.10f * (2.f * P - 1.f);
		}
		Tom *= 0.25f;
		Semente = Semente * 1664525u + 1013904223u;
		const float Ruido = ((Semente >> 9) / 4194304.f) * 2.f - 1.f;
		FiltroRuido += 0.18f * (Ruido - FiltroRuido);   // chiado das hélices
		FiltroVento += 0.02f * (Ruido - FiltroVento);   // ar passando
		const float Motor = Tom * (0.18f + 0.82f * AcelSuave) + FiltroRuido * (0.10f + 0.45f * AcelSuave);
		const float Vento = FiltroVento * 0.6f;
		const float Batida = EnvImpacto * Ruido;
		EnvImpacto *= 0.99965f;
		const float S = FMath::Clamp((Motor * 0.42f + Vento + Batida * 0.7f) * Vol, -1.f, 1.f);
		BufferAudio[i] = (int16)(S * 32000.f);
	}
	W->QueueAudio((const uint8*)BufferAudio.GetData(), N * sizeof(int16));
}

void ADronePawn::MostrarMensagem(const FString& Texto, float Segundos)
{
	Mensagem = Texto;
	TempoMensagem = Segundos;
}

void ADronePawn::TrocarModo()
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
}

void ADronePawn::LerControles(float Dt)
{
	APlayerController* PC = Cast<APlayerController>(GetController());
	if (!PC) return;
	const FAjustesDrone& Cfg = FAjustesDrone::Get();

	// controle (modo 2): esquerdo = acelerador/guinada, direito = frente-trás/lados
	float A = ZonaMorta(PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftY));
	float G1 = ZonaMorta(PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftX));
	float P = ZonaMorta(PC->GetInputAnalogKeyState(EKeys::Gamepad_RightY));
	float R = ZonaMorta(PC->GetInputAnalogKeyState(EKeys::Gamepad_RightX));
	if (Cfg.bInvAcelerador) A = -A;
	if (Cfg.bInvGuinada) G1 = -G1;
	if (Cfg.bInvArfagem) P = -P;
	if (Cfg.bInvRolagem) R = -R;

	// teclado (não inverte)
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
		TrocarModo();
	}
	if (PC->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Left) || PC->WasInputKeyJustPressed(EKeys::R))
	{
		Recomecar(Inicio);
		MostrarMensagem(TEXT("Voltou para o início"));
	}
}

void ADronePawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (TempoMensagem > 0.f) TempoMensagem -= DeltaSeconds;
	AudioVolume.store(bModoTour ? 0.f : FAjustesDrone::Get().Volume);
	AudioAcel.store(bCaido ? 0.f : Acelerador);

	if (bModoTour)
	{
		AtualizarCamera(DeltaSeconds);
		return;
	}
	if (bCongelado)
	{
		return; // menu aberto: o drone fica parado no ar
	}

	LerControles(DeltaSeconds);

	if (bCaido)
	{
		TempoCaido += DeltaSeconds;
		if (TempoCaido > 2.2f)
		{
			Recomecar(Inicio);
			MostrarMensagem(TEXT("Drone recolocado no início"));
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
	const FAjustesDrone& Cfg = FAjustesDrone::Get();
	const float Sens = Cfg.Sensibilidade;
	const FVector Pos = GetActorLocation();
	const FRotator Rot = Orientacao.Rotator();
	const float VelM = Velocidade.Size() / 100.f;

	float Comando = 0.f;

	if (bCaido)
	{
		Comando = 0.f;
		TaxaCorpo *= 0.995f;
	}
	else if (Modo == EModoVoo::Estabilizado)
	{
		float VzAlvo;
		if (FMath::Abs(InAcel) > 0.02f)
		{
			VzAlvo = Expo(InAcel, Cfg.Expo * 0.5f) * 320.f * Sens;
			AlturaAlvo = Pos.Z;
		}
		else
		{
			VzAlvo = FMath::Clamp((AlturaAlvo - Pos.Z) * 2.2f, -150.f, 150.f);
		}
		const float AzAlvo = (VzAlvo - Velocidade.Z) / 100.f * 3.0f + G;

		const FRotator SoGuinada(0.f, Rot.Yaw, 0.f);
		const FVector VLocal = SoGuinada.UnrotateVector(Velocidade) / 100.f;
		const float VMax = 6.5f * Sens;
		const float AxAlvo = FMath::Clamp((Expo(InArfagem, Cfg.Expo) * VMax - VLocal.X) * 2.4f, -7.f, 7.f);
		const float AyAlvo = FMath::Clamp((Expo(InRolagem, Cfg.Expo) * VMax - VLocal.Y) * 2.4f, -7.f, 7.f);
		const float MaxInc = 35.f;
		const float ArfAlvo = FMath::Clamp(-FMath::RadiansToDegrees(FMath::Atan2(AxAlvo, G)), -MaxInc, MaxInc);
		const float RolAlvo = FMath::Clamp(FMath::RadiansToDegrees(FMath::Atan2(AyAlvo, G)), -MaxInc, MaxInc);

		const float K = FMath::Min(1.f, h / 0.09f);
		const float NovaArf = FMath::Lerp(Rot.Pitch, ArfAlvo, K);
		const float NovaRol = FMath::Lerp(Rot.Roll, RolAlvo, K);
		const float NovaGui = Rot.Yaw + Expo(InGuinada, Cfg.Expo) * 170.f * Sens * h;
		Orientacao = FRotator(NovaArf, NovaGui, NovaRol).Quaternion();

		const float CosInc = FMath::Max(0.4f, Orientacao.GetUpVector().Z);
		Comando = FMath::Clamp(Massa * AzAlvo / CosInc / EmpuxoMax, 0.f, 1.f);
	}
	else
	{
		const float TaxaMax = 640.f * Sens;
		const float E = FMath::Clamp(Cfg.Expo + 0.25f, 0.f, 0.9f);
		TaxaCorpo.X = Expo(InRolagem, E) * TaxaMax;
		TaxaCorpo.Y = -Expo(InArfagem, E) * TaxaMax; // para frente = nariz para baixo
		TaxaCorpo.Z = Expo(InGuinada, E) * 420.f * Sens;
		const FQuat Delta = FRotator(TaxaCorpo.Y * h, TaxaCorpo.Z * h, TaxaCorpo.X * h).Quaternion();
		Orientacao = (Orientacao * Delta).GetNormalized();
		Comando = FMath::Clamp(0.42f + InAcel * 0.58f, 0.f, 1.f);
	}

	for (int32 i = 0; i < 4; ++i)
	{
		const float Var = (i % 2 == 0 ? 1.f : -1.f) * 0.004f * FMath::Sin(TremorFase * (1.3f + i * 0.21f));
		Motores[i] += (FMath::Clamp(Comando + Var, 0.f, 1.f) - Motores[i]) * FMath::Min(1.f, h / 0.035f);
	}
	Acelerador = (Motores[0] + Motores[1] + Motores[2] + Motores[3]) * 0.25f;
	TremorFase += h * 60.f;

	float Empuxo = Acelerador * EmpuxoMax;
	{
		FHitResult Chao;
		FCollisionQueryParams Q(SCENE_QUERY_STAT(EfeitoSolo), false, this);
		if (GetWorld()->LineTraceSingleByChannel(Chao, Pos, Pos - FVector(0, 0, 45.f), ECC_Visibility, Q))
		{
			Empuxo *= 1.f + 0.18f * (1.f - Chao.Distance / 45.f);
		}
	}
	const FVector Cima = Orientacao.GetUpVector();
	FVector Forca = Cima * Empuxo;
	Forca += FVector(0, 0, -Massa * G);
	const FVector Vms = Velocidade / 100.f;
	Forca -= Vms * (0.06f + 0.028f * VelM);
	if (bCaido) Forca -= Vms * 0.02f;

	Velocidade += Forca / Massa * 100.f * h;

	MoverComColisao(h);
	PrenderNosLimites();
	SetActorRotation(Orientacao);
}

void ADronePawn::PrenderNosLimites()
{
	if (!bUsarLimites || !Limites.IsValid) return;
	const FVector P = GetActorLocation();
	FVector Q = P;
	for (int32 E = 0; E < 3; ++E)
	{
		if (Q[E] < Limites.Min[E])
		{
			Q[E] = Limites.Min[E];
			if (Velocidade[E] < 0.f) Velocidade[E] = -Velocidade[E] * 0.3f; // encosta na tela e volta devagar
		}
		else if (Q[E] > Limites.Max[E])
		{
			Q[E] = Limites.Max[E];
			if (Velocidade[E] > 0.f) Velocidade[E] = -Velocidade[E] * 0.3f;
		}
	}
	if (!Q.Equals(P, 0.01f))
	{
		Velocidade *= 0.97f;
		if (Q.Z < P.Z) AlturaAlvo = FMath::Min(AlturaAlvo, Limites.Max.Z); // estabilizado não insiste no teto
		SetActorLocation(Q, false, nullptr, ETeleportType::None);
	}
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
			const float Agora = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f;
			if (!bCaido && Impacto > 520.f && Agora - UltimoImpacto > 0.3f)
			{
				bCaido = true;
				TempoCaido = 0.f;
				AudioImpacto.store(1);
				MostrarMensagem(TEXT("BATEU! Hélice quebrada…"), 2.2f);
			}
			else if (Impacto > 150.f)
			{
				if (Impacto > 250.f) AudioImpacto.store(1);
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
		Camera->PostProcessSettings.MotionBlurAmount = 0.f;
	}
	const float Inclinacao = (Modo == EModoVoo::Acro) ? 22.f : 6.f;
	const float Amp = (bModoTour || bCongelado) ? 0.f : (0.04f + 0.10f * Acelerador);
	const FRotator Tremor(
		Amp * FMath::Sin(TremorFase * 2.1f),
		Amp * 0.6f * FMath::Sin(TremorFase * 1.7f + 1.f),
		Amp * 0.8f * FMath::Sin(TremorFase * 2.9f + 2.f));
	Camera->SetRelativeRotation(FRotator(Inclinacao, 0.f, 0.f) + Tremor);
}
