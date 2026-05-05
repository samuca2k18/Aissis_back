# Monitoramento leve para Oracle VM (1 GB RAM)

Este pacote sobe uma stack com:

- `Prometheus` (metricas)
- `Grafana` (dashboards)
- `Loki` (logs)
- `Alloy` (coletor de logs Docker para o Loki)
- `node-exporter` (metricas do host Linux)

Todos os servicos foram limitados com `mem_limit` e `cpus` para reduzir impacto na VM.

## 1) O que cada componente faz

1. `node-exporter`
   - Le CPU, memoria, disco e rede do host Linux.
   - Expoe em `:9100/metrics` para o Prometheus.

2. `Prometheus`
   - Coleta metricas de `node-exporter`, `loki`, `alloy` e dele mesmo.
   - Guarda pouco historico (2 dias e ate 350 MB) para caber no Free Tier.

3. `Loki`
   - Banco de logs.
   - Retencao configurada em 7 dias (`168h`).
   - Limite de ingestao configurado para evitar explosao de memoria.

4. `Alloy`
   - Conecta no Docker socket.
   - Descobre containers automaticamente.
   - Envia logs dos containers para o Loki.

5. `Grafana`
   - Interface para consultar metricas/logs.
   - Datasources de Prometheus e Loki ja provisionadas automaticamente.

## 2) Pre-requisitos na VM

1. Docker e Docker Compose plugin instalados.
2. Seu backend ja rodando em container Docker (para o Alloy capturar logs dele).

## 3) Passo a passo para subir

1. Criar arquivo de ambiente:

```bash
cp monitoring/.env.monitoring.example monitoring/.env.monitoring
```

2. Edite a senha do Grafana:

```bash
nano monitoring/.env.monitoring
```

3. Subir a stack:

```bash
docker compose \
  --env-file monitoring/.env.monitoring \
  -f monitoring/docker-compose.monitoring.yml \
  up -d
```

4. Verificar se tudo subiu:

```bash
docker compose -f monitoring/docker-compose.monitoring.yml ps
docker stats --no-stream
```

## 4) Como acessar com seguranca

As portas foram expostas apenas em `127.0.0.1` (localhost da VM), por seguranca.

Se quiser abrir no seu computador local, use tunel SSH:

```bash
ssh -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 -L 3100:127.0.0.1:3100 usuario@IP_DA_VM
```

Depois acesse:

- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`

## 5) Login inicial do Grafana

- Usuario: valor de `GRAFANA_ADMIN_USER`
- Senha: valor de `GRAFANA_ADMIN_PASSWORD`

No Explore:
- escolha datasource `Prometheus` para metricas
- escolha datasource `Loki` para logs

## 6) Queries uteis para testar

### Prometheus

- CPU (host): `rate(node_cpu_seconds_total{mode!="idle"}[5m])`
- Memoria livre: `node_memory_MemAvailable_bytes`
- Disco livre: `node_filesystem_avail_bytes`

### Loki

- Todos os logs docker: `{job="docker"}`
- Logs do backend (exemplo de filtro por nome): `{job="docker"} |= "iassis-backend"`

## 7) Operacao do dia a dia

Subir:

```bash
docker compose --env-file monitoring/.env.monitoring -f monitoring/docker-compose.monitoring.yml up -d
```

Parar:

```bash
docker compose -f monitoring/docker-compose.monitoring.yml down
```

Ver logs da stack:

```bash
docker compose -f monitoring/docker-compose.monitoring.yml logs -f
```

## 8) Se faltar memoria (1 GB e apertado)

1. Primeiro veja consumo:

```bash
docker stats --no-stream
```

2. Se precisar aliviar, pare so o Grafana e mantenha coleta:

```bash
docker compose -f monitoring/docker-compose.monitoring.yml stop grafana
```

3. Se ainda estiver pesado, aumente `scrape_interval` no Prometheus para `60s`.

## 9) Arquivos principais

- Compose: `monitoring/docker-compose.monitoring.yml`
- Prometheus: `monitoring/prometheus/prometheus.yml`
- Loki: `monitoring/loki/loki-config.yml`
- Alloy: `monitoring/alloy/config.alloy`
- Datasources Grafana: `monitoring/grafana/provisioning/datasources/datasources.yml`
