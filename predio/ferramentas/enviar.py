"""Prepara arquivos para device_commit_files: copia para /mnt/user-data/outputs com nome ÚNICO
(o envio guarda cache pelo nome; repetir o nome pode mandar a versão antiga).
Uso: enviar.py BASE_LOCAL BASE_PC arquivo1 arquivo2 ..."""
import json, os, shutil, sys, hashlib, time
base, basepc, arqs = sys.argv[1], sys.argv[2], sys.argv[3:]
out = []
v = time.strftime("%H%M%S")
for a in arqs:
    rel = os.path.relpath(a, base)
    dados = open(a, "rb").read()
    h = hashlib.md5(dados).hexdigest()[:8]
    nome = f"v{v}_{h}_{os.path.basename(a)}"
    dst = os.path.join("/mnt/user-data/outputs", nome)
    shutil.copyfile(a, dst)
    out.append({"stagedPath": dst, "devicePath": basepc + "\\" + rel.replace("/", "\\")})
print(json.dumps(out, ensure_ascii=False))
