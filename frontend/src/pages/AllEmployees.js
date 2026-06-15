import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { employeeAPI } from '../api/employees';
import { cameraAPI } from '../api/cameras';
import EmployeeAvatar from '../components/dashboard/EmployeeAvatar';
import './AllEmployees.css';

const WEEKDAYS = [
    { label: 'M', value: 0, fullName: 'Monday' },
    { label: 'T', value: 1, fullName: 'Tuesday' },
    { label: 'W', value: 2, fullName: 'Wednesday' },
    { label: 'T', value: 3, fullName: 'Thursday' },
    { label: 'F', value: 4, fullName: 'Friday' },
    { label: 'S', value: 5, fullName: 'Saturday' },
    { label: 'S', value: 6, fullName: 'Sunday' }
];

const CameraMultiSelect = ({ cameras, selectedCameraIds = [], onChange }) => {
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = React.useRef(null);

    React.useEffect(() => {
        const handleClickOutside = (event) => {
            if (containerRef.current && !containerRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    return (
        <div className="custom-multiselect-container" ref={containerRef}>
            <div className="multiselect-trigger" onClick={() => setIsOpen(!isOpen)}>
                <span>
                    {selectedCameraIds.length === 0 
                        ? 'No Cameras Assigned' 
                        : `${selectedCameraIds.length} Camera(s) Selected`}
                </span>
                <span className="arrow" style={{ fontSize: '0.8rem', opacity: 0.7 }}>▼</span>
            </div>
            {isOpen && (
                <div className="multiselect-dropdown">
                    {cameras.length === 0 ? (
                        <div style={{ padding: '8px', color: '#6b7280', fontSize: '0.9rem' }}>No cameras available</div>
                    ) : (
                        cameras.map(cam => {
                            const isChecked = selectedCameraIds.includes(cam.id);
                            return (
                                <label key={cam.id} className="multiselect-item">
                                    <input
                                        type="checkbox"
                                        checked={isChecked}
                                        onChange={() => {
                                            const newIds = isChecked
                                                ? selectedCameraIds.filter(id => id !== cam.id)
                                                : [...selectedCameraIds, cam.id];
                                            onChange(newIds);
                                        }}
                                        style={{ marginRight: '8px', cursor: 'pointer' }}
                                    />
                                    <span className="item-text">{cam.room} ({cam.building || 'No Location'})</span>
                                </label>
                            );
                        })
                    )}
                </div>
            )}
        </div>
    );
};

const AllEmployees = () => {
    const [employees, setEmployees] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    
    // Pagination State
    const [currentPage, setCurrentPage] = useState(1);
    const recordsPerPage = 12; // Show 12 employee cards per page

    // Modal State
    const [isEditModalOpen, setIsEditModalOpen] = useState(false);
    const [selectedEmployee, setSelectedEmployee] = useState(null);
    const [updateForm, setUpdateForm] = useState({ 
        first_name: '', 
        last_name: '', 
        role: '', 
        assigned_camera_ids: [],
        assigned_days: [],
        assigned_shift_start: '',
        assigned_shift_end: ''
    });
    const [cameras, setCameras] = useState([]);
    const [isUpdating, setIsUpdating] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const [showDeleteModal, setShowDeleteModal] = useState(false); // Added for delete functionality
    const navigate = useNavigate(); // Keep navigate for the Add New button

    const fetchEmployees = async () => {
        try {
            const data = await employeeAPI.getAllEmployees();
            setEmployees(data);
            setIsLoading(false);
        } catch (err) {
            console.error("Failed to fetch employees:", err);
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchEmployees();
        const fetchCameras = async () => {
            try {
                const list = await cameraAPI.getAllCameras();
                setCameras(list || []);
            } catch (err) {
                console.error("Failed to load cameras list", err);
            }
        };
        fetchCameras();
    }, []);

    const handleEditClick = (emp) => {
        setSelectedEmployee(emp);
        setUpdateForm({
            first_name: emp.first_name,
            last_name: emp.last_name,
            role: emp.role,
            assigned_camera_ids: emp.assigned_camera_ids || [],
            assigned_days: emp.assigned_days || [0, 1, 2, 3, 4],
            assigned_shift_start: emp.assigned_shift_start || '',
            assigned_shift_end: emp.assigned_shift_end || ''
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
            alert('An error occurred during update');
        } finally {
            setIsUpdating(false);
        }
    };

    const handleDeleteClick = async () => {
        if (!window.confirm("Are you sure you want to delete this employee? This action cannot be undone.")) return;
        setIsDeleting(true);
        try {
            const response = await employeeAPI.deleteEmployee(selectedEmployee.id);
            setIsEditModalOpen(false);
            fetchEmployees();
        } catch (err) {
            console.error("Delete error:", err);
            alert("An error occurred while deleting the employee.");
        } finally {
            setIsDeleting(false);
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

    // Reset to first page when searching
    useEffect(() => {
        setCurrentPage(1);
    }, [searchTerm]);

    // Pagination Logic
    const indexOfLastRecord = currentPage * recordsPerPage;
    const indexOfFirstRecord = indexOfLastRecord - recordsPerPage;
    const currentRecords = filteredEmployees.slice(indexOfFirstRecord, indexOfLastRecord);
    const totalPages = Math.ceil(filteredEmployees.length / recordsPerPage);

    const paginate = (pageNumber) => setCurrentPage(pageNumber);

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
                    <div className="employee-grid-container">
                        <div className="employee-grid">
                            {currentRecords.length > 0 ? (
                                currentRecords.map(emp => (
                                    <div key={emp.id} className="employee-card" onClick={() => handleEditClick(emp)}>
                                        <div className="card-image">
                                            <EmployeeAvatar 
                                                imageUrl={emp.profile_image_url} 
                                                firstName={emp.first_name} 
                                                lastName={emp.last_name} 
                                                size={60} 
                                            />
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
                        
                        {/* Pagination Controls */}
                        {totalPages > 1 && (
                            <div className="pagination">
                                <button 
                                    onClick={() => paginate(currentPage - 1)} 
                                    disabled={currentPage === 1}
                                    className="page-btn"
                                >
                                    Prev
                                </button>
                                <span className="page-info">
                                    Page <span className="page-number">{currentPage}</span> of {totalPages}
                                </span>
                                <button 
                                    onClick={() => paginate(currentPage + 1)} 
                                    disabled={currentPage === totalPages}
                                    className="page-btn"
                                >
                                    Next
                                </button>
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
                                        <option value="Intern">Intern</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label>Assigned Cameras / Rooms</label>
                                    <CameraMultiSelect
                                        cameras={cameras}
                                        selectedCameraIds={updateForm.assigned_camera_ids}
                                        onChange={(newIds) => setUpdateForm({ ...updateForm, assigned_camera_ids: newIds })}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Routine Days (Weekly)</label>
                                    <div className="days-selector">
                                        {WEEKDAYS.map(day => {
                                            const isSelected = (updateForm.assigned_days || []).includes(day.value);
                                            return (
                                                <button
                                                    key={day.value}
                                                    type="button"
                                                    className={`day-pill ${isSelected ? 'active' : ''}`}
                                                    onClick={() => {
                                                        const currentDays = updateForm.assigned_days || [];
                                                        const newDays = isSelected
                                                            ? currentDays.filter(d => d !== day.value)
                                                            : [...currentDays, day.value];
                                                        setUpdateForm({ ...updateForm, assigned_days: newDays });
                                                    }}
                                                    title={day.fullName}
                                                >
                                                    {day.label}
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                                    <div className="form-group">
                                        <label>Shift Start Time</label>
                                        <input
                                            type="time"
                                            value={updateForm.assigned_shift_start || ''}
                                            onChange={(e) => setUpdateForm({ ...updateForm, assigned_shift_start: e.target.value })}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Shift End Time</label>
                                        <input
                                            type="time"
                                            value={updateForm.assigned_shift_end || ''}
                                            onChange={(e) => setUpdateForm({ ...updateForm, assigned_shift_end: e.target.value })}
                                        />
                                    </div>
                                </div>
                                <div className="modal-actions" style={{ justifyContent: 'space-between' }}>
                                    <button type="button" className="btn-cancel" style={{ color: '#dc3545', borderColor: '#dc3545' }} onClick={handleDeleteClick} disabled={isDeleting}>
                                        {isDeleting ? 'Deleting...' : 'Delete Employee'}
                                    </button>
                                    <div style={{ display: 'flex', gap: '8px' }}>
                                        <button type="button" className="btn-cancel" onClick={() => setIsEditModalOpen(false)}>Cancel</button>
                                        <button type="submit" className="btn-save" disabled={isUpdating}>
                                            {isUpdating ? 'Saving...' : 'Save Changes'}
                                        </button>
                                    </div>
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
