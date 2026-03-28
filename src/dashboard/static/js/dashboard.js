/**
 * AgenteDeVoz Dashboard - JavaScript
 * Actualizaciones en tiempo real via WebSocket y polling.
 */

(function () {
  "use strict";

  // ── WebSocket de actualizaciones en tiempo real ──────────────────────────

  let ws = null;
  let reconnectTimer = null;

  function connectWS() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${location.host}/dashboard/ws/live`;

    ws = new WebSocket(url);

    ws.onopen = function () {
      console.info("[WS] Conectado al dashboard");
      clearTimeout(reconnectTimer);
      setLiveBadge(true);
    };

    ws.onmessage = function (evt) {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === "stats") {
          applyStats(msg.data);
        }
      } catch (e) {
        console.warn("[WS] Mensaje inválido:", e);
      }
    };

    ws.onerror = function () {
      setLiveBadge(false);
    };

    ws.onclose = function () {
      setLiveBadge(false);
      // Reconectar en 10 segundos
      reconnectTimer = setTimeout(connectWS, 10000);
    };
  }

  function setLiveBadge(online) {
    const badge = document.getElementById("live-badge");
    if (!badge) return;
    if (online) {
      badge.textContent = "LIVE";
      badge.className = "badge badge-ok";
    } else {
      badge.textContent = "OFFLINE";
      badge.className = "badge badge-warning";
    }
  }

  // ── Aplicar estadísticas al DOM ──────────────────────────────────────────

  function applyStats(stats) {
    setElText("active-calls", stats.active_calls);
    setElText("uptime", stats.uptime);

    // Actualizar puntos de estado de componentes si existen
    updateComponentDot("api", stats.api_status);
    updateComponentDot("stt", stats.stt_status);
    updateComponentDot("tts", stats.tts_status);
    updateComponentDot("db", stats.db_status);
    updateComponentDot("redis", stats.redis_status);
  }

  function updateComponentDot(name, status) {
    const el = document.getElementById(`comp-${name}`);
    if (!el) return;
    el.textContent = status;
    el.className = status === "ok" ? "badge badge-ok" : "badge badge-warning";
  }

  // ── Utilidades ────────────────────────────────────────────────────────────

  function setElText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function formatDuration(seconds) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  // ── Notificaciones ────────────────────────────────────────────────────────

  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    Object.assign(toast.style, {
      position: "fixed", bottom: "20px", right: "20px",
      padding: "12px 20px", borderRadius: "6px",
      background: type === "error" ? "#ef4444" :
                  type === "success" ? "#22c55e" : "#4f86f7",
      color: "#fff", fontWeight: "500", fontSize: "13px",
      zIndex: "9999", boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
      transition: "opacity 0.3s",
    });
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 350);
    }, 3500);
  }

  // ── Chat de demo (disponible en todas las páginas) ─────────────────────

  function initDemoChat() {
    const chatBtn = document.getElementById("demo-chat-btn");
    if (!chatBtn) return;

    const panel = document.getElementById("demo-chat-panel");
    const input = document.getElementById("demo-chat-input");
    const messages = document.getElementById("demo-chat-messages");

    let chatWs = null;
    let sessionId = null;

    chatBtn.addEventListener("click", function () {
      panel.style.display = panel.style.display === "none" ? "flex" : "none";
      if (panel.style.display === "flex" && !chatWs) {
        startChatWS();
      }
    });

    function startChatWS() {
      sessionId = "demo_" + Math.random().toString(36).slice(2, 10);
      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      chatWs = new WebSocket(`${proto}//${location.host}/ws/chat/${sessionId}`);

      chatWs.onmessage = function (evt) {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type === "response") {
            appendMessage("bot", msg.content);
          }
        } catch (e) {}
      };

      chatWs.onerror = function () {
        appendMessage("system", "Error de conexion.");
      };
    }

    if (input) {
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          const text = input.value.trim();
          if (!text || !chatWs) return;
          appendMessage("user", text);
          chatWs.send(JSON.stringify({ type: "text", content: text }));
          input.value = "";
        }
      });
    }

    function appendMessage(role, text) {
      if (!messages) return;
      const div = document.createElement("div");
      div.className = `chat-msg chat-msg-${role}`;
      div.textContent = text;
      messages.appendChild(div);
      messages.scrollTop = messages.scrollHeight;
    }
  }

  // ── Auto-highlight de fila activa ─────────────────────────────────────────

  function highlightActiveSessions() {
    document.querySelectorAll("[data-state]").forEach(row => {
      const state = row.dataset.state;
      if (state && state !== "FIN") {
        row.style.borderLeft = "3px solid var(--primary)";
      }
    });
  }

  // ── Init ──────────────────────────────────────────────────────────────────

  document.addEventListener("DOMContentLoaded", function () {
    connectWS();
    initDemoChat();
    highlightActiveSessions();
  });

  // Exponer showToast globalmente para uso desde HTML inline
  window.showToast = showToast;

})();
