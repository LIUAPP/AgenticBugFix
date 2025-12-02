# Based on https://github.com/openai/codex/blob/main/codex-cli/Dockerfile
FROM node:22-slim

ARG TZ
ENV TZ="$TZ"

# Install basic development tools, python, and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    aggregate \
    ca-certificates \
    curl \
    dnsutils \
    fzf \
    gh \
    git \
    gnupg2 \
    iproute2 \
    ipset \
    iptables \
    jq \
    less \
    man-db \
    procps \
    unzip \
    ripgrep \
    zsh \
    && rm -rf /var/lib/apt/lists/*

# Ensure default node user has access to /usr/local/share
RUN mkdir -p /usr/local/share/npm-global && \
    chown -R node:node /usr/local/share

ARG USERNAME=node

# Set up non-root user
USER node

# Install global packages
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin

# --- Python Setup for Service Wrapper ---
WORKDIR /app
ENV VIRTUAL_ENV=/app/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY --chown=node:node requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Codex CLI Setup ---
# Note: You must provide dist/codex.tgz in the build context for this to work.
# If you do not have it, comment out the following lines.
COPY --chown=node:node dist/codex.tgz codex.tgz
RUN npm install -g codex.tgz \
    && npm cache clean --force \
    && rm -rf /usr/local/share/npm-global/lib/node_modules/codex-cli/node_modules/.cache \
    && rm -rf /usr/local/share/npm-global/lib/node_modules/codex-cli/tests \
    && rm -rf /usr/local/share/npm-global/lib/node_modules/codex-cli/docs

# Inside the container we consider the environment already sufficiently locked
# down, therefore instruct Codex CLI to allow running without sandboxing.
ENV CODEX_UNSAFE_ALLOW_NO_SANDBOX=1

# Copy and set up firewall script as root.
USER root
COPY --chown=root:root scripts/init_firewall.sh /usr/local/bin/
RUN chmod 500 /usr/local/bin/init_firewall.sh

# Drop back to non-root.
USER node

COPY --chown=node:node main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
