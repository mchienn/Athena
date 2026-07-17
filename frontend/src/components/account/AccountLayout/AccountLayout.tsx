import { CalendarClock, FileHeart, LogOut, Shield, UserRound } from 'lucide-react';
import { NavLink, useNavigate } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { authService } from '../../../services';
import styles from './AccountLayout.module.css';

const links = [
  { to: '/tai-khoan', label: 'Thông tin cá nhân', icon: UserRound, end: true },
  { to: '/tai-khoan/lich-hen', label: 'Quản lý lịch hẹn', icon: CalendarClock },
  { to: '/tai-khoan/ho-so', label: 'Hồ sơ sức khỏe', icon: FileHeart },
  { to: '/tai-khoan/bao-mat', label: 'Bảo mật', icon: Shield }
];

export function AccountLayout({ title, children }: { title: string; children: ReactNode }) {
  const navigate = useNavigate();

  // Get stored user info to display dynamically on sidebar
  const storedUser = localStorage.getItem('auth_user');
  const user = storedUser ? JSON.parse(storedUser) : null;
  const fullName = user?.fullName || 'Bệnh nhân';
  const patientId = user?.id ? `BN-${user.id.slice(-8).toUpperCase()}` : 'Chưa xác minh';

  // Get initials for avatar (e.g. "Nguyễn Minh Anh" -> "MA")
  const getInitials = (name: string) => {
    const parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return (parts[parts.length - 2][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  };
  const initials = getInitials(fullName);

  const queryClient = useQueryClient();

  const handleLogout = () => {
    authService.logout();
    queryClient.clear();
    navigate('/dang-nhap');
  };

  return (
    <section className="section section-soft">
      <div className={`container ${styles.layout}`}>
        <aside>
          <div className={styles.user}>
            <span>{initials}</span>
            <div>
              <strong>{fullName}</strong>
              <small>Mã BN: {patientId}</small>
            </div>
          </div>
          <nav aria-label="Tài khoản bệnh nhân">
            {links.map((item) => (
              <NavLink
                end={item.end}
                key={item.to}
                to={item.to}
                className={({ isActive }) => (isActive ? styles.active : undefined)}
              >
                <item.icon />
                {item.label}
              </NavLink>
            ))}
          </nav>
          <button onClick={handleLogout}>
            <LogOut />
            Đăng xuất
          </button>
        </aside>
        <div className={styles.content}>
          <h1>{title}</h1>
          {children}
        </div>
      </div>
    </section>
  );
}
