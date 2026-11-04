/* Pantalla de diagnóstico independiente de app.js. No toca IndexedDB ni las colas offline. */
(() => {
  const root = document.getElementById("app");
  if (!root) return;
  let done = false;
  let timer;
  const messageText = (message) => String(message || "No se pudo iniciar Catastro.");
  function showFailure(message) {
    if (done) return;
    done = true;
    clearTimeout(timer);
    root.dataset.ready = "error";
    root.replaceChildren();
    const pane = document.createElement("div");
    pane.className = "boot-screen boot-error";
    const icon = document.createElement("div");
    icon.className = "boot-logo";
    icon.textContent = "!";
    const title = document.createElement("strong");
    title.textContent = "Catastro no pudo iniciar";
    const description = document.createElement("p");
    description.className = "boot-error-text";
    description.textContent = messageText(message);
    const note = document.createElement("p");
    note.className = "boot-error-note";
    note.textContent = "No borre los datos del sitio ni desinstale la PWA si tiene registros sin sincronizar.";
    const actions = document.createElement("div");
    actions.className = "boot-actions";
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "btn btn-primary";
    retry.textContent = "Reintentar";
    retry.addEventListener("click", () => window.location.replace("/catastro/app?retry=" + Date.now()));
    const repair = document.createElement("button");
    repair.type = "button";
    repair.className = "btn btn-outline";
    repair.textContent = "Reparar caché de la interfaz";
    repair.addEventListener("click", async () => {
      if (!navigator.onLine) { note.textContent = "Conéctese a Internet antes de reparar la interfaz; los datos locales se conservarán."; return; }
      repair.disabled = true;
      note.textContent = "Actualizando los archivos de la interfaz. No se borrarán catastros ni pendientes del dispositivo.";
      try {
        // La comprobación es un fetch normal (no navegación), por lo que el SW no
        // devuelve su copia offline de /catastro/app. No borrar caché sin servidor.
        const check = await fetch("/catastro/app?health=" + Date.now(), {
          cache: "no-store", credentials: "same-origin",
        });
        if (!check.ok || check.redirected || !(check.headers.get("content-type") || "").includes("text/html")) {
          throw new Error("No se pudo comprobar una sesión activa y una respuesta válida de Odoo");
        }
        if ("serviceWorker" in navigator) {
          const registrations = await navigator.serviceWorker.getRegistrations();
          for (const reg of registrations) {
            if (new URL(reg.scope).pathname.startsWith("/catastro/")) await reg.unregister();
          }
        }
        if ("caches" in window) {
          for (const key of await caches.keys()) {
            if (key.startsWith("catastro-field-") || key.startsWith("conedera-field-")) await caches.delete(key);
          }
        }
        window.location.replace("/catastro/app?repair=" + Date.now());
      } catch (error) {
        repair.disabled = false;
        note.textContent = "No se pudo actualizar: " + messageText(error?.message || error) + ". No se han borrado los registros locales.";
      }
    });
    const back = document.createElement("a");
    back.className = "btn btn-outline";
    back.href = "/web";
    back.textContent = "Abrir Odoo";
    actions.append(retry, repair, back);
    pane.append(icon, title, description, note, actions);
    root.append(pane);
  }
  window.catastroBootReady = () => {
    done = true;
    clearTimeout(timer);
    root.dataset.ready = "1";
  };
  window.catastroBootError = showFailure;
  timer = setTimeout(() => {
    if (root.dataset.ready === "1" || root.querySelector(".app-shell")) return;
    showFailure("La pantalla tardó demasiado en cargar. Puede ser una pestaña anterior bloqueando la base local, un archivo JavaScript antiguo o un problema de conectividad.");
  }, 13000);
})();
