#pragma once

#include "CoreMinimal.h"

/** Configurações do jogador (menu). Ficam num arquivo ao lado do jogo (disco D), não no C. */
struct FAjustesDrone
{
	float Sensibilidade = 1.0f;   // 0.3 .. 2.0
	float Expo = 0.30f;           // 0 .. 0.8 (suavidade no centro do analógico)
	bool bInvArfagem = true;      // frente/trás (o padrão já vem invertido — pedido do Leonardo)
	bool bInvAcelerador = false;  // subir/descer
	bool bInvGuinada = false;     // girar
	bool bInvRolagem = false;     // lados
	bool bComecarAcro = false;
	float Volume = 0.8f;          // 0 .. 1
	int32 ModoFSR = 1;            // 0 AA nativo, 1 Qualidade, 2 Equilibrado, 3 Desempenho
	bool bGerador = true;
	bool bVSync = false;
	bool bPainel = true;
	bool bAjusteAuto = true;
	float EscalaInterface = 1.0f; // tamanho do OSD (acessibilidade)
	// recordes (segundos; 0 = ainda não tem)
	float RecordeTopo = 0.f;      // prédio: chegar ao topo
	float RecordeAros = 0.f;      // campo: aros em ordem
	float RecordeRelogio = 0.f;   // campo: contra o relógio (tempo total)

	static FAjustesDrone& Get();
	static FString Arquivo();
	void Carregar();
	void Salvar() const;
	void AplicarGraficos() const;
};
