FROM mcr.microsoft.com/dotnet/sdk:9.0-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash ubuntu

USER ubuntu
WORKDIR /home/ubuntu

ENV DOTNET_CLI_TELEMETRY_OPTOUT=1
ENV PATH="/home/ubuntu/.dotnet/tools:${PATH}"
