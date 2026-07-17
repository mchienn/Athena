import { getApp, getApps, initializeApp, type FirebaseApp } from 'firebase/app';
import {
  browserLocalPersistence,
  getAuth,
  setPersistence,
  signInAnonymously,
  type Auth,
  type User,
} from 'firebase/auth';
import { getFirestore, type Firestore } from 'firebase/firestore';
import { FirebaseError } from 'firebase/app';
import { apiClient } from './apiClient';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const firebaseConfigured = Boolean(
  firebaseConfig.apiKey &&
    firebaseConfig.authDomain &&
    firebaseConfig.projectId &&
    firebaseConfig.appId,
);

let app: FirebaseApp | null = null;
let auth: Auth | null = null;
let firestore: Firestore | null = null;
let userPromise: Promise<User> | null = null;

function getAuthError(error: unknown): Error {
  if (error instanceof FirebaseError) {
    if (error.code === 'auth/configuration-not-found') {
      return new Error(
        'Firebase Authentication chưa được khởi tạo. Hãy mở Firebase Console, chọn Authentication, nhấn Get started và bật Anonymous.',
      );
    }
    if (error.code === 'auth/operation-not-allowed') {
      return new Error(
        'Đăng nhập Anonymous chưa được bật trong Firebase Authentication.',
      );
    }
    if (error.code === 'auth/api-key-not-valid') {
      return new Error('Firebase Web API Key không hợp lệ hoặc không thuộc project hiện tại.');
    }
  }

  return error instanceof Error ? error : new Error('Không thể đăng nhập Firebase.');
}

if (firebaseConfigured) {
  app = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
  auth = getAuth(app);
  firestore = getFirestore(app);
}

export function getFirebaseServices(): { auth: Auth; firestore: Firestore } {
  if (!auth || !firestore) {
    throw new Error(
      'Firebase chưa được cấu hình. Hãy thêm các biến VITE_FIREBASE_* vào frontend/.env.',
    );
  }

  return { auth, firestore };
}

export async function getAnonymousUser(): Promise<User> {
  if (userPromise) return userPromise;

  // Keep configuration errors inside the returned Promise so React effects can
  // handle them without crashing the complete application tree.
  const services = getFirebaseServices();
  userPromise = (async () => {
    await setPersistence(services.auth, browserLocalPersistence);
    if (services.auth.currentUser) return services.auth.currentUser;
    return (await signInAnonymously(services.auth)).user;
  })().catch((error: unknown) => {
    userPromise = null;
    throw getAuthError(error);
  });

  return await userPromise;
}

export async function getChatUserId(): Promise<string> {
  const firebaseUser = await getAnonymousUser();
  if (!localStorage.getItem('auth_token')) return firebaseUser.uid;

  try {
    const binding = await apiClient.post<{ user_id: string }, { firebase_uid: string }>(
      '/chat/bind-firebase',
      { firebase_uid: firebaseUser.uid },
    );
    return binding.user_id;
  } catch (error) {
    throw new Error(
      `Không thể liên kết lịch sử chat với tài khoản bệnh nhân: ${
        error instanceof Error ? error.message : 'lỗi không xác định'
      }`,
    );
  }
}
