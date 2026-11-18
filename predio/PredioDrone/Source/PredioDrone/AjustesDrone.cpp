#include "AjustesDrone.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "HAL/IConsoleManager.h"

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
		else if (K == TEXT("RecordeTopo")) RecordeTopo = FMath::Max(0.f, F);
		else if (K == TEXT("RecordeAros")) RecordeAros = FMath::Max(0.f, F);
		else if (K == TEXT("RecordeRelogio")) RecordeRelogio = FMath::Max(0.f, F);
		else if (K == TEXT("MedalhaTopo")) MedalhaTopo = FMath::Clamp((int32)F, 0, 3);
		else if (K == TEXT("MedalhaAros")) MedalhaAros = FMath::Clamp((int32)F, 0, 3);
		else if (K == TEXT("MedalhaRelogio")) MedalhaRelogio = FMath::Clamp((int32)F, 0, 3);
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
	L.Add(FString::Printf(TEXT("RecordeTopo=%.2f"), RecordeTopo));
	L.Add(FString::Printf(TEXT("RecordeAros=%.2f"), RecordeAros));
	L.Add(FString::Printf(TEXT("RecordeRelogio=%.2f"), RecordeRelogio));
	L.Add(FString::Printf(TEXT("MedalhaTopo=%d"), MedalhaTopo));
	L.Add(FString::Printf(TEXT("MedalhaAros=%d"), MedalhaAros));
	L.Add(FString::Printf(TEXT("MedalhaRelogio=%d"), MedalhaRelogio));
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
}
