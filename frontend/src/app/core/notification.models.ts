export interface Notification {
  id: string;
  title: string;
  body?: string;
  level: 'info' | 'warning' | 'danger' | 'success';
  verb: string;
  project?: string | null;
  organization?: string | null;
  created_at: string;
  read_at?: string | null;
  metadata?: Record<string, unknown>;
}

export interface NotificationPreference {
  in_app: boolean;
  email: boolean;
  email_frequency: string;
}

export interface UnreadCount {
  unread: number;
}
