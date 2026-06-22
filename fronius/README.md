## Pipeline Fronius

1. Lista e descarrega todos os ficheiros `.xlsx` da Pasta Fronius do repositório  [Datafiles](https://github.com/pedroccpimenta/datafiles) .
2. Classifica cada ficheiro em um de três tipos (`normal`, `specific`, `rectifiers`) com base nas colunas presentes, converte timestamps para UTC, e calcula um hash por linha para deduplicação.
3. Aplica opcionalmente um intervalo de datas às linhas do tipo `normal`.
4. Insere os dados em todos os destinos definidos em `TO_dblist_json`.
5. Se `CREATE_SUMMARY=True`, recalcula tabelas/coleções de resumo diário e mensal a partir dos dados inseridos.
6. Envia email com o log de execução se `EMAIL_SEND=True`.


## Variáveis de Ambiente

Todas as variáveis são lidas de um ficheiro `.env` na raiz do projeto.

### Identidade

| Variável | Descrição | Exemplo |
|---|---|---|
| `USER` | Prefixo usado para resolver os secrets do utilizador | `PI` |

**Atenção**  O prefixo `USER` é concatenado com os nomes das variáveis seguintes. Por exemplo, se `USER=TO`, o cliente procura `TO_crate_json`.

---

```
TO_dblist_json=["crate","tidb","mongodb"]
```

---

#### `{USER}_crate_json`

| Campo | Descrição |
|---|---|
| `dest_host` | URL completo incluindo protocolo e porto. Formato: `https://<host>:<porto>` |
| `username` | Utilizador da instância CrateDB |
| `password` | Password |
| `database` | Schema (normalmente `doc`) |
| `port` | Porta |
| `timeout` | Timeout de ligação em segundos |
| `dbms` | Deve ser `"crate"` |

```
PI_crate_json='{
    "dest_host": "https://<host>:4200",
    "username": "<user>",
    "password": "<password>",
    "database": "doc",
    "port": 4200,
    "timeout": 20,
    "dbms": "crate"
}'
```

#### `{USER}_tidb_json`

| Campo | Descrição |
|---|---|
| `dest_host` | Hostname do gateway (sem protocolo) |
| `port` | Porto (normalmente `4000`) |
| `username` | Utilizador |
| `password` | Password |
| `database` | Nome da base de dados |
| `dbms` | Deve ser `"tidb"` |

```
PI_tidb_json='{
    "dest_host": "<gateway>.tidbcloud.com",
    "port": 4000,
    "username": "<user>",
    "password": "<password>",
    "database": "Fronius",
    "dbms": "tidb"
}'
```

---

#### `{USER}_mongodb_json`

| Campo | Descrição |
|---|---|
| `dest_host` | Hostname do cluster Atlas (sem `mongodb+srv://`) |
| `username` | Utilizador |
| `password` | Password |
| `database` | Nome da base de dados |
| `port` | Ignorado na ligação Atlas (usa SRV), mas deve estar presente |
| `timeout` | Timeout de seleção de servidor em ms |
| `dbms` | Deve ser `"mongodb"` |

```
PI_mongodb_json='{
    "dest_host": "<cluster>.mongodb.net",
    "username": "<user>",
    "password": "<password>",
    "database": "EletricEnergyConsumption",
    "port": 27017,
    "timeout": 20,
    "dbms": "mongodb"
}'
```

---

### GitHub

#### `{USER}_github_json`

Token de acesso ao repositório GitHub.

```
TO_github_json='{"key": "<github_token>"}'
```

O repositório, branch e pasta são configurados em `config.py` na variável `GITHUB`.

---

### Email

| Variável | Descrição | Exemplo |
|---|---|---|
| `EMAIL_SEND` | Ativa o envio de email no final da pipeline | `True` |
| `EMAIL_ADDRESSES` | Endereço(s) de destino, separados por vírgula | `user@example.com` |
| `RESEND_API_KEY` | API key do serviço Resend | `re_...` |
| `BREVO_USER` | Utilizador SMTP do Brevo (alternativa ao Resend) | `abc@smtp-brevo.com` |
| `BREVO_PASSWORD` | Password SMTP do Brevo | `xkeysib-...` |
| `BREVO_FROM` | Endereço de remetente no Brevo | `noreply@example.com` |

---

### Comportamento da pipeline

| Variável | Descrição | Valores aceites | Exemplo |
|---|---|---|---|
| `INSERT_MODE` | Modo de insert nas tabelas | `ignore`  ( Aberto a expansão) | `ignore` |
| `CREATE_SUMMARY` | Recalcula tabelas de sumário diário e mensal após insert | `True` / `False` | `True` |
| `TIMESTAMP_FILTER` | Filtra linhas do tipo `normal` por intervalo de datas | `YYYY-M-D,YYYY-M-D`  ou `None`  | `2024-1-1,2024-12-31` |

---