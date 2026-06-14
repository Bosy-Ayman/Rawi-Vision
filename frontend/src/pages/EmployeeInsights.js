import React, { useState, useEffect } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { employeeAPI } from '../api/employees';
import { attendanceAPI } from '../api/attendance';
import EmployeeAvatar from '../components/dashboard/EmployeeAvatar';
import EmployeeModal from '../components/dashboard/EmployeeModal';
import './EmployeeInsights.css';

const EmployeeInsights = () => {
    const [employees, setEmployees] = useState([]);
    const [attendanceData, setAttendanceData] = useState([]);
    const [anomalies, setAnomalies] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedRole, setSelectedRole] = useState('All');
    const [isLoading, setIsLoading] = useState(true);
    const [selectedEmployee, setSelectedEmployee] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const { anomalyAPI } = require('../api/anomalies');
                const [empData, attData, anomData] = await Promise.all([
                    employeeAPI.getAllEmployees(),
                    attendanceAPI.getAllAttendance(),
                    anomalyAPI.getAnomalies().catch(() => [])
                ]);
                setEmployees(empData);
                setAttendanceData(attData);
                setAnomalies(anomData);
            } catch (err) {
                console.error("Failed to fetch employees and attendance:", err);
            } finally {
                setIsLoading(false);
            }
        };
        fetchData();
    }, []);

    // Get unique roles for the filter dropdown
    const roles = ['All', ...new Set(employees.map(emp => emp.role).filter(Boolean))];

    // Filter logic
    const filteredEmployees = employees.filter(emp => {
        const matchesSearch = 
            `${emp.first_name || ''} ${emp.last_name || ''}`.toLowerCase().includes(searchTerm.toLowerCase()) ||
            (emp.role || '').toLowerCase().includes(searchTerm.toLowerCase());
        const matchesRole = selectedRole === 'All' || emp.role === selectedRole;
        return matchesSearch && matchesRole;
    });

    // Stats calculations
    const totalEmployees = employees.length;
    const roleCounts = employees.reduce((acc, emp) => {
        if (emp.role) {
            acc[emp.role] = (acc[emp.role] || 0) + 1;
        }
        return acc;
    }, {});

    // Count present today
    const todayStr = new Date().toISOString().split('T')[0];
    const presentTodayCount = new Set(
        attendanceData
            .filter(record => record.day && record.day === todayStr)
            .map(record => record.employee_id)
    ).size;

    return (
        <DashboardLayout title="Employee Insights">
            <div className="employee-insights-container">
                
                {/* Stats Dashboard Row */}
                <div className="insights-stats-row">
                    <div className="stat-glass-card">
                        <div className="stat-icon-wrapper blue">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                        </div>
                        <div className="stat-content">
                            <h3>Total Employees</h3>
                            <p className="stat-number">{totalEmployees}</p>
                            <span className="stat-subtext">Registered in Directory</span>
                        </div>
                    </div>
                    
                    <div className="stat-glass-card">
                        <div className="stat-icon-wrapper green">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                        </div>
                        <div className="stat-content">
                            <h3>Present Today</h3>
                            <p className="stat-number">{presentTodayCount}</p>
                            <span className="stat-subtext">Active checking today</span>
                        </div>
                    </div>

                    <div className="stat-glass-card">
                        <div className="stat-icon-wrapper purple">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path></svg>
                        </div>
                        <div className="stat-content">
                            <h3>Total Departments</h3>
                            <p className="stat-number">{Object.keys(roleCounts).length}</p>
                            <span className="stat-subtext">Active roles & divisions</span>
                        </div>
                    </div>
                </div>

                {/* Filter and Search Bar */}
                <div className="insights-filter-bar">
                    <div className="search-wrapper">
                        <svg className="search-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                        <input
                            type="text"
                            placeholder="Search by employee name or role..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                    </div>
                    
                    <div className="select-wrapper">
                        <label>Filter by Role:</label>
                        <select value={selectedRole} onChange={(e) => setSelectedRole(e.target.value)}>
                            {roles.map(role => (
                                <option key={role} value={role}>{role}</option>
                            ))}
                        </select>
                    </div>
                </div>

                {/* Employees Grid */}
                {isLoading ? (
                    <div className="insights-loading">
                        <div className="spinner"></div>
                        <p>Retrieving employee insights...</p>
                    </div>
                ) : (
                    <div className="insights-employees-grid">
                        {filteredEmployees.length > 0 ? (
                            filteredEmployees.map(emp => (
                                <div 
                                    key={emp.id} 
                                    className="insight-employee-card" 
                                    onClick={() => setSelectedEmployee(emp)}
                                >
                                    <div className="card-avatar-section">
                                        <EmployeeAvatar 
                                            imageUrl={emp.profile_image_url} 
                                            firstName={emp.first_name} 
                                            lastName={emp.last_name} 
                                            size={70} 
                                        />
                                    </div>
                                    <div className="card-details-section">
                                        <h3>{emp.first_name} {emp.last_name}</h3>
                                        <span className="card-role-badge">{emp.role || 'Employee'}</span>
                                        <p className="card-meta">
                                            Registered: {new Date(emp.date_created).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
                                        </p>
                                    </div>
                                    <div className="card-action-overlay">
                                        <span>View Analytics & Insights</span>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="insights-empty-state">
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
                                <h3>No employees found</h3>
                                <p>Try adjusting your search criteria or role filters.</p>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Employee Details Modal */}
            <EmployeeModal 
                employee={selectedEmployee} 
                allAttendanceData={{ records: attendanceData, alerts: anomalies }} 
                onClose={() => setSelectedEmployee(null)} 
            />
        </DashboardLayout>
    );
};

export default EmployeeInsights;
