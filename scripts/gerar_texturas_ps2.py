#!/usr/bin/env python3
"""Texturas do chão no estilo PS2 — feitas do zero (nenhuma imagem de jogo usada).

Regras da época que seguimos (ver PDF "Otimização da velha guarda"):
  - textura pequena (128 x 128) e repetível;
  - poucas cores (16, como uma paleta de 4 bits);
  - sem mapa de normal nem rugosidade: o relevo e a luz vêm pintados.

Uso:  python3 scripts/gerar_texturas_ps2.py   (grava em voo_e88/texturas_ps2/)
"""
import os
import numpy as np
from PIL import Image, ImageDraw

T = 128            # tamanho final
S = 256            # desenha no dobro e reduz (bordas mais suaves)
SAIDA = os.path.join(os.path.dirname(__file__), "..", "voo_e88", "texturas_ps2")
rng = np.random.default_rng(1996)


def ruido(tam, beta, semente):
    """Ruído periódico (repete sem emenda): ruído branco filtrado no espaço de frequência."""
    r = np.random.default_rng(semente)
    f = np.fft.fftfreq(tam)
    fx, fy = np.meshgrid(f, f)
    raio = np.sqrt(fx ** 2 + fy ** 2)
    raio[0, 0] = 1.0
    espectro = np.fft.fft2(r.normal(size=(tam, tam))) / raio ** beta
    espectro[0, 0] = 0
    n = np.real(np.fft.ifft2(espectro))
    return (n - n.min()) / (n.max() - n.min())


def rampa(v, cores):
    """Mapeia 0..1 numa rampa de cores (lista de (posição, (r,g,b)))."""
    pos = np.array([c[0] for c in cores])
    rgb = np.array([c[1] for c in cores], dtype=float)
    out = np.zeros(v.shape + (3,))
    for k in range(3):
        out[..., k] = np.interp(v, pos, rgb[:, k])
    return out


def para_imagem(arr):
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def tracos(img, n, comp, cores, semente, vertical=0.7):
    """Folhas de capim: traços curtos, repetidos nas bordas para a textura emendar."""
    r = np.random.default_rng(semente)
    d = ImageDraw.Draw(img)
    for _ in range(n):
        x, y = r.uniform(0, S, 2)
        ang = r.normal(-np.pi / 2, (1 - vertical) * 1.6)
        L = r.uniform(*comp)
        x2, y2 = x + np.cos(ang) * L, y + np.sin(ang) * L
        cor = tuple(int(c) for c in cores[r.integers(len(cores))])
        for ox in (-S, 0, S):
            for oy in (-S, 0, S):
                d.line([(x + ox, y + oy), (x2 + ox, y2 + oy)], fill=cor, width=2)
    return img


def pedrinhas(img, n, raio, base, semente):
    """Pedrinhas com luz pintada: claro em cima à esquerda, sombra embaixo à direita."""
    r = np.random.default_rng(semente)
    d = ImageDraw.Draw(img)
    for _ in range(n):
        x, y = r.uniform(0, S, 2)
        rr = r.uniform(*raio)
        tom = r.uniform(0.75, 1.15)
        c = tuple(int(min(255, v * tom)) for v in base)
        esc = tuple(int(v * 0.55) for v in c)
        cla = tuple(int(min(255, v * 1.3 + 20)) for v in c)
        for ox in (-S, 0, S):
            for oy in (-S, 0, S):
                cx, cy = x + ox, y + oy
                d.ellipse([cx - rr + 1.5, cy - rr * 0.8 + 1.5, cx + rr + 1.5, cy + rr * 0.8 + 1.5], fill=esc)
                d.ellipse([cx - rr, cy - rr * 0.8, cx + rr, cy + rr * 0.8], fill=c)
                d.ellipse([cx - rr * 0.6, cy - rr * 0.6, cx, cy - rr * 0.05], fill=cla)
    return img


def rachaduras(tam, celulas, semente):
    """Distância à borda das células (Voronoi periódico): terra seca rachada."""
    r = np.random.default_rng(semente)
    pts = r.uniform(0, tam, (celulas, 2))
    yy, xx = np.mgrid[0:tam, 0:tam]
    d1 = np.full((tam, tam), 1e9)
    d2 = np.full((tam, tam), 1e9)
    for px, py in pts:
        dx = np.abs(xx - px); dx = np.minimum(dx, tam - dx)
        dy = np.abs(yy - py); dy = np.minimum(dy, tam - dy)
        dd = np.sqrt(dx ** 2 + dy ** 2)
        d2 = np.where(dd < d1, d1, np.minimum(d2, dd))
        d1 = np.minimum(d1, dd)
    return d2 - d1


def finalizar(img, nome, cores=16):
    img = img.resize((T, T), Image.BOX)
    q = img.quantize(colors=cores, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    os.makedirs(SAIDA, exist_ok=True)
    q.convert("RGB").save(os.path.join(SAIDA, nome + ".png"), optimize=True)
    print(nome, "->", len(q.getpalette()) // 3 if q.getpalette() else "?", "entradas de paleta")


# ---------------------------------------------------------------- capim verde
v = ruido(S, 1.1, 1) * 0.65 + ruido(S, 0.6, 2) * 0.35
img = para_imagem(rampa(v, [(0.0, (46, 74, 30)), (0.45, (78, 112, 42)), (0.75, (110, 138, 56)), (1.0, (150, 160, 74))]))
tracos(img, 900, (5, 12), [(58, 92, 34), (96, 132, 50), (128, 156, 64), (150, 164, 80)], 3)
tracos(img, 120, (4, 8), [(176, 170, 96), (40, 62, 26)], 4)
finalizar(img, "capim_verde")

# ---------------------------------------------------------------- capim seco (pasto queimado de sol)
v = ruido(S, 1.1, 5) * 0.65 + ruido(S, 0.6, 6) * 0.35
img = para_imagem(rampa(v, [(0.0, (104, 92, 46)), (0.5, (150, 134, 70)), (1.0, (196, 176, 104))]))
tracos(img, 900, (5, 12), [(128, 112, 54), (170, 150, 80), (204, 186, 116), (112, 118, 52)], 7)
finalizar(img, "capim_seco")

# ---------------------------------------------------------------- terra vermelha (estrada de piçarra)
v = ruido(S, 1.2, 8) * 0.7 + ruido(S, 0.4, 9) * 0.3
img = para_imagem(rampa(v, [(0.0, (96, 58, 44)), (0.5, (126, 80, 60)), (1.0, (152, 106, 82))]))
pedrinhas(img, 140, (1.2, 3.0), (160, 116, 88), 10)
pedrinhas(img, 25, (3.0, 5.0), (150, 128, 108), 11)
finalizar(img, "terra_vermelha")

# ---------------------------------------------------------------- terra batida (seca e rachada)
v = ruido(S, 1.0, 12)
borda = rachaduras(S, 26, 13)
risco = np.clip(1.0 - borda / 3.0, 0, 1)            # 1 em cima da rachadura
base = rampa(v, [(0.0, (116, 86, 58)), (0.5, (146, 112, 76)), (1.0, (172, 138, 98))])
claro = np.clip((borda - 3) / 10.0, 0, 1)[..., None] * 18   # meio da placa um pouco mais claro
arr = base + claro - risco[..., None] * np.array([62, 50, 36])
img = para_imagem(arr)
pedrinhas(img, 30, (1.0, 2.2), (150, 130, 104), 14)
finalizar(img, "terra_batida")
