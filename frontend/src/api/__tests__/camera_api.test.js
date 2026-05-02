import { cameraAPI } from '../../api/cameras';

// Mock the global fetch
global.fetch = jest.fn();

describe('Camera API Logic', () => {
    beforeEach(() => {
        fetch.mockClear();
    });

    test('startIngestion calls the correct endpoint', async () => {
        fetch.mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ status: 'success' }),
        });

        const result = await cameraAPI.startIngestion();
        
        expect(fetch).toHaveBeenCalledWith(
            expect.stringContaining('/ingestion/start'),
            expect.any(Object)
        );
        expect(result.status).toBe('success');
        console.log("✅ Frontend API Connection Logic Verified");
    });
});
