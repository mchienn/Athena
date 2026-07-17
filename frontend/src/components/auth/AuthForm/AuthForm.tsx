import { useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Eye, EyeOff, LoaderCircle, LockKeyhole, Phone, UserRound } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom';
import { z } from 'zod';
import { useQueryClient } from '@tanstack/react-query';
import { authService } from '../../../services';
import styles from './AuthForm.module.css';

export type AuthMode = 'login' | 'register' | 'forgot';

const schema = z.object({
  fullName: z.string().optional(),
  phone: z.string().regex(/^(0|\+84)\d{9}$/, 'Số điện thoại không hợp lệ'),
  email: z.string().optional(),
  password: z.string().optional(),
});

type Values = z.infer<typeof schema>;

export function AuthForm({ mode }: { mode: AuthMode }) {
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      fullName: '',
      phone: '',
      email: '',
      password: '',
    },
  });

  const submit = async (values: Values) => {
    setLoading(true);
    setMessage('');
    try {
      if (mode === 'login') {
        if (!values.password) {
          setMessage('Vui lòng nhập mật khẩu');
          return;
        }
        await authService.login({
          phone: values.phone,
          password: values.password,
        });
        queryClient.clear(); // Clear cached queries from the previous user
        navigate('/tai-khoan');
      } else if (mode === 'register') {
        if (!values.fullName || !values.password) {
          setMessage('Vui lòng nhập đủ thông tin bắt buộc');
          return;
        }
        await authService.register({
          fullName: values.fullName,
          phone: values.phone,
          email: values.email ?? '',
          password: values.password,
        });
        queryClient.clear(); // Clear cached queries from the previous user
        navigate('/tai-khoan');
      } else {
        await authService.forgotPassword(values.phone);
        setMessage('Mã xác thực đã được gửi đến số điện thoại của bạn.');
      }
    } catch {
      setMessage('Không thể xử lý yêu cầu. Vui lòng thử lại.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className={styles.form} onSubmit={(event) => void handleSubmit(submit)(event)}>
      {mode === 'register' && (
        <label>
          Họ và tên *
          <span>
            <UserRound />
            <input {...register('fullName')} placeholder="Nguyễn Văn A" />
          </span>
        </label>
      )}
      <label>
        Số điện thoại *
        <span>
          <Phone />
          <input {...register('phone')} inputMode="tel" placeholder="0912 345 678" />
        </span>
        {errors.phone && <small>{errors.phone.message}</small>}
      </label>
      {mode === 'register' && (
        <label>
          Email
          <span>
            <UserRound />
            <input {...register('email')} type="email" placeholder="email@example.com" />
          </span>
        </label>
      )}
      {mode !== 'forgot' && (
        <label>
          Mật khẩu *
          <span>
            <LockKeyhole />
            <input
              {...register('password')}
              type={show ? 'text' : 'password'}
              placeholder="Ít nhất 6 ký tự"
            />
            <button
              type="button"
              onClick={() => setShow((value) => !value)}
              aria-label={show ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
            >
              {show ? <EyeOff /> : <Eye />}
            </button>
          </span>
        </label>
      )}
      {mode === 'login' && (
        <div className={styles.links}>
          <label>
            <input type="checkbox" />
            Ghi nhớ đăng nhập
          </label>
          <Link to="/quen-mat-khau">Quên mật khẩu?</Link>
        </div>
      )}
      {message && (
        <p className={styles.message} role="status">
          {message}
        </p>
      )}
      <button className={styles.submit} disabled={loading}>
        {loading && <LoaderCircle />}
        {mode === 'login' ? 'Đăng nhập' : mode === 'register' ? 'Tạo tài khoản' : 'Gửi mã xác thực'}
      </button>
      <p className={styles.switch}>
        {mode === 'login' ? (
          <>
            Chưa có tài khoản? <Link to="/dang-ky">Đăng ký</Link>
          </>
        ) : mode === 'register' ? (
          <>
            Đã có tài khoản? <Link to="/dang-nhap">Đăng nhập</Link>
          </>
        ) : (
          <Link to="/dang-nhap">Quay lại đăng nhập</Link>
        )}
      </p>
    </form>
  );
}
export default AuthForm;
