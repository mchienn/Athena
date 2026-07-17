import { apiClient, mockDelay } from './apiClient';

export interface AuthCredentials { phone: string; password: string; }
export interface RegisterPayload extends AuthCredentials { fullName: string; email: string; }
export interface AuthUser { id: string; fullName: string; phone: string; email: string; }

export interface PatientProfile {
  patient_id: string;
  full_name: string;
  phone: string;
  dob: string;
  gender: string;
  bhyt_code?: string;
  address?: string;
}

const mockUser: AuthUser = { id: 'patient-1', fullName: 'Nguyễn Minh Anh', phone: '0912345678', email: 'minhanh@example.com' };

export const authService = {
  login: async (payload: AuthCredentials): Promise<AuthUser> => {
    if (apiClient.useMocks) {
      const user = { ...mockUser, phone: payload.phone };
      localStorage.setItem('auth_user', JSON.stringify(user));
      localStorage.setItem('auth_token', 'mock-token');
      return mockDelay(user);
    }
    
    const res = await apiClient.post<{ access_token: string; user_id: string; patient_id: string }>('/auth/login', payload);
    localStorage.setItem('auth_token', res.access_token);
    localStorage.setItem('patient_id', res.patient_id);
    
    const profile = await authService.getProfile();
    return profile;
  },

  register: async (payload: RegisterPayload): Promise<AuthUser> => {
    if (apiClient.useMocks) {
      const user = { ...mockUser, fullName: payload.fullName, phone: payload.phone, email: payload.email };
      localStorage.setItem('auth_user', JSON.stringify(user));
      localStorage.setItem('auth_token', 'mock-token');
      return mockDelay(user);
    }

    const apiPayload = {
      phone: payload.phone,
      password: payload.password,
      full_name: payload.fullName,
      dob: '1990-01-01', // Fallback defaults
      gender: 'Nam',     // Fallback defaults
      address: ''
    };
    
    await apiClient.post<{ user_id: string; patient_id: string }>('/auth/register', apiPayload);
    // Auto login after successful registration
    return authService.login({ phone: payload.phone, password: payload.password });
  },

  forgotPassword: async (phone: string): Promise<void> => {
    return apiClient.useMocks ? mockDelay(undefined) : apiClient.post('/auth/forgot-password', { phone });
  },

  getProfile: async (): Promise<AuthUser> => {
    if (apiClient.useMocks) {
      const stored = localStorage.getItem('auth_user');
      return stored ? JSON.parse(stored) : mockUser;
    }
    const res = await apiClient.get<{ profile: PatientProfile }>('/patients/me');
    const user: AuthUser = {
      id: res.profile.patient_id,
      fullName: res.profile.full_name,
      phone: res.profile.phone,
      email: '' // Fallback as backend doesn't store email in patients
    };
    localStorage.setItem('auth_user', JSON.stringify(user));
    return user;
  },

  getDetailedProfile: async (): Promise<PatientProfile> => {
    if (apiClient.useMocks) {
      return mockDelay({
        patient_id: 'patient-1',
        full_name: 'Nguyễn Minh Anh',
        phone: '0912345678',
        dob: '1990-05-20',
        gender: 'Nam',
        bhyt_code: 'GD4010123456789',
        address: 'Hoàn Kiếm, Hà Nội'
      });
    }
    const res = await apiClient.get<{ profile: PatientProfile }>('/patients/me');
    return res.profile;
  },

  updateProfile: async (data: Partial<PatientProfile> & { fullName?: string }): Promise<PatientProfile> => {
    if (apiClient.useMocks) {
      return mockDelay({
        patient_id: 'patient-1',
        full_name: data.full_name || 'Nguyễn Minh Anh',
        phone: data.phone || '0912345678',
        dob: data.dob || '1990-05-20',
        gender: data.gender || 'Nam',
        bhyt_code: data.bhyt_code,
        address: data.address
      });
    }
    const payload = {
      full_name: data.fullName || data.full_name,
      dob: data.dob,
      gender: data.gender,
      bhyt_code: data.bhyt_code,
      address: data.address
    };
    const res = await apiClient.put<{ profile: PatientProfile }>('/patients/me', payload);
    
    // Update stored user basic info
    const user: AuthUser = {
      id: res.profile.patient_id,
      fullName: res.profile.full_name,
      phone: res.profile.phone,
      email: ''
    };
    localStorage.setItem('auth_user', JSON.stringify(user));
    
    return res.profile;
  },

  getMedicalRecords: async (): Promise<any[]> => {
    if (apiClient.useMocks) {
      return mockDelay([
        {
          record_id: 'mock-rec-1',
          patient_id: 'patient-1',
          visit_date: '2026-05-15',
          department: 'Nội tim mạch',
          doctor_name: 'BS. Nguyễn Hoàng Nam',
          diagnosis: 'Tăng huyết áp vô căn độ II',
          symptoms: 'Đau đầu nhẹ vùng chẩm',
          treatment_plan: 'Uống thuốc đều, ăn nhạt',
          prescription: [
            { medicine_name: 'Amlodipine 5mg', dosage: '1 viên/ngày', quantity: 30 }
          ],
          next_appointment_date: '2026-06-15'
        }
      ]);
    }
    const res = await apiClient.get<{ records: any[] }>('/patients/me/records');
    return res.records;
  },

  logout: () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    localStorage.removeItem('patient_id');
  },

  isAuthenticated: (): boolean => {
    return !!localStorage.getItem('auth_token');
  }
};
