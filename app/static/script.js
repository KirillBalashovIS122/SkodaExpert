function editEmployee(id, name, email, phone, role) {
    document.getElementById('editEmployeeId').value = id;
    document.getElementById('editEmployeeName').value = name;
    document.getElementById('editEmployeeEmail').value = email;
    document.getElementById('editEmployeePhone').value = phone;
    document.getElementById('editEmployeeRole').value = role;
    document.getElementById('editEmployeeModal').style.display = 'block';
}

function editService(id, name, description, price, duration) {
    document.getElementById('editServiceId').value = id;
    document.getElementById('editServiceName').value = name;
    document.getElementById('editServiceDescription').value = description;
    document.getElementById('editServicePrice').value = price;
    document.getElementById('editServiceDuration').value = duration;
    document.getElementById('editServiceModal').style.display = 'block';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        closeModal(event.target.id);
    }
}

function confirmDelete(appointmentId) {
    if (confirm("Вы уверены, что хотите удалить эту запись?")) {
        document.getElementById('deleteForm' + appointmentId).submit();
    }
}

function viewOrderDetails(orderId, clientName, carModel, appointmentDate, appointmentTime) {
    document.getElementById('orderClientName').innerText = clientName;
    document.getElementById('orderCarModel').innerText = carModel;
    document.getElementById('orderAppointmentDate').innerText = appointmentDate;
    document.getElementById('orderAppointmentTime').innerText = appointmentTime;
    document.getElementById('viewOrderDetailsModal').style.display = 'block';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        closeModal(event.target.id);
    }
}