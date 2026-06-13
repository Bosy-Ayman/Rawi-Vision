import React, { useState } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { employeeAPI } from '../api/employees';
import { cameraAPI } from '../api/camera';
import './EmployeeOnboarding.css';

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

const EmployeeOnboarding = () => {
    const [employees, setEmployees] = useState([
        { firstName: '', lastName: '', role: '', assignedCameraIds: [], assignedDays: [0, 1, 2, 3, 4], assignedShiftStart: '', assignedShiftEnd: '', photo: null, photoPreview: null }
    ]);
    const [cameras, setCameras] = useState([]);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [submitStatus, setSubmitStatus] = useState(null); // 'success', 'error', or null
    const [successCount, setSuccessCount] = useState(0);

    React.useEffect(() => {
        const fetchCameras = async () => {
            try {
                const list = await cameraAPI.getAllCameras();
                setCameras(list || []);
            } catch (err) {
                console.error("Failed to load cameras list for onboarding", err);
            }
        };
        fetchCameras();
    }, []);

    const handleAddRow = () => {
        setEmployees([...employees, { firstName: '', lastName: '', role: '', assignedCameraIds: [], assignedDays: [0, 1, 2, 3, 4], assignedShiftStart: '', assignedShiftEnd: '', photo: null, photoPreview: null }]);
    };

    const handleRemoveRow = (index) => {
        const newEmployees = [...employees];
        newEmployees.splice(index, 1);
        setEmployees(newEmployees);
    };

    const handleChange = (index, field, value) => {
        const newEmployees = [...employees];
        newEmployees[index][field] = value;
        setEmployees(newEmployees);
    };

    const handlePhotoChange = (index, e) => {
        const file = e.target.files[0];
        if (file) {
            const newEmployees = [...employees];
            newEmployees[index].photo = file;
            newEmployees[index].photoPreview = URL.createObjectURL(file);
            setEmployees(newEmployees);
        }
    };

    const handleSubmitAll = async () => {
        setIsSubmitting(true);
        setSubmitStatus(null);
        setSuccessCount(0);

        let currentSuccessCount = 0;
        let errors = [];

        try {
            for (let i = 0; i < employees.length; i++) {
                const emp = employees[i];
                if (!emp.firstName || !emp.lastName || !emp.role || !emp.photo) {
                    errors.push(`Row ${i + 1}: Missing required fields`);
                    continue;
                }

                const formData = new FormData();
                formData.append('first_name', emp.firstName);
                formData.append('last_name', emp.lastName);
                formData.append('role', emp.role);
                formData.append('assigned_camera_ids', JSON.stringify(emp.assignedCameraIds || []));
                formData.append('assigned_days', JSON.stringify(emp.assignedDays || []));
                
                if (emp.assignedShiftStart) {
                    formData.append('assigned_shift_start', emp.assignedShiftStart);
                }
                if (emp.assignedShiftEnd) {
                    formData.append('assigned_shift_end', emp.assignedShiftEnd);
                }
                formData.append('employee_pictures', emp.photo);

                try {
                    await employeeAPI.createEmployee(formData);
                    currentSuccessCount++;
                } catch (error) {
                    console.error(`Error uploading employee at row ${i + 1}: `, error);
                    const errorMessage = error.response && error.response.data && error.response.data.detail
                        ? error.response.data.detail
                        : error.message || 'Failed to upload';
                    errors.push(`Row ${i + 1}: ${errorMessage} `);
                }
            }

            if (errors.length === 0 && currentSuccessCount > 0) {
                setSuccessCount(currentSuccessCount);
                setSubmitStatus('success');
                setEmployees([{ firstName: '', lastName: '', role: '', assignedCameraIds: [], assignedDays: [0, 1, 2, 3, 4], assignedShiftStart: '', assignedShiftEnd: '', photo: null, photoPreview: null }]); // Reset form
                setTimeout(() => setSubmitStatus(null), 3000);
            } else if (errors.length > 0) {
                setSubmitStatus('error');
                console.error("Errors:", errors);
                alert(`Some employees failed to upload: \n${errors.join('\n')} `);
            }

        } catch (error) {
            console.error("Submission error:", error);
            setSubmitStatus('error');
            alert("Network error or server unavailable.");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <DashboardLayout title="Employee Onboarding">
            <div className="onboarding-container">
                <div className="onboarding-header">
                    <h2>Add New Employees</h2>
                    <p>Enter employee details and upload a photo for facial recognition.</p>
                </div>

                {submitStatus === 'success' && (
                    <div className="status-message success">
                        Successfully added {successCount} {successCount === 1 ? 'employee' : 'employees'}!
                    </div>
                )}

                <div className="employee-rows">
                    {employees.map((emp, index) => (
                        <div key={index} className="employee-row-card">
                            <div className="row-header">
                                <h3>Employee #{index + 1}</h3>
                                {employees.length > 1 && (
                                    <button
                                        className="btn-remove"
                                        onClick={() => handleRemoveRow(index)}
                                        title="Remove this row"
                                    >
                                        ×
                                    </button>
                                )}
                            </div>

                            <div className="row-content">
                                <div className="photo-upload-section">
                                    <div className="photo-preview" onClick={() => document.getElementById(`photo-upload-${index}`).click()}>
                                        {emp.photoPreview ? (
                                            <img src={emp.photoPreview} alt="Preview" />
                                        ) : (
                                            <div className="placeholder">
                                                <span>+ Upload Photo</span>
                                            </div>
                                        )}
                                    </div>
                                    <input
                                        type="file"
                                        id={`photo-upload-${index}`}
                                        className="hidden-input"
                                        accept="image/*"
                                        onChange={(e) => handlePhotoChange(index, e)}
                                    />
                                </div>

                                <div className="details-form">
                                    <div className="form-group">
                                        <label>First Name</label>
                                        <input
                                            type="text"
                                            value={emp.firstName}
                                            onChange={(e) => handleChange(index, 'firstName', e.target.value)}
                                            placeholder="e.g. John"
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Last Name</label>
                                        <input
                                            type="text"
                                            value={emp.lastName}
                                            onChange={(e) => handleChange(index, 'lastName', e.target.value)}
                                            placeholder="e.g. Doe"
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Role</label>
                                        <select
                                            value={emp.role}
                                            onChange={(e) => handleChange(index, 'role', e.target.value)}
                                        >
                                            <option value="">Select Role...</option>
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
                                            selectedCameraIds={emp.assignedCameraIds}
                                            onChange={(newIds) => handleChange(index, 'assignedCameraIds', newIds)}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Routine Days (Weekly)</label>
                                        <div className="days-selector">
                                            {WEEKDAYS.map(day => {
                                                const isSelected = (emp.assignedDays || []).includes(day.value);
                                                return (
                                                    <button
                                                        key={day.value}
                                                        type="button"
                                                        className={`day-pill ${isSelected ? 'active' : ''}`}
                                                        onClick={() => {
                                                            const currentDays = emp.assignedDays || [];
                                                            const newDays = isSelected
                                                                ? currentDays.filter(d => d !== day.value)
                                                                : [...currentDays, day.value];
                                                            handleChange(index, 'assignedDays', newDays);
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
                                                value={emp.assignedShiftStart}
                                                onChange={(e) => handleChange(index, 'assignedShiftStart', e.target.value)}
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>Shift End Time</label>
                                            <input
                                                type="time"
                                                value={emp.assignedShiftEnd}
                                                onChange={(e) => handleChange(index, 'assignedShiftEnd', e.target.value)}
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                <div className="onboarding-actions">
                    <button className="btn-add-row" onClick={handleAddRow}>
                        + Add Another Employee
                    </button>
                    <button
                        className="btn-submit-all"
                        onClick={handleSubmitAll}
                        disabled={isSubmitting}
                    >
                        {isSubmitting ? 'Submitting...' : 'Submit All Employees'}
                    </button>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default EmployeeOnboarding;
