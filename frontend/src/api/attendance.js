import apiClient from './client';

export const attendanceAPI = {
    getAllAttendance: async () => {
        return await apiClient('/attendance', {
            method: 'GET'
        });
    }
};
