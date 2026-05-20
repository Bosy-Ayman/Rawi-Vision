import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import apiClient from '../api/client';

const SubscriptionContext = createContext(null);

export const SubscriptionProvider = ({ children }) => {
    const [status, setStatus] = useState('active'); // active, suspended, expired, canceled, loading
    const [capabilities, setCapabilities] = useState({
        attendance: true,
        search: true,
        summarization: true
    });
    const [isLoading, setIsLoading] = useState(true);

    const getInstallationUuid = () => {
        return localStorage.getItem('installation_uuid') || 'test_installation_id';
    };

    const checkSubscriptionStatus = useCallback(async () => {
        try {
            // 1. Fetch the server's configured installation UUID
            const config = await apiClient('/subscription/installation-id/config');
            const uuid = config?.installation_uuid || 'test_installation_id';
            localStorage.setItem('installation_uuid', uuid);

            // 2. Query status using that exact UUID
            const data = await apiClient(`/subscription/${uuid}`);
            if (data) {
                setStatus(data.status || 'active');
                setCapabilities({
                    attendance: !!data.attendance,
                    search: !!data.search,
                    summarization: !!data.summarization
                });
            }
        } catch (error) {
            console.error('Failed to check subscription status:', error);
            if (error?.status === 402) {
                setStatus('expired');
                setCapabilities({ attendance: false, search: false, summarization: false });
            }
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Perform check-in on mount and set up periodic polling every 5 minutes
    useEffect(() => {
        checkSubscriptionStatus();
        const interval = setInterval(checkSubscriptionStatus, 300000);
        return () => clearInterval(interval);
    }, [checkSubscriptionStatus]);

    return (
        <SubscriptionContext.Provider value={{
            status,
            capabilities,
            isLoading,
            installationUuid: getInstallationUuid(),
            checkSubscriptionStatus
        }}>
            {children}
        </SubscriptionContext.Provider>
    );
};

export const useSubscription = () => {
    const context = useContext(SubscriptionContext);
    if (!context) {
        throw new Error('useSubscription must be used within a SubscriptionProvider');
    }
    return context;
};
