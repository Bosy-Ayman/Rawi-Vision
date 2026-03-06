import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { employeeAPI } from '../api/employees';
import './AllEmployees.css';

const AllEmployees = () => {
    const [employees, setEmployees] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [isLoading, setIsLoading] = useState(true);

    // Modal State
    const [isEditModalOpen, setIsEditModalOpen] = useState(false);
    const [selectedEmployee, setSelectedEmployee] = useState(null);
    const [updateForm, setUpdateForm] = useState({ first_name: '', last_name: '', role: '' });
    const [isUpdating, setIsUpdating] = useState(false);
    const [showDeleteModal, setShowDeleteModal] = useState(false); // Added for delete functionality
    const navigate = useNavigate(); // Keep navigate for the Add New button

    const fetchEmployees = async () => {
        try {
            const data = await employeeAPI.getAllEmployees();
            setEmployees(data);
            setIsLoading(false);
        } catch (err) {
            console.error("Failed to fetch employees:", err);
            // Optionally set an error state here if needed for display
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchEmployees();
    }, []);

    const handleEditClick = (emp) => {
        setSelectedEmployee(emp);
        setUpdateForm({
            first_name: emp.first_name,
            last_name: emp.last_name,
            role: emp.role
        });
        setIsEditModalOpen(true);
    };

    const handleUpdateSubmit = async (e) => {
        e.preventDefault();
        setIsUpdating(true);
        try {
            const response = await employeeAPI.updateEmployee(selectedEmployee.id, updateForm); // Changed to employeeAPI.updateEmployee
            if (response) { // employeeAPI.updateEmployee should return the updated employee or true/false
                setIsEditModalOpen(false);
                fetchEmployees(); // Refresh the list
            } else {
                alert('Failed to update employee');
            }
        } catch (error) {
            console.error('Update error:', error);
            alert('Error connecting to server');
        } finally {
            setIsUpdating(false);
        }
    };

    // Added handleDelete function based on the provided snippet's content
    const handleDelete = async () => {
        setIsUpdating(true); // Reusing isUpdating for delete operation feedback
        try {
            await employeeAPI.deleteEmployee(selectedEmployee.id);
            setEmployees(employees.filter(emp => emp.id !== selectedEmployee.id));
            setShowDeleteModal(false);
            setSelectedEmployee(null);
        } catch (err) {
            console.error("Failed to delete employee:", err);
            alert('Error connecting to server'); // Added alert for delete error
        } finally {
            setIsUpdating(false);
        }
    };

    const filteredEmployees = employees.filter(emp =>
        emp.first_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        emp.last_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        emp.role.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <DashboardLayout title="Employee Directory">
            <div className="all-employees-container">
                <div className="page-header">
                    <h2 className="header-title">All Employees</h2>
                    <div className="header-center">
                        <div className="search-bar">
                            <input
                                type="text"
                                placeholder="Search by name or role..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>
                    </div>
                    <div className="header-right">
                        <button className="btn-add-new" onClick={() => navigate('/dashboard/employee-onboarding')}>
                            + Add New
                        </button>
                    </div>
                </div>

                {isLoading ? (
                    <div className="loading">Loading employees...</div>
                ) : (
                    <div className="employee-grid">
                        {filteredEmployees.length > 0 ? (
                            filteredEmployees.map(emp => (
                                <div key={emp.id} className="employee-card" onClick={() => handleEditClick(emp)}>
                                    <div className="card-image">
                                        <div className="avatar-placeholder">
                                            {emp.first_name.charAt(0)}{emp.last_name.charAt(0)}
                                        </div>
                                    </div>
                                    <div className="card-info">
                                        <h3>{emp.first_name} {emp.last_name}</h3>
                                        <p className="role-badge">{emp.role}</p>
                                        <p className="joined-date">Joined: {new Date(emp.date_created).toLocaleDateString()}</p>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="empty-state">
                                <p>No employees found matching your search.</p>
                            </div>
                        )}
                    </div>
                )}

                {/* Edit Modal */}
                {isEditModalOpen && (
                    <div className="modal-overlay">
                        <div className="edit-modal">
                            <div className="modal-header">
                                <h3>Update Employee</h3>
                                <button className="close-btn" onClick={() => setIsEditModalOpen(false)}>×</button>
                            </div>
                            <form onSubmit={handleUpdateSubmit}>
                                <div className="form-group">
                                    <label>First Name</label>
                                    <input
                                        type="text"
                                        value={updateForm.first_name}
                                        onChange={(e) => setUpdateForm({ ...updateForm, first_name: e.target.value })}
                                        required
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Last Name</label>
                                    <input
                                        type="text"
                                        value={updateForm.last_name}
                                        onChange={(e) => setUpdateForm({ ...updateForm, last_name: e.target.value })}
                                        required
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Role</label>
                                    <select
                                        value={updateForm.role}
                                        onChange={(e) => setUpdateForm({ ...updateForm, role: e.target.value })}
                                        required
                                    >
                                        <option value="Software Engineer">Software Engineer</option>
                                        <option value="HR">HR</option>
                                        <option value="Manager">Manager</option>
                                        <option value="Security">Security</option>
                                        <option value="Staff">Staff</option>
                                    </select>
                                </div>
                                <div className="modal-actions">
                                    <button type="button" className="btn-cancel" onClick={() => setIsEditModalOpen(false)}>Cancel</button>
                                    <button type="submit" className="btn-save" disabled={isUpdating}>
                                        {isUpdating ? 'Saving...' : 'Save Changes'}
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                )}
            </div>
        </DashboardLayout>
    );
};

export default AllEmployees;
