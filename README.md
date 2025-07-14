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

### Health Check
- **GET** `/api/v1/health` - Verificar status

## Documentação

- Swagger: http://localhost:8001/api/v1/docs
