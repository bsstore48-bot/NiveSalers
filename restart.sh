#!/bin/bash
# restart.sh — Watchdog do bot Nive Vendas
# Fica rodando o bot em loop: se ele cair por qualquer motivo
# (erro de sintaxe, TypeError, exceção não tratada, etc.), reinicia sozinho.
#
# Uso: ./restart.sh   (ou: bash restart.sh)
# Pra rodar em segundo plano no Termux: nohup ./restart.sh > watchdog.log 2>&1 &

cd "$(dirname "$0")" || exit 1

FAST_FAIL_LIMIT=5       # quantas quedas rápidas seguidas até dar uma pausa maior
FAST_FAIL_THRESHOLD=10  # segundos rodando = considerado "queda rápida"
fail_count=0

while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando o bot..."
    start_time=$(date +%s)

    node index.js
    exit_code=$?

    end_time=$(date +%s)
    elapsed=$((end_time - start_time))

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Bot caiu (código de saída: $exit_code). Rodou por ${elapsed}s."

    if [ "$elapsed" -lt "$FAST_FAIL_THRESHOLD" ]; then
        fail_count=$((fail_count + 1))
    else
        fail_count=0
    fi

    if [ "$fail_count" -ge "$FAST_FAIL_LIMIT" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] O bot caiu $fail_count vezes seguidas rápido demais."
        echo "Provavelmente é um erro de sintaxe/código no arquivo que não vai se resolver sozinho reiniciando."
        echo "Aguardando 60s antes de tentar de novo (dá pra corrigir o erro acima enquanto isso)."
        sleep 60
        fail_count=0
    else
        sleep 5
    fi
done
