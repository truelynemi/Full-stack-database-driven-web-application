// consent.js — cookie consent banner handler
// Sets a 1-year cookie when the user clicks Accept, then reloads so Flask
// can render the page with consent=accepted and load tracking scripts.
document.addEventListener('DOMContentLoaded', function () {
    var btn = document.getElementById('accept-btn');
    if (!btn) return;

    btn.addEventListener('click', function () {
        var exp = new Date();
        exp.setFullYear(exp.getFullYear() + 1);
        document.cookie =
            'cookie_consent=accepted; expires=' + exp.toUTCString() +
            '; path=/; SameSite=Lax';
        // Reload so Flask re-renders with the new cookie value
        window.location.reload();
    });
});
