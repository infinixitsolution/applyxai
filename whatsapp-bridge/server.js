/**
 * Local WhatsApp Web bridge for ApplyXAI admin outreach.
 * Scan the QR code once; POST /send delivers approved proposal text.
 */
const express = require("express");
const fs = require("fs");
const path = require("path");
const os = require("os");
const { execFile } = require("child_process");
const QRCode = require("qrcode");
const { Client, LocalAuth, MessageMedia } = require("whatsapp-web.js");

const PORT = Number(process.env.WHATSAPP_BRIDGE_PORT || 39219);
const API_URL = (process.env.APPLYXAI_API_URL || "http://127.0.0.1:8010").replace(/\/$/, "");
const BRIDGE_SECRET = process.env.WHATSAPP_BRIDGE_SECRET || "";
const sessionDir =
  process.env.WHATSAPP_SESSION_DIR ||
  path.join(process.env.LOCALAPPDATA || os.homedir(), "ApplyXAI", "whatsapp-session");

let status = "disconnected";
let lastQr = null;
let lastError = "";
let client = null;
let ready = false;
let resetting = false;

const PUPPETEER_ARGS = [
  "--no-sandbox",
  "--disable-setuid-sandbox",
  "--disable-dev-shm-usage",
  "--disable-gpu",
  "--no-first-run",
  "--disable-extensions",
];

function isStaleBrowserError(err) {
  const msg = String((err && err.message) || err || "");
  return /detached Frame|Execution context was destroyed|Target closed|Session closed|Protocol error|browser has disconnected/i.test(
    msg,
  );
}

function killStaleChromeForSession() {
  if (process.platform !== "win32") return Promise.resolve();
  const psScript = [
    "$procs = Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" -ErrorAction SilentlyContinue",
    "| Where-Object { $_.CommandLine -match 'ApplyXAI[\\\\/]whatsapp-session' }",
    "; $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }",
  ].join(" ");
  return new Promise((resolve) => {
    execFile(
      "powershell.exe",
      ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", psScript],
      { timeout: 20000 },
      (err) => {
        if (err) console.warn("killStaleChromeForSession:", err.message || err);
        resolve();
      },
    );
  });
}

async function hardResetClient(reason) {
  if (resetting) return;
  resetting = true;
  ready = false;
  status = "disconnected";
  lastError = reason || "Browser session lost; reconnecting…";
  const old = client;
  client = null;
  try {
    if (old && typeof old.destroy === "function") {
      await old.destroy();
    }
  } catch (err) {
    console.warn("destroy during reset:", err.message || err);
  }
  await killStaleChromeForSession();
  resetting = false;
  setTimeout(bootClient, 2000);
}

function waitForReady(timeoutMs = 120000) {
  if (ready && client) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs;
    const tick = () => {
      if (ready && client) return resolve();
      if (Date.now() >= deadline) {
        return reject(
          new Error(
            "Timed out waiting for WhatsApp to reconnect. Open Outreach → WhatsApp and scan QR if shown.",
          ),
        );
      }
      setTimeout(tick, 1000);
    };
    tick();
  });
}

async function assertClientAlive(c) {
  if (!c || typeof c.getState !== "function") return;
  const state = await c.getState();
  if (state !== "CONNECTED") {
    const err = new Error(`WhatsApp is ${state}, not connected.`);
    if (state === "CONFLICT" || state === "UNPAIRED") err.code = "NOT_READY";
    throw err;
  }
}

async function runClientOp(label, fn, allowRetry = true) {
  if (!client || !ready) {
    const err = new Error("WhatsApp not connected. Scan QR in admin Outreach tab.");
    err.code = "NOT_READY";
    throw err;
  }
  try {
    await assertClientAlive(client);
    return await fn(client);
  } catch (err) {
    if (
      isStaleBrowserError(err) ||
      err.code === "STALE" ||
      (err && err.message && err.message.includes("not connected"))
    ) {
      console.error(`${label} session problem:`, err.message || err);
      if (!allowRetry) {
        const fail = new Error(
          "WhatsApp browser session is still unstable after reconnect. Restart the bridge: .\\scripts\\start_whatsapp_bridge.ps1",
        );
        fail.code = "STALE_SESSION";
        throw fail;
      }
      await hardResetClient("WhatsApp Web tab crashed or logged out. Reconnecting…");
      try {
        await waitForReady(120000);
      } catch (waitErr) {
        const fail = new Error(waitErr.message || String(waitErr));
        fail.code = "STALE_SESSION";
        throw fail;
      }
      return runClientOp(label, fn, false);
    }
    throw err;
  }
}

function messageId(result) {
  if (!result) return "sent";
  const id = result.id;
  if (id && typeof id === "object") {
    if (id._serialized) return String(id._serialized);
    if (id.id) return String(id.id);
  }
  if (id) return String(id);
  return "sent";
}

function normalizePhone(input) {
  const digits = String(input || "").replace(/\D/g, "");
  if (digits.length === 10) return `91${digits}@c.us`;
  if (digits.startsWith("91") && digits.length === 12) return `${digits}@c.us`;
  if (digits.length > 8) return `${digits}@c.us`;
  throw new Error("Invalid phone number");
}

function bootClient() {
  if (client || resetting) return;
  const headless = process.env.WHATSAPP_HEADLESS !== "0";
  client = new Client({
    authStrategy: new LocalAuth({ dataPath: sessionDir }),
    takeoverOnConflict: true,
    takeoverTimeoutMs: 15000,
    puppeteer: { headless, args: PUPPETEER_ARGS },
  });

  client.on("qr", async (qr) => {
    status = "qr";
    ready = false;
    try {
      lastQr = await QRCode.toDataURL(qr);
    } catch (err) {
      lastQr = null;
      lastError = String(err.message || err);
    }
  });

  client.on("ready", () => {
    status = "connected";
    ready = true;
    lastQr = null;
    lastError = "";
    console.log("WhatsApp bridge connected");
  });

  client.on("change_state", (state) => {
    if (state === "CONNECTED") {
      status = "connected";
      ready = true;
      return;
    }
    ready = false;
    status = "disconnected";
    lastError = `WhatsApp state: ${state}`;
  });

  client.on("auth_failure", (msg) => {
    status = "disconnected";
    ready = false;
    lastError = String(msg || "auth_failure");
  });

  client.on("disconnected", (reason) => {
    status = "disconnected";
    ready = false;
    lastError = String(reason || "disconnected");
    const old = client;
    client = null;
    if (old && typeof old.destroy === "function") {
      old.destroy().catch(() => {});
    }
    setTimeout(bootClient, 5000);
  });

  const recentInboundIds = new Set();

  async function resolveInboundFrom(msg) {
    const chatId = String(msg.from || "");
    if (!chatId || chatId.endsWith("@g.us") || chatId.includes("broadcast")) return null;
    let from = chatId;
    if (!chatId.endsWith("@c.us")) {
      try {
        const contact = await msg.getContact();
        const num = contact.number || (contact.id && contact.id.user);
        const digits = normalizeContactDigits(num || "");
        if (digits) {
          from = `${digits}@c.us`;
        }
      } catch (err) {
        console.warn("Contact lookup failed for", chatId, err.message || err);
      }
    } else {
      const digits = String(chatId.split("@", 1)[0] || "").replace(/\D/g, "");
      if (digits.length > 12) {
        from = `${digits}@lid`;
      }
    }
    return { from, chat_id: chatId };
  }

  async function messageBodyForInbound(msg) {
    let body = String(msg.body || "").trim();
    if (!body && msg.hasMedia) {
      const kind = msg.type && msg.type !== "chat" ? msg.type : "media";
      body = `[${kind} message]`;
    }
    return body;
  }

  async function forwardInboundMessage(msg) {
    try {
      if (!msg || msg.fromMe) return;
      if (!BRIDGE_SECRET) {
        console.warn("Inbound WhatsApp ignored: set WHATSAPP_BRIDGE_SECRET (same value as the API .env).");
        return;
      }
      const resolved = await resolveInboundFrom(msg);
      if (!resolved) return;
      const { from, chat_id: inboundChatId } = resolved;
      const body = await messageBodyForInbound(msg);
      if (!body) return;
      const messageId = msg.id && (msg.id._serialized || msg.id.id || msg.id);
      const idKey = messageId ? String(messageId) : `${inboundChatId}:${body.slice(0, 40)}`;
      if (recentInboundIds.has(idKey)) return;
      recentInboundIds.add(idKey);
      if (recentInboundIds.size > 500) recentInboundIds.clear();

      let displayName = "";
      try {
        const contact = await msg.getContact();
        displayName = String(contact.pushname || contact.name || "").trim();
      } catch {
        /* optional */
      }

      const resp = await fetch(`${API_URL}/api/internal/outreach/whatsapp/inbound`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-WhatsApp-Bridge-Secret": BRIDGE_SECRET,
        },
        body: JSON.stringify({
          from,
          chat_id: inboundChatId || undefined,
          body,
          message_id: messageId ? String(messageId) : undefined,
          display_name: displayName || undefined,
        }),
      });
      if (!resp.ok) {
        const detail = (await resp.text()).slice(0, 300);
        console.warn("Inbound forward rejected:", resp.status, detail);
        recentInboundIds.delete(idKey);
        return;
      }
      console.log("Inbound forwarded to API:", from, body.slice(0, 60));
    } catch (err) {
      console.warn("Inbound forward failed:", err.message || err);
    }
  }

  client.on("message_create", (msg) => {
    void forwardInboundMessage(msg);
  });

  client.initialize().catch((err) => {
    status = "disconnected";
    ready = false;
    lastError = String(err.message || err);
    console.error("WhatsApp init failed:", lastError);
    const old = client;
    client = null;
    if (old && typeof old.destroy === "function") {
      old.destroy().catch(() => {});
    }
    if (/already running/i.test(lastError)) {
      lastError = "Stale Chrome session detected; cleaning up and reconnecting…";
      killStaleChromeForSession().then(() => setTimeout(bootClient, 3000));
      return;
    }
    setTimeout(bootClient, 8000);
  });
}

bootClient();

const BRIDGE_VERSION = "1.2.1";

const app = express();
app.use(express.json({ limit: "32kb" }));

app.get("/", (_req, res) => {
  res.json({
    service: "applyxai-whatsapp-bridge",
    version: BRIDGE_VERSION,
    endpoints: ["/status", "/qr", "/chats", "/chats/:chatId/messages", "/send", "/reset"],
  });
});

app.post("/reset", async (_req, res) => {
  await hardResetClient("Manual reset requested");
  res.json({ ok: true, message: "Reconnecting WhatsApp client…" });
});

app.get("/status", (_req, res) => {
  res.json({
    status,
    qr: lastQr,
    error: lastError || undefined,
    ready,
    version: BRIDGE_VERSION,
    inbound_enabled: Boolean(BRIDGE_SECRET),
  });
});

app.get("/qr", (_req, res) => {
  res.json({ status, qr: lastQr, error: lastError || undefined });
});

function chatIdSerialized(chat) {
  if (!chat || !chat.id) return "";
  if (typeof chat.id === "string") return chat.id;
  if (chat.id._serialized) return String(chat.id._serialized);
  return String(chat.id);
}

/** List chats inside the WA page only — avoids ChatFactory/getChats() detached-frame failures. */
async function listChatsMinimal(c, limit) {
  const page = c.pupPage;
  if (!page || page.isClosed()) {
    const err = new Error("Browser page closed");
    err.code = "STALE";
    throw err;
  }
  const payload = await page.evaluate((max) => {
    try {
      if (typeof window.require !== "function") {
        return { ok: false, error: "WhatsApp page not ready (require missing). Reload bridge." };
      }
      const Chat = window.require("WAWebCollections").Chat;
      const models = Chat.getModelsArray();
      const items = [];
      for (const chat of models) {
        if (!chat || !chat.id) continue;
        const id = chat.id._serialized || String(chat.id);
        if (chat.isGroup) continue;
        if (!id.endsWith("@c.us") && !id.endsWith("@lid")) continue;
        const phone = chat.id.user || id.split("@")[0];
        let preview = "";
        let fromMe = false;
        let msgTs = chat.t || chat.timestamp || null;
        let msgId = "";
        try {
          const msgs = chat.msgs;
          if (msgs && msgs.getModelsArray) {
            const arr = msgs.getModelsArray();
            const last = arr[arr.length - 1];
            if (last) {
              preview = String(last.body || last.caption || "").slice(0, 500);
              fromMe = Boolean(last.id && last.id.fromMe);
              msgTs = last.t || msgTs;
              msgId = (last.id && last.id._serialized) || "";
            }
          }
        } catch (_e) {
          /* ignore preview errors */
        }
        items.push({
          id,
          name: chat.formattedTitle || chat.name || chat.contact?.pushname || phone,
          phone,
          timestamp: msgTs,
          unread_count: chat.unreadCount || 0,
          last_message: preview
            ? { body: preview, from_me: fromMe, timestamp: msgTs, id: msgId || `${id}:preview` }
            : null,
        });
      }
      items.sort((a, b) => (Number(b.timestamp) || 0) - (Number(a.timestamp) || 0));
      return { ok: true, items: items.slice(0, max), total: items.length };
    } catch (e) {
      return { ok: false, error: String(e.message || e) };
    }
  }, limit);
  if (!payload.ok) {
    const err = new Error(payload.error || "list failed");
    if (/detached|destroyed|closed/i.test(err.message)) err.code = "STALE";
    throw err;
  }
  return payload;
}

function phoneTail(value) {
  const n = String(value || "").replace(/\D/g, "");
  return n.length >= 10 ? n.slice(-10) : n;
}

function looksLikeUnresolvedLid(item) {
  const id = String(item.id || "");
  const digits = String(item.phone || "").replace(/\D/g, "");
  return id.endsWith("@lid") || digits.length > 13;
}

function normalizeContactDigits(raw) {
  let digits = String(raw || "").replace(/\D/g, "");
  if (digits.length === 10) digits = `91${digits}`;
  if (digits.startsWith("91") && digits.length === 12) return digits;
  return "";
}

async function resolveItemPhone(client, item) {
  if (!item || !looksLikeUnresolvedLid(item)) return item;
  const id = String(item.id || "");
  if (!id) return item;
  try {
    const contact = await client.getContactById(id);
    let digits = normalizeContactDigits(contact.number || "");
    if (!digits && contact.id && contact.id.user) {
      digits = normalizeContactDigits(contact.id.user);
    }
    if (digits) {
      item.phone = digits;
      item.phone_resolved = true;
    }
  } catch (err) {
    console.warn("resolveItemPhone", id, err.message || err);
  }
  return item;
}

async function enrichChatPhones(client, items, maxResolve = 50) {
  let done = 0;
  for (const item of items || []) {
    if (done >= maxResolve) break;
    if (!looksLikeUnresolvedLid(item)) continue;
    await resolveItemPhone(client, item);
    done += 1;
  }
  return items;
}

/** Read message history from WA Web in-page store (works for @lid chats). */
async function fetchMessagesFromPage(c, chatId, limit) {
  const page = c.pupPage;
  if (!page || page.isClosed()) {
    const err = new Error("Browser page closed");
    err.code = "STALE";
    throw err;
  }
  const payload = await page.evaluate(
    (wantedId, max) => {
      try {
        if (typeof window.require !== "function") {
          return { ok: false, error: "WhatsApp page not ready" };
        }
        const Chat = window.require("WAWebCollections").Chat;
        const models = Chat.getModelsArray();
        const chat = models.find((ch) => {
          if (!ch || !ch.id) return false;
          const id = ch.id._serialized || String(ch.id);
          return id === wantedId;
        });
        if (!chat || !chat.msgs || !chat.msgs.getModelsArray) {
          return { ok: false, error: "Chat not found in page" };
        }
        const arr = chat.msgs.getModelsArray();
        const slice = arr.slice(-Math.max(1, max));
        const items = slice.map((m) => {
          const hasMedia = Boolean(m.isMedia || m.mediaData || m.type === "image" || m.type === "video");
          let body = String(m.body || m.caption || "").trim();
          if (!body && hasMedia) body = `[${m.type || "media"} message]`;
          return {
            id: (m.id && m.id._serialized) || "",
            body: body.slice(0, 8000),
            from_me: Boolean(m.id && m.id.fromMe),
            timestamp: m.t || null,
            type: m.type || "chat",
          };
        });
        return { ok: true, items };
      } catch (e) {
        return { ok: false, error: String(e.message || e) };
      }
    },
    chatId,
    limit,
  );
  if (!payload.ok) {
    const err = new Error(payload.error || "fetch failed");
    if (/not found/i.test(err.message)) err.code = "NOT_FOUND";
    throw err;
  }
  return payload.items || [];
}

async function resolveChatIdForMessages(client, chatId) {
  const wanted = decodeURIComponent(chatId || "").trim();
  if (!wanted) return null;
  try {
    await fetchMessagesFromPage(client, wanted, 1);
    return wanted;
  } catch (err) {
    if (err.code !== "NOT_FOUND") throw err;
  }
  const digits = wanted.split("@")[0].replace(/\D/g, "");
  if (!digits) return null;
  const wantTail = phoneTail(digits);
  const payload = await listChatsMinimal(client, 300);
  await enrichChatPhones(client, payload.items, 80);
  for (const item of payload.items || []) {
    const id = String(item.id || "");
    if (!id) continue;
    if (id === wanted) return id;
    if (phoneTail(item.phone) === wantTail) return id;
    if (id.startsWith(`${digits}@`)) return id;
  }
  return null;
}

app.get("/chats", async (req, res) => {
  try {
    const limit = Math.min(Math.max(Number(req.query.limit) || 100, 1), 200);
    let payload;
    try {
      payload = await runClientOp("listChats", async (c) => {
        const listed = await listChatsMinimal(c, limit);
        await enrichChatPhones(c, listed.items, 60);
        return listed;
      });
    } catch (err) {
      console.error("listChats failed:", err);
      return res.status(503).json({
        ok: false,
        error: err.message || String(err),
        stale_session: err.code === "STALE_SESSION" || isStaleBrowserError(err),
      });
    }
    res.json({ ok: true, items: payload.items, total: payload.total });
  } catch (err) {
    console.error("/chats failed:", err);
    res.status(502).json({ ok: false, error: String((err && err.message) || err) });
  }
});

app.get("/chats/:chatId/messages", async (req, res) => {
  try {
    const chatId = decodeURIComponent(req.params.chatId || "");
    const limit = Math.min(Math.max(Number(req.query.limit) || 80, 1), 200);
    const items = await runClientOp("fetchMessages", async (c) => {
      const resolvedId = await resolveChatIdForMessages(c, chatId);
      if (!resolvedId) {
        const err = new Error("Chat not found");
        err.code = "NOT_FOUND";
        throw err;
      }
      return fetchMessagesFromPage(c, resolvedId, limit);
    });
    res.json({ ok: true, items });
  } catch (err) {
    if (err.code === "NOT_FOUND") {
      return res.status(404).json({ ok: false, error: "Chat not found" });
    }
    const statusCode = err.code === "STALE_SESSION" || err.code === "NOT_READY" ? 503 : 502;
    res.status(statusCode).json({ ok: false, error: String(err.message || err) });
  }
});

app.post("/send", async (req, res) => {
  try {
    const phone = normalizePhone(req.body.phone);
    const text = String(req.body.text || "").trim();
    const mediaPath = String(req.body.media_path || "").trim();
    const caption = String(req.body.caption || text || "").trim();
    if (!text && !mediaPath) return res.status(422).json({ ok: false, error: "text or media_path required" });
    const result = await runClientOp("sendMessage", async (c) => {
      if (mediaPath) {
        if (!fs.existsSync(mediaPath)) {
          const err = new Error(`Media file not found: ${mediaPath}`);
          err.code = "NOT_FOUND";
          throw err;
        }
        const media = MessageMedia.fromFilePath(mediaPath);
        const sent = await c.sendMessage(phone, media, { caption: caption.slice(0, 1024) });
        if (text && text !== caption) {
          await c.sendMessage(phone, text);
        }
        return sent;
      }
      return c.sendMessage(phone, text);
    });
    res.json({ ok: true, id: messageId(result) });
  } catch (err) {
    if (err.code === "NOT_FOUND") {
      return res.status(422).json({ ok: false, error: String(err.message || err) });
    }
    const statusCode = err.code === "STALE_SESSION" || err.code === "NOT_READY" ? 503 : 502;
    res.status(statusCode).json({ ok: false, error: String(err.message || err) });
  }
});

setInterval(() => {
  if (!ready || !client) return;
  client
    .getState()
    .then((state) => {
      if (state !== "CONNECTED") {
        ready = false;
        status = "disconnected";
        lastError = `WhatsApp state: ${state}`;
      }
    })
    .catch((err) => {
      if (isStaleBrowserError(err)) {
        void hardResetClient("Session keepalive failed (detached frame). Reconnecting…");
      }
    });
}, 45000);

app.listen(PORT, "127.0.0.1", () => {
  console.log(`ApplyXAI WhatsApp bridge http://127.0.0.1:${PORT} (v${BRIDGE_VERSION})`);
  if (BRIDGE_SECRET) {
    console.log("Inbound chat forwarding: enabled (WHATSAPP_BRIDGE_SECRET set)");
  } else {
    console.warn("Inbound chat forwarding: DISABLED — set WHATSAPP_BRIDGE_SECRET to match the API .env");
  }
});
