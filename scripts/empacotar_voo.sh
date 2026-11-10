#!/bin/bash
# Empacota o código do voo do E88 (sem os recursos pesados) para mandar ao PC.
set -e
cd "$(dirname "$0")/.."
rm -f /tmp/claude-0/entrega/voo_e88.zip
zip -q -r /tmp/claude-0/entrega/voo_e88.zip voo_e88 -x "voo_e88/recursos/*" "voo_e88/.godot/*" "voo_e88/prints/*"
ls -la /tmp/claude-0/entrega/voo_e88.zip
