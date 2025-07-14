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

## Documentação

- Swagger: http://localhost:8001/api/v1/docs
