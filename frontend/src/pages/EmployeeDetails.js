import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import './EmployeeDetails.css';

const EmployeeDetails = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [employee, setEmployee] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchEmployeeDetails();
    }, [id]);

    const fetchEmployeeDetails = async () => {
        try {
            const response = await fetch(`http://127.0.0.1:8000/employee/${id}`);
            if (!response.ok) throw new Error('Employee not found');
            const data = await response.json();
            setEmployee(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async () => {
        if (!window.confirm('Are you sure you want to delete this employee?')) return;

        try {
            const response = await fetch(`http://127.0.0.1:8000/employee/${id}`, {
                method: 'DELETE',
            });

            if (response.status === 204) {
                navigate('/dashboard/all-employees');
            } else {
                throw new Error('Failed to delete');
            }
        } catch (error) {
            alert('Error deleting employee');
        }
    };

    if (loading) return <DashboardLayout><div className="loading">Loading...</div></DashboardLayout>;
    if (error) return <DashboardLayout><div className="error">{error}</div></DashboardLayout>;
    if (!employee) return null;

    return (
        <DashboardLayout title="Employee Details">
            <div className="details-container">
                <button className="btn-back" onClick={() => navigate('/dashboard/all-employees')}>
                    ← Back to List
                </button>

                <div className="profile-header">
                    <div className="profile-avatar">
                        {employee.first_name[0]}{employee.last_name[0]}
                    </div>
                    <div className="profile-info">
                        <h1>{employee.first_name} {employee.last_name}</h1>
                        <span className="profile-role">{employee.role}</span>
                        <p className="profile-meta">ID: {employee.id}</p>
                    </div>
                    <div className="profile-actions">
                        <button className="btn-delete" onClick={handleDelete}>Delete Employee</button>
                    </div>
                </div>

                <div className="details-section">
                    <h3>Personal Information</h3>
                    <div className="info-grid">
                        <div className="info-item">
                            <label>First Name</label>
                            <p>{employee.first_name}</p>
                        </div>
                        <div className="info-item">
                            <label>Last Name</label>
                            <p>{employee.last_name}</p>
                        </div>
                        <div className="info-item">
                            <label>Role</label>
                            <p>{employee.role}</p>
                        </div>
                        <div className="info-item">
                            <label>Join Date</label>
                            <p>{new Date(employee.date_created).toLocaleDateString()}</p>
                        </div>
                    </div>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default EmployeeDetails;
