"""Gera a textura de carbono trançado 2x2 (twill) que repete sem emenda.
Como é uma imagem (e não um padrão calculado no shader), a placa de vídeo usa
mipmaps: de longe a trama vira um cinza escuro uniforme em vez de cintilar.
Uso: python gerar_carbono.py PASTA"""
import sys, os
import numpy as np
from PIL import Image

N = 1024; TOWS = 8; T = N // TOWS
y, x = np.mgrid[0:N, 0:N].astype(np.float32)
i = (x // T).astype(int); j = (y // T).astype(int)
u = (x % T) / T; v = (y % T) / T                 # posição dentro de cada célula
por_cima_h = ((i - j) % 4) < 2                   # fio horizontal por cima (twill 2x2)
# o fio é um "tubo": brilho e altura máximos no meio, caindo nas bordas
across = np.where(por_cima_h, v, u)
along = np.where(por_cima_h, u, v)
tubo = np.sin(np.pi * across) ** 0.6
# cada fio tem 3000 filamentos: listras finas no sentido do fio
rng = np.random.default_rng(3)
fil = rng.normal(0, 1, (N, N)).astype(np.float32)
from numpy.fft import fft2, ifft2
def borrar(a, sx, sy):
    ky = np.fft.fftfreq(N)[:, None]; kx = np.fft.fftfreq(N)[None, :]
    return np.real(ifft2(fft2(a) * np.exp(-(kx * sx) ** 2 * 200 - (ky * sy) ** 2 * 200)))
fh = borrar(fil, 40, 1.5); fv = borrar(fil, 1.5, 40)
filamento = np.where(por_cima_h, fh, fv); filamento /= np.abs(filamento).max() + 1e-6
ondula = 0.85 + 0.15 * np.sin(np.pi * along)
altura = tubo * ondula * 0.85 + 0.15 * (0.5 + 0.5 * filamento) * tubo
# cor: quase preto, fio por cima um pouco mais claro no meio (reflexo das fibras)
base = 0.018 + 0.035 * tubo * ondula + 0.008 * filamento * tubo
# variação suave entre fios horizontais e verticais (a luz pega diferente)
base *= np.where(por_cima_h, 1.0, 0.85)
cor = np.clip(base, 0, 1)
srgb = np.where(cor <= 0.0031308, cor * 12.92, 1.055 * cor ** (1 / 2.4) - 0.055)
os.makedirs(sys.argv[1], exist_ok=True)
Image.fromarray((np.stack([srgb] * 3, -1) * 255).astype(np.uint8)).save(os.path.join(sys.argv[1], 'carbono_cor.png'))
Image.fromarray((np.clip(altura, 0, 1) * 65535).astype(np.uint16)).save(os.path.join(sys.argv[1], 'carbono_altura.png'))
# rugosidade: fio por cima no meio mais liso
rug = np.clip(0.48 - 0.16 * tubo * ondula, 0, 1)
Image.fromarray((rug * 255).astype(np.uint8)).save(os.path.join(sys.argv[1], 'carbono_rugosidade.png'))
print('ok')

# granulado de molde do plástico injetado (fosco "areado" dos drones de brinquedo)
M = 512
g = np.random.default_rng(7).normal(0, 1, (M, M))
ky = np.fft.fftfreq(M)[:, None]; kx = np.fft.fftfreq(M)[None, :]
g = np.real(ifft2(fft2(g) * np.exp(-(kx ** 2 + ky ** 2) * 2500)))
g = (g - g.min()) / (g.max() - g.min())
Image.fromarray((g * 255).astype(np.uint8)).save(os.path.join(sys.argv[1], 'grao_plastico.png'))
