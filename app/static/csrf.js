document.addEventListener('DOMContentLoaded', function() {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    document.querySelectorAll('form').forEach(form => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'csrf_token';
        input.value = csrfToken;
        form.appendChild(input);
    });
});