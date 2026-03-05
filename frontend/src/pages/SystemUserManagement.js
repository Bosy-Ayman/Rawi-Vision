import React, { useState, useEffect } from 'react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { authAPI } from '../api/auth';
import './SystemUserManagement.css';

const SystemUserManagement = () => {
    const [users, setUsers] = useState([]);
    const [form, setForm] = useState({ fullName: '', email: '', role: 'HR' });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [successMsg, setSuccessMsg] = useState('');
    const [errorMsg, setErrorMsg] = useState('');

    useEffect(() => {
        fetchUsers();
    }, []);

    const fetchUsers = async () => {
        try {
            const data = await authAPI.getSystemUsers();
            setUsers(data);
        } catch (err) {
            setErrorMsg('Failed to load users.');
        }
    };

    const handleChange = (e) => {
        setForm({ ...form, [e.target.name]: e.target.value });
    };

    const isFormValid = form.fullName.trim() && form.email.trim() && form.role;

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!isFormValid) return;

        setIsSubmitting(true);
        setErrorMsg('');

        try {
            const newUser = await authAPI.addSystemUser({
                email: form.email,
                full_name: form.fullName,
                role: form.role
            });

            setUsers(prev => [...prev, newUser]);
            setForm({ fullName: '', email: '', role: 'HR' });
            setSuccessMsg(`${newUser.full_name} added as ${newUser.role}.`);
            setTimeout(() => setSuccessMsg(''), 3000);
        } catch (err) {
            setErrorMsg(err.detail || 'Failed to add user. Email may already exist.');
            setTimeout(() => setErrorMsg(''), 3000);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleRemove = async (email) => {
        if (!window.confirm(`Remove user ${email}?`)) return;

        try {
            await authAPI.removeSystemUser(email);
            setUsers(prev => prev.filter(u => u.email !== email));
        } catch (err) {
            setErrorMsg('Failed to remove user.');
            setTimeout(() => setErrorMsg(''), 3000);
        }
    };

    return (
        <DashboardLayout title="System User Management">
            <div className="sum-container">

                {/* ── Add User Card ── */}
                <section className="sum-card">
                    <h2 className="sum-card-title">Add New System User</h2>
                    <p className="sum-card-subtitle">
                        Enter the email of an HR or Manager who can log in to RawiVision.
                    </p>

                    {successMsg && <div className="sum-alert sum-alert--success">✓ {successMsg}</div>}
                    {errorMsg && <div className="sum-alert sum-alert--error">✕ {errorMsg}</div>}

                    <form className="sum-form" onSubmit={handleSubmit}>
                        <div className="sum-form-row">
                            <div className="sum-field">
                                <label htmlFor="fullName">Full Name</label>
                                <input
                                    id="fullName"
                                    name="fullName"
                                    type="text"
                                    placeholder="e.g. Sarah Ahmed"
                                    value={form.fullName}
                                    onChange={handleChange}
                                    required
                                />
                            </div>
                            <div className="sum-field">
                                <label htmlFor="email">Email Address</label>
                                <input
                                    id="email"
                                    name="email"
                                    type="email"
                                    placeholder="e.g. sarah@company.com"
                                    value={form.email}
                                    onChange={handleChange}
                                    required
                                />
                            </div>
                            <div className="sum-field sum-field--narrow">
                                <label htmlFor="role">Role</label>
                                <select
                                    id="role"
                                    name="role"
                                    value={form.role}
                                    onChange={handleChange}
                                >
                                    <option value="HR">HR</option>
                                    <option value="Manager">Manager</option>
                                </select>
                            </div>
                            <button
                                type="submit"
                                className={`sum-btn-add ${isFormValid ? 'sum-btn-add--active' : ''}`}
                                disabled={!isFormValid || isSubmitting}
                            >
                                {isSubmitting ? 'Adding…' : '+ Add'}
                            </button>
                        </div>
                    </form>
                </section>

                {/* ── Users Table ── */}
                <section className="sum-card">
                    <h2 className="sum-card-title">
                        Current System Users
                        <span className="sum-count">{users.length}</span>
                    </h2>

                    {users.length === 0 ? (
                        <div className="sum-empty">
                            <p>No system users added yet. Use the form above to add HRs and Managers.</p>
                        </div>
                    ) : (
                        <div className="sum-table-wrap">
                            <table className="sum-table">
                                <thead>
                                    <tr>
                                        <th>Full Name</th>
                                        <th>Email</th>
                                        <th>Role</th>
                                        <th>Added On</th>
                                        <th></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.map(u => (
                                        <tr key={u.id}>
                                            <td className="sum-td-name">
                                                <div className="sum-avatar">{u.full_name.charAt(0)}</div>
                                                {u.full_name}
                                            </td>
                                            <td>{u.email}</td>
                                            <td>
                                                <span className={`sum-chip sum-chip--${u.role.toLowerCase()}`}>
                                                    {u.role}
                                                </span>
                                            </td>
                                            <td>{new Date(u.date_created).toISOString().split('T')[0]}</td>
                                            <td>
                                                <button className="sum-btn-remove" onClick={() => handleRemove(u.email)}>
                                                    Remove
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </section>

            </div>
        </DashboardLayout>
    );
};

export default SystemUserManagement;
