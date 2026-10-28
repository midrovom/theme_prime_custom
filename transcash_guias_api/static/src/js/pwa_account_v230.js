/** Account entry fallback for detail pages with no shared branding header.
 *  Never logs out automatically, never handles or stores passwords.
 */
document.addEventListener('DOMContentLoaded', function () {
    if (document.querySelector('.tc-account-menu')) return;
    var host = document.querySelector('.tc-top') || document.querySelector('.tc-hub-page-top');
    if (!host) return;
    var menu = document.createElement('details');
    menu.className = 'tc-account-menu';
    var summary = document.createElement('summary');
    summary.textContent = 'Mi cuenta ▾';
    menu.appendChild(summary);
    var box = document.createElement('div');
    box.className = 'tc-account-dropdown';
    var change = document.createElement('a');
    change.href = '/logistica/mi-cuenta';
    change.textContent = '🔒 Cambiar contraseña';
    var logout = document.createElement('a');
    logout.href = '/web/session/logout?redirect=/web/login';
    logout.className = 'tc-account-logout';
    logout.textContent = '↪ Cerrar sesión';
    box.appendChild(change);
    box.appendChild(logout);
    menu.appendChild(box);
    host.appendChild(menu);
});
