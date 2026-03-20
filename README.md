# IAssis Pianos — Backend

> CRM + Secretária Digital + Bot WhatsApp da **Assis Pianos**  
> Tech: **Python · FastAPI · PostgreSQL · ReportLab · Evolution API v2**

---

## Módulos

| Módulo | Rota | Descrição |
|---|---|---|
| Clientes | `/clientes` | Cadastro e gestão de clientes |
| Leads | `/leads` | Pipeline de marketing com temperatura |
| Negócios | `/negocios` | Funil de vendas (manutenção, locação…) |
| Documentos | `/documentos` | Orçamento, Recibo e Contrato (PDF) |
| Campanhas | `/campanhas` | Campanhas de marketing |
| Agenda | `/agenda` | Agendamentos de afinação / manutenção |
| Dashboard | `/dashboard` | Métricas e KPIs consolidados |
| WhatsApp Bot | `/whatsapp/webhook` | Bot com menu interativo via Evolution API |

---

## Arquitetura

```
app/
├── main.py              # Inicialização FastAPI + CORS
├── settings.py          # Configurações via .env (Pydantic)
├── database.py          # Sessão SQLAlchemy
├── models/              # Modelos ORM (SQLAlchemy)
├── schemas/             # Schemas de entrada/saída (Pydantic)
├── routes/              # Endpoints REST + Webhook WhatsApp
├── services/
│   ├── pdf_generator.py # Geração de PDFs (ReportLab)
│   ├── whatsapp_bot.py  # Máquina de estados do bot
│   ├── evolution_api.py # Cliente HTTP da Evolution API
│   └── scheduler.py     # Jobs agendados (resumo diário)
└── assets/
    ├── logo_recibo.jpeg # Logo usada no Recibo
    ├── logo.png         # Logo usada no Orçamento / Contrato
    └── assinatura.png   # Assinatura do responsável
```

---

## Rodar localmente

### 1. Dependências
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Banco de dados
```bash
# Opção A: PostgreSQL local via Docker
docker run --name iassis-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=iassis \
  -p 5432:5432 -d postgres:16

# Opção B: Supabase (recomendado para produção)
# Configure DATABASE_URL no .env com a URL do Supabase
```

### 3. Configurar `.env`
```bash
cp .env.example .env
# Edite DATABASE_URL, EVOLUTION_API_URL, EVOLUTION_API_KEY, etc.
```

### 4. Rodar
```bash
uvicorn app.main:app --reload
```

Acesse a documentação em: **http://localhost:8000/docs**

---

## Deploy (Oracle Cloud + Docker)

```bash
# Na VM
cd ~/Aissis_back
git pull
sudo docker compose up -d --build iassis-backend
sudo docker compose logs -f iassis-backend
```

O `docker-compose.yml` sobe também a **Evolution API v2** para o bot WhatsApp.

---

## Variáveis de Ambiente (`.env`)

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | URL PostgreSQL (Supabase ou local) |
| `COMPANY_NAME` | Razão social da empresa |
| `COMPANY_CNPJ` | CNPJ principal |
| `COMPANY_ADDRESS` | Endereço completo |
| `COMPANY_PHONE` | Telefones |
| `COMPANY_EMAIL` | E-mails |
| `COMPANY_RESPONSAVEL` | Nome do responsável (aparece na assinatura) |
| `EVOLUTION_API_URL` | URL da Evolution API (ex: `http://IP:8080`) |
| `EVOLUTION_API_KEY` | API Key da Evolution API |
| `EVOLUTION_API_INSTANCE` | Nome da instância (ex: `iassis_bot`) |
| `WHATSAPP_NOTIFY_PHONE` | Número que recebe o resumo diário do bot |

---

## Bot WhatsApp

O bot opera via **Evolution API v2** com um menu interativo:

```
1️⃣  Solicitar Orçamento   → coleta dados → gera PDF → envia
2️⃣  Agendar Afinação     → coleta data/tipo → cria na agenda
3️⃣  Consultar Agenda do dia
0️⃣  Voltar ao menu
```

**Configuração do Webhook (na instância do Manager UI):**
- URL: `http://IP_DA_VM:8000/whatsapp/webhook`
- Eventos habilitados: apenas `MESSAGES_UPSERT`

---

## Documentos PDF

| Documento | Rota POST | Download PDF |
|---|---|---|
| Orçamento | `POST /documentos/orcamento` | `GET /documentos/orcamento/{id}/pdf` |
| Recibo | `POST /documentos/recibo` | `GET /documentos/recibo/{id}/pdf` |
| Contrato Locação | `POST /documentos/contrato-locacao` | `GET /documentos/contrato-locacao/{id}/pdf` |

---

## Funil de Vendas

| Status | Significado |
|---|---|
| `novo` | Negócio recém criado |
| `orcamento_enviado` | Orçamento gerado |
| `negociacao` | Em tratativa |
| `fechado` | Venda concluída ✅ |
| `perdido` | Negócio perdido ❌ |

```bash
# Atualizar status
PUT /negocios/{id}/status
{ "status": "fechado" }
```
