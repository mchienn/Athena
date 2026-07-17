import { useEffect } from 'react';
import { useLocation, useRoutes } from 'react-router-dom';
import { AppShell } from '../components/common/AppShell';
import { HomePage } from '../pages/HomePage';
import { DoctorsPage } from '../pages/DoctorsPage';
import { DoctorDetailPage } from '../pages/DoctorDetailPage';
import { SpecialtiesPage } from '../pages/SpecialtiesPage';
import { SchedulePage } from '../pages/SchedulePage';
import { BookingPage } from '../pages/BookingPage';
import { BookingConfirmationPage } from '../pages/BookingConfirmationPage';
import { AuthPage } from '../pages/AuthPages';
import { AccountPage } from '../pages/AccountPage';
import { MedicalHistoryPage } from '../pages/MedicalHistoryPage';
import { AppointmentsPage } from '../pages/AppointmentsPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import styles from './App.module.css';

export default function App() {
  const location = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, [location.pathname]);

  const routes = useRoutes([
    {
      element: <AppShell />,
      children: [
        { index: true, element: <HomePage /> },
        { path: 'bac-si', element: <DoctorsPage /> },
        { path: 'bac-si/:id', element: <DoctorDetailPage /> },
        { path: 'chuyen-khoa', element: <SpecialtiesPage /> },
        { path: 'lich-kham', element: <SchedulePage /> },
        { path: 'dat-lich', element: <BookingPage /> },
        { path: 'dat-lich/xac-nhan', element: <BookingConfirmationPage /> },
        { path: 'dang-nhap', element: <AuthPage mode="login" /> },
        { path: 'dang-ky', element: <AuthPage mode="register" /> },
        { path: 'quen-mat-khau', element: <AuthPage mode="forgot" /> },
        { path: 'tai-khoan', element: <AccountPage /> },
        { path: 'tai-khoan/lich-hen', element: <AppointmentsPage /> },
        { path: 'tai-khoan/ho-so', element: <MedicalHistoryPage /> },
        { path: 'tai-khoan/bao-mat', element: <AccountPage /> },
        { path: '*', element: <NotFoundPage /> },
      ],
    },
  ]);

  return <div className={styles.app}>{routes}</div>;
}
