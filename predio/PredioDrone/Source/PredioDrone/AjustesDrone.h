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
	int32 MetaFPS = 0;            // 0 = livre; senão o FPS que o jogo tenta alcançar (e não passa)
	float VelMaxKmh = 50.f;       // velocidade máxima no modo estabilizado (25 .. 90 km/h)
	float VentoKmh = 10.f;        // força do vento (0 .. 40 km/h)
	bool bRajadas = true;         // vento com rajadas
	float VolumeEfeitos = 0.8f;   // sons de coleta, foto, vitória
	static const int32 MetasFPS[];
	static const int32 NumMetas;
	// recordes (segundos; 0 = ainda não tem) e melhor medalha (0 nenhuma, 1 bronze, 2 prata, 3 ouro)
	// de cada objetivo, na ordem do EObjetivo (Livre, Topo, ArosOrdem, ArosRelogio, Entregas, Pulverizar, Fotos, Ferraduras)
	static constexpr int32 NumObjetivos = 8;
	float Recordes[NumObjetivos] = {};
	int32 Medalhas[NumObjetivos] = {};

	static FAjustesDrone& Get();
	static FString Arquivo();
	void Carregar();
	void Salvar() const;
	void AplicarGraficos() const;
};
