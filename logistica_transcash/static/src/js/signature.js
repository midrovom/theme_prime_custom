/** Firma manuscrita en destino: el receptor firma en el dispositivo del chofer. */
(function () {
    'use strict';
    function activate(box) {
        const canvas = box.querySelector('.tc-sign-canvas');
        const hidden = box.querySelector('.tc-sign-value');
        const clear = box.querySelector('.tc-sign-clear');
        const form = box.closest('form');
        if (!canvas || !form || !hidden) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.strokeStyle = '#16273b';
        ctx.lineWidth = 3;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        let pressed = false;
        let drawn = false;
        function coordinate(evt) {
            const rect = canvas.getBoundingClientRect();
            return {
                x: (evt.clientX - rect.left) * canvas.width / rect.width,
                y: (evt.clientY - rect.top) * canvas.height / rect.height,
            };
        }
        canvas.addEventListener('pointerdown', function (evt) {
            if (evt.cancelable) evt.preventDefault();
            canvas.setPointerCapture(evt.pointerId);
            const pos = coordinate(evt);
            pressed = true;
            ctx.beginPath();
            ctx.moveTo(pos.x, pos.y);
        });
        canvas.addEventListener('pointermove', function (evt) {
            if (!pressed) return;
            if (evt.cancelable) evt.preventDefault();
            const pos = coordinate(evt);
            ctx.lineTo(pos.x, pos.y);
            ctx.stroke();
            drawn = true;
        });
        for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) {
            canvas.addEventListener(event, function () { pressed = false; });
        }
        clear.addEventListener('click', function () {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            drawn = false;
            hidden.value = '';
        });
        form.addEventListener('submit', function (evt) {
            if (!drawn) {
                evt.preventDefault();
                window.alert('Solicita la firma de la persona que recibe para finalizar la entrega.');
                canvas.scrollIntoView({behavior: 'smooth', block: 'center'});
                return;
            }
            hidden.value = canvas.toDataURL('image/png');
        });
    }
    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.tc-sign-box').forEach(activate);
    });
})();
