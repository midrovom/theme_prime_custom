(function () {
    "use strict";
    const installButton = document.getElementById("pwa-install-btn");
    const message = document.getElementById("pwa-install-message");
    const guide = document.getElementById("pwa-install-guide");
    let installPrompt = null;

    const standalone = window.matchMedia("(display-mode: standalone)").matches ||
        window.navigator.standalone === true;
    if (standalone) {
        message.textContent = "La aplicación ya está instalada. Pulsa Abrir Control de Gastos.";
        guide.hidden = true;
    } else if (!window.isSecureContext) {
        message.textContent = "Para instalar, abre Odoo desde un dominio HTTPS. La dirección HTTP con IP no permite instalar esta PWA.";
    }

    window.addEventListener("beforeinstallprompt", (event) => {
        event.preventDefault();
        installPrompt = event;
        if (window.isSecureContext && !standalone) {
            installButton.hidden = false;
            message.textContent = "Instalación disponible en este dispositivo.";
        }
    });

    installButton.addEventListener("click", async () => {
        if (!installPrompt) return;
        const prompt = installPrompt;
        installPrompt = null;
        installButton.hidden = true;
        try {
            await prompt.prompt();
            const result = await prompt.userChoice;
            message.textContent = result.outcome === "accepted" ?
                "Se aceptó la instalación." : "Puedes instalar más tarde desde el menú del navegador.";
        } catch (error) {
            message.textContent = "Instala desde el menú del navegador.";
        }
    });

    window.addEventListener("appinstalled", () => {
        installButton.hidden = true;
        guide.hidden = true;
        message.textContent = "Aplicación instalada. Ya puedes abrirla desde la pantalla de inicio.";
    });
})();
