# IAssis Pianos — Backend FastAPI

CRM + Secretária Executiva + Gestora de Marketing da **Assis Pianos**.

---

## Módulos

| Módulo | Endpoints |
|---|---|
| Clientes | `/clientes` |
| Leads (Marketing) | `/leads` |
| Negócios (Funil) | `/negocios` |
| Documentos (Orçamento + Contrato) | `/documentos` |
| Campanhas | `/campanhas` |
| Agenda | `/agenda` |
| Dashboard | `/dashboard` |

---

## Rodar localmente

### 1. Postgres via Docker
```bash
docker run --name iassis-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=iassis \
  -p 5432:5432 -d postgres:16
```

### 2. Instalar dependências
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configurar .env
```bash
cp .env.example .env
# Editar DATABASE_URL e dados da empresa
```

### 4. Rodar
```bash
uvicorn app.main:app --reload
```

Acesse: http://localhost:8000/docs

---

## Deploy no Render

### PostgreSQL
1. New → PostgreSQL → Nome: `iassis-postgres`
2. Copie a **Internal Database URL**

### Web Service
1. New → Web Service → conecte o repositório GitHub
2. Runtime: **Python**
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `./start.sh`

### Variáveis de Ambiente (copie do .env.example)
```
DATABASE_URL        → URL interna do PostgreSQL do Render
APP_NAME            → IAssis Pianos
COMPANY_NAME        → JR NASCIMENTOS VENDA E CONSERTO DE INSTRUMENTOS MUSICAIS LTDA.
COMPANY_CNPJ        → 09.481.301/0001-59
COMPANY_CNPJ_CONTRATO → 09.481.301/0002-30
COMPANY_CPF_SOCIO   → 408.321.983-15
COMPANY_ADDRESS     → Av. Rui Barbosa, 780 lj.10 – Meireles – Fortaleza – CE
COMPANY_PHONE       → (85) 3067-1283 / 99622-4480
COMPANY_EMAIL       → otpianos@yahoo.com.br / assispianos@hotmail.com
COMPANY_RESPONSAVEL → Francisco de Assis do Nascimento Jr.
DEFAULT_BUDGET_VALID_DAYS → 7
```

---

## Fluxo completo de exemplo

### 1. Criar cliente
```json
POST /clientes
{
  "nome": "João da Silva",
  "telefone": "85999990000",
  "cidade": "Fortaleza/CE",
  "cpf_cnpj": "123.456.789-00",
  "origem": "Instagram"
}
```

### 2. Criar negócio
```json
POST /negocios
{
  "cliente_id": 1,
  "tipo": "manutencao",
  "observacoes": "Reparo geral + afinação"
}
```

### 3. Gerar Orçamento (gera PDF automaticamente)
```json
POST /documentos/orcamento
{
  "negocio_id": 1,
  "cliente_nome": "João da Silva",
  "cliente_telefone": "85999990000",
  "cliente_cidade": "Fortaleza/CE",
  "itens": [
    { "descricao": "Troca Tampa do Cepo", "valor": 350 },
    { "descricao": "Imunização Geral", "valor": 700 },
    { "descricao": "Reparo Geral do Móvel e Verniz Brilhante", "valor": 3000 },
    { "descricao": "Reparo Geral do Mecanismo e Teclado", "valor": 4500 },
    { "descricao": "Afinação e Regulagem", "valor": 1200 },
    { "descricao": "Polimentos dos Metais e Limpeza Geral", "valor": 250 }
  ],
  "condicoes_pagamento": "40% na retirada e restante na entrega",
  "prazo_entrega_dias": 60
}
```

→ Download PDF: `GET /documentos/orcamento/{doc_id}/pdf`

### 4. Gerar Contrato de Locação
```json
POST /documentos/contrato-locacao
{
  "negocio_id": 2,
  "locatario_nome": "Maria Souza",
  "locatario_endereco": "Rua das Flores, 123 – Meireles, Fortaleza/CE",
  "descricao_piano": "piano meia cauda Yamaha C3",
  "valor_total": 12000,
  "data_entrega_dia": "15",
  "data_entrega_mes": "março",
  "local_entrega": "Hotel Gran Marquise",
  "data_segunda_parcela_dia": "15",
  "data_segunda_parcela_mes": "março",
  "data_contrato_dia": "03",
  "data_contrato_mes": "março"
}
```

→ Download PDF: `GET /documentos/contrato-locacao/{doc_id}/pdf`

---

## Funil de Vendas

Status disponíveis:
- `novo` → 🟡
- `orcamento_enviado` → 🔵
- `negociacao` → 🟠
- `fechado` → 🟢
- `perdido` → 🔴

Atualizar: `PUT /negocios/{id}/status { "status": "fechado" }`
# Aissis_back
