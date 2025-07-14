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

## Executando com Docker

Para executar a aplicação em um ambiente containerizado com Docker, siga os passos abaixo.

### 1. Pré-requisitos

- Docker instalado e em execução.
- O arquivo `.env` deve estar criado e configurado na raiz do projeto (veja a seção "Configurar Variáveis de Ambiente").

### 2. Construir a Imagem

Na raiz do projeto, execute o comando a seguir para construir a imagem Docker:

```bash
docker build -t poupeai-notification-service .
```

### 3. Executar o Contêiner

Após a construção da imagem, execute o contêiner com o comando:

```bash
docker run -d --name notification-service -p 8001:8001 --env-file .env poupeai-notification-service
```

O serviço estará disponível no endereço `http://localhost:8001`.

### Health Check
- **GET** `/api/v1/health` - Verificar status

## Documentação

- Swagger: http://localhost:8001/api/v1/docs
