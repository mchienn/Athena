import React from 'react';
import { reportFrontendError } from '../../services/telemetry';

interface State {
  failed: boolean;
}

export class TelemetryErrorBoundary extends React.Component<React.PropsWithChildren, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error): void {
    void reportFrontendError(error, 'react_error');
  }

  render(): React.ReactNode {
    if (this.state.failed) {
      return (
        <main role="alert" style={{ maxWidth: 640, margin: '15vh auto', padding: 24 }}>
          <h1>Không thể hiển thị trang</h1>
          <p>Hệ thống đã ghi nhận lỗi kỹ thuật. Vui lòng tải lại trang để tiếp tục.</p>
          <button type="button" onClick={() => window.location.reload()}>Tải lại trang</button>
        </main>
      );
    }
    return this.props.children;
  }
}
