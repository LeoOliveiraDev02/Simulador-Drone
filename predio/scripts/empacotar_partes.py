"""Empacota uma pasta em vários .zip de até LIMITE_MB cada (para mandar ao PC em partes).

Uso: python empacotar_partes.py PASTA_ORIGEM PREFIXO_DENTRO_DO_ZIP SAIDA_BASE [LIMITE_MB]
Ex.:  python empacotar_partes.py recursos_predio recursos /tmp/predio_recursos 380
      -> /tmp/predio_recursos_parte01.zip, _parte02.zip ...
Cada pasta de material/modelo fica inteira dentro de um único zip.
Todas as partes extraem para a mesma árvore (PREFIXO/...), então é só extrair todas no mesmo lugar.
"""
import os
import sys
import zipfile

JA_COMPRIMIDO = {".jpg", ".jpeg", ".png", ".zip", ".7z"}


def blocos(origem):
    """Cada bloco = uma pasta-folha de recurso (ex.: texturas/concreto/cracked_concrete)."""
    for raiz, pastas, arquivos in os.walk(origem):
        pastas.sort()
        if arquivos:
            caminhos = [os.path.join(raiz, a) for a in sorted(arquivos)]
            yield raiz, caminhos, sum(os.path.getsize(c) for c in caminhos)


def main():
    origem, prefixo, saida = sys.argv[1], sys.argv[2], sys.argv[3]
    limite = int(sys.argv[4]) if len(sys.argv) > 4 else 380
    limite_b = limite * 1024 * 1024
    partes, atual, tam = [], [], 0
    for raiz, caminhos, t in blocos(origem):
        if atual and tam + t > limite_b:
            partes.append(atual)
            atual, tam = [], 0
        atual.extend(caminhos)
        tam += t
    if atual:
        partes.append(atual)
    for i, arquivos in enumerate(partes, 1):
        nome = f"{saida}_parte{i:02d}.zip"
        with zipfile.ZipFile(nome, "w") as z:
            for c in arquivos:
                rel = os.path.relpath(c, origem).replace(os.sep, "/")
                ext = os.path.splitext(c)[1].lower()
                modo = zipfile.ZIP_STORED if ext in JA_COMPRIMIDO else zipfile.ZIP_DEFLATED
                z.write(c, f"{prefixo}/{rel}", compress_type=modo)
        print(nome, os.path.getsize(nome) // 2**20, "MB", len(arquivos), "arquivos")


if __name__ == "__main__":
    main()
