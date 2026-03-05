// frontend/src/api/employees.js
import apiClient from './client';

export const employeeAPI = {
    // Get all employees
    getAllEmployees: async () => {
        return await apiClient('/employee', {
            method: 'GET'
        });
    },

    // Get a specific employee by ID
    getEmployeeById: async (id) => {
        return await apiClient(`/employee/${id}`, {
            method: 'GET'
        });
    },

    // Create a new employee (uses FormData because of images)
    createEmployee: async (formData) => {
        // We do *not* set Content-Type to application/json here. 
        // fetch automatically sets multipart/form-data with boundaries when we pass a FormData object.
        return await apiClient('/employee', {
            method: 'POST',
            body: formData
        });
    },

    // Update employee partially
    updateEmployee: async (id, employeeData) => {
        return await apiClient(`/employee/${id}`, {
            method: 'PATCH',
            body: JSON.stringify(employeeData)
        });
    },

    // Delete an employee
    deleteEmployee: async (id) => {
        return await apiClient(`/employee/${id}`, {
            method: 'DELETE'
        });
    }
};
