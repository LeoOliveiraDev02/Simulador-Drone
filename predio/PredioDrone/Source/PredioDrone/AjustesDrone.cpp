#include "AjustesDrone.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "HAL/IConsoleManager.h"

const int32 FAjustesDrone::MetasFPS[] = { 0, 30, 60, 90, 120, 144, 165, 240 };
const int32 FAjustesDrone::NumMetas = UE_ARRAY_COUNT(FAjustesDrone::MetasFPS);

FAjustesDrone& FAjustesDrone::Get()
{
	static FAjustesDrone Instancia;
	static bool bCarregado = false;
	if (!bCarregado)
	{
		bCarregado = true;
		Instancia.Carregar();
	}
	return Instancia;
}

FString FAjustesDrone::Arquivo()
{
	return FPaths::ConvertRelativePathToFull(FPaths::ProjectDir()) / TEXT("Configuracoes_Drone.txt");
}

void FAjustesDrone::Carregar()
{
	TArray<FString> Linhas;
	if (!FFileHelper::LoadFileToStringArray(Linhas, *Arquivo())) return;
	for (const FString& L : Linhas)
	{
		FString K, V;
		if (!L.Split(TEXT("="), &K, &V)) continue;
		K.TrimStartAndEndInline();
		V.TrimStartAndEndInline();
		const float F = FCString::Atof(*V);
		const bool B = F != 0.f;
		if (K == TEXT("Sensibilidade")) Sensibilidade = FMath::Clamp(F, 0.3f, 2.0f);
		else if (K == TEXT("Expo")) Expo = FMath::Clamp(F, 0.f, 0.8f);
		else if (K == TEXT("InvArfagem")) bInvArfagem = B;
		else if (K == TEXT("InvAcelerador")) bInvAcelerador = B;
		else if (K == TEXT("InvGuinada")) bInvGuinada = B;
		else if (K == TEXT("InvRolagem")) bInvRolagem = B;
		else if (K == TEXT("ComecarAcro")) bComecarAcro = B;
		else if (K == TEXT("Volume")) Volume = FMath::Clamp(F, 0.f, 1.f);
		else if (K == TEXT("ModoFSR")) ModoFSR = FMath::Clamp((int32)F, 0, 3);
		else if (K == TEXT("Gerador")) bGerador = B;
		else if (K == TEXT("VSync")) bVSync = B;
		else if (K == TEXT("Painel")) bPainel = B;
		else if (K == TEXT("AjusteAuto")) bAjusteAuto = B;
		else if (K == TEXT("EscalaInterface")) EscalaInterface = FMath::Clamp(F, 0.7f, 1.6f);
		else if (K == TEXT("MetaFPS")) MetaFPS = FMath::Clamp((int32)F, 0, 360);
		else if (K == TEXT("VelMaxKmh")) VelMaxKmh = FMath::Clamp(F, 25.f, 90.f);
		else if (K == TEXT("VentoKmh")) VentoKmh = FMath::Clamp(F, 0.f, 40.f);
		else if (K == TEXT("Rajadas")) bRajadas = B;
		else if (K == TEXT("VolumeEfeitos")) VolumeEfeitos = FMath::Clamp(F, 0.f, 1.f);
		else if (K.StartsWith(TEXT("Recorde_")) || K.StartsWith(TEXT("Medalha_")))
		{
			const int32 I = FCString::Atoi(*K.RightChop(8));
			if (I >= 0 && I < NumObjetivos)
			{
				if (K.StartsWith(TEXT("Recorde_"))) Recordes[I] = FMath::Max(0.f, F);
				else Medalhas[I] = FMath::Clamp((int32)F, 0, 3);
			}
		}
		// nomes antigos (versão de 18/11 de madrugada)
		else if (K == TEXT("RecordeTopo")) Recordes[1] = FMath::Max(0.f, F);
		else if (K == TEXT("RecordeAros")) Recordes[2] = FMath::Max(0.f, F);
		else if (K == TEXT("RecordeRelogio")) Recordes[3] = FMath::Max(0.f, F);
	}
}

void FAjustesDrone::Salvar() const
{
	TArray<FString> L;
	L.Add(FString::Printf(TEXT("Sensibilidade=%.2f"), Sensibilidade));
	L.Add(FString::Printf(TEXT("Expo=%.2f"), Expo));
	L.Add(FString::Printf(TEXT("InvArfagem=%d"), bInvArfagem ? 1 : 0));
	L.Add(FString::Printf(TEXT("InvAcelerador=%d"), bInvAcelerador ? 1 : 0));
	L.Add(FString::Printf(TEXT("InvGuinada=%d"), bInvGuinada ? 1 : 0));
	L.Add(FString::Printf(TEXT("InvRolagem=%d"), bInvRolagem ? 1 : 0));
	L.Add(FString::Printf(TEXT("ComecarAcro=%d"), bComecarAcro ? 1 : 0));
	L.Add(FString::Printf(TEXT("Volume=%.2f"), Volume));
	L.Add(FString::Printf(TEXT("ModoFSR=%d"), ModoFSR));
	L.Add(FString::Printf(TEXT("Gerador=%d"), bGerador ? 1 : 0));
	L.Add(FString::Printf(TEXT("VSync=%d"), bVSync ? 1 : 0));
	L.Add(FString::Printf(TEXT("Painel=%d"), bPainel ? 1 : 0));
	L.Add(FString::Printf(TEXT("AjusteAuto=%d"), bAjusteAuto ? 1 : 0));
	L.Add(FString::Printf(TEXT("EscalaInterface=%.2f"), EscalaInterface));
	L.Add(FString::Printf(TEXT("MetaFPS=%d"), MetaFPS));
	L.Add(FString::Printf(TEXT("VelMaxKmh=%.0f"), VelMaxKmh));
	L.Add(FString::Printf(TEXT("VentoKmh=%.0f"), VentoKmh));
	L.Add(FString::Printf(TEXT("Rajadas=%d"), bRajadas ? 1 : 0));
	L.Add(FString::Printf(TEXT("VolumeEfeitos=%.2f"), VolumeEfeitos));
	for (int32 i = 1; i < NumObjetivos; ++i)
	{
		L.Add(FString::Printf(TEXT("Recorde_%d=%.2f"), i, Recordes[i]));
		L.Add(FString::Printf(TEXT("Medalha_%d=%d"), i, Medalhas[i]));
	}
	FFileHelper::SaveStringArrayToFile(L, *Arquivo());
}

void FAjustesDrone::AplicarGraficos() const
{
	auto Set = [](const TCHAR* Nome, int32 V)
	{
		if (IConsoleVariable* C = IConsoleManager::Get().FindConsoleVariable(Nome)) C->Set(V, ECVF_SetByConsole);
	};
	Set(TEXT("r.FidelityFX.FSR.Enabled"), 1);
	Set(TEXT("r.FidelityFX.FSR.QualityMode"), ModoFSR);
	Set(TEXT("r.FidelityFX.FI.Enabled"), bGerador ? 1 : 0);
	Set(TEXT("r.VSync"), bVSync ? 1 : 0);
	// meta de FPS: com o gerador ligado metade dos quadros é criada pela IA, então a base fica na metade
	const int32 Base = MetaFPS <= 0 ? 0 : (bGerador ? FMath::Max(20, MetaFPS / 2) : MetaFPS);
	if (IConsoleVariable* C = IConsoleManager::Get().FindConsoleVariable(TEXT("t.MaxFPS"))) C->Set((float)Base, ECVF_SetByConsole);
}
