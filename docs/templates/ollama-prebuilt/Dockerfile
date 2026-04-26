FROM ollama/ollama:latest

# ── Configurazione ───────────────────────────────────────────────────────────
# Parametri sovrascrivibili al build:
#   docker build \
#     --build-arg BASE_MODEL=llama3.2:3b \
#     --build-arg NUM_CTX=8192 \
#     --build-arg MODEL_TAG=mymodel:8k \
#     -t ghcr.io/my-org/my-project-ollama:latest .
ARG BASE_MODEL=llama3.1:8b
ARG NUM_CTX=16384
ARG MODEL_TAG=llama3.1:16k

ENV OLLAMA_BASE_MODEL=${BASE_MODEL}
ENV OLLAMA_NUM_CTX=${NUM_CTX}
ENV OLLAMA_MODEL=${MODEL_TAG}

# ── Bake del modello ─────────────────────────────────────────────────────────
# Avvia il server, scarica il modello, crea il modelfile con num_ctx esteso,
# poi ferma il server. I pesi rimangono nel layer dell'immagine.
#
# Note:
#   - Il Modelfile viene scritto su file reale (/tmp/Modelfile). `ollama create -f -`
#     (stdin) non è affidabile tra le versioni di Ollama.
#   - kill/wait è in subshell così `|| true` non maschera errori precedenti.
RUN set -e && \
    ollama serve & \
    SERVER_PID=$! && \
    echo "Waiting for Ollama server..." && \
    until ollama list > /dev/null 2>&1; do sleep 1; done && \
    echo "Pulling ${OLLAMA_BASE_MODEL}..." && \
    ollama pull "${OLLAMA_BASE_MODEL}" && \
    echo "Creating ${OLLAMA_MODEL} with num_ctx=${OLLAMA_NUM_CTX}..." && \
    printf "FROM %s\nPARAMETER num_ctx %s\n" "${OLLAMA_BASE_MODEL}" "${OLLAMA_NUM_CTX}" > /tmp/Modelfile && \
    ollama create "${OLLAMA_MODEL}" -f /tmp/Modelfile && \
    ollama list && \
    rm /tmp/Modelfile && \
    (kill $SERVER_PID && wait $SERVER_PID) 2>/dev/null || true

EXPOSE 11434
