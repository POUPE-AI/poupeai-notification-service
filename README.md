# Notification Service

Serviço de notificações usando FastAPI.

## Estrutura do Projeto

```
poupeai-notification-service
├── requirements/
│   └── base.txt 
├── src/
│   ├── notification_service/
│   │   ├── __init__.py
│   │   ├── models.py      # Modelos do banco de dados
│   │   ├── router.py      # Endpoints
│   │   ├── consumer.py    # Configuração do consumer do RabbitMQ
│   │   ├── exceptions.py  # Exceções personalizadas
│   │   ├── schemas.py     # Modelos pydantic
│   │   ├── config.py      # Configurações locais
│   │   └── service.py     # Regras de négocio
│   │
│   ├── __init__.py
│   ├── config.py          # Configurações globais
│   ├── database.py        # Conexão com o banco de dados
│   └── main.py            
│
├── .env.template
├── .gitignore
└──  README.md
```

## Instalação e Execução

Siga os passos abaixo para configurar e executar o projeto localmente.

### 1. Configurar Variáveis de Ambiente

As configurações da aplicação, como conexões com bancos de dados e serviços externos (RabbitMQ, Redis, etc.), são carregadas a partir de variáveis de ambiente.

Copie o arquivo de template `.env.template` para criar seu próprio arquivo de configuração local `.env`.

```bash
cp .env.template .env
```

Após copiar, **abra o arquivo `.env`** e preencha os valores para cada variável com as suas credenciais e configurações de ambiente.

### 2. Instalar dependências

```bash
pip install -r requirements\base.txt
```

### 3. Executar o serviço

```bash
cd src
python main.py
```

O serviço será iniciado usando as configurações definidas em `config.py`:
- Host: localhost
- Porta: 8001

Também é possível executar usando o uvicorn diretamente especificando a porta

```bash
uvicorn main:app --reload --port 8001
```

## Ambiente de Desenvolvimento com Docker Compose

O método recomendado para executar o projeto localmente é usando Docker Compose. Ele irá configurar a aplicação, o RabbitMQ e o Redis automaticamente.

### 1. Pré-requisitos

- Docker e Docker Compose instalados.
- Crie um arquivo `.env` a partir do template `.env.template` e preencha as variáveis, se necessário.

```bash
cp .env.template .env
```

### 2 Iniciar o Ambiente

Na raiz do projeto, execute o seguinte comando para construir as imagens e iniciar os contêineres:

```bash
docker-compose up --build -d
```

### 3 Verificar os Serviços

Após a execução, os seguintes serviços estarão disponíveis:

  - **API do Serviço de Notificação**: `http://localhost:8001`
      - **Swagger UI**: `http://localhost:8001/api/v1/docs`
  - **Interface de Gerenciamento do RabbitMQ**: `http://localhost:15672`
      - Use as credenciais `RABBITMQ_USER` e `RABBITMQ_PASSWORD` definidas no seu arquivo `.env`.

Para visualizar os logs da aplicação em tempo real, use:

```bash
docker-compose logs -f app
```

### 4 Parar o Ambiente

Para parar todos os contêineres, execute:

```bash
docker-compose down
```

Se desejar remover também os volumes de dados (todas as mensagens e dados do Redis serão perdidos), execute:

```bash
docker-compose down -v
```

### Health Check
- **GET** `/api/v1/health` - Verificar status

## Estratégia de Filas (RabbitMQ)

O serviço utiliza o RabbitMQ para processamento assíncrono de notificações, implementando uma estratégia resiliente com **retentativas automáticas** para falhas temporárias e uma **Dead-Letter Queue (DLQ)** para erros irrecuperáveis.

### Topologia

A arquitetura é composta por um conjunto de filas e exchanges que trabalham juntas para garantir que nenhuma mensagem seja perdida. Os nomes exatos das entidades (ex: `notification_events`, `notification_exchange`) são carregados a partir de variáveis de ambiente para flexibilidade.

1.  **Exchange Principal (`notification_exchange`)**

      * **Tipo:** `Direct`
      * **Responsabilidade:** Ponto de entrada para todas as novas mensagens de notificação.

2.  **Fila Principal (`notification_events`)**

      * **Tipo:** `Durable`
      * **Responsabilidade:** Armazena novas mensagens aguardando a **primeira tentativa** de processamento.

3.  **Exchange de Retry (`notification_exchange.retry`)**

      * **Tipo:** `Direct`
      * **Responsabilidade:** Receber mensagens que falharam no processamento devido a um erro temporário.

4.  **Fila de Retry (`notification_events.retry`)**

      * **Tipo:** `Durable`
      * **Responsabilidade:** Reter temporariamente as mensagens que falharam. Possui um **TTL (Time-To-Live)** que, ao expirar, envia a mensagem de volta à Exchange Principal para uma nova tentativa.

5.  **Dead-Letter Exchange Final (DLX) (`notification_exchange.dlq`)**

      * **Tipo:** `Direct`
      * **Responsabilidade:** Ponto de entrada para mensagens que **não podem ou não devem mais ser processadas**.

6.  **Fila de Dead-Letter Final (DLQ) (`notification_events.dlq`)**

      * **Tipo:** `Durable`
      * **Responsabilidade:** Armazenar permanentemente mensagens com **erros irrecuperáveis** (ex: falha de validação) ou que **excederam o limite de retentativas**.

### Contrato da Mensagem e Payloads de Exemplo

Para ser processada corretamente, toda mensagem enviada ao `notification_exchange` deve seguir um contrato específico, dividido entre as **Propriedades** da mensagem e o **Corpo** (Payload).

#### Propriedades da Mensagem

As seguintes propriedades devem ser configuradas ao publicar a mensagem:

| Propriedade | Valor Exemplo | Obrigatório | Descrição |
| :--- | :--- | :--- | :--- |
| `routing_key` | `notification.event` | Sim | Chave de roteamento para ligar a exchange à fila principal. |
| `correlation_id` | `"trace-abc-123"` | Sim | Identificador para rastreabilidade e logs ponta a ponta. |
| `content_type` | `application/json` | Sim | Indica que o corpo da mensagem é um JSON. |

#### Corpo da Mensagem (Payload)

O corpo da mensagem deve ser um objeto JSON que segue a estrutura abaixo. O campo `message_id` é usado para controle de idempotência.

<details open>
<summary><strong><code>INVOICE_DUE_SOON</code> - Fatura Próxima do Vencimento</strong></summary>

```json
{
  "message_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "timestamp": "2025-07-20T10:00:00Z",
  "trigger_type": "system_scheduled",
  "event_type": "INVOICE_DUE_SOON",
  "recipient": {
    "user_id": "user-987",
    "email": "maria.santos@email.com",
    "name": "Maria Santos"
  },
  "payload": {
    "credit_card": "Cartão BB",
    "month": 7,
    "year": 2025,
    "due_date": "2025-07-25",
    "amount": 150.50,
    "invoice_deep_link": "poupeai://app/invoices/inv-2025-07-1234"
  }
}
```

</details>

<details>
<summary><strong><code>INVOICE_OVERDUE</code> - Fatura Vencida</strong></summary>

```json
{
  "message_id": "b2c3d4e5-f6a7-8901-2345-67890abcdef1",
  "timestamp": "2025-07-26T09:00:00Z",
  "trigger_type": "system_scheduled",
  "event_type": "INVOICE_OVERDUE",
  "recipient": {
    "user_id": "user-987",
    "email": "maria.santos@email.com",
    "name": "Maria Santos"
  },
  "payload": {
    "credit_card": "Cartão BB",
    "month": 7,
    "year": 2025,
    "due_date": "2025-07-25",
    "amount": 150.50,
    "days_overdue": 1,
    "invoice_deep_link": "poupeai://app/invoices/inv-2025-07-1234"
  }
}
```

</details>

<details>
<summary><strong><code>PROFILE_DELETION_SCHEDULED</code> - Exclusão de Perfil Agendada</strong></summary>

```json
{
  "message_id": "c3d4e5f6-a7b8-9012-3456-7890abcdef12",
  "timestamp": "2025-08-01T18:00:00Z",
  "trigger_type": "user_action",
  "event_type": "PROFILE_DELETION_SCHEDULED",
  "recipient": {
    "user_id": "user-456",
    "email": "carlos.pereira@email.com",
    "name": "Carlos Pereira"
  },
  "payload": {
    "deletion_scheduled_at": "2025-09-01T18:00:00Z",
    "reactivate_account_deep_link": "poupeai://app/account/reactivate"
  }
}
```

</details>

### Fluxo da Mensagem

O caminho que uma mensagem percorre depende do resultado de seu processamento.

1.  **Publicação:** Um produtor envia uma mensagem para a `notification_exchange`.

2.  **Primeira Tentativa:** A exchange roteia a mensagem para a `notification_events`, e o consumidor a pega para processar.

      * ✅ **Caminho Feliz:** A lógica de negócio é executada com sucesso. A mensagem é confirmada (`ACK`) e removida permanentemente do sistema. A chave de idempotência (`message_id`) é gravada no Redis.

      * ❌ **Caminho de Erro Irrecuperável:** A mensagem falha na validação inicial (ex: JSON inválido, schema incorreto). O consumidor publica a mensagem diretamente na `notification_exchange.dlq` e dá `ACK` na mensagem original. O ciclo termina.

      * 🔄 **Caminho de Erro Temporário:** A lógica de negócio falha (ex: serviço externo indisponível). O consumidor publica a mensagem na `notification_exchange.retry` e dá `ACK` na mensagem original.

3.  **Ciclo de Retentativa:**

      * A mensagem entra na `notification_events.retry` e aguarda o TTL expirar.
      * Ao expirar, ela é roteada de volta para a `notification_exchange` e entra novamente na `notification_events` para uma nova tentativa.
      * O consumidor pega a mensagem e verifica o número de tentativas anteriores no header `x-death`.
      * Se o limite de tentativas não foi atingido, o passo 2 se repete.
      * Se o limite de tentativas **foi atingido**, o consumidor considera a falha como permanente, publica a mensagem na `notification_exchange.dlq` e dá `ACK` na mensagem original, encerrando o ciclo.

## Documentação

- Swagger: http://localhost:8001/api/v1/docs