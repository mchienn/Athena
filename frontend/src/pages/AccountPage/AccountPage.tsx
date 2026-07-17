import { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { AccountLayout } from '../../components/account/AccountLayout';
import { authService } from '../../services';
import styles from './AccountPage.module.css';

interface FormValues {
  fullName: string;
  phone: string;
  dob: string;
  gender: string;
  address: string;
  bhyt_code: string;
}

export function AccountPage() {
  const queryClient = useQueryClient();

  const { data: profile, isLoading, error } = useQuery({
    queryKey: ['patient_profile'],
    queryFn: authService.getDetailedProfile,
  });

  const { register, handleSubmit, reset } = useForm<FormValues>({
    defaultValues: {
      fullName: '',
      phone: '',
      dob: '',
      gender: 'Nam',
      address: '',
      bhyt_code: '',
    },
  });

  // Reset form values when profile data is loaded
  useEffect(() => {
    if (profile) {
      reset({
        fullName: profile.full_name,
        phone: profile.phone,
        dob: profile.dob,
        gender: profile.gender || 'Nam',
        address: profile.address || '',
        bhyt_code: profile.bhyt_code || '',
      });
    }
  }, [profile, reset]);

  const mutation = useMutation({
    mutationFn: authService.updateProfile,
    onSuccess: (updatedProfile) => {
      queryClient.setQueryData(['patient_profile'], updatedProfile);
      alert('Đã cập nhật thông tin thành công!');
    },
    onError: () => {
      alert('Lỗi: Không thể cập nhật thông tin hồ sơ.');
    },
  });

  const onSubmit = (values: FormValues) => {
    mutation.mutate({
      fullName: values.fullName,
      dob: values.dob,
      gender: values.gender,
      bhyt_code: values.bhyt_code,
      address: values.address,
    });
  };

  if (isLoading) {
    return (
      <AccountLayout title="Thông tin cá nhân">
        <p>Đang tải thông tin hồ sơ bệnh nhân...</p>
      </AccountLayout>
    );
  }

  if (error) {
    return (
      <AccountLayout title="Thông tin cá nhân">
        <p style={{ color: 'red' }}>Lỗi kết nối. Vui lòng đăng nhập lại.</p>
      </AccountLayout>
    );
  }

  return (
    <AccountLayout title="Thông tin cá nhân">
      <form className={styles.form} onSubmit={(event) => void handleSubmit(onSubmit)(event)}>
        <div>
          <label>
            Họ và tên
            <input {...register('fullName')} placeholder="Nguyễn Văn A" required />
          </label>
          <label>
            Số điện thoại
            <input {...register('phone')} disabled />
          </label>
        </div>
        <div>
          <label>
            Ngày sinh
            <input type="date" {...register('dob')} required />
          </label>
          <label>
            Giới tính
            <select {...register('gender')} required>
              <option value="Nam">Nam</option>
              <option value="Nữ">Nữ</option>
              <option value="Khác">Khác</option>
            </select>
          </label>
        </div>
        <div>
          <label>
            Mã thẻ BHYT (nếu có)
            <input {...register('bhyt_code')} placeholder="GD401XXXXXXXXXX" />
          </label>
        </div>
        <label>
          Địa chỉ
          <textarea rows={3} {...register('address')} placeholder="Nhập địa chỉ của bạn..." />
        </label>
        <button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Đang lưu...' : 'Lưu thay đổi'}
        </button>
      </form>
      <aside className={styles.note}>
        <strong>Thông tin y tế</strong>
        <p>Để thay đổi số điện thoại hoặc các thông tin hành chính đã xác minh, vui lòng liên hệ trực tiếp quầy tiếp đón Bệnh viện Tim Hà Nội.</p>
      </aside>
    </AccountLayout>
  );
}
