FROM ollama/ollama:latest

# Build arguments — override at build time to change model or context size:
#   docker build --build-arg BASE_MODEL=llama3.2:3b --build-arg NUM_CTX=8192 .
ARG BASE_MODEL=qwen2.5:7b-instruct
ARG NUM_CTX=16384
ARG MODEL_TAG=qwen2.5:16k

ENV OLLAMA_BASE_MODEL=${BASE_MODEL}
ENV OLLAMA_NUM_CTX=${NUM_CTX}
ENV OLLAMA_MODEL=${MODEL_TAG}

# Pull the base model and create the custom modelfile with extended context.
# The server is started in background, we wait for it, run the setup, then stop it.
# The pulled weights stay in /root/.ollama which is committed to the image layer.
#
# Notes:
#   - Modelfile is written to a real file (/tmp/Modelfile). `ollama create -f -`
#     (stdin) is unreliable across Ollama versions and fails with
#     "no Modelfile or safetensors files found" when piping content in.
#   - The kill/wait at the end is wrapped in a subshell so its `|| true` only
#     swallows the wait warning, not errors from earlier steps in the chain.
RUN set -e && \
    ollama serve & \
    SERVER_PID=$! && \
    echo "Waiting for Ollama server..." && \
    until ollama list > /dev/null 2>&1; do sleep 1; done && \
    echo "Pulling ${OLLAMA_BASE_MODEL}..." && \
    ollama pull "${OLLAMA_BASE_MODEL}" && \
    echo "Creating ${OLLAMA_MODEL} with num_ctx=${OLLAMA_NUM_CTX}..." && \
    printf "FROM %s\nPARAMETER num_ctx %s\n" "${OLLAMA_BASE_MODEL}" "${OLLAMA_NUM_CTX}" > /tmp/Modelfile && \
    cat /tmp/Modelfile && \
    ollama create "${OLLAMA_MODEL}" -f /tmp/Modelfile && \
    echo "Verifying ${OLLAMA_MODEL} is registered:" && \
    ollama list && \
    rm /tmp/Modelfile && \
    echo "Stopping server..." && \
    (kill $SERVER_PID && wait $SERVER_PID) 2>/dev/null || true

EXPOSE 11434
