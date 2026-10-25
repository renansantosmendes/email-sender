# email-sender

Envia emails com a API do [Resend](https://resend.com). Pode ser usado pela linha de comando ou como uma API HTTP, que só aceita usuários autenticados pelo [auth_service](../auth_service).

## Configuração

1. Instale as dependências com `uv` (o `uv sync` cria o ambiente a partir do `uv.lock`).
2. Copie `.env.example` para `.env` e preencha:
   - `RESEND_API_KEY`: chave criada no painel do Resend.
   - `RESEND_FROM`: remetente. Precisa ser de um domínio verificado no Resend; sem isso, use `onboarding@resend.dev`, que só envia para o email da própria conta.
3. Para a API, configure também as variáveis que o auth_service usa nos tokens. Elas têm o valor padrão do auth_service publicado, então só precisam ser definidas se o auth_service for outro:
   - `AUTH_SERVICE_URL`: endereço base do auth_service (padrão `https://authservice-delta.vercel.app`).
   - `AUTH_JWT_ISSUER`: emissor dos tokens (padrão `auth-service`).
   - `AUTH_JWT_AUDIENCE`: audiência dos tokens (padrão `synapse-apps`).

## Linha de comando

```bash
uv run python send_email.py destinatario@exemplo.com "Assunto" "Texto da mensagem"
```

O script imprime o id do email quando o Resend aceita o envio e termina com status 1 em caso de erro.

Também é possível usar a função direto no código:

```python
from send_email import send_email

email_id = send_email("destinatario@exemplo.com", "Assunto", "Texto da mensagem")
```

## API HTTP

Suba a API a partir da pasta do projeto:

```bash
uv run uvicorn api:app --reload
```

A documentação interativa fica em `http://127.0.0.1:8000/docs`.

| Rota | Autenticação | Descrição |
| --- | --- | --- |
| `GET /health` | não | Confirma que a API está no ar. |
| `GET /me` | token | Mostra o usuário identificado pelo token. |
| `POST /emails` | token | Envia um email. Corpo: `{"to", "subject", "text"}`. Responde `202` com o `id` do Resend. |

Toda rota protegida recebe o token de acesso que o auth_service devolve no login, no cabeçalho `Authorization: Bearer <token>`. A API verifica a assinatura do token localmente, com as chaves públicas publicadas em `/.well-known/jwks.json` do auth_service, e confere o emissor, a audiência, a validade e o tipo do token. Não chama o auth_service a cada envio.

Respostas de erro:

- `401`: token ausente, inválido ou expirado.
- `422`: dados do email inválidos.
- `502`: o Resend recusou o envio.
- `503`: o serviço de envio não está configurado, ou o auth_service não pôde ser alcançado para verificar o token.

Exemplo, com o token obtido no login do auth_service:

```bash
curl -X POST http://127.0.0.1:8000/emails \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to": "destinatario@exemplo.com", "subject": "Oi", "text": "Mensagem"}'
```

### Limitação atual

A API aceita qualquer token válido emitido pelo auth_service. Ela ainda não verifica se o usuário tem acesso à aplicação `email-sender`, porque o token não informa a aplicação para a qual foi emitido. Para restringir o envio, o auth_service precisa incluir essa informação no token e a API precisa conferi-la.

## Testes

```bash
uv run pytest
```

Os testes não falam com o Resend nem com o auth_service: a chave pública e o envio são substituídos por dublês.
