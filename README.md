# email-sender

Script básico que envia um email para um usuário com a API do [Resend](https://resend.com).

## Configuração

1. Instale as dependências com `uv` (o `uv sync` cria o ambiente a partir do `uv.lock`).
2. Copie `.env.example` para `.env` e preencha:
   - `RESEND_API_KEY`: chave criada no painel do Resend.
   - `RESEND_FROM`: remetente. Precisa ser de um domínio verificado no Resend; sem isso, use `onboarding@resend.dev`, que só envia para o email da própria conta.

## Uso

```bash
uv run python send_email.py destinatario@exemplo.com "Assunto" "Texto da mensagem"
```

O script imprime o id do email quando o Resend aceita o envio e termina com status 1 em caso de erro.

Também é possível usar a função direto no código:

```python
from send_email import send_email

email_id = send_email("destinatario@exemplo.com", "Assunto", "Texto da mensagem")
```
