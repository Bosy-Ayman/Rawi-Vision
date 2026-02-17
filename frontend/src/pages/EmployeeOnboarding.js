import React, { useState } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import './EmployeeOnboarding.css'; // We'll create this specific CSS file

const EmployeeOnboarding = () => {
    const [employees, setEmployees] = useState([
        { firstName: '', lastName: '', role: '', photo: null, photoPreview: null }
    ]);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [submitStatus, setSubmitStatus] = useState(null); // 'success', 'error', or null

    const [successCount, setSuccessCount] = useState(0);

    const handleAddRow = () => {
        setEmployees([...employees, { firstName: '', lastName: '', role: '', photo: null, photoPreview: null }]);
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
                formData.append('employee_pictures', emp.photo);

                const response = await fetch('http://127.0.0.1:8000/employee', {
                    method: 'POST',
                    body: formData,
                });

                if (response.ok) {
                    currentSuccessCount++;
                } else {
                    const errorData = await response.json();
                    errors.push(`Row ${i + 1}: ${errorData.detail || 'Failed to upload'}`);
                }
            }

            if (errors.length === 0 && currentSuccessCount > 0) {
                setSuccessCount(currentSuccessCount);
                setSubmitStatus('success');
                setEmployees([{ firstName: '', lastName: '', role: '', photo: null, photoPreview: null }]); // Reset form
                setTimeout(() => setSubmitStatus(null), 3000);
            } else if (errors.length > 0) {
                setSubmitStatus('error');
                console.error("Errors:", errors);
                alert(`Some employees failed to upload:\n${errors.join('\n')}`);
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
                                            <option value="Select Role">Select Role</option> {/* Placeholder as seen in your request about dropdowns? User asked for predefined roles eventually. */}
                                            <option value="Software Engineer">Software Engineer</option>
                                            <option value="HR">HR</option>
                                            <option value="Manager">Manager</option>
                                            <option value="Security">Security</option>
                                            <option value="Staff">Staff</option>
                                            <option value="Intern">Intern</option>
                                        </select>
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
