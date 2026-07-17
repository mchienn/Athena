import { useState, useEffect } from 'react';
import { CalendarDays, ChevronDown, HeartPulse, Menu, Phone, UserRound, X } from 'lucide-react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { AssistantWidget } from '../../assistant/AssistantWidget';
import styles from './AppShell.module.css';

const navigation = [
  { label: 'Trang chủ', to: '/' }, { label: 'Bác sĩ', to: '/bac-si' }, { label: 'Chuyên khoa', to: '/chuyen-khoa' },
  { label: 'Lịch khám', to: '/lich-kham' },
];

export function AppShell() {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [user, setUser] = useState<{ fullName: string } | null>(null);

  useEffect(() => {
    const storedUser = localStorage.getItem('auth_user');
    setUser(storedUser ? JSON.parse(storedUser) : null);
  }, [location]);

  return <>
    <a className={styles.skipLink} href="#main-content">Chuyển đến nội dung chính</a>
    <header>
      <div className={styles.topbar}><div className={`container ${styles.topbarInner}`}><span>Chăm sóc trái tim — Vì một Hà Nội khỏe mạnh</span><div><a href="tel:115"><Phone size={14} /> Cấp cứu: 115</a><span>Hotline: 024 3942 2430</span></div></div></div>
      <div className={styles.header}><div className={`container ${styles.headerInner}`}>
        <Link className={styles.brand} to="/" aria-label="Bệnh viện Tim Hà Nội - Trang chủ"><img src="/logos/hanoi-heart-hospital.svg" alt="" width="52" height="52"/><span><strong>Bệnh viện Tim Hà Nội</strong><small>Hanoi Heart Hospital</small></span></Link>
        <nav className={styles.desktopNav} aria-label="Điều hướng chính">{navigation.map((item) => <NavLink key={item.to} className={({ isActive }) => isActive ? styles.active : undefined} to={item.to}>{item.label}</NavLink>)}</nav>
        <div className={styles.actions}>
          <Link className={styles.bookingButton} to="/dat-lich"><CalendarDays size={18}/> <span>Đặt lịch</span></Link>
          {user ? (
            <Link className={styles.accountButton} to="/tai-khoan">
              <UserRound size={18}/>
              <span>{user.fullName}</span>
            </Link>
          ) : (
            <Link className={styles.accountButton} to="/dang-nhap">
              <UserRound size={18}/>
              <span>Đăng nhập</span>
            </Link>
          )}
          <button className={styles.mobileToggle} onClick={() => setMenuOpen((value) => !value)} aria-expanded={menuOpen} aria-label={menuOpen ? 'Đóng menu' : 'Mở menu'}>{menuOpen ? <X/> : <Menu/>}</button>
        </div>
      </div>
      {menuOpen && <nav className={styles.mobileNav} aria-label="Điều hướng di động">{navigation.map((item) => <NavLink onClick={() => setMenuOpen(false)} key={item.to} to={item.to}>{item.label}<ChevronDown size={15}/></NavLink>)}<Link onClick={() => setMenuOpen(false)} to="/tai-khoan">Tài khoản bệnh nhân</Link></nav>}
      </div>
    </header>
    <main id="main-content"><Outlet/></main>
    <footer className={styles.footer}><div className={`container ${styles.footerGrid}`}>
      <div><div className={styles.footerBrand}><img src="/logos/hanoi-heart-hospital.svg" alt="" width="48"/><strong>Bệnh viện Tim Hà Nội</strong></div><p>Bệnh viện chuyên khoa đầu ngành về tim mạch của Thủ đô, tận tâm chăm sóc sức khỏe trái tim cộng đồng.</p></div>
      <div><h2>Truy cập nhanh</h2><Link to="/bac-si">Đội ngũ bác sĩ</Link><Link to="/chuyen-khoa">Chuyên khoa</Link><Link to="/lich-kham">Lịch khám</Link><Link to="/dat-lich">Đặt lịch khám</Link></div>
      <div className={styles.contactColumn}><h2>Liên hệ</h2><p><strong>Cơ sở 1:</strong> Số 92 Trần Hưng Đạo, phường Cửa Nam, Hà Nội</p><p><strong>Cơ sở 2:</strong> Số 695 Lạc Long Quân, phường Tây Hồ, Hà Nội</p><a href="tel:02439422430">024 3942 2430</a><a href="mailto:contact@hanoihearthospital.vn">contact@hanoihearthospital.vn</a></div>
      <div><h2>Cấp cứu 24/7</h2><a className={styles.emergency} href="tel:115"><HeartPulse size={20}/> Gọi 115</a><p>Không trì hoãn khi có dấu hiệu đau ngực, khó thở, vã mồ hôi hoặc ngất.</p></div>
    </div><div className={styles.copyright}>© 2026 Bệnh viện Tim Hà Nội. Giao diện demo phục vụ tích hợp hệ thống.</div></footer>
    {!location.pathname.startsWith('/dat-lich') && <AssistantWidget/>}
  </>;
}
export default AppShell;
