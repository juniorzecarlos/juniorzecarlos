# Instruções: migrar WhatsApp de W-API → Evolution API (self-hosted, grátis)

> Cole este arquivo no outro projeto (ex.: `docs/whatsapp.md` ou no `CLAUDE.md`) e peça:
> "Siga docs/whatsapp.md e substitua a integração W-API pela Evolution API".

## Por que Evolution API
- Open source (Apache 2.0), roda em Docker no nosso servidor → **custo zero** além da VPS.
- Mesmo modelo da W-API (conecta via QR Code num número comum), então a migração é quase 1:1.
- Volume baixo = perfeito. Uma VPS de 1 vCPU / 1–2 GB aguenta tranquilo.

⚠️ **Aviso honesto:** assim como a W-API, é API **não oficial** (usa Baileys/WhatsApp Web).
Existe risco de banimento se mandar spam/disparo em massa para quem não te salvou.
Se o uso for principalmente **responder clientes**, considere a **API oficial da Meta (Cloud API)**:
mensagens de resposta dentro da janela de 24h são grátis; só templates iniciados pela empresa são pagos.

---

## 1. Subir a Evolution API (Docker)

`docker-compose.yml`:

```yaml
services:
  evolution-api:
    image: evoapicloud/evolution-api:v2.3.0   # fixe a versão, não use latest
    restart: always
    ports:
      - "8080:8080"
    env_file: .env.evolution
    volumes:
      - evolution_instances:/evolution/instances
    depends_on: [postgres, redis]

  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_USER: evolution
      POSTGRES_PASSWORD: troque_esta_senha
      POSTGRES_DB: evolution
    volumes:
      - pg_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    restart: always
    volumes:
      - redis_data:/data

volumes:
  evolution_instances:
  pg_data:
  redis_data:
```

`.env.evolution` (NÃO commitar):

```env
SERVER_URL=https://whats.suaempresa.com.br
AUTHENTICATION_API_KEY=gere-uma-chave-forte-aqui
DATABASE_PROVIDER=postgresql
DATABASE_CONNECTION_URI=postgresql://evolution:troque_esta_senha@postgres:5432/evolution?schema=public
CACHE_REDIS_ENABLED=true
CACHE_REDIS_URI=redis://redis:6379/6
CACHE_LOCAL_ENABLED=false
DEL_INSTANCE=false
```

Coloque atrás de um proxy com HTTPS (Nginx/Caddy/Traefik). Nunca exponha a porta 8080 crua na internet.

---

## 2. Criar a instância e conectar o número

Todas as chamadas usam o header `apikey: <AUTHENTICATION_API_KEY>`.

```bash
# criar instância
curl -X POST "$EVO_URL/instance/create" \
  -H "apikey: $EVO_KEY" -H "Content-Type: application/json" \
  -d '{"instanceName":"empresa","integration":"WHATSAPP-BAILEYS","qrcode":true}'

# pegar QR Code (retorna base64) → escanear no celular
curl "$EVO_URL/instance/connect/empresa" -H "apikey: $EVO_KEY"

# checar status (esperado: "open")
curl "$EVO_URL/instance/connectionState/empresa" -H "apikey: $EVO_KEY"
```

> Dica: também tem um painel web em `$EVO_URL/manager` pra fazer isso clicando.

---

## 3. Endpoints principais (equivalentes da W-API)

| Ação | Método / rota | Body |
|---|---|---|
| Enviar texto | `POST /message/sendText/{instance}` | `{"number":"5511999999999","text":"Olá!"}` |
| Enviar mídia | `POST /message/sendMedia/{instance}` | `{"number":"...","mediatype":"image\|document\|video","mimetype":"application/pdf","media":"<url ou base64>","fileName":"boleto.pdf","caption":"Segue"}` |
| Enviar áudio | `POST /message/sendWhatsAppAudio/{instance}` | `{"number":"...","audio":"<url ou base64>"}` |
| Checar se número tem WhatsApp | `POST /chat/whatsappNumbers/{instance}` | `{"numbers":["5511999999999"]}` |
| Configurar webhook | `POST /webhook/set/{instance}` | ver abaixo |

Número sempre no formato **DDI+DDD+número, só dígitos** (ex.: `5511999999999`).

---

## 4. Receber mensagens (webhook)

```bash
curl -X POST "$EVO_URL/webhook/set/empresa" \
  -H "apikey: $EVO_KEY" -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "enabled": true,
      "url": "https://api.suaempresa.com.br/webhooks/whatsapp?token=SEGREDO",
      "webhookByEvents": false,
      "webhookBase64": false,
      "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"]
    }
  }'
```

Payload de mensagem recebida (`event: "messages.upsert"`), campos que importam:

```json
{
  "event": "messages.upsert",
  "instance": "empresa",
  "data": {
    "key": { "remoteJid": "5511999999999@s.whatsapp.net", "fromMe": false, "id": "ABC123" },
    "pushName": "Fulano",
    "message": {
      "conversation": "texto simples",
      "extendedTextMessage": { "text": "texto com link/resposta" }
    },
    "messageType": "conversation"
  }
}
```

Regras no handler:
1. Validar o `token` da query (a Evolution não assina o webhook).
2. Ignorar `fromMe: true` (senão o bot responde a si mesmo, loop infinito 🔁).
3. Ignorar grupos: `remoteJid` terminando em `@g.us`.
4. Texto = `message.conversation ?? message.extendedTextMessage?.text`.
5. Responder **200 rápido** e processar em fila/assíncrono.
6. Deduplicar por `key.id` (pode chegar repetido).
7. `CONNECTION_UPDATE` com `state: "close"` → alertar alguém (número desconectou).

---

## 5. Como implementar no código (padrão obrigatório)

Não espalhar chamadas HTTP da Evolution pelo projeto. Criar **uma camada de provider**:

```ts
// whatsapp/provider.ts
export interface WhatsAppProvider {
  sendText(to: string, text: string): Promise<{ id: string }>;
  sendMedia(to: string, media: { url: string; mimetype: string; fileName?: string; caption?: string }): Promise<{ id: string }>;
  parseIncoming(payload: unknown): IncomingMessage | null; // null = ignorar
}

export type IncomingMessage = { id: string; from: string; name?: string; text: string };
```

```ts
// whatsapp/evolution.provider.ts
const BASE = process.env.EVO_URL!;
const KEY = process.env.EVO_KEY!;
const INSTANCE = process.env.EVO_INSTANCE!;

async function call(path: string, body: unknown) {
  const res = await fetch(`${BASE}${path}/${INSTANCE}`, {
    method: "POST",
    headers: { apikey: KEY, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Evolution ${path} ${res.status}: ${await res.text()}`);
  return res.json();
}

export const evolutionProvider: WhatsAppProvider = {
  async sendText(to, text) {
    const r = await call("/message/sendText", { number: to, text });
    return { id: r.key?.id };
  },
  async sendMedia(to, m) {
    const mediatype = m.mimetype.startsWith("image/") ? "image"
      : m.mimetype.startsWith("video/") ? "video" : "document";
    const r = await call("/message/sendMedia", {
      number: to, mediatype, mimetype: m.mimetype, media: m.url, fileName: m.fileName, caption: m.caption,
    });
    return { id: r.key?.id };
  },
  parseIncoming(p: any) {
    if (p?.event !== "messages.upsert") return null;
    const d = p.data;
    if (!d || d.key?.fromMe || d.key?.remoteJid?.endsWith("@g.us")) return null;
    const text = d.message?.conversation ?? d.message?.extendedTextMessage?.text;
    if (!text) return null;
    return { id: d.key.id, from: d.key.remoteJid.split("@")[0], name: d.pushName, text };
  },
};
```

Se o projeto não for TypeScript, manter **a mesma interface** na linguagem do projeto.
Assim, se um dia trocar de novo (ex.: para Cloud API oficial), muda só um arquivo.

Variáveis de ambiente do projeto:

```env
EVO_URL=https://whats.suaempresa.com.br
EVO_KEY=...
EVO_INSTANCE=empresa
WHATSAPP_WEBHOOK_TOKEN=...
```

---

## 6. Checklist da migração

- [ ] Subir Evolution + Postgres + Redis com HTTPS
- [ ] Criar instância e conectar o número via QR
- [ ] Criar `WhatsAppProvider` + `evolutionProvider`
- [ ] Trocar todas as chamadas da W-API pelo provider (buscar por `w-api`, `wapi` no código)
- [ ] Criar rota de webhook com validação de token, filtro `fromMe`/grupos e dedupe
- [ ] Configurar webhook na instância
- [ ] Testar: enviar texto, enviar PDF, receber mensagem, derrubar conexão e ver alerta
- [ ] Remover credenciais/env da W-API e cancelar o plano 💸

## 7. Boas práticas anti-ban
- Não disparar em massa para quem nunca falou com o número.
- Delay entre envios (ex.: 2–5 s) se mandar vários seguidos.
- Usar chip dedicado, número "aquecido" (com uso normal antes).
- Manter o celular com o WhatsApp ativo de vez em quando.
