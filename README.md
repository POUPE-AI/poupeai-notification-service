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

O serviço utiliza o RabbitMQ para processamento assíncrono de notificações, implementando uma estratégia robusta com Dead-Letter Queue (DLQ) para garantir a durabilidade e a observabilidade das mensagens.

### Topologia

1.  **Exchange Principal (`notification_exchange`)**:
    * **Tipo:** `Direct`
    * **Responsabilidade:** Receber todas as mensagens de notificação publicadas e roteá-las para a fila principal.

2.  **Fila Principal (`notification_events`)**:
    * **Tipo:** `Durable`
    * **Binding:** Ligada à `notification_exchange` com a routing key `notification.event`.
    * **Responsabilidade:** Armazenar as mensagens que aguardam processamento pelo consumidor.
    * **Configuração DLQ:** Mensagens que falham no processamento (são rejeitadas/NACKed) são automaticamente enviadas para a Dead-Letter Exchange.

3.  **Dead-Letter Exchange (DLX) (`notification_exchange.dlq`)**:
    * **Tipo:** `Direct`
    * **Responsabilidade:** Receber mensagens rejeitadas da fila principal e roteá-las para a fila de dead-letter.

4.  **Fila de Dead-Letter (DLQ) (`notification_events.dlq`)**:
    * **Tipo:** `Durable`
    * **Binding:** Ligada à `notification_exchange.dlq` com a routing key `notification.event`.
    * **Responsabilidade:** Armazenar permanentemente as mensagens que não puderam ser processadas, permitindo análise de falhas e reprocessamento manual, se necessário.

### Fluxo da Mensagem

1.  Um produtor envia uma mensagem para a `notification_exchange`.
2.  A exchange roteia a mensagem para a fila `notification_events`.
3.  O consumidor (`RabbitMQConsumer`) pega a mensagem da fila.
    * **Caminho Feliz:** A mensagem é processada com sucesso e confirmada (`ACK`), sendo removida da fila.
    * **Caminho de Erro:** Ocorre uma exceção durante o processamento. A mensagem é rejeitada (`NACK`) e, devido à configuração da fila, o RabbitMQ a move para a `notification_exchange.dlq`.
4.  A DLX roteia a mensagem para a `notification_events.dlq`, onde ela fica armazenada para análise.

## Documentação

- Swagger: http://localhost:8001/api/v1/docs
