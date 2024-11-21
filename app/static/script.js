document.addEventListener('DOMContentLoaded', function() {
    flatpickr('.flatpickr', {
        locale: 'ru',
        dateFormat: 'Y-m-d',
        minDate: "today"
    });
});