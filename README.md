# Notification Service

Serviço de notificações usando FastAPI.

## Estrutura do Projeto

```
poupeai-notification-service
├── requirements/
│   └── base.txt 
├── src/
│   ├── notification_service/
│   │   ├── __init__.py
│   │   ├── templates/         # Templates de e-mail (HTML)
│   │   │   ├── invoice_due_soon.html
│   │   │   └── ...
│   │   ├── consumer.py        # Lógica do consumidor RabbitMQ
│   │   ├── exceptions.py      # Exceções personalizadas
│   │   ├── router.py          # Endpoints HTTP (sem uso no momento)
│   │   ├── schemas.py         # Schemas de validação (Pydantic)
│   │   └── service.py         # Lógica de negócio e manipulação de eventos
│   │
│   ├── __init__.py
│   ├── config.py              # Configurações globais (via Pydantic)
│   ├── redis_client.py        # Configuração da conexão com Redis
│   ├── logging_config.py      # Configuração dos logs
│   └── main.py                # Ponto de entrada da aplicação FastAPI
│
├── .env.example
├── docker-compose.yml
├── .gitignore
└──  README.md
```

## Arquitetura e Padrões de Projeto

- **Processamento Assíncrono com Filas:** O RabbitMQ é usado para receber e processar eventos de notificação de forma assíncrona, garantindo que o sistema de origem não precise esperar pela conclusão do envio.
- **Idempotência:** Cada evento de notificação contém um `message_id` único. O serviço utiliza o Redis para rastrear os IDs das mensagens já processadas com sucesso, prevenindo envios duplicados em caso de reentregas pela fila.
- **Estratégia de Retry e Dead-Letter Queue (DLQ):** A arquitetura de filas implementa um padrão de retentativas com delay para falhas transientes (ex: falha de conexão com o servidor de e-mail) e move mensagens com falhas permanentes ou que excederam o limite de tentativas para uma DLQ.

## Instalação e Execução

Siga os passos abaixo para configurar e executar o projeto localmente.

### 1. Configurar Variáveis de Ambiente

As configurações da aplicação, como conexões com bancos de dados e serviços externos (RabbitMQ, Redis, etc.), são carregadas a partir de variáveis de ambiente.

Copie o arquivo de template `.env.example` para criar seu próprio arquivo de configuração local `.env`.

```bash
cp .env.example .env
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

> **Nota:** Este `docker-compose.yml` foi projetado para o desenvolvimento isolado deste serviço. Para executar a stack completa da aplicação, com todos os microsserviços integrados, utilize o arquivo `docker-compose.yml` principal localizado no repositório `.gitbub` da organização.

### 1. Pré-requisitos

- Docker e Docker Compose instalados.
- Crie um arquivo `.env` a partir do template `.env.example` e preencha as variáveis, se necessário.

```bash
cp .env.example .env
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

- **GET** `/api/v1/health` - Verifica o status da aplicação e a conectividade com o Redis.

## Logging

O serviço utiliza a biblioteca `structlog` para gerar logs estruturados no formato JSON. Essa abordagem padroniza a saída de logs, facilitando a coleta, busca e análise em ambientes centralizados. Todos os logs incluem campos importantes como `correlation_id`, `event_type` e `timestamp`, permitindo uma rastreabilidade detalhada das operações.

Os logs gerados são enviados para a saída padrão (`stdout`) e são coletados pela nossa stack de logging central (**Promtail/Loki/Grafana**), onde podem ser consultados e correlacionados com eventos de outros serviços.

## Estratégia de Filas (RabbitMQ)

O serviço utiliza o RabbitMQ para processamento assíncrono de notificações, implementando uma estratégia resiliente com **retentativas automáticas** para falhas temporárias e uma **Dead-Letter Queue (DLQ)** para erros irrecuperáveis.

### Topologia

A arquitetura é composta por um conjunto de filas e exchanges que trabalham juntas para garantir que nenhuma mensagem seja perdida. Os nomes exatos das entidades (ex: `notification_events`, `notification_exchange`) são carregados a partir de variáveis de ambiente para flexibilidade.

1.  **Exchange Principal (`notification_exchange`)**

    - **Tipo:** `Direct`
    - **Responsabilidade:** Ponto de entrada para todas as novas mensagens de notificação.

2.  **Fila Principal (`notification_events`)**

    - **Tipo:** `Durable`
    - **Responsabilidade:** Armazena novas mensagens aguardando a **primeira tentativa** de processamento.

3.  **Exchange de Retry (`notification_exchange.retry`)**

    - **Tipo:** `Direct`
    - **Responsabilidade:** Receber mensagens que falharam no processamento devido a um erro temporário.

4.  **Fila de Retry (`notification_events.retry`)**

    - **Tipo:** `Durable`
    - **Responsabilidade:** Reter temporariamente as mensagens que falharam. Possui um **TTL (Time-To-Live)** que, ao expirar, envia a mensagem de volta à Exchange Principal para uma nova tentativa.

5.  **Dead-Letter Exchange Final (DLX) (`notification_exchange.dlq`)**

    - **Tipo:** `Direct`
    - **Responsabilidade:** Ponto de entrada para mensagens que **não podem ou não devem mais ser processadas**.

6.  **Fila de Dead-Letter Final (DLQ) (`notification_events.dlq`)**

    - **Tipo:** `Durable`
    - **Responsabilidade:** Armazenar permanentemente mensagens com **erros irrecuperáveis** (ex: falha de validação) ou que **excederam o limite de retentativas**.

### Contrato da Mensagem e Payloads de Exemplo

Para ser processada corretamente, toda mensagem enviada ao `notification_exchange` deve seguir um contrato específico, dividido entre as **Propriedades** da mensagem e o **Corpo** (Payload).

#### Propriedades da Mensagem

As seguintes propriedades devem ser configuradas ao publicar a mensagem:

| Propriedade      | Valor Exemplo        | Obrigatório | Descrição                                                   |
| :--------------- | :------------------- | :---------- | :---------------------------------------------------------- |
| `routing_key`    | `notification.event` | Sim         | Chave de roteamento para ligar a exchange à fila principal. |
| `correlation_id` | `"trace-abc-123"`    | Sim         | Identificador para rastreabilidade e logs ponta a ponta.    |
| `content_type`   | `application/json`   | Sim         | Indica que o corpo da mensagem é um JSON.                   |

**É fundamental que todo produtor de mensagens garanta a inclusão e o repasse do `correlation_id`. Este identificador é a chave para a rastreabilidade ponta a ponta da requisição através dos diferentes microsserviços e para a depuração de problemas utilizando a stack de logging centralizada.**

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
    "amount": 150.5,
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
    "amount": 150.5,
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

    - ✅ **Caminho Feliz:** A lógica de negócio é executada com sucesso. A mensagem é confirmada (`ACK`) e removida permanentemente do sistema. A chave de idempotência (`message_id`) é gravada no Redis.

    - ❌ **Caminho de Erro Irrecuperável:** A mensagem falha na validação inicial (ex: JSON inválido, schema incorreto). O consumidor publica a mensagem diretamente na `notification_exchange.dlq` e dá `ACK` na mensagem original. O ciclo termina.

    - 🔄 **Caminho de Erro Temporário:** A lógica de negócio falha (ex: serviço externo indisponível). O consumidor publica a mensagem na `notification_exchange.retry` e dá `ACK` na mensagem original.

3.  **Ciclo de Retentativa:**

    - A mensagem entra na `notification_events.retry` e aguarda o TTL expirar.
    - Ao expirar, ela é roteada de volta para a `notification_exchange` e entra novamente na `notification_events` para uma nova tentativa.
    - O consumidor pega a mensagem e verifica o número de tentativas anteriores no header `x-death`.
    - Se o limite de tentativas não foi atingido, o passo 2 se repete.
    - Se o limite de tentativas **foi atingido**, o consumidor considera a falha como permanente, publica a mensagem na `notification_exchange.dlq` e dá `ACK` na mensagem original, encerrando o ciclo.

## Documentação

- Swagger: http://localhost:8001/api/v1/docs

## Testes

O projeto utiliza `pytest` para testes automatizados. A estratégia de teste inclui testes unitários (já implementados) e testes de integração (planejados, mas ainda não implementados).

### Pré-requisitos para Testes

1.  **Ambiente Virtual Ativo:** Certifique-se de que seu ambiente virtual (`venv`) esteja ativado.
2.  **Dependências de Teste Instaladas:** Instale as bibliotecas necessárias para rodar os testes unitários e gerar cobertura:

        pip install -r requirements/base.txt

3.  **Para Testes de Integração (Quando Implementados):** O ambiente Docker Compose deverá estar rodando em segundo plano (`docker compose up -d`).

### Executando os Testes Unitários

Todos os comandos de teste devem ser executados a partir da **raiz do projeto**.

Este comando executa rapidamente todos os testes unitários implementados, que validam a lógica interna do serviço sem depender de serviços externos (RabbitMQ, Redis).

    pytest tests/unit/

Você também pode rodar com mais detalhes (mostrando o nome de cada teste) usando a flag `-v`:

    pytest -v tests/unit/

### Testes de Integração (Planejados)

Os testes de integração foram planejados (ver casos IT-001 a IT-003 no Plano de Teste) para validar a interação do serviço com os contêineres Docker (RabbitMQ, Redis). **Estes testes ainda não foram implementados.**

Quando forem implementados, o comando para executá-los (assumindo que usem o marcador `integration`) será:

    # Comando FUTURO - Requer Docker rodando e testes implementados
    docker compose exec app pytest -m integration -v tests/integration/

### Gerando o Relatório de Cobertura (Coverage)

Para verificar qual porcentagem do código da aplicação (`src/`) é coberta pelos testes unitários e gerar o relatório HTML:

**Método Recomendado (Com Link Clicável no Terminal):**

    # 1. Executa os testes unitários medindo a cobertura apenas do código 'src/'
    coverage run --source=src -m pytest tests/unit/

    # 2. Gera o relatório HTML e mostra o link no terminal
    coverage html

Após executar `coverage html`, procure a linha `Wrote HTML report to htmlcov/index.html` no terminal. Abra este arquivo no seu navegador (pode ser necessário usar Ctrl+Click no link gerado pelo comando `echo "file://$(pwd)/htmlcov/index.html"` se o link direto não funcionar) para ver o relatório detalhado. A cobertura atual com testes unitários é de aproximadamente 67% do código em `src/`.

**Alternativa (Com Resumo no Terminal e Relatório HTML):**

    # Executa os testes unitários e gera o relatório HTML de uma vez
    pytest --cov=src --cov-report=html tests/unit/

Este comando também cria a pasta `htmlcov/` com o relatório, e o resumo de cobertura já aparece no terminal.

### Limpando Arquivos de Cobertura

Para remover os arquivos gerados pelo coverage:

    coverage erase
    rm -rf htmlcov/

**(Nota:** A pasta `htmlcov/` e o arquivo `.coverage` estão incluídos no `.gitignore` para não serem enviados ao repositório).\*
